"""Celery review processing and race-safe product aggregation tasks."""

from __future__ import annotations

import logging
from contextlib import suppress
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from celery import Task
from redis import Redis
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.ml.calibration.empirical_bayes import EmpiricalBayesAggregator, ReviewSignal, rank_products
from app.ml.pipeline import VERAPipeline
from app.models.product import Product
from app.models.review import Review, ReviewStatus
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)
_AGGREGATION_LOCK = "vera:aggregation:global"


@lru_cache(maxsize=1)
def get_pipeline() -> VERAPipeline:
    """Load production artifacts once per worker process; never fall back."""
    return VERAPipeline(settings.MODEL_DIR, settings.HF_MODEL_REPO, settings.HF_TOKEN)


def _mark_review_failed(db: Session, review_id: int, exc: Exception) -> None:
    review = db.get(Review, review_id)
    if review is None:
        return
    review.status = ReviewStatus.FAILED.value
    review.error_message = str(exc)[:2_000]
    db.commit()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5, name="vera.process_review")
def process_review_task(self: Task, review_id: int) -> dict[str, Any] | None:
    """Run the seven-agent pipeline and persist a review result.

    Failures retry up to three times. Only the terminal attempt marks a review
    failed, avoiding a misleading terminal state while Celery still retries.
    """
    db = SessionLocal()
    try:
        review = db.get(Review, review_id)
        if review is None:
            logger.warning("Review %s disappeared before processing", review_id)
            return None
        if review.status == ReviewStatus.DONE.value:
            return {"review_id": review_id, "status": ReviewStatus.DONE.value}

        review.status = ReviewStatus.PROCESSING.value
        review.error_message = None
        db.commit()

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
        review.status = ReviewStatus.DONE.value
        db.commit()

        asin = (review.product_asin or "").strip()
        if asin:
            aggregate_products_task.delay()
        return {"review_id": review_id, "status": ReviewStatus.DONE.value}
    except Exception as exc:
        db.rollback()
        if self.request.retries >= self.max_retries:
            _mark_review_failed(db, review_id, exc)
            logger.exception("Review %s failed permanently", review_id)
            raise
        raise self.retry(exc=exc) from exc
    finally:
        db.close()


def _completed_review_signals(db: Session) -> list[ReviewSignal]:
    """Load the complete population required to fit one coherent EB prior."""
    reviews = (
        db.query(Review)
        .filter(
            Review.status == ReviewStatus.DONE.value,
            Review.corrected_score.is_not(None),
            Review.product_asin.is_not(None),
        )
        .all()
    )
    signals: list[ReviewSignal] = []
    for review in reviews:
        asin = (review.product_asin or "").strip()
        score = review.corrected_score
        if not asin or score is None:
            continue
        signals.append(
            ReviewSignal(
                product_asin=asin,
                corrected_score=float(score),
                quality_weight=float(review.review_quality or 0.5),
                star_rating=float(review.star_rating),
                aspects=review.aspects or {},
            )
        )
    return signals


@celery_app.task(bind=True, max_retries=5, default_retry_delay=12, name="vera.aggregate_products")
def aggregate_products_task(self: Task) -> dict[str, int]:
    """Recompute all product aggregates atomically from completed reviews.

    A global Redis lock is deliberate: a statistically valid EB prior and rank
    needs the complete product population, so partial concurrent recomputes
    would otherwise publish inconsistent scores/ranks. The short aggregation
    is infrequent and the lock has a TTL as a worker-crash safety net.
    """
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    lock = redis_client.lock(_AGGREGATION_LOCK, timeout=30, blocking_timeout=0)
    if not lock.acquire(blocking=False):
        raise self.retry(countdown=12)

    db = SessionLocal()
    try:
        signals = _completed_review_signals(db)
        if not signals:
            return {"products": 0}

        _, aggregates = EmpiricalBayesAggregator().aggregate_all(signals)
        ranking = rank_products(aggregates)
        now = datetime.now(UTC)
        for rank, asin in enumerate(ranking, start=1):
            aggregate = aggregates[asin]
            product = db.get(Product, asin)
            if product is None:
                product = Product(asin=asin)
                db.add(product)
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
        db.commit()
        return {"products": len(aggregates)}
    except Exception as exc:
        db.rollback()
        if self.request.retries >= self.max_retries:
            logger.exception("Product aggregation failed permanently")
            raise
        raise self.retry(exc=exc) from exc
    finally:
        db.close()
        with suppress(Exception):
            lock.release()
