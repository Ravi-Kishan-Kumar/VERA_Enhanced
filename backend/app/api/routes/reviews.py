"""Asynchronous review-submission and polling routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.product import Product
from app.models.review import Review, ReviewStatus
from app.schemas.review import ReviewCreate, ReviewResponse, ReviewTaskStatus
from app.worker.tasks import process_review_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reviews", tags=["reviews"])


def _get_review_or_404(db: Session, review_id: int) -> Review:
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    return review


@router.post("", response_model=ReviewTaskStatus, status_code=status.HTTP_202_ACCEPTED)
def submit_review(payload: ReviewCreate, db: Session = Depends(get_db)) -> ReviewTaskStatus:
    """Persist a review, enqueue it, and return immediately for client polling."""
    asin = payload.product_asin
    if asin:
        # The FK is intentional: create a lightweight product shell first so a
        # first-ever review for an ASIN never fails its insert.
        product = db.get(Product, asin)
        if product is None:
            product = Product(asin=asin, title=payload.product_title)
            db.add(product)
        elif payload.product_title and not product.title:
            product.title = payload.product_title

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
    db.commit()
    db.refresh(review)

    try:
        task = process_review_task.delay(review.id)
    except Exception as exc:
        # A persisted-but-unqueueable review must not look silently pending.
        logger.exception("Could not enqueue review %s", review.id)
        review.status = ReviewStatus.FAILED.value
        review.error_message = "The review could not be queued. Please submit it again."
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Review queue is unavailable; please retry shortly.",
        ) from exc

    return ReviewTaskStatus(
        review_id=review.id,
        task_id=task.id,
        status=review.status,
        message="Review queued for processing",
    )


@router.get("/{review_id}", response_model=ReviewResponse)
def get_review(review_id: int, db: Session = Depends(get_db)) -> Review:
    """Get a review and, when available, its pipeline output."""
    return _get_review_or_404(db, review_id)


@router.get("/{review_id}/status", response_model=ReviewTaskStatus)
def get_review_status(review_id: int, db: Session = Depends(get_db)) -> ReviewTaskStatus:
    """Get just the lifecycle state used by polling clients."""
    review = _get_review_or_404(db, review_id)
    messages = {
        ReviewStatus.PENDING.value: "Review is queued for processing",
        ReviewStatus.PROCESSING.value: "Review is being processed",
        ReviewStatus.DONE.value: "Review processing completed",
        ReviewStatus.FAILED.value: "Review processing failed",
    }
    return ReviewTaskStatus(
        review_id=review.id,
        task_id=None,
        status=review.status,
        message=messages[review.status],
    )
