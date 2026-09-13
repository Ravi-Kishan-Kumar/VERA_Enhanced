"""Application settings loaded from environment variables / the repo-root `.env`.

Every setting is documented in `.env.example`. Settings are read once and
cached via :func:`get_settings`; import the module-level ``settings`` object for
convenience.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Repository root (``backend/app/config.py`` -> two parents up from ``app``).
REPO_ROOT = Path(__file__).resolve().parents[2]


def _normalize_database_url(url: str) -> str:
    """Force the psycopg2 driver for Postgres URLs.

    Supabase/Heroku-style ``postgres://`` URLs are rejected by SQLAlchemy 2.x,
    so both ``postgres://`` and bare ``postgresql://`` are rewritten to
    ``postgresql+psycopg2://``. Other schemes (e.g. ``sqlite://``) pass through.
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix) :]
    return url


def _normalize_redis_url(url: str) -> str:
    """Ensure TLS Redis URLs carry ``ssl_cert_reqs``.

    Celery refuses ``rediss://`` broker URLs without an explicit
    ``ssl_cert_reqs`` query parameter. Upstash presents a valid public
    certificate, so ``required`` (full verification) is the safe default.
    """
    if not url.startswith("rediss://"):
        return url
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query.setdefault("ssl_cert_reqs", "required")
    return urlunsplit(parts._replace(query=urlencode(query)))


class Settings(BaseSettings):
    """Typed runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # --- Database / queue ---------------------------------------------------
    DATABASE_URL: str = Field(..., description="SQLAlchemy URL (Supabase or local Postgres).")
    REDIS_URL: str = Field(..., description="Redis URL (Upstash rediss:// or local redis://).")
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    # --- App ------------------------------------------------------------------
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    SECRET_KEY: str = ""
    CORS_ORIGINS: str = "http://localhost:3000"

    # --- Models -----------------------------------------------------------------
    MODEL_DIR: Path = Path("data/models")
    HF_MODEL_REPO: str = ""
    HF_TOKEN: str = ""

    @field_validator("DATABASE_URL")
    @classmethod
    def _db_url(cls, value: str) -> str:
        return _normalize_database_url(value.strip())

    @field_validator("REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND")
    @classmethod
    def _redis_url(cls, value: str) -> str:
        return _normalize_redis_url(value.strip())

    @field_validator("MODEL_DIR")
    @classmethod
    def _model_dir(cls, value: Path) -> Path:
        # Relative paths are anchored at the repo root so the API (run from
        # `backend/`) and notebooks (run from the root) resolve the same folder.
        return value if value.is_absolute() else (REPO_ROOT / value).resolve()

    # --- Derived --------------------------------------------------------------
    @property
    def broker_url(self) -> str:
        """Celery broker; falls back to ``REDIS_URL``."""
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @property
    def result_backend(self) -> str:
        """Celery result backend; falls back to ``REDIS_URL``."""
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL

    @property
    def cors_origins(self) -> list[str]:
        """``CORS_ORIGINS`` split on commas, blanks removed."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()  # values come from env


settings = get_settings()
