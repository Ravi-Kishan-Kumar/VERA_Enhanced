"""`jobs` table — transactional outbox for background work.

Why an outbox: Postgres and Redis cannot commit atomically. The API writes the
review AND its job row in one database transaction, so a job can never be lost
between "review saved" and "task queued". Redis only carries wake-up messages;
the database owns attempts, back-off, and completion. Duplicate deliveries are
harmless because consumers lock the job row and skip finished jobs.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JobKind(StrEnum):
    REVIEW = "review"  # run the ML pipeline for one review
    AGGREGATE = "aggregate"  # recompute every product aggregate + ranking


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("idx_jobs_dispatch", "finished_at", "available_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    review_id: Mapped[int | None] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), unique=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    #: Earliest time the job may run (pushed forward by retry back-off).
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    #: Last time a wake-up was sent to Redis; NULL means "send now".
    last_dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Job {self.id} kind={self.kind} attempts={self.attempts} done={self.finished_at}>"
