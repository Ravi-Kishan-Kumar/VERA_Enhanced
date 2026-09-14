"""Celery task: execute one outbox job (review inference or product aggregation).

Delivery model (see :mod:`app.models.job`): Redis messages are only wake-ups
and may be duplicated or lost; the ``jobs`` row is the source of truth. Every
run locks its job row, skips finished jobs, and records retries durably with
exponential back-off. :mod:`app.worker.outbox` re-sends anything unfinished.

ML models load lazily through :func:`get_pipeline`, so importing this module
(e.g. from tests) never touches model artifacts.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Final

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.job import Job, JobKind
from app.models.product import Product
from app.models.review import Review, ReviewStatus
from app.worker.celery_app import celery_app

if TYPE_CHECKING:
    from app.ml.pipeline import VERAPipeline

logger = logging.getLogger(__name__)

MAX_REVIEW_ATTEMPTS: Final = 4
MAX_AGGREGATE_ATTEMPTS: Final = 10
MAX_BACKOFF_SECONDS: Final = 300
#: Arbitrary constant key for the Postgres advisory lock around aggregation.
AGGREGATION_LOCK_KEY: Final = 19842026
FAILED_REVIEW_MESSAGE: Final = "Review analysis failed. Please try again later."


@lru_cache(maxsize=1)
def get_pipeline() -> VERAPipeline:
    """Load production artifacts once per worker process. Never falls back."""
    from app.ml.pipeline import VERAPipeline

    return VERAPipeline(settings.MODEL_DIR, settings.HF_MODEL_REPO, settings.HF_TOKEN)


def _as_utc(value: datetime) -> datetime:
    """Normalise DB datetimes: SQLite returns naive values, Postgres aware ones."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def backoff_seconds(attempts: int) -> int:
    """5 s, 10 s, 20 s, … capped at :data:`MAX_BACKOFF_SECONDS`."""
    return min(MAX_BACKOFF_SECONDS, 5 * 2 ** min(attempts, 6))


# ----------------------------------------------------------------------------
# Job handlers — run inside the caller's transaction; the caller commits.
# ----------------------------------------------------------------------------
def process_review(db: Session, review_id: int) -> None:
    """Run the pipeline for one review and store its result.

    The review row stays locked for the whole inference, so a crash rolls back
    cleanly and a duplicate delivery cannot write concurrently. The status is not
    committed as "processing" separately; clients see "pending" until "done".
    """
    review = db.query(Review).filter(Review.id == review_id).with_for_update().one_or_none()
    if review is None or review.status in (ReviewStatus.DONE.value, ReviewStatus.FAILED.value):
        return

    result = get_pipeline().process(
        text=review.text,
        star_rating=review.star_rating,
        helpful_votes=review.helpful_votes,
        verified_purchase=review.verified_purchase,
        product_title=review.product_title,
    )
    review.corrected_score = result["corrected_score"]
    review.interval_lower, review.interval_upper = result["interval"]
    review.confidence_value = result["confidence"]
    review.star_text_gap = result["star_text_gap"]
    review.review_quality = result["review_quality"]
    review.aspects = result["aspects"]
    review.flags = result["flags"]
    review.explanation = result["explanation"]
    review.error_message = None
    review.status = ReviewStatus.DONE.value

    # Reviews without an ASIN never create aggregation work (PRD weakness #3).
    if review.product_asin:
        db.add(Job(kind=JobKind.AGGREGATE.value))


def aggregate_products(db: Session, current_job_id: str | None = None) -> int:
    """Recompute EB aggregates and ranks for ALL products. Returns product count.

    The EB prior is a population quantity, so every product is refreshed under
    one lock (Postgres advisory transaction lock — released on commit/rollback,
    no TTL to expire mid-run). Other unfinished aggregate jobs visible *before*
    the review snapshot is read are marked finished: their reviews are already
    committed and therefore included, so re-running them would be pure waste.
    """
    from app.ml.calibration.empirical_bayes import (
        EmpiricalBayesAggregator,
        ReviewSignal,
        rank_products,
    )

    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": AGGREGATION_LOCK_KEY})

    superseded = (
        db.query(Job)
        .filter(
            Job.kind == JobKind.AGGREGATE.value,
            Job.finished_at.is_(None),
            Job.id != (current_job_id or ""),
        )
        .with_for_update(skip_locked=True)
        .all()
    )

    rows = (
        db.query(
            Review.product_asin,
            Review.corrected_score,
            Review.review_quality,
            Review.star_rating,
            Review.aspects,
        )
        .filter(
            Review.status == ReviewStatus.DONE.value,
            Review.product_asin.is_not(None),
            Review.corrected_score.is_not(None),
        )
        .all()
    )
    now = datetime.now(UTC)
    for job in superseded:
        job.finished_at = now

    signals = [
        ReviewSignal(
            product_asin=row.product_asin,
            corrected_score=float(row.corrected_score),
            quality_weight=float(row.review_quality) if row.review_quality is not None else 0.5,
            star_rating=float(row.star_rating),
            aspects=row.aspects or {},
        )
        for row in rows
    ]
    if not signals:
        return 0

    _, aggregates = EmpiricalBayesAggregator().aggregate_all(signals)
    for rank, asin in enumerate(rank_products(aggregates), start=1):
        aggregate = aggregates[asin]
        product = db.get(Product, asin)
        if product is None:  # FK makes this impossible unless data was edited by hand
            raise RuntimeError(f"Completed review references missing product {asin!r}")
        product.previous_rank_position = product.rank_position
        product.rank_position = rank
        product.corrected_score = aggregate.corrected_score
        product.uncertainty = aggregate.uncertainty
        product.trust_weighted_score = aggregate.trust_weighted_score
        product.star_average = aggregate.star_average
        product.eb_shrinkage_factor = aggregate.eb_shrinkage_factor
        product.review_count = aggregate.review_count
        product.aspect_summary = aggregate.aspect_summary
        product.last_aggregated_at = now
    return len(aggregates)


# ----------------------------------------------------------------------------
# Celery entry point
# ----------------------------------------------------------------------------
def _record_failure(db: Session, job_id: str) -> None:
    """Increment attempts; schedule a retry or mark the job (and review) failed."""
    job = db.query(Job).filter(Job.id == job_id).with_for_update().one_or_none()
    if job is None or job.finished_at is not None:
        return  # a duplicate delivery finished it meanwhile

    job.attempts += 1
    limit = MAX_REVIEW_ATTEMPTS if job.kind == JobKind.REVIEW.value else MAX_AGGREGATE_ATTEMPTS
    now = datetime.now(UTC)
    if job.attempts >= limit:
        job.finished_at = now
        if job.kind == JobKind.REVIEW.value and job.review_id is not None:
            review = db.get(Review, job.review_id)
            if review is not None and review.status != ReviewStatus.DONE.value:
                review.status = ReviewStatus.FAILED.value
                review.error_message = FAILED_REVIEW_MESSAGE
        logger.error("Job %s (%s) failed permanently after %d attempts", job.id, job.kind, limit)
    else:
        job.available_at = now + timedelta(seconds=backoff_seconds(job.attempts))
        job.last_dispatched_at = None  # let the outbox re-send once due
    db.commit()


def execute_job(job_id: str) -> str:
    """Run one job to completion or record its failure. Returns an outcome label."""
    with SessionLocal() as db:
        try:
            job = (
                db.query(Job)
                .filter(Job.id == job_id)
                .with_for_update(skip_locked=True)
                .one_or_none()
            )
            if job is None or job.finished_at is not None:
                return "ignored"  # unknown, finished, or locked by a concurrent delivery
            if _as_utc(job.available_at) > datetime.now(UTC):
                return "deferred"

            if job.kind == JobKind.REVIEW.value and job.review_id is not None:
                process_review(db, job.review_id)
            elif job.kind == JobKind.AGGREGATE.value:
                aggregate_products(db, current_job_id=job.id)
            else:
                raise ValueError(f"Unknown job kind {job.kind!r}")

            job.finished_at = datetime.now(UTC)
            db.commit()
            return "done"
        except Exception:
            db.rollback()
            logger.exception("Job %s failed; recording durable retry", job_id)
            _record_failure(db, job_id)
            return "retry_or_failed"


@celery_app.task(name="vera.run_job", ignore_result=True)
def run_job(job_id: str) -> dict[str, Any]:
    """Celery wrapper around :func:`execute_job`."""
    return {"job_id": job_id, "status": execute_job(job_id)}
