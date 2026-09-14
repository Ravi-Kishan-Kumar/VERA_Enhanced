"""Product API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.review import ReviewResponse


class ProductResponse(BaseModel):
    """One row of the product ranking."""

    model_config = ConfigDict(from_attributes=True)

    asin: str
    title: str | None
    corrected_score: float | None
    uncertainty: float | None
    trust_weighted_score: float | None
    star_average: float | None
    review_count: int
    rank_position: int | None
    previous_rank_position: int | None
    aspect_summary: dict[str, Any] | None


class ProductDetailResponse(ProductResponse):
    """Product aggregate plus one page of completed reviews."""

    eb_shrinkage_factor: float | None
    last_aggregated_at: datetime | None
    reviews: list[ReviewResponse]
    reviews_total: int
    reviews_limit: int
    reviews_offset: int
    reviews_has_more: bool
