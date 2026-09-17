# Deployment

## Current free deployment (2026-09-17)

| Part | Service | Address |
|---|---|---|
| API + worker + Redis | Hugging Face **Gradio Space on ZeroGPU hardware** (free) | `https://prathvi9607-vera-api.hf.space` (Space `prathvi9607/vera-api`) |
| Model artifacts (round 3) | Hugging Face private model repo | `prathvi9607/vera-models` |
| Database | Supabase free, session pooler (`sslmode=require`) | project `fjwiqiuhwkdscbpskyha` |
| Frontend | Vercel Hobby, root directory `frontend/` | set `API_URL` to the Space origin |

Why ZeroGPU: Docker Spaces and CPU-basic Gradio Spaces now require PRO (the Hub API returns
402 "hosting Gradio and Docker Spaces on free cpu-basic requires a PRO subscription"), while
Gradio on ZeroGPU is free. ZeroGPU stops apps that never report startup; `deploy/hf-zerogpu/app.py`
serves the existing FastAPI app with uvicorn and calls `spaces.zero.startup()` itself. It defines one
unused `@spaces.GPU` placeholder (required for the report). Inference stays on CPU (onnxruntime), so
no GPU quota is consumed. The container limit observed was ~104 GB RAM.

Redeploy the Space: copy `deploy/hf-zerogpu/{app.py,README.md,packages.txt,requirements.txt}` plus
`backend/app`, `backend/migrations`, `backend/alembic.ini` into a folder and upload it to the Space
(`HfApi.upload_folder(..., repo_type="space", delete_patterns=["backend/**"])`). Space secrets:
`DATABASE_URL`, `HF_MODEL_REPO`, `HF_TOKEN` (read), `SECRET_KEY`, `CORS_ORIGINS`.
`deploy/hf-zerogpu/requirements.txt` leaves the web stack unpinned for gradio 5.49.1
(fastapi 0.141, pydantic 2.11, huggingface_hub 0.36); the backend suite passes with those versions.
Verified: `/health` healthy with all 9 artifacts, `/ready` ready, reviews complete in 4-6 s.

Risks: ZeroGPU is intended for GPU apps and its policy may change; the Space sleeps when idle
(first request after wake reloads models); Space storage is ephemeral (reviews live in Supabase).

## Original Docker-based plan (requires Hugging Face PRO)

This is a deployment package, not evidence of a running production service. Obtain the user's
approval before creating resources, uploading artifacts, or pushing a Space. Do not execute these
steps on the shared machine while Claude owns training. Model acceptance remains separate from
API readiness; see [model card](model_card.md) and [operations](operations.md).

## Production path

1. **Supabase:** create an approved project and copy its **session pooler** PostgreSQL connection
   string from the Connect panel (port 5432, not transaction-pooler port 6543). Use
   `postgresql://postgres.PROJECT:PASSWORD@POOLER_HOST:5432/postgres?sslmode=require` as
   `DATABASE_URL`; percent-encode reserved password characters. Store it as a secret, not in Git.
   Configure backups/retention appropriate to the review data and test restoration before launch.
2. **Hugging Face model repository:** after the owner accepts the reports and artifact set, upload
   the complete compatible release to an approved private model repository. The current upload
   helper makes separate file commits: stop consumers during publication, do not serve a partially
   updated release. Use a new release repository for isolation when approved. Give the runtime a
   read-only token; keep upload credentials separate. Record the accepted Hub revision.
3. **Docker Space:** follow the [Space package guide](../deploy/huggingface-space/README.md).
   Stage only the documented source files. Set `DATABASE_URL`, `HF_TOKEN`, `HF_MODEL_REPO`,
   `CORS_ORIGINS` (exact frontend origins), and `SECRET_KEY` in Space settings. Run non-root UID 1000,
   expose 7860, and use a single API process and solo worker. The package starts Redis on loopback,
   applies migrations, then starts worker/API. A child exit terminates the container for restart.
   No model artifacts or `.env` belong in the build context. Hardware availability, pricing, and
   sleep policy must be reconfirmed before deployment; do not treat a free Space as an uptime SLA.
4. **Vercel:** import `frontend/`, set server-only `API_URL=https://YOUR-SPACE.hf.space` and
   `SITE_URL=https://YOUR-FRONTEND-DOMAIN`, install from the lockfile, then build. `API_URL` is an
   origin, not an `/api` URL. The frontend proxies API traffic and `/api/ready` server-side;
   never expose database, Hugging Face, or provider keys through `NEXT_PUBLIC_*`. Redeploy when
   build-time origin settings change. Configure the Space's CORS list for approved origins only.
5. **Verification:** check `/health` for process liveness and `/ready` for database availability.
   `/ready` is **not** a model, Redis, worker, or quality-gate check. Only after artifacts are
   accepted, submit one approved non-sensitive fixture, wait for `done`, then verify review and
   product outputs. Test backend failure, 429 recovery, mobile navigation, and review retention.
6. **Monitoring:** after approval, configure UptimeRobot against backend `/health` for liveness.
   Add a separate `/ready` alert for database failures. Monitor worker exits, pending job age,
   request error counts, memory, and disk through host tooling. A monitor does not guarantee that
   a free service stays awake or that inference is ready.

## Redis and persistence

The Space package deliberately overrides Celery URLs to its local Redis. This avoids remote
Celery polling charges described in `DECISIONS.md`. Redis binds only to `127.0.0.1`; port 6379
is never exposed. Queues/results/cache are ephemeral across Space restarts. Durable review jobs
live in PostgreSQL; the existing outbox recovers eligible jobs when the worker returns. Verify
recovery on a staging deployment; ephemeral Redis is not a backup.

Upstash provides independent managed Redis and TLS (`rediss://`), but Celery polling and result
traffic count toward its quotas. To adopt it, explicitly change the package's local-Redis policy
after reviewing cost, connection limits, and failure recovery. Do not silently set a remote URL
and expect this entrypoint to honor it.

SQLite is suitable only for an expendable single-instance demo. Space-local filesystem changes
can disappear on rebuild/restart; use Supabase for persistent public reviews. The old Render
free-tier blueprint is a non-production placeholder for an undersized worker; its `/ready`
health check does not make that hardware suitable.

## Request boundary and proxies

Review submission defaults to 10 accepted attempts per client per 60 seconds, with a 64 KiB
request-body cap. `REVIEW_RATE_LIMIT`, `REVIEW_RATE_WINDOW_SECONDS`,
`RATE_LIMIT_MAX_CLIENTS`, and `MAX_REQUEST_BODY_BYTES` configure these bounds. Malformed
submissions also consume attempts. Capacity is bounded and fails closed for new clients when
full. Buckets are process-local, reset on restart, and multiply across replicas: use an edge or
shared limiter before scaling. This is abuse mitigation, not authentication or a DDoS defense.

`TRUSTED_PROXY_CIDRS` defaults empty: the connection peer determines the bucket and untrusted
`X-Forwarded-For` is ignored. Behind Vercel and a Space proxy, clients may share a bucket until
the operator verifies the entire forwarded chain and explicitly trusts the immediate and
intermediate proxy CIDRs. Never trust `0.0.0.0/0`, `::/0`, or arbitrary client-supplied headers.
The Space disables uvicorn's implicit proxy-header rewriting so that this policy has one owner.
Do not claim distinct end-user limits until proxy behavior has been verified in staging.

JSON API request logs contain a sanitized request ID, route template, method, status, and duration,
not query strings or review text. `X-Request-ID` is a correlation hint, not an authenticated identity.
Error responses include security headers and expose request IDs/Retry-After to allowed origins.
TLS terminates at the host; production API responses include HSTS. Avoid personal data in reviews.
Public review reads remain unauthenticated; CORS and robots directives are not access control.

## Key rotation and release rollback

Rotate one credential at a time: issue least-privilege replacement, update the host secret,
restart/redeploy only the approved consumer, verify health and an authorized smoke test, then
revoke the old credential. Database credentials need a planned reconnect; labeling keys belong
to Claude during the live round. Never paste credentials into logs, screenshots, or commands.

Keep the previous image/source revision and a complete compatible model release. Roll back both
together if their contracts changed. Check migration compatibility first; do not automatically
downgrade a database containing new data. Record recovery decisions in the operations log.

Provider references: [HF Docker Spaces](https://huggingface.co/docs/hub/spaces-sdks-docker),
[Supabase connections](https://supabase.com/docs/guides/database/connecting-to-postgres),
[Vercel environment variables](https://vercel.com/docs/environment-variables).
