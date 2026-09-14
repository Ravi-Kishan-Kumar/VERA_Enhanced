# VERA Progress Tracker

## Overall status

Code, tests, frontend, and documentation are implemented on `feat/training-and-release`.
Model training and labeling remain owned by Claude's active session. G2–G4, full-artifact
runtime checks, and deployment are not verified by this Codex session.

## Completed in this work

- [x] Backend API, transactional outbox worker, migrations, product ranking/detail routes, and
  regression coverage for concurrent first submissions.
- [x] Frontend analyzer, ranking/detail/methodology pages, responsive behavior, and smoke tests.
- [x] Agreement reports now use `reference_agreement`; legacy values are accepted only when
  metadata explicitly identifies a non-human reference and `human_validated` is false.
- [x] Documentation clarifies that Claude's annotations are not human validation and that a
  512 MB Render service is not a viable FP32 worker target.
- [x] Full pytest: 54 passed. Frontend lint, typecheck, build, and Playwright smoke: passed.

## Validation remaining

- [ ] Resolve Ruff/Black formatting findings in training-side files after coordinating with
  Claude; do not edit `training/vera_training/export.py` or `training/scripts/train_all.py`
  without user approval.
- [ ] Resolve the two mypy typing errors in `training/vera_training/labeling.py` only after
  confirming with Claude that changing the active labeling module is safe.
- [ ] After Claude releases ownership and the user authorizes it, verify trained-model gates
  G2/G3/G4 using the corresponding files under `reports/` and run the full-artifact loader check.
- [ ] Verify the local Docker/API/worker flow when complete model artifacts are available.
- [ ] Select and approve a deployment target before creating any external resources.

## Active-work boundary

Claude owns the labeling/training processes, GPU, `data/`, and `reports/`. Do not run labeling or
training scripts, stop Python processes, or inspect/modify live labels, model artifacts, or reports
until the user explicitly lifts this boundary. The last label-status snapshot is stale; ask Claude
for live status instead of relying on the previous handoff.

**Last updated:** 2026-09-14 | **Owner:** Codex
