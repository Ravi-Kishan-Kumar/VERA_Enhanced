"""Structured API logging with request correlation and bounded, safe access fields."""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.config import dictConfig

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    """Serialize log records without exception bodies, query strings, or request payloads."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_context.get(),
        }
        for field in ("method", "route", "status_code", "duration_ms", "exception_type"):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info and record.exc_info[0]:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=True, default=str)


def configure_json_logging() -> None:
    """Configure the API's console logs; access logging is owned by the middleware."""
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": JsonFormatter}},
            "handlers": {
                "console": {"class": "logging.StreamHandler", "formatter": "json"},
                "null": {"class": "logging.NullHandler"},
            },
            "root": {"level": "INFO", "handlers": ["console"]},
            "loggers": {
                "uvicorn": {"handlers": ["console"], "propagate": False},
                "uvicorn.access": {"handlers": ["null"], "propagate": False},
            },
        }
    )
