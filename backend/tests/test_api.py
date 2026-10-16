"""Public API behaviour with the broker replaced by fakes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.job import Job, JobKind
from app.models.product import Product
from app.models.review import Review, ReviewStatus


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "text": "The sound is clear and comfortable, though the battery could last longer.",
        "star_rating": 4.0,
        "helpful_votes": 3,
        "verified_purchase": True,
        "product_title": "VERA Wireless Earbuds",
        "product_asin": "B012345678",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Capture wake-ups instead of talking to Redis."""
    captured: list[str] = []
    monkeypatch.setattr("app.api.routes.reviews.send_wakeup", captured.append)
    return captured


def test_submit_creates_product_review_and_job_atomically(
    client: TestClient, db: Session, sent: list[str]
) -> None:
    response = client.post("/api/reviews", json=_payload())

    assert response.status_code == 202
    body = response.json()
    job = db.query(Job).one()
    assert body == {
        "review_id": 1,
        "task_id": job.id,
        "status": "pending",
        "message": "Review queued for processing",
    }
    assert job.kind == JobKind.REVIEW.value and job.review_id == 1
    assert job.last_dispatched_at is not None
    assert sent == [job.id]
    product = db.get(Product, "B012345678")
    assert product is not None and product.title == "VERA Wireless Earbuds"
    assert db.get(Review, 1).status == ReviewStatus.PENDING.value  # type: ignore[union-attr]


def test_submit_recovers_when_another_request_creates_the_product_first(
    client: TestClient,
    db: Session,
    sent: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A unique-key race must not discard a valid review submission."""
    product = Product(asin="B012345678")
    db.add(product)
    db.commit()

    original_get = Session.get
    raced = False
    calls: list[tuple[int, object, object]] = []

    def hide_product_once(
        session: Session, entity: type[object], ident: object, *args: object, **kwargs: object
    ) -> object | None:
        nonlocal raced
        calls.append((id(session), entity, ident))
        if entity is Product and ident == product.asin and not raced:
            raced = True  # another request commits the row after our initial lookup
            return None
        return original_get(session, entity, ident, *args, **kwargs)

    monkeypatch.setattr(Session, "get", hide_product_once)
    response = client.post("/api/reviews", json=_payload())

    assert response.status_code == 202
    assert raced
    assert calls[0][0] != id(db)
    assert calls[0][1:] == (Product, product.asin)
    assert db.query(Product).count() == 1
    db.refresh(product)  # the fixture session cached the pre-request shell
    assert product.title == "VERA Wireless Earbuds"
    assert db.query(Review).count() == 1
    assert sent


def test_broker_outage_still_accepts_review_for_outbox_retry(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(_: str) -> None:
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr("app.api.routes.reviews.send_wakeup", unavailable)
    response = client.post("/api/reviews", json=_payload(product_asin=None))

    assert response.status_code == 202
    job = db.query(Job).one()
    assert job.last_dispatched_at is None  # outbox will pick it up
    assert db.get(Review, 1).status == ReviewStatus.PENDING.value  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "overrides",
    [
        {"text": "too short"},
        {"star_rating": 0},
        {"star_rating": 5.5},
        {"helpful_votes": -1},
        {"product_asin": "X" * 21},
    ],
)
def test_submit_rejects_invalid_payloads(
    client: TestClient, sent: list[str], overrides: dict[str, object]
) -> None:
    assert client.post("/api/reviews", json=_payload(**overrides)).status_code == 422
    assert sent == []


def test_blank_asin_is_normalised_to_none(client: TestClient, db: Session, sent: list[str]) -> None:
    assert client.post("/api/reviews", json=_payload(product_asin="   ")).status_code == 202
    assert db.get(Review, 1).product_asin is None  # type: ignore[union-attr]
    assert db.query(Product).count() == 0


def test_review_status_and_detail_are_pollable(client: TestClient, db: Session) -> None:
    review = Review(text="A sufficiently long review body for testing status.", star_rating=3.0)
    db.add(review)
    db.commit()

    status_response = client.get(f"/api/reviews/{review.id}/status")
    detail_response = client.get(f"/api/reviews/{review.id}")

    assert status_response.status_code == 200
    assert status_response.json()["status"] == "pending"
    assert detail_response.json()["corrected_score"] is None
    assert client.get("/api/reviews/999/status").status_code == 404
    assert client.get("/api/reviews/999").status_code == 404


def test_product_ranking_excludes_unscored_and_breaks_ties_stably(
    client: TestClient, db: Session
) -> None:
    db.add_all(
        [
            Product(asin="B", title="Second", corrected_score=4.5, review_count=1),
            Product(asin="A", title="First", corrected_score=4.5, review_count=4),
            Product(asin="S", title="Shell only"),
        ]
    )
    db.commit()

    listing = client.get("/api/products?sort_by=corrected_score&order=desc")

    assert listing.status_code == 200
    assert [row["asin"] for row in listing.json()] == ["A", "B"]
    assert listing.headers["X-Total-Count"] == "2"
    assert client.get("/api/products?sort_by=bogus").status_code == 422


def test_product_detail_paginates_completed_reviews(client: TestClient, db: Session) -> None:
    db.add(Product(asin="A", title="First", corrected_score=4.0, review_count=3))
    for index in range(3):
        db.add(
            Review(
                text=f"Completed review number {index} with enough words.",
                star_rating=4.0,
                product_asin="A",
                status=ReviewStatus.DONE.value,
                corrected_score=4.0,
            )
        )
    db.add(
        Review(text="Pending review should not be listed here.", star_rating=2, product_asin="A")
    )
    db.commit()

    page = client.get("/api/products/A?reviews_limit=2").json()

    assert page["reviews_total"] == 3
    assert len(page["reviews"]) == 2 and page["reviews_has_more"] is True
    assert client.get("/api/products/missing").status_code == 404


def test_health_is_always_200_and_reports_missing_artifacts(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: "Path"
) -> None:
    from pathlib import Path
    empty_dir = tmp_path / "no-models"
    empty_dir.mkdir()
    monkeypatch.setattr("app.api.routes.health.settings.MODEL_DIR", empty_dir)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["database"] is True
    assert body["status"] == "degraded"
    assert not any(body["model_artifacts"].values())

