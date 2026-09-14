"""Outbox job execution with the ML pipeline and broker replaced by fakes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.models.job import Job, JobKind
from app.models.product import Product
from app.models.review import Review, ReviewStatus
from app.worker import outbox, tasks


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


class _BrokenPipeline:
    def process(self, **_: object) -> dict[str, Any]:
        raise RuntimeError("onnx exploded")


def _review_job(db: Session, asin: str | None = "B012345678") -> tuple[Review, Job]:
    if asin:
        db.add(Product(asin=asin))
    review = Review(
        text="A sufficiently long review body for worker.", star_rating=4.0, product_asin=asin
    )
    db.add(review)
    db.flush()
    job = Job(kind=JobKind.REVIEW.value, review_id=review.id)
    db.add(job)
    db.commit()
    return review, job


def test_review_job_persists_result_then_aggregation_ranks_product(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    review, job = _review_job(db)
    monkeypatch.setattr(tasks, "get_pipeline", lambda: _Pipeline())

    assert tasks.execute_job(job.id) == "done"
    db.expire_all()
    saved = db.get(Review, review.id)
    assert saved is not None and saved.status == ReviewStatus.DONE.value
    assert saved.corrected_score == 3.4

    aggregate_job = db.query(Job).filter(Job.kind == JobKind.AGGREGATE.value).one()
    assert tasks.execute_job(aggregate_job.id) == "done"
    db.expire_all()
    product = db.get(Product, "B012345678")
    assert product is not None and product.rank_position == 1 and product.review_count == 1

    assert tasks.execute_job(job.id) == "ignored"  # duplicate delivery is harmless


def test_review_without_asin_schedules_no_aggregation(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, job = _review_job(db, asin=None)
    monkeypatch.setattr(tasks, "get_pipeline", lambda: _Pipeline())

    assert tasks.execute_job(job.id) == "done"
    assert db.query(Job).filter(Job.kind == JobKind.AGGREGATE.value).count() == 0


def test_failures_back_off_then_mark_review_failed(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    review, job = _review_job(db)
    monkeypatch.setattr(tasks, "get_pipeline", lambda: _BrokenPipeline())

    for attempt in range(1, tasks.MAX_REVIEW_ATTEMPTS + 1):
        db.query(Job).filter(Job.id == job.id).update({"available_at": datetime.now(UTC)})
        db.commit()
        assert tasks.execute_job(job.id) == "retry_or_failed"
        db.expire_all()
        assert db.get(Job, job.id).attempts == attempt  # type: ignore[union-attr]

    saved_job = db.get(Job, job.id)
    saved_review = db.get(Review, review.id)
    assert saved_job is not None and saved_job.finished_at is not None
    assert saved_review is not None and saved_review.status == ReviewStatus.FAILED.value


def test_deferred_job_is_not_run_early(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    _, job = _review_job(db)
    db.query(Job).filter(Job.id == job.id).update(
        {"available_at": datetime.now(UTC) + timedelta(minutes=5)}
    )
    db.commit()
    monkeypatch.setattr(tasks, "get_pipeline", lambda: _BrokenPipeline())

    assert tasks.execute_job(job.id) == "deferred"


def test_aggregation_supersedes_other_pending_aggregate_jobs(db: Session) -> None:
    first, second = Job(kind=JobKind.AGGREGATE.value), Job(kind=JobKind.AGGREGATE.value)
    db.add_all([first, second])
    db.commit()

    assert tasks.execute_job(first.id) == "done"
    db.expire_all()
    assert db.get(Job, second.id).finished_at is not None  # type: ignore[union-attr]


def test_outbox_dispatches_due_jobs_once(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    _, job = _review_job(db)
    sent: list[str] = []
    monkeypatch.setattr(outbox, "send_wakeup", sent.append)

    assert outbox.dispatch_pending() == 1
    assert outbox.dispatch_pending() == 0  # within the re-dispatch window
    assert sent == [job.id]
