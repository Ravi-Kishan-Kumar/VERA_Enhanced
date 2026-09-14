# VERA Progress Tracker

## Overall status

Round-two code and documentation are implemented on `feat/training-and-release`.
Claude still owns live labeling, training, GPU, data, and reports. Model gates, full-artifact
runtime checks, image execution, and deployment are not verified by this Codex session.

## Round two — 2026-09-14

- [x] HF Docker Space source package: non-root runtime, loopback Redis, migration/startup ordering,
  solo worker, child supervision, safe build-context exclusions, and deployment instructions.
- [x] API request IDs, JSON access logs, bounded per-client submission throttling, request-body
  limit, security headers, and database-only `/ready`, with regression tests.
- [x] CSV/JSONL demo importer with validation, dry-run, bounded backoff, polling, and mock-only tests.
  No live demo seeding was performed; tests use temporary fixtures and mocked HTTP.
- [x] CI jobs for browser smoke tests, Space image build (no push), report-only dependency scans,
  and weekly Dependabot updates. These remote jobs have not been executed by Codex.
- [x] Deployment/operations/model-card documentation and environment placeholders. Reference
  annotations remain Claude-generated and non-human; model metrics are evidence placeholders.
- [x] UI contrast/focus/touch improvements, finite page/result/navigation motion, reduced-motion
  support, metadata/share image/favicon, robots/sitemap, and input-preserving 429/503 recovery.
- [x] Scoped backend Ruff, Black, mypy, and non-pipeline pytest pass. Desktop/mobile Playwright
  smoke tests pass with mocked APIs and one worker. Static accessibility and screenshot review
  completed; no Lighthouse score or trained-model performance claim is made.
- [x] Final frontend lint, typecheck, and one production build pass with bounded worker concurrency.

See [Codex notes](docs/codex_notes.md) for exact verification scope and next steps.

## Previously completed (historical, not rerun during the freeze)

- [x] Backend API, transactional outbox worker, migrations, product ranking/detail routes, and
  regression coverage for concurrent first submissions.
- [x] Frontend analyzer, ranking/detail/methodology pages, responsive behavior, and smoke tests.
- [x] Agreement reports now use `reference_agreement`; legacy values are accepted only when
  metadata explicitly identifies a non-human reference and `human_validated` is false.
- [x] Documentation clarifies that Claude's annotations are not human validation and that a
  512 MB Render service is not a viable FP32 worker target.
- [x] Previous session reported full pytest and frontend checks passing; the full suite is not
  rerun during the live training freeze.

## Validation remaining

- [x] Ruff and Black pass on the round-two changed backend paths. Frozen paths were not formatted.
- [ ] Resolve the two mypy typing errors in `training/vera_training/labeling.py` only after
  confirming with Claude that changing the active labeling module is safe.
- [ ] `git diff --check` flags trailing whitespace inside the exact labeling system-prompt string;
  preserve it unless Claude approves a prompt change and its downstream effects are evaluated.
- [ ] After Claude releases ownership and the user authorizes it, verify trained-model gates
  G2/G3/G4 using the corresponding files under `reports/` and run the full-artifact loader check.
- [ ] Verify the local Docker/API/worker flow when complete model artifacts are available.
- [ ] Select and approve a deployment target before creating any external resources.

## Active-work boundary

Claude owns the labeling/training processes, GPU, `data/`, and `reports/`. Do not run labeling or
training scripts, stop Python processes, or inspect/modify live labels, model artifacts, or reports
until the user explicitly lifts this boundary. The last label-status snapshot is stale; ask Claude
for live status instead of relying on the previous handoff.

There are pre-existing, uncommitted workspace diffs in `training/scripts/agreement_preview.py`,
`training/scripts/label_status.py`, `training/scripts/run_labeling.py`, `training/scripts/smoke_finetune.py`,
`training/scripts/train_all.py`, and `training/vera_training/export.py`. They were left unstaged;
preserve them, especially the two protected pipeline files, until their owner/user confirms they
are safe to include.

**Last updated:** 2026-09-14 | **Owner:** Codex
