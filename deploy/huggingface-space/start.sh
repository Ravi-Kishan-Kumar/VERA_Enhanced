#!/bin/sh
# One container owns Redis, migrations, API, and a single model worker.
set -eu
cd /app/backend
: "${DATABASE_URL:?Set DATABASE_URL in Space secrets}"
: "${HF_MODEL_REPO:?Set HF_MODEL_REPO in Space secrets}"
export REDIS_URL=redis://127.0.0.1:6379/0
export CELERY_BROKER_URL="$REDIS_URL"
export CELERY_RESULT_BACKEND=""
REDIS_PID=""
MIGRATION_PID=""
WORKER_PID=""
API_PID=""

cleanup() {
    trap '' INT TERM
    for pid in $API_PID $WORKER_PID $MIGRATION_PID $REDIS_PID; do
        kill -TERM "$pid" 2>/dev/null || true
    done
    attempts=0
    while [ "$attempts" -lt 10 ]; do
        alive=0
        for pid in $API_PID $WORKER_PID $MIGRATION_PID $REDIS_PID; do
            if kill -0 "$pid" 2>/dev/null; then alive=1; fi
        done
        [ "$alive" -eq 0 ] && break
        sleep 1
        attempts=$((attempts + 1))
    done
    for pid in $API_PID $WORKER_PID $MIGRATION_PID $REDIS_PID; do
        kill -KILL "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    done
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

# The database outbox recovers unfinished jobs after ephemeral Redis is lost.
redis-server --bind 127.0.0.1 --protected-mode yes --port 6379 \
    --dir /home/vera/redis --save '' --appendonly no &
REDIS_PID=$!
attempts=0
until redis-cli -h 127.0.0.1 ping >/dev/null 2>&1; do
    kill -0 "$REDIS_PID" 2>/dev/null || exit 1
    attempts=$((attempts + 1))
    [ "$attempts" -lt 30 ] || exit 1
    sleep 1
done

alembic upgrade head &
MIGRATION_PID=$!
wait "$MIGRATION_PID"
MIGRATION_PID=""
celery -A app.worker.celery_app worker --pool=solo --concurrency=1 --loglevel=info &
WORKER_PID=$!
# Trust forwarded client addresses only when the deployment's proxy is known.
uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-7860}" \
    --no-access-log --no-proxy-headers &
API_PID=$!

while kill -0 "$REDIS_PID" 2>/dev/null \
    && kill -0 "$WORKER_PID" 2>/dev/null \
    && kill -0 "$API_PID" 2>/dev/null; do
    sleep 2
done
echo 'A required VERA child exited; stopping the container.' >&2
exit 1
