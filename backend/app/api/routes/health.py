"""Liveness and diagnostic health endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.ml.models.loader import artifact_status

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, Any]:
    """Return 200 for liveness, with explicit dependency diagnostics.

    The API itself does not load ML artifacts: workers own inference and fail
    closed on missing artifacts. Keeping liveness independent means uptime
    monitors can report a useful degraded state during a model rollout.
    """
    database_ok = True
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        database_ok = False

    models = artifact_status(settings.MODEL_DIR)
    ready = database_ok and all(models.values())
    return {
        "status": "healthy" if ready else "degraded",
        "database": database_ok,
        "model_artifacts": models,
        "environment": settings.ENVIRONMENT,
    }
