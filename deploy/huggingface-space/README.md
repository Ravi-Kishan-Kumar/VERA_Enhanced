---
title: VERA Review Analyzer API
emoji: 🎧
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
---

# VERA Docker Space

Deployment package only. Do not build locally during the training freeze. Deployment and uploads
require user approval. The target is a CPU Docker Space with enough memory for both FP32 models;
verify the available hardware and peak worker RSS before launch.

1. After approval, create a Hugging Face Space using the Docker SDK. Use a private model repository
   for the validated artifacts. Verify G2–G4 before exposing review submission to users.
2. Prepare a separate Space checkout containing this README as root `README.md`, this Dockerfile as
   root `Dockerfile`, this `.dockerignore` as root `.dockerignore`, the complete `backend/` directory, and this `start.sh` at
   `deploy/huggingface-space/start.sh`. Include no `.env`, local database, data, reports, or model files.
   The Dockerfile always builds with that checkout's root as its context.
3. In Space Settings, set secrets: `DATABASE_URL`, `HF_TOKEN` (read access to the model repository),
   `HF_MODEL_REPO`, `CORS_ORIGINS` (your frontend origin), and a random `SECRET_KEY`.
   Add `TRUSTED_PROXY_CIDRS` only after confirming the proxy network that reaches this app; never
   trust arbitrary forwarded headers. Until configured, clients behind one proxy share a rate bucket.
4. Push the prepared checkout only after approval. The container runs as UID 1000, starts loopback
   Redis, applies migrations, and starts one Celery worker and the API on port 7860. The existing
   model loader downloads missing files from `HF_MODEL_REPO` at worker startup.
5. Verify `GET /health` returns 200 and inspect its diagnostics. `GET /ready` returns 200 only when
   the database is reachable (503 otherwise). Neither endpoint proves the worker finished loading;
   verify a controlled end-to-end submission after its startup logs confirm model readiness.

Use Supabase's session-pooler PostgreSQL URL with `sslmode=require` for durable reviews and the job
outbox. SQLite (`sqlite:////home/vera/vera.db`) is only a disposable demonstration: the default Space
filesystem is ephemeral, so a restart/rebuild can lose the database. In-container Redis is ephemeral
by design; the persistent PostgreSQL outbox redispatches unfinished work. Do not expose Redis publicly.

The supervisor exits nonzero when any child dies and forwards shutdown to its own children.
Allow for artifact-download cold starts. Read `docs/deployment.md` in the VERA source repository
before launch (it is not part of the minimal Space checkout).

Reference: [Hugging Face Docker Spaces](https://huggingface.co/docs/hub/spaces-sdks-docker).
