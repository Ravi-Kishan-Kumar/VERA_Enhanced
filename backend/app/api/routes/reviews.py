"""Review submission and polling routes (PRD §14.1–14.2)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.job import Job, JobKind
from app.models.product import Product
from app.models.review import Review, ReviewStatus
from app.schemas.review import ReviewCreate, ReviewResponse, ReviewTaskStatus
from app.worker.outbox import send_wakeup

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reviews", tags=["reviews"])

STATUS_MESSAGES: dict[str, str] = {
    ReviewStatus.PENDING.value: "Review is queued for processing",
    ReviewStatus.PROCESSING.value: "Review is being processed",
    ReviewStatus.DONE.value: "Review processing completed",
    ReviewStatus.FAILED.value: "Review processing failed",
}


def _get_review_or_404(db: Session, review_id: int) -> Review:
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    return review


def _ensure_product_shell(db: Session, asin: str, title: str | None) -> None:
    """Create or update the product row without losing concurrent first reviews."""
    product = db.get(Product, asin)
    if product is None:
        try:
            # The savepoint lets a concurrent ASIN insert fail locally while
            # preserving the review/job transaction that follows it.
            with db.begin_nested():
                db.add(Product(asin=asin, title=title))
                db.flush()
        except IntegrityError:
            product = db.get(Product, asin)
            if product is None:
                raise
    if product is not None and title and not product.title:
        product.title = title


@router.post("", response_model=ReviewTaskStatus, status_code=status.HTTP_202_ACCEPTED)
def submit_review(payload: ReviewCreate, db: Session = Depends(get_db)) -> ReviewTaskStatus:
    """Persist a review and its processing job atomically; return for polling.

    The product shell is created first because ``reviews.product_asin`` is a
    foreign key (the PRD's schema made every first review of an ASIN fail).
    After commit a wake-up is sent to Redis; if Redis is down the job is still
    durable and the outbox dispatcher delivers it later, so this never 503s.
    """
    asin = payload.product_asin
    if asin:
        _ensure_product_shell(db, asin, payload.product_title)

    review = Review(
        text=payload.text,
        star_rating=payload.star_rating,
        helpful_votes=payload.helpful_votes,
        verified_purchase=payload.verified_purchase,
        product_title=payload.product_title,
        product_asin=asin,
        status=ReviewStatus.PENDING.value,
    )
    db.add(review)
    db.flush()  # assigns review.id
    job = Job(kind=JobKind.REVIEW.value, review_id=review.id)
    db.add(job)
    db.commit()

    try:
        send_wakeup(job.id)
        job.last_dispatched_at = datetime.now(UTC)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Broker unavailable for job %s; outbox will retry", job.id, exc_info=True)

    return ReviewTaskStatus(
        review_id=review.id,
        task_id=job.id,
        status=ReviewStatus.PENDING.value,
        message="Review queued for processing",
    )


@router.get("/{review_id}", response_model=ReviewResponse)
def get_review(review_id: int, db: Session = Depends(get_db)) -> Review:
    """Get a review and, when available, its pipeline output."""
    return _get_review_or_404(db, review_id)


@router.get("/{review_id}/status", response_model=ReviewTaskStatus)
def get_review_status(review_id: int, db: Session = Depends(get_db)) -> ReviewTaskStatus:
    """Lightweight lifecycle state for polling clients."""
    review = _get_review_or_404(db, review_id)
    job_id = db.query(Job.id).filter(Job.review_id == review.id).scalar()
    return ReviewTaskStatus(
        review_id=review.id,
        task_id=job_id,
        status=review.status,
        message=STATUS_MESSAGES.get(review.status, "Unknown status"),
    )
