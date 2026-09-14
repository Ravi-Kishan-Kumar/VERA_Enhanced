"""Seed a demo through the public API. Never imports training or inference code."""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx


def parse_review(row: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the public review fields without loading application settings."""
    text = row.get("text")
    if not isinstance(text, str) or not 20 <= len(text.strip()) <= 10_000:
        raise ValueError("text must contain 20-10000 characters")
    try:
        rating = float(row["star_rating"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("star_rating must be numeric") from exc
    if isinstance(row["star_rating"], bool) or not math.isfinite(rating) or not 1 <= rating <= 5:
        raise ValueError("star_rating must be between 1 and 5")
    result: dict[str, Any] = {"text": text.strip(), "star_rating": rating}
    for field, maximum in (("product_title", 1000), ("product_asin", 20)):
        value = row.get(field)
        if value not in (None, ""):
            if not isinstance(value, str) or len(value.strip()) > maximum:
                raise ValueError(f"{field} must be a string of at most {maximum} characters")
            result[field] = value.strip() or None
    votes = row.get("helpful_votes")
    if votes not in (None, ""):
        if isinstance(votes, bool) or not str(votes).isascii() or not str(votes).isdigit():
            raise ValueError("helpful_votes must be a nonnegative integer")
        result["helpful_votes"] = int(str(votes))
    verified = row.get("verified_purchase")
    if verified not in (None, ""):
        normalized = str(verified).strip().lower()
        if normalized not in ("true", "false", "1", "0"):
            raise ValueError("verified_purchase must be true/false or 1/0")
        result["verified_purchase"] = normalized in ("true", "1")
    return result


def read_reviews(path: Path, limit: int) -> list[dict[str, Any]]:
    """Read and validate up to limit records; reject errors before submitting anything."""
    if limit < 1:
        raise ValueError("limit must be positive")
    if path.suffix.lower() not in (".csv", ".jsonl"):
        raise ValueError("input must be a .csv or .jsonl file")
    records = []
    with path.open(encoding="utf-8-sig", newline="") as source:
        rows = csv.DictReader(source) if path.suffix.lower() == ".csv" else source
        for number, raw in enumerate(rows, 1):
            try:
                row = json.loads(raw) if isinstance(raw, str) else raw
                if not isinstance(row, dict):
                    raise ValueError("record must be an object")
                records.append(parse_review(row))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid record {number}: {exc}") from exc
            if len(records) == limit:
                break
    return records


def retry_delay(value: str | None, now: datetime | None = None) -> float:
    """Honor delta/date Retry-After; invalid values use a conservative minute."""
    try:
        delay = float(value or "60")
    except ValueError:
        try:
            date = parsedate_to_datetime(value or "")
            if date.tzinfo is None:
                date = date.replace(tzinfo=UTC)
            delay = (date - (now or datetime.now(UTC))).total_seconds()
        except (TypeError, ValueError, OverflowError):
            delay = 60.0
    return max(1.0, delay) if math.isfinite(delay) else 60.0


def request_with_backoff(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    attempts: int = 5,
    max_wait: float = 300,
) -> httpx.Response:
    """Retry rejected POSTs only on 429; never duplicate an ambiguous submission."""
    remaining = max_wait
    for attempt in range(attempts):
        response = client.request(method, path, json=payload)
        retryable = response.status_code == 429 or (method == "GET" and response.status_code == 503)
        if not retryable or attempt == attempts - 1:
            response.raise_for_status()
            return response
        delay = retry_delay(response.headers.get("Retry-After"))
        if delay > remaining:
            response.raise_for_status()
        remaining -= delay
        sleep(delay)
    raise ValueError("attempts must be positive")


def percentile(values: list[float], fraction: float) -> float | None:
    """Linearly interpolated percentile, with an explicit empty-sample result."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low, high = math.floor(position), math.ceil(position)
    return round(ordered[low] + (ordered[high] - ordered[low]) * (position - low), 3)


def seed(
    client: httpx.Client,
    reviews: list[dict[str, Any]],
    *,
    poll_timeout: float = 300,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Submit sequentially and poll with bounded waits; summarize without review text."""
    counts = {"done": 0, "failed": 0, "unconfirmed": 0}
    latencies: list[float] = []
    for review in reviews:
        started = clock()
        try:
            response = request_with_backoff(
                client, "POST", "/api/reviews", payload=review, sleep=sleep
            )
            review_id = response.json()["review_id"]
            if type(review_id) is not int or review_id < 1:
                raise ValueError("Invalid review ID")
            deadline = clock() + poll_timeout
            outcome = "unconfirmed"
            while clock() < deadline:
                status = request_with_backoff(
                    client,
                    "GET",
                    f"/api/reviews/{review_id}/status",
                    sleep=sleep,
                    max_wait=max(0, deadline - clock()),
                ).json()["status"]
                if status in ("done", "failed"):
                    outcome = status
                    break
                if status not in ("pending", "processing"):
                    raise ValueError("Unknown review status")
                sleep(min(2, max(0, deadline - clock())))
            counts[outcome] += 1
            if outcome == "done":
                latencies.append(clock() - started)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            # A network error can happen after persistence. Do not blindly resubmit.
            counts["unconfirmed"] += 1
    return {
        **counts,
        "total": len(reviews),
        "latency_scope": "successful end-to-end submissions, including backoff",
        "latency_p50_seconds": percentile(latencies, 0.5),
        "latency_p95_seconds": percentile(latencies, 0.95),
    }


def main() -> int:
    """CLI entry point; dry-run performs no network operations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    url = urlsplit(args.api_url)
    if (
        url.scheme not in ("http", "https")
        or not url.netloc
        or url.username
        or url.password
        or url.path not in ("", "/")
        or url.query
        or url.fragment
    ):
        parser.error("--api-url must be an HTTP(S) origin without credentials")
    try:
        reviews = read_reviews(args.input, args.limit)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.dry_run:
        print(json.dumps({"validated": len(reviews), "dry_run": True}))
        return 0
    with httpx.Client(base_url=args.api_url, timeout=20, follow_redirects=False) as client:
        summary = seed(client, reviews)
    print(json.dumps(summary, indent=2))
    return 1 if summary["failed"] or summary["unconfirmed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
