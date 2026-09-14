"""Liveness and diagnostic health endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.ml.models.loader import artifact_status

router = APIRouter(tags=["health"])


def database_ready() -> bool:
    """Check database reachability without loading models or publishing queue work."""
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@router.get("/ready")
def ready() -> JSONResponse:
    """Readiness is database reachability, not a guarantee of worker/model readiness."""
    available = database_ready()
    return JSONResponse(
        {"status": "ready" if available else "unavailable", "database": available},
        status_code=200 if available else 503,
        headers={} if available else {"Retry-After": "10"},
    )


@router.get("/health")
def health() -> dict[str, Any]:
    """Return 200 for liveness, with explicit dependency diagnostics.

    The API itself does not load ML artifacts: workers own inference and fail
    closed on missing artifacts. Keeping liveness independent means uptime
    monitors can report a useful degraded state during a model rollout.
    """
    database_ok = database_ready()
    try:
        models = artifact_status(settings.MODEL_DIR)
    except OSError:
        models = {"accessible": False}
    ready = database_ok and all(models.values())
    return {
        "status": "healthy" if ready else "degraded",
        "database": database_ok,
        "model_artifacts": models,
        "environment": settings.ENVIRONMENT,
    }
