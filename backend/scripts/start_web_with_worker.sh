#!/usr/bin/env sh
# Single-service API + Celery worker start command (requires a suitable runtime).
#
# Render background workers are not available on the free plan, so this can run
# the worker (solo pool, which also starts the outbox dispatcher thread) next to
# uvicorn only on a runtime with sufficient memory. The production requirement
# is at least 2 GiB for the FP32 models plus runtime; Render's 512 MB free plan
# is not suitable. On an appropriately sized paid plan, prefer a separate worker.
#
# If either process exits, the script exits non-zero so Render restarts the service.
set -eu
cd "$(dirname "$0")/.."

alembic upgrade head

celery -A app.worker.celery_app worker --loglevel=info &
WORKER_PID=$!

uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers &
API_PID=$!

# Stop both children when Render sends SIGTERM.
trap 'kill "$WORKER_PID" "$API_PID" 2>/dev/null || true' INT TERM

# POSIX sh has no `wait -n`: poll until one child exits.
while kill -0 "$WORKER_PID" 2>/dev/null && kill -0 "$API_PID" 2>/dev/null; do
  sleep 5
done
echo "A VERA process exited; stopping the service." >&2
kill "$WORKER_PID" "$API_PID" 2>/dev/null || true
exit 1
