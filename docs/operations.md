# Operations runbook

**Training freeze:** all commands below are reference instructions, not actions performed by Codex.
Until the user says **"training released"**, Claude alone owns GPU, labeling, training, data,
reports, and lazily imported ML code. Never start duplicate runs, edit those modules, or stop
Python processes. The active owner's newest `HANDOFF.md` and `DECISIONS.md` override older commands.

## Labeling and training (owner only, after coordination)

From `C:\Workspace\VERA` using the Python 3.12 venv:

```powershell
# Read-only status, but still reserved for the owner during the freeze.
.\.venv\Scripts\python.exe training\scripts\label_status.py
```

For a stopped labeling run, first confirm that its checkpoint is not owned by a live process.
Copy its **exact** command from the active owner's handoff, preserving provider, model, run ID,
dataset slice, and output/checkpoint arguments, and append `--until-done` if absent. Use a separate
background terminal per run. Do not guess missing arguments or overwrite a checkpoint. If the
handoff no longer contains restart commands, ask Claude for them before restarting. The historical
`primary-a`, `qwen-a`, and `consistency` names are not proof those runs are currently active.

At the planned label milestones (1,000, 2,000, and 4,000), obtain the owner's release of resources,
validate the label inputs and run names, then use the orchestrator rather than disconnected stages:

```powershell
# Example only: confirm run IDs against the current handoff first.
.\.venv\Scripts\python.exe training\scripts\train_all.py --label-runs primary-a,qwen-a --allow-non-human-reference --force
```

`--force` regenerates outputs; preserve accepted prior artifacts/reports first through the owner's
release procedure. Do not run it concurrently with another round. The flow is labels → crossfit →
final models → fusion → calibration → evaluation → report. Production features must flow through
`extract_signals` and `build_feature_vector`, never a separate training-only feature formula.

## Gate interpretation

Read the actual gate fields, annotator metadata, split IDs, and artifact provenance in files;
do not infer a pass from script exit or an old progress note.

| Gate | What it establishes | Current evidence placeholder |
| --- | --- | --- |
| G1 | Reference/cross-model labeling agreement; not human validation | TBD — reports/agreement_report.json |
| G2 | Export acceptance, including whether quantization is safe | TBD — reports/experience_export.json |
| G3 | End-to-end CPU latency acceptance | TBD — reports/evaluation_report.json |
| G4 | Baseline comparison, significance, win rate, and interval coverage | TBD — reports/evaluation_report.json |

The agreement file historically lives under `data/labels/`; the report path above is a publication
placeholder, not a claim that a report exists. Have the owner publish the authoritative agreement
evidence under `reports/` before quoting any metric. Reference annotations are **Claude-generated,
not human**. Preserve `human_validated=false`; an explicit non-human-reference option acknowledges
the limitation rather than converting surrogate labels into human evidence. Do not deploy quantized
DeBERTa if its export gate fails. If a gate fails, retain the safe prior release and ask the owner
to investigate; do not weaken thresholds to create a passing report.

## Publishing accepted artifacts

After user approval of the destination resource and the owner's approval of a complete artifact
set, the helper is `vera_training.hub.upload_artifacts(model_dir, repo_id, token, names=None,
private=True)`. Supply the token through environment/configuration; never print it. Omitting
`names` validates the required set, but upload happens file-by-file, **not atomically**. Publish
to an isolated approved release repository or stop readers until the upload is complete, then
record its revision and restart the deployment. Verify the exact manifest expected by the
existing loader. Do not run this helper in the live training session from Codex.

## Groq/Gemini key rotation

Request permission from the labeling owner before touching its environment. Issue a replacement
at the provider, update `GROQ_API_KEY` or its numbered `_2..N` entry (similarly `GEMINI_API_KEY[_N]`),
then let the owner restart/resume only the affected run from its checkpoint. Confirm successful
provider responses before revoking the old key. Shared provider/project rate limits still apply;
additional keys do not authorize quota evasion. `.env.example` contains placeholders only.

## API incident triage

- `/health` failing: check Space lifecycle, entrypoint logs, and whether a child exited. Restart
  through the host only with owner approval; never kill local Python processes to fix a remote Space.
- `/ready` returning 503: check database service, pooler URL, TLS, and credentials. It is a DB-only
  check; a ready response does not prove the inference worker is available.
- 429: honor `Retry-After`. Check verified proxy configuration for shared buckets; do not bypass
  throttling with fabricated forwarded headers. Keep the user's input intact.
- Queued review not completing: inspect worker logs/outbox age and accepted model availability.
  A broker wake-up failure does not mean the persisted review should be submitted again.
- 500: correlate `X-Request-ID` with JSON request logs. Avoid collecting review text or secrets
  in an incident ticket. New API exception logs expose the exception type, not raw details.

## Demo import (write-only during this session)

After deployment acceptance, use approved non-sensitive CSV/JSONL fixtures with `text`,
`star_rating`, optional `product_title`, `product_asin`, `helpful_votes`, `verified_purchase`:

```powershell
.\.venv\Scripts\python.exe backend\scripts\seed_demo.py demo.csv --limit 20 --dry-run
.\.venv\Scripts\python.exe backend\scripts\seed_demo.py demo.csv --limit 20 --api-url https://YOUR-SPACE.hf.space
```

Dry-run validates without networking. The importer honors 429 backoff and polls sequentially,
reporting done/failed/unconfirmed and successful end-to-end latency percentiles. An unconfirmed
submission may already exist: investigate before rerunning the input, which has no deduplication
key. CLI timing is an operational diagnostic, not model evaluation evidence. Published metrics
must be sourced from approved files under `reports/`.
