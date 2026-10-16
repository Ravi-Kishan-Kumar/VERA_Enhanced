"""Review API contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ml.constants import Sentiment


class AspectSentiment(BaseModel):
    """Inference result for one earbud aspect."""

    detected: bool
    sentiment: Sentiment
    confidence: float = Field(ge=0.0, le=1.0)
    prob_neg: float | None = Field(default=None, ge=0.0, le=1.0)
    prob_neu: float | None = Field(default=None, ge=0.0, le=1.0)
    prob_pos: float | None = Field(default=None, ge=0.0, le=1.0)


class ReviewCreate(BaseModel):
    """A review submitted for asynchronous scoring."""

    text: str = Field(min_length=20, max_length=10_000)
    star_rating: float = Field(ge=1.0, le=5.0)
    helpful_votes: int | None = Field(default=None, ge=0)
    verified_purchase: bool | None = None
    product_title: str | None = Field(default=None, max_length=1_000)
    product_asin: str | None = Field(default=None, max_length=20)
    product_category: str = Field(default="earbuds", max_length=20)

    @field_validator("text")
    @classmethod
    def text_must_contain_non_whitespace(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must contain non-whitespace characters")
        return value

    @field_validator("product_title", "product_asin", mode="before")
    @classmethod
    def strip_optional_strings(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("must be a string")
        return value.strip() or None


class ReviewTaskStatus(BaseModel):
    """Polling response returned after a review is submitted."""

    review_id: int
    task_id: str | None
    status: str
    message: str


class ReviewResponse(BaseModel):
    """Persisted review plus any completed pipeline result."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    star_rating: float
    product_category: str = "earbuds"
    helpful_votes: int | None
    verified_purchase: bool | None
    product_title: str | None
    product_asin: str | None
    corrected_score: float | None
    interval_lower: float | None
    interval_upper: float | None
    confidence_value: float | None
    star_text_gap: float | None
    review_quality: float | None
    aspects: dict[str, AspectSentiment] | None
    flags: dict[str, Any] | None
    explanation: str | None
    error_message: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ReviewLifecycle(StrEnum):
    """Public lifecycle values; mirrors the persisted ORM enum."""

    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
