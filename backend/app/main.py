"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.logging import configure_json_logging
from app.api.middleware import RequestGuard
from app.api.routes import health, products, reviews
from app.config import settings


def create_app() -> FastAPI:
    """Construct the HTTP API without loading worker-owned ML models."""
    app = FastAPI(title="VERA API", version="1.0.0")
    configure_json_logging()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
        expose_headers=["X-Total-Count", "X-Request-ID", "Retry-After"],
    )
    app.add_middleware(RequestGuard, settings=settings)
    app.include_router(health.router)
    app.include_router(reviews.router)
    app.include_router(products.router)
    return app


app = create_app()
