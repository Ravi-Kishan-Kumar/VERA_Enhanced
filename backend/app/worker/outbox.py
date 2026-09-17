"""Outbox dispatcher: turns unfinished `jobs` rows into Celery wake-ups.

Runs as a daemon thread inside the worker (started on ``worker_ready`` in
:mod:`app.worker.celery_app`), so a free-tier deployment needs no extra process.
It can also run standalone::

    cd backend && python -m app.worker.outbox

A job is (re)sent when it is unfinished, due (``available_at <= now``), and was
never dispatched or was dispatched more than :data:`REDISPATCH_AFTER` ago — this
recovers messages lost to a Redis outage or a crashed worker. Importing this
module never loads ML models.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import or_

from app.database import SessionLocal
from app.models.job import Job

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS: Final = 5.0
REDISPATCH_AFTER: Final = timedelta(seconds=60)
RUN_JOB_TASK: Final = "vera.run_job"


def send_wakeup(job_id: str) -> None:
    """Publish one wake-up message. Raises if the broker is unreachable."""
    from app.worker.celery_app import celery_app  # lazy: avoid import cycle

    celery_app.send_task(RUN_JOB_TASK, args=[job_id], retry=False)


def dispatch_pending(limit: int = 100) -> int:
    """Send wake-ups for due jobs. Returns the number sent.

    Jobs are marked dispatched and committed BEFORE publishing, so no row lock is held when
    the worker receives the message (the worker skips locked rows). Jobs whose publish fails
    are un-marked so the next poll retries them.
    """
    now = datetime.now(UTC)
    with SessionLocal() as db:
        jobs = (
            db.query(Job)
            .filter(
                Job.finished_at.is_(None),
                Job.available_at <= now,
                or_(
                    Job.last_dispatched_at.is_(None),
                    Job.last_dispatched_at < now - REDISPATCH_AFTER,
                ),
            )
            .order_by(Job.available_at, Job.id)
            .with_for_update(skip_locked=True)
            .limit(limit)
            .all()
        )
        job_ids = [job.id for job in jobs]
        for job in jobs:
            job.last_dispatched_at = now
        db.commit()

    sent = 0
    failed: list[str] = []
    for job_id in job_ids:
        try:
            send_wakeup(job_id)
            sent += 1
        except Exception:
            failed.append(job_id)
    if failed:
        with SessionLocal() as db:
            db.query(Job).filter(Job.id.in_(failed), Job.last_dispatched_at == now).update(
                {Job.last_dispatched_at: None}, synchronize_session=False
            )
            db.commit()
        raise RuntimeError(f"Broker unavailable; {len(failed)} wake-up(s) not sent")
    return sent


def run_forever(stop: threading.Event | None = None) -> None:
    """Poll until ``stop`` is set. Errors are logged; the loop never dies."""
    stop = stop or threading.Event()
    while not stop.is_set():
        try:
            count = dispatch_pending()
            if count:
                logger.info("Outbox dispatched %d job(s)", count)
        except Exception:
            logger.exception("Outbox dispatch failed; will retry")
        stop.wait(POLL_INTERVAL_SECONDS)


def start_background_dispatcher() -> threading.Event:
    """Start :func:`run_forever` in a daemon thread; set the returned event to stop it."""
    stop = threading.Event()
    threading.Thread(target=run_forever, args=(stop,), name="vera-outbox", daemon=True).start()
    return stop


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with contextlib.suppress(KeyboardInterrupt):
        run_forever()
