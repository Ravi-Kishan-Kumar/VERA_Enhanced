"""Mock-only coverage: no requests reach a running API or inference worker."""

from datetime import UTC, datetime

import httpx
import pytest
from scripts.seed_demo import (
    parse_review,
    percentile,
    read_reviews,
    request_with_backoff,
    retry_delay,
    seed,
)

REVIEW = {"text": "Comfortable earbuds with a detailed sound.", "star_rating": "4"}


def test_parse_optional_fields():
    assert parse_review({**REVIEW, "verified_purchase": "false", "helpful_votes": "0"}) == {
        "text": REVIEW["text"],
        "star_rating": 4.0,
        "verified_purchase": False,
        "helpful_votes": 0,
    }


@pytest.mark.parametrize(
    "update",
    [
        {"text": "short"},
        {"star_rating": "nan"},
        {"star_rating": True},
        {"verified_purchase": "yes"},
        {"helpful_votes": -1},
        {"product_asin": 123},
    ],
)
def test_invalid_fields(update):
    with pytest.raises(ValueError):
        parse_review({**REVIEW, **update})


def test_read_csv_and_jsonl(tmp_path):
    import json

    csv = tmp_path / "reviews.csv"
    csv.write_text(
        "text,star_rating\nComfortable earbuds with excellent bass.,4\n", encoding="utf-8"
    )
    jsonl = tmp_path / "reviews.jsonl"
    jsonl.write_text(json.dumps(REVIEW) + "\nnot json", encoding="utf-8")
    assert len(read_reviews(csv, 1)) == 1
    assert len(read_reviews(jsonl, 1)) == 1
    with pytest.raises(ValueError, match="record 2"):
        read_reviews(jsonl, 2)


def test_backoff_respects_retry_after():
    requests = []
    waits = []

    def handler(request):
        requests.append(request)
        return (
            httpx.Response(429, headers={"Retry-After": "2"})
            if len(requests) == 1
            else httpx.Response(202)
        )

    with httpx.Client(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    ) as client:
        assert (
            request_with_backoff(client, "POST", "/api/reviews", sleep=waits.append).status_code
            == 202
        )
    assert waits == [2]
    assert len(requests) == 2


def test_ambiguous_post_is_not_retried():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503)

    with (
        httpx.Client(
            base_url="https://example.test", transport=httpx.MockTransport(handler)
        ) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        request_with_backoff(client, "POST", "/api/reviews")
    assert len(calls) == 1


def test_retry_budget_and_date():
    assert retry_delay("Mon, 14 Sep 2026 00:00:05 GMT", datetime(2026, 9, 14, tzinfo=UTC)) == 5
    assert retry_delay("nan") == 60
    with (
        httpx.Client(
            base_url="https://example.test",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(429, headers={"Retry-After": "999"})
            ),
        ) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        request_with_backoff(
            client, "POST", "/api/reviews", sleep=lambda _: pytest.fail("must not sleep")
        )


def test_seed_summary_without_live_api():
    def handler(request):
        return (
            httpx.Response(202, json={"review_id": 1})
            if request.method == "POST"
            else httpx.Response(200, json={"status": "done"})
        )

    with httpx.Client(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    ) as client:
        summary = seed(client, [parse_review(REVIEW)], clock=lambda: 0)
    assert summary["done"] == 1
    assert summary["failed"] == summary["unconfirmed"] == 0
    assert summary["latency_p50_seconds"] == 0
    assert percentile([], 0.95) is None
    assert percentile([1, 2, 3], 0.95) == 2.9


def test_dry_run_never_creates_http_client(tmp_path, monkeypatch, capsys):
    from scripts.seed_demo import main

    source = tmp_path / "reviews.csv"
    source.write_text(
        "text,star_rating\nComfortable earbuds with excellent bass.,4\n", encoding="utf-8"
    )
    monkeypatch.setattr("sys.argv", ["seed_demo.py", str(source), "--dry-run"])
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: pytest.fail("dry-run must not network"))
    assert main() == 0
    assert '"validated": 1' in capsys.readouterr().out


def test_network_failure_does_not_duplicate_submission():
    requests = []

    def handler(request):
        requests.append(request)
        raise httpx.ReadTimeout("Response lost", request=request)

    with httpx.Client(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    ) as client:
        summary = seed(client, [parse_review(REVIEW)])
    assert summary["unconfirmed"] == 1
    assert len(requests) == 1


def test_polling_timeout_is_unconfirmed_not_failed():
    elapsed = [0.0]

    def advance(seconds):
        elapsed[0] += seconds

    def handler(request):
        return httpx.Response(200, json={"review_id": 1, "status": "pending"})

    with httpx.Client(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    ) as client:
        summary = seed(
            client, [parse_review(REVIEW)], poll_timeout=3, sleep=advance, clock=lambda: elapsed[0]
        )
    assert summary["unconfirmed"] == 1
    assert summary["failed"] == 0
    assert elapsed[0] == 3
