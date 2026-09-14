# Codex round-two notes — 2026-09-14

## Ownership and scope

Read `CODEX_TASKS_ROUND2.md` completely and performed its six tasks in order. Worked on
`feat/training-and-release` without branch switching, stash/reset/rebase/clean, or push.
Claude's live labeling/training processes were not started, stopped, or signaled. No edits were
made to training, ML modules, notebooks, live data/reports/artifacts, `.env`, `HANDOFF.md`, or
`DECISIONS.md`. Existing training diffs and untracked input/data/report files remain outside this
commit. This document replaces a HANDOFF update while that file is owned by Claude.

## Changes

1. `deploy/huggingface-space/`: source-only Docker package, UID 1000, port 7860, local Redis,
   migrations, solo worker, bounded child shutdown and failure propagation. Separate Space
   checkout instructions include `.dockerignore`; no image was built or run locally.
2. API: sanitized request IDs on responses/logs; JSON request logs use route templates and avoid
   bodies/query strings. Rate limiting is bounded, process-local, and proxy-aware only with
   explicit trust configuration. Body cap applies before handlers persist side effects. Security
   headers cover rejection/error responses. `/ready` checks only the DB; `/health` remains liveness.
3. Demo importer: CSV/JSONL validation before submission, explicit dry-run, 429 backoff, safe
   polling, and done/failed/unconfirmed summaries. Ambiguous POST failures are not resubmitted.
   Parsing, mock HTTP requests, dry-run isolation, and timeout behavior are unit-tested.
4. CI: browser smoke and Space image-build jobs; pip-audit/npm audit produce artifacts for
   manual triage, without automatic fixes. Dependabot is weekly. Existing dependency pins remain.
5. Docs: deployment path, operating boundaries/runbook, model-card skeleton, environment examples.
   `human_validated=false`; no claimed model metrics or invented gate outcomes.
6. Frontend: stronger typography/contrast, aligned brand mark, finite CSS transitions, focus and
   touch targets, reduced motion, clearer ranking copy, and no readiness-success layout shift.
   The existing-project redesign skill guided targeted improvements with the current Next/React,
   local fonts, and CSS stack; no new UI dependencies or decorative image downloads were added.
   429 cooldown honors Retry-After without auto-submitting; DB-unavailable checks preserve drafts.
   Static metadata, branded social image/favicon, robots, sitemap, and canonical-origin validation
   do not need a trained backend. Removed redundant decoding of Next's decoded ASIN parameter.

## Verification

Passed locally (source/test checks, not model evaluation):

```powershell
.\.venv\Scripts\python.exe -m ruff check backend/app/api backend/app/main.py backend/app/config.py backend/scripts/seed_demo.py backend/tests/test_hardening.py backend/tests/test_seed_demo.py backend/tests/conftest.py
.\.venv\Scripts\python.exe -m black --check backend/app/api backend/app/main.py backend/app/config.py backend/scripts/seed_demo.py backend/tests/test_hardening.py backend/tests/test_seed_demo.py backend/tests/conftest.py
.\.venv\Scripts\python.exe -m mypy backend/app/api backend/app/main.py backend/app/config.py backend/scripts/seed_demo.py --follow-imports=silent
.\.venv\Scripts\python.exe -m pytest backend/tests -k "not pipeline" --ignore=backend/tests/test_pipeline.py -q
# From frontend/:
npm run test:e2e -- --workers=1
```

The final `npm run lint`, `npm run typecheck`, and `npm run build` sequence passed. The production
build ran once, with prerender concurrency limited to one worker and Rust worker threads limited
to two. No trained backend was required during prerendering.

Also passed: YAML parsing of CI/Dependabot/Render and `sh -n` syntax validation of the Space
entrypoint using Git's shell (not execution). Reviewed desktop/mobile screenshots and static
accessibility on analyzer, rankings, detail, and methodology. Browser tests cover narrow layout,
keyboard skip navigation, reduced motion, metadata, successful results, pagination failure, rate
limits, and readiness recovery. All browser `/api/**` calls are intercepted, including defaults
for missing fixtures; none reach the shared worker. Initial new recovery tests used an ambiguous
alert selector matching Next's route announcer; scoped it to main content and reran successfully.
No Lighthouse audit, remote dependency scan, Docker runtime test, or trained-model check was run.

## Exact next steps / unresolved release work

1. Claude continues the active runs. Do not restart, relabel, retrain, regenerate reports, or alter
   frozen paths until the user explicitly says **"training released"**.
2. Claude provides accepted gate evidence and a complete compatible artifact manifest. Check
   `reports/experience_export.json` and `reports/evaluation_report.json`; publish authoritative
   agreement evidence under reports before quoting G1. Preserve non-human reference provenance.
3. Once a PR/approved CI run exists, inspect Playwright, Space build, and dependency scan outputs.
   The scanner jobs are report-only: green CI alone does not prove no vulnerabilities. Triage
   findings manually and document any required pin updates. The pre-existing full-project mypy
   issues in frozen labeling code remain for its owner, not this patch.
4. Obtain user approval before creating Supabase/HF/Vercel/monitor resources or uploading/pushing.
   Verify proxy CIDRs in the actual deployment; until then peer-based buckets may group users.
   Production scaling requires a shared/edge limiter; this process-local limiter is for one instance.
5. After artifact acceptance and on an approved target, build/run the Space, verify migrations,
   cold start, worker crash/restart, queue recovery, memory headroom, health/readiness, and a
   controlled non-sensitive review through completion. `/ready` alone is not model readiness.
6. Configure `API_URL` and `SITE_URL` for the frontend, confirm canonical/share URLs, and test
   deployed 429/503/proxy behavior. Define public-demo retention/deletion and contact procedures.
7. Only after that, run the demo importer first with `--dry-run`, then on approved fixtures.
   Investigate any unconfirmed submission before rerunning; the public API has no idempotency key.

No claim is made that the remaining model or deployment gates have passed.
