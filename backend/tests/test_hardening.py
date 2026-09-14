"""HTTP boundary regressions; no models, broker, or external network required."""

from __future__ import annotations

import json
import logging

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.api.logging import JsonFormatter, request_id_context
from app.api.middleware import RequestGuard, SlidingWindowLimiter
from app.config import settings


def guarded_client(**overrides: object) -> TestClient:
    app = FastAPI()

    @app.post("/api/reviews")
    async def submit(request: Request) -> dict[str, int]:
        return {"bytes": len(await request.body())}

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("private-provider-key-and-review")

    app.add_middleware(RequestGuard, settings=settings.model_copy(update=overrides))
    return TestClient(app)


def test_correlation_security_and_safe_exception() -> None:
    with guarded_client(ENVIRONMENT="production") as client:
        response = client.get("/boom", headers={"X-Request-ID": "test-request_1"})
        assert response.status_code == 500
        assert response.headers["X-Request-ID"] == "test-request_1"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Strict-Transport-Security"] == "max-age=31536000"
        assert "private-provider" not in response.text
        invalid = client.get("/missing", headers={"X-Request-ID": "bad id " * 50})
        assert len(invalid.headers["X-Request-ID"]) == 32


def test_rate_limit_backoff_and_cors() -> None:
    with guarded_client(REVIEW_RATE_LIMIT=1) as client:
        assert client.post("/api/reviews", content=b"small").status_code == 200
        blocked = client.post(
            "/api/reviews/", content=b"small", headers={"Origin": "http://localhost:3000"}
        )
        assert blocked.status_code == 429
        assert 1 <= int(blocked.headers["Retry-After"]) <= 60
        assert blocked.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
        assert blocked.headers["X-Request-ID"]
        assert client.get("/missing").status_code == 404


def test_limiter_expires_and_bounds_cardinality() -> None:
    limiter = SlidingWindowLimiter(1, 60, 1)
    assert limiter.check("a", now=0) == 0
    assert limiter.check("a", now=30) == 30
    assert limiter.check("b", now=30) == 60
    assert len(limiter.clients) == 1
    assert limiter.check("b", now=60) == 0
    assert list(limiter.clients) == ["b"]


def test_proxy_headers_require_trusted_peer() -> None:
    guard = RequestGuard(
        FastAPI(), settings=settings.model_copy(update={"TRUSTED_PROXY_CIDRS": "10.0.0.0/8"})
    )
    from starlette.datastructures import Headers

    forwarded = Headers({"x-forwarded-for": "198.51.100.9, 203.0.113.8, 10.0.0.2"})
    assert guard.client_key({"client": ("10.0.0.1", 0)}, forwarded) == "203.0.113.8"
    assert guard.client_key({"client": ("192.0.2.1", 0)}, forwarded) == "192.0.2.1"
    assert (
        guard.client_key({"client": ("10.0.0.1", 0)}, Headers({"x-forwarded-for": "invalid"}))
        == "10.0.0.1"
    )


def test_body_headers_are_rejected_without_handler_side_effects() -> None:
    with guarded_client() as client:
        assert client.post("/api/reviews", content=b"x" * 65537).status_code == 413
        assert client.post("/api/reviews", headers={"Content-Length": "invalid"}).status_code == 400
        assert client.post("/api/reviews", headers={"Content-Encoding": "gzip"}).status_code == 415


@pytest.mark.asyncio
async def test_chunked_body_cannot_bypass_limit() -> None:
    called = False

    async def downstream(scope, receive, send):
        nonlocal called
        called = True

    guard = RequestGuard(downstream, settings=settings)
    chunks = iter(
        [
            {"type": "http.request", "body": b"x" * 40000, "more_body": True},
            {"type": "http.request", "body": b"x" * 40000, "more_body": False},
        ]
    )
    messages = []

    async def receive():
        return next(chunks)

    async def send(message):
        messages.append(message)

    await guard(
        {"type": "http", "method": "POST", "path": "/api/reviews", "headers": []}, receive, send
    )
    assert messages[0]["status"] == 413
    assert not called
    assert request_id_context.get() == "-"


def test_ready_tracks_database_and_liveness_survives_failure(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.health.database_ready", lambda: False)
    assert client.get("/ready").status_code == 503
    assert client.get("/health").status_code == 200
    monkeypatch.setattr("app.api.routes.health.database_ready", lambda: True)
    assert client.get("/ready").status_code == 200


def test_json_log_includes_request_id_without_exception_details() -> None:
    token = request_id_context.set("log-request")
    try:
        record = logging.LogRecord("vera", logging.ERROR, "", 0, "request_failed", (), None)
        record.exc_info = (ValueError, ValueError("secret-token"), None)
        payload = json.loads(JsonFormatter().format(record))
        assert payload["request_id"] == "log-request"
        assert payload["exception_type"] == "ValueError"
        assert "secret-token" not in json.dumps(payload)
    finally:
        request_id_context.reset(token)


def test_cors_preflight_and_rejected_origin(client) -> None:
    response = client.options(
        "/api/reviews",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Request-ID, Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    blocked = client.get("/ready", headers={"Origin": "https://untrusted.example"})
    assert "Access-Control-Allow-Origin" not in blocked.headers


def test_exact_body_limit_is_accepted() -> None:
    with guarded_client() as client:
        response = client.post("/api/reviews", content=b"x" * 65536)
    assert response.status_code == 200
    assert response.json() == {"bytes": 65536}
