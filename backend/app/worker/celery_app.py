"""Celery application (PRD §14.4), tuned for the Upstash free tier.

UPSTASH BUDGET: the free tier allows 10,000 Redis commands/day. Celery's default
0.1 s broker polling would burn ~864K/day, so ``polling_interval`` is 2.0 s.
Even that is ~43K polls/day for ONE worker — above the free quota. Run a single
worker, and expect to need a paid Upstash plan (or local Redis) for sustained
use. Results are ignored (the DB stores outcomes), saving result-backend writes.

Worker start::

    cd backend && celery -A app.worker.celery_app worker --loglevel=info

Startup behaviour:
* ``worker_init`` loads the ML pipeline and exits the process if any artifact is
  missing (hard-fail policy, DECISIONS.md) — before consuming any message.
* ``worker_ready`` starts the outbox dispatcher thread (:mod:`app.worker.outbox`).
"""

from __future__ import annotations

import logging
from typing import Any

from celery import Celery
from celery.signals import worker_init, worker_ready

from app.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery("vera", broker=settings.broker_url, include=["app.worker.tasks"])
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_ignore_result=True,
    broker_transport_options={"visibility_timeout": 3600, "polling_interval": 2.0},
    broker_connection_timeout=3,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Serialize inference so this worker does not duplicate the loaded FP32
    # models. Deployment memory must be sized and verified separately; the
    # free-tier 512 MB target is below the documented production requirement.
    worker_pool="solo",
    worker_concurrency=1,
)


@worker_init.connect
def load_models_or_exit(**_: Any) -> None:
    """Fail fast: a worker without valid artifacts must not consume jobs."""
    from app.worker.tasks import get_pipeline

    try:
        get_pipeline()
    except Exception as exc:
        logger.critical("VERA model initialisation failed: %s", exc)
        # SystemExit (a BaseException) escapes Celery's signal error handling.
        raise SystemExit(1) from exc


@worker_ready.connect
def start_outbox(**_: Any) -> None:
    """Run the outbox dispatcher alongside the worker (no extra process needed)."""
    from app.worker.outbox import start_background_dispatcher

    start_background_dispatcher()
    logger.info("Outbox dispatcher thread started")
