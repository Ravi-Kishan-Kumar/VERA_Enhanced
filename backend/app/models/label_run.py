"""`label_runs` table — audit trail of LLM-generated labels (PRD §7, §15)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, JSONType


class LabelRun(Base):
    __tablename__ = "label_runs"
    __table_args__ = (Index("idx_label_runs_hash", "review_text_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # sha256 hex
    labeler: Mapped[str] = mapped_column(String(100), nullable=False)
    experience_score: Mapped[float | None] = mapped_column(Float)
    aspects: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    has_irony: Mapped[bool | None] = mapped_column()
    review_quality: Mapped[str | None] = mapped_column(String(10))
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
