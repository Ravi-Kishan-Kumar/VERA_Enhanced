"""Bounded ASGI request handling and process-local submission throttling."""

from __future__ import annotations

import logging
import math
import re
import time
from collections import OrderedDict, deque
from ipaddress import ip_address, ip_network
from threading import Lock
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.logging import request_id_context
from app.config import Settings

logger = logging.getLogger("vera.requests")
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,64}\Z")


class SlidingWindowLimiter:
    """Bound memory and requests per client; restart/multiple-process limits are documented."""

    def __init__(self, limit: int, window: int, max_clients: int) -> None:
        self.limit, self.window, self.max_clients = limit, window, max_clients
        self.clients: OrderedDict[str, deque[float]] = OrderedDict()
        self.lock = Lock()

    def check(self, client: str, now: float | None = None) -> int:
        """Return zero when allowed, otherwise seconds until a retry may be accepted."""
        now = time.monotonic() if now is None else now
        with self.lock:
            while self.clients and next(iter(self.clients.values()))[-1] <= now - self.window:
                self.clients.popitem(last=False)
            bucket = self.clients.get(client)
            if bucket is None:
                if len(self.clients) >= self.max_clients:
                    return self.window
                bucket = self.clients[client] = deque()
            while bucket and bucket[0] <= now - self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return max(1, math.ceil(bucket[0] + self.window - now))
            bucket.append(now)
            self.clients.move_to_end(client)
            return 0


class RequestGuard:
    """Apply correlation IDs, body bounds, security headers, and POST rate limits."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings
        self.limiter = SlidingWindowLimiter(
            settings.REVIEW_RATE_LIMIT,
            settings.REVIEW_RATE_WINDOW_SECONDS,
            settings.RATE_LIMIT_MAX_CLIENTS,
        )
        self.proxies = [
            ip_network(value.strip(), strict=False)
            for value in settings.TRUSTED_PROXY_CIDRS.split(",")
            if value.strip()
        ]

    def client_key(self, scope: Scope, headers: Headers) -> str:
        """Strip only explicitly trusted proxy hops from the right of a forwarded chain."""
        peer = (scope.get("client") or ("unknown", 0))[0]
        try:
            address = ip_address(peer)
            if not any(address in network for network in self.proxies):
                return str(address)
            hops = headers.get("x-forwarded-for", "").split(",")
            if len(hops) > 20:
                return peer
            for hop in reversed(hops):
                address = ip_address(hop.strip())
                if not any(address in network for network in self.proxies):
                    return str(address)
            return str(address)
        except ValueError:
            return peer

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        supplied = headers.get("x-request-id", "")
        request_id = supplied if REQUEST_ID_PATTERN.fullmatch(supplied) else uuid4().hex
        token = request_id_context.set(request_id)
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.monotonic()
        status_code = 500
        response_started = False

        async def guarded_send(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                outgoing = MutableHeaders(scope=message)
                outgoing["X-Request-ID"] = request_id
                outgoing["X-Content-Type-Options"] = "nosniff"
                outgoing["X-Frame-Options"] = "DENY"
                outgoing["Referrer-Policy"] = "no-referrer"
                outgoing["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                outgoing["Cache-Control"] = "no-store"
                origin = headers.get("origin")
                if origin and (
                    origin in self.settings.cors_origins or "*" in self.settings.cors_origins
                ):
                    outgoing["Access-Control-Allow-Origin"] = origin
                    outgoing["Access-Control-Expose-Headers"] = (
                        "X-Total-Count, X-Request-ID, Retry-After"
                    )
                    outgoing.add_vary_header("Origin")
                if self.settings.is_production:
                    outgoing["Strict-Transport-Security"] = "max-age=31536000"
            await send(message)

        async def reject(code: int, detail: str, extra: dict[str, str] | None = None) -> None:
            await JSONResponse(
                {"detail": detail, "request_id": request_id}, status_code=code, headers=extra
            )(scope, receive, guarded_send)

        try:
            length = headers.get("content-length")
            if length is not None:
                if not length.isascii() or not length.isdigit() or len(length) > 10:
                    await reject(400, "Invalid Content-Length header.")
                    return
                if int(length) > self.settings.MAX_REQUEST_BODY_BYTES:
                    await reject(413, "Request body is too large.")
                    return
            if headers.get("content-encoding", "identity").lower() != "identity":
                await reject(415, "Compressed request bodies are not supported.")
                return
            if scope["method"] == "POST" and scope["path"].rstrip("/") == "/api/reviews":
                retry = self.limiter.check(self.client_key(scope, headers))
                if retry:
                    await reject(
                        429,
                        "Too many reviews submitted. Please wait before trying again.",
                        {"Retry-After": str(retry)},
                    )
                    return
            # Buffer at most the configured limit before any handler can persist side effects.
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    status_code = 499
                    return
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > self.settings.MAX_REQUEST_BODY_BYTES:
                    await reject(413, "Request body is too large.")
                    return
                body.extend(chunk)
                if not message.get("more_body", False):
                    break
            delivered = False

            async def replay() -> Message:
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            await self.app(scope, replay, guarded_send)
        except Exception as exc:
            logger.error("request_failed", extra={"exception_type": type(exc).__name__})
            if response_started:
                raise
            await reject(500, "The service could not complete this request.")
        finally:
            route = getattr(scope.get("route"), "path", "unmatched")
            logger.info(
                "request_completed",
                extra={
                    "method": scope["method"],
                    "route": route,
                    "status_code": status_code,
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                },
            )
            request_id_context.reset(token)
