"""Worker persistence behaviour with pipeline and Redis replaced by deterministic fakes."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.review import Review, ReviewStatus


class _Pipeline:
    def process(self, **_: object) -> dict[str, Any]:
        return {
            "corrected_score": 3.4,
            "interval": [3.0, 3.8],
            "confidence": 0.8,
            "star_text_gap": 0.6,
            "review_quality": 0.7,
            "aspects": {},
            "flags": {"is_english": True},
            "explanation": "Test explanation.",
        }


def test_worker_persists_result_and_schedules_aggregation(db: Session, monkeypatch: object) -> None:
    from app.worker import tasks

    review = Review(
        text="A sufficiently long review body for worker processing.",
        star_rating=4.0,
        product_asin="B012345678",
    )
    db.add(Product(asin="B012345678"))
    db.add(review)
    db.commit()
    scheduled: list[bool] = []

    monkeypatch.setattr(tasks, "get_pipeline", lambda: _Pipeline())
    monkeypatch.setattr(tasks.aggregate_products_task, "delay", lambda: scheduled.append(True))

    result = tasks.process_review_task.run(review.id)
    db.expire_all()
    saved = db.get(Review, review.id)

    assert result == {"review_id": review.id, "status": "done"}
    assert saved is not None
    assert saved.status == ReviewStatus.DONE.value
    assert saved.corrected_score == 3.4
    assert scheduled == [True]
