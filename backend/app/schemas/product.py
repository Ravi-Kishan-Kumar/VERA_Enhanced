"""Product ranking API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.review import ReviewResponse


class ProductResponse(BaseModel):
    """Compact item in the product-ranking response."""

    model_config = ConfigDict(from_attributes=True)

    asin: str
    title: str | None
    corrected_score: float | None
    uncertainty: float | None
    trust_weighted_score: float | None
    star_average: float | None
    review_count: int
    rank_position: int | None


class ProductDetailResponse(ProductResponse):
    """Product plus its aspect aggregate and completed/pending reviews."""

    eb_shrinkage_factor: float | None
    aspect_summary: dict[str, Any] | None
    previous_rank_position: int | None
    last_aggregated_at: datetime | None
    reviews: list[ReviewResponse]
