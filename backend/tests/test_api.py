"""Public API behaviour, including database/queue integration boundaries."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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


def test_submit_creates_product_shell_and_queues_review(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    queued: list[int] = []

    def delay(review_id: int) -> SimpleNamespace:
        queued.append(review_id)
        return SimpleNamespace(id="task-123")

    monkeypatch.setattr("app.api.routes.reviews.process_review_task.delay", delay)
    response = client.post("/api/reviews", json=_payload())

    assert response.status_code == 202
    body = response.json()
    assert body == {
        "review_id": 1,
        "task_id": "task-123",
        "status": "pending",
        "message": "Review queued for processing",
    }
    assert queued == [1]
    product = db.get(Product, "B012345678")
    review = db.get(Review, 1)
    assert product is not None and product.title == "VERA Wireless Earbuds"
    assert review is not None and review.status == ReviewStatus.PENDING.value


def test_review_status_and_detail_are_pollable(client: TestClient, db: Session) -> None:
    review = Review(
        text="A sufficiently long review body for testing status endpoints.",
        star_rating=3.0,
    )
    db.add(review)
    db.commit()

    status_response = client.get(f"/api/reviews/{review.id}/status")
    detail_response = client.get(f"/api/reviews/{review.id}")

    assert status_response.status_code == 200
    assert status_response.json()["status"] == "pending"
    assert detail_response.status_code == 200
    assert detail_response.json()["corrected_score"] is None
    assert client.get("/api/reviews/999/status").status_code == 404


def test_queue_outage_marks_review_failed_and_returns_503(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    def unavailable(_: int) -> None:
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr("app.api.routes.reviews.process_review_task.delay", unavailable)
    response = client.post("/api/reviews", json=_payload(product_asin=None))

    assert response.status_code == 503
    failed = db.get(Review, 1)
    assert failed is not None
    assert failed.status == ReviewStatus.FAILED.value
    assert failed.error_message is not None


def test_product_routes_have_stable_ranking_and_detail(client: TestClient, db: Session) -> None:
    first = Product(asin="A", title="First", corrected_score=4.5, review_count=4)
    second = Product(asin="B", title="Second", corrected_score=4.5, review_count=1)
    db.add_all([first, second])
    db.commit()

    listing = client.get("/api/products?sort_by=corrected_score&order=desc")
    detail = client.get("/api/products/A")

    assert listing.status_code == 200
    assert [row["asin"] for row in listing.json()] == ["A", "B"]
    assert detail.status_code == 200
    assert detail.json()["title"] == "First"
    assert client.get("/api/products/missing").status_code == 404
