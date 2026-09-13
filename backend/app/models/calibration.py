"""`calibration_checkpoints` table — history of fitted conformal q_hat values (PRD §10.3)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CalibrationCheckpoint(Base):
    __tablename__ = "calibration_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="absolute")
    q_hat: Mapped[float] = mapped_column(Float, nullable=False)
    empirical_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    nominal_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    calibration_set_size: Mapped[int] = mapped_column(Integer, nullable=False)
    fitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
