# Handoff to the next VERA engineer

> Branch: `feat/training-and-release`. Codex did not push or create deployment resources.
> Read `PROGRESS.md`, `DECISIONS.md` (newest entries win), PRD §23, `README.md`, and
> `CODEX_PROMPT.md` before continuing.

## 1. Important ownership boundary

Claude is running labeling and `train_all.py` in its own session and owns the GPU, `data/`, and
`reports/`. Do not run any labeling/training script, `train_all.py`, or a command that stops Python
processes. Do not change active label checkpoints, model files, or report outputs. Do not edit
`training/vera_training/{finetune,signals,fusion,calibration,evaluation,export}.py` or
`training/scripts/train_all.py` without asking the user first. Coordinate with Claude for live status;
the last label-status snapshot is stale and must not be reused as current status.

## 2. What is implemented and checked

- Backend submission is transactional through the `jobs` outbox; a broker outage leaves durable
  work for the dispatcher. Concurrent first submissions for one ASIN now recover from a unique-key
  race without losing the review. Product rankings/details are paginated and covered by API tests.
- Frontend analyzer, rankings, product details, methodology, responsive layout, and smoke tests are
  implemented. The About page explicitly distinguishes Claude reference agreement from human
  validation.
- New agreement reports write `reference_agreement`. The compatibility reader accepts the legacy
  `human_agreement` name only when metadata unambiguously identifies a non-human annotator and
  `human_validated` is false. The live report was not rewritten.
- Verification: full pytest 54 passed; frontend lint/typecheck/build passed; Playwright 8/8 passed
  for desktop and mobile.
- Ruff and Black pass on the current workspace. Mypy reports two typing errors in
  `training/vera_training/labeling.py`. Get user approval before editing the protected training
  modules listed above; coordinate before changing any code Claude may have imported.
- `git diff --check` flagged trailing whitespace inside the exact labeling system-prompt string.
  The training lint config preserves that prompt verbatim; do not normalize it without coordinating
  with Claude because changing it can change the prompt sent to labelers.
- Formatter-only, uncommitted workspace diffs are present in `training/scripts/agreement_preview.py`,
  `training/scripts/label_status.py`, `training/scripts/run_labeling.py`, `training/scripts/smoke_finetune.py`,
  `training/scripts/train_all.py`, and `training/vera_training/export.py`. They were not included in
  Codex's commits; preserve them until their owner/user confirms they are safe to include.

## 3. Modeling and evaluation status

G1 was generated before this handoff and its live artifact was left untouched. Its reference
annotations are Claude-generated, not human; `human_validated` must remain false. Do not present the
legacy `human_agreement` field as human evidence. Regenerate a corrected report only after Claude
confirms the relevant label inputs are frozen and the user lifts the no-report-access boundary.

G2/G3/G4 and complete-artifact worker readiness were not verified in this Codex session. The user
has explicitly reserved training and reports for Claude, so the next engineer must wait for release
before reading those outputs or launching any pipeline step. Once authorized, check the relevant
`reports/*.json` artifacts and the model loader; report every model metric only from a report file.

## 4. Remaining steps, in order

1. Keep clear of Claude's active labeling/training work and ask for its live status when needed.
2. After the user explicitly authorizes access, confirm data/report artifacts are stable; verify
   G2/G3/G4 and the 8-artifact loader check from on-disk evidence. Do not lower any gate.
3. With complete artifacts available and without competing with an active GPU run, verify the
   local migration/API/worker flow and Docker image. Do not submit external or production reviews.
4. Get explicit user approval for a deployment target before creating resources. The FP32 worker
   needs at least 2 GiB as a starting allocation and a peak-RSS check; the 512 MB Render free tier is
   not a production target. The current `render.yaml` is not a verified production deployment.
5. Refresh `PROGRESS.md` and this file after the next authorized verification. Never add metrics
   without their source report.

`.env`, `data/`, `reports/`, and model artifacts remain uncommitted. Do not push or open a PR unless
the user asks.
