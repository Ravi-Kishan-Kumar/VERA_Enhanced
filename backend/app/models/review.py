"""`reviews` table — one submitted review and its pipeline output (PRD §15)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, JSONType

if TYPE_CHECKING:
    from app.models.product import Product


class ReviewStatus(StrEnum):
    """Processing lifecycle of a review."""

    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("star_rating >= 1 AND star_rating <= 5", name="ck_reviews_star_range"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'done', 'failed')", name="ck_reviews_status"
        ),
        Index("idx_reviews_asin", "product_asin"),
        Index("idx_reviews_status", "status"),
        Index("idx_reviews_category", "product_category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- Input ----------------------------------------------------------------
    text: Mapped[str] = mapped_column(Text, nullable=False)
    star_rating: Mapped[float] = mapped_column(Float, nullable=False)
    product_category: Mapped[str] = mapped_column(
        String(20), nullable=False, default="earbuds", server_default="earbuds"
    )
    # NULL means "not supplied" — the pipeline imputes training means (PRD §10.1).
    helpful_votes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verified_purchase: Mapped[bool | None] = mapped_column(nullable=True)
    product_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_asin: Mapped[str | None] = mapped_column(
        String(20), ForeignKey("products.asin", ondelete="SET NULL"), nullable=True
    )

    # --- Pipeline output ------------------------------------------------------
    corrected_score: Mapped[float | None] = mapped_column(Float)
    interval_lower: Mapped[float | None] = mapped_column(Float)
    interval_upper: Mapped[float | None] = mapped_column(Float)
    confidence_value: Mapped[float | None] = mapped_column(Float)
    star_text_gap: Mapped[float | None] = mapped_column(Float)
    review_quality: Mapped[float | None] = mapped_column(Float)
    aspects: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    flags: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    explanation: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    # --- Bookkeeping ----------------------------------------------------------
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ReviewStatus.PENDING.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    product: Mapped[Product | None] = relationship(back_populates="reviews")

    def __repr__(self) -> str:
        return f"<Review id={self.id} status={self.status} asin={self.product_asin!r}>"
