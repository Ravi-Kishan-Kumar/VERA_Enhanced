"""`products` table — Empirical-Bayes product aggregates (PRD §11, §15)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, JSONType

if TYPE_CHECKING:
    from app.models.review import Review


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("idx_products_rank", "rank_position"),
        Index("idx_products_category", "product_category"),
    )

    asin: Mapped[str] = mapped_column(String(20), primary_key=True)
    title: Mapped[str | None] = mapped_column(Text)
    product_category: Mapped[str] = mapped_column(
        String(20), nullable=False, default="earbuds", server_default="earbuds"
    )
    price_inr: Mapped[float | None] = mapped_column(Float, nullable=True)

    corrected_score: Mapped[float | None] = mapped_column(Float)
    uncertainty: Mapped[float | None] = mapped_column(Float)
    trust_weighted_score: Mapped[float | None] = mapped_column(Float)
    star_average: Mapped[float | None] = mapped_column(Float)
    eb_shrinkage_factor: Mapped[float | None] = mapped_column(Float)
    review_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    aspect_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONType)

    rank_position: Mapped[int | None] = mapped_column(Integer)
    previous_rank_position: Mapped[int | None] = mapped_column(Integer)
    last_aggregated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    reviews: Mapped[list[Review]] = relationship(back_populates="product")

    def __repr__(self) -> str:
        return f"<Product asin={self.asin!r} score={self.corrected_score} n={self.review_count}>"
