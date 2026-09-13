"""Upstash-conscious Celery configuration (PRD §14.4)."""

from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery("vera", broker=settings.broker_url, backend=settings.result_backend)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    broker_transport_options={"visibility_timeout": 3600, "polling_interval": 2.0},
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)
