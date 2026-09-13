"""SQLAlchemy engine, session factory, and declarative base."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings

#: JSON column type: native JSONB on Postgres, plain JSON elsewhere (SQLite tests/CI).
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def build_engine(url: str) -> Engine:
    """Create an engine with settings appropriate for the URL's dialect."""
    if url.startswith("sqlite"):
        # In-memory SQLite needs a single shared connection across threads.
        in_memory = ":memory:" in url or url.rstrip("/") == "sqlite:"
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool if in_memory else None,
        )
    return create_engine(
        url,
        pool_pre_ping=True,  # survive Supabase/pooler idle disconnects
        pool_size=5,
        max_overflow=5,
        pool_recycle=1800,
    )


engine = build_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context-managed session for non-request code (Celery tasks, scripts).

    Rolls back on any exception and always closes the session.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
