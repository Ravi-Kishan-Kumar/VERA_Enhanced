# Codex task: finish VERA to production quality

You are a senior ML/backend engineer taking over the VERA project (Verified Experience & Review
Analyzer) in `C:\Workspace\VERA` (Windows, PowerShell, Python 3.12 venv at `.venv`). The code base is
largely complete and tested; the remaining work is labeling completion, model training, evaluation,
deployment, and release hygiene. Work autonomously, verify every step with real commands, and never
report something as done without evidence.

## 0. Read first (in this order) — do not skip
1. `HANDOFF.md` — exact current state, running jobs, commands.
2. `PROGRESS.md`
3. `DECISIONS.md` — especially entries dated 2026-09-14 (measured findings that override the PRD).
4. `PRD.md` §23 (v1.1 corrections table; it wins over older PRD sections), then §13, §20.1, §22.
5. `README.md`
Then run `git status` and `git log --oneline -5`.

## 1. Non-negotiable engineering rules
- **Honesty:** every metric in reports/README must come from an artifact on disk produced by the
  pipeline. Report negative results. The 200 reference annotations were produced by Claude (an LLM):
  keep `human_validated: false` everywhere and never call them human labels.
- **No leakage:** product-grouped splits only; Agent 2 features for fusion/calibration/eval must be
  out-of-fold (`crossfit_predictions`); domain model excludes all labeling-pool products.
- **No train/serve skew:** build features only through `app.ml.pipeline.extract_signals` and
  `app.ml.features.build_feature_vector`. The exported `experience_tokenizer.json` carries the training
  `max_length`; do not override it in production.
- **Production dependencies:** `backend/requirements.txt` must never contain torch, transformers, or mapie.
- **Model precision:** do not ship INT8/4-bit DeBERTa unless `training/vera_training/export.py`'s gate
  passes (it measured 17–92% agreement for all quantization variants; FP32 is expected).
- **Secrets:** never print, log, or commit `.env` or API keys. Tell the user to rotate the Groq keys
  (they were pasted in chat).
- **Quality bar on every change:** `ruff check backend training`, `black --check backend training`,
  `mypy backend/app training/vera_training`, `pytest -q` all green; frontend `npm run lint`,
  `npm run typecheck`, `npm run build` green. Add/adjust tests for any behavior you change.
  Docstrings on public functions; comments explain *why*, not *what*.
- **Commits:** create a branch `feat/training-and-release`. Commit in logical units with conventional
  messages (e.g. `feat(training): ...`, `fix(export): ...`, `docs: ...`). Do not commit `data/`,
  `dist/`, model artifacts, or `.env` (check `.gitignore` first). Do not push or open PRs unless the
  user asks.

## 2. Phase A — finish labeling (long-running; start immediately)
1. Check whether labeling processes are alive (`Get-Process python`) and run
   `training\scripts\label_status.py`. If not running, restart the three runs with the exact commands in
   `HANDOFF.md` §2 (they resume from checkpoints; use `--until-done`), each in its own background terminal.
2. G1 is already generated and passed (`data/labels/agreement_report.json`); only regenerate it if label inputs change, using the snippet in
   `HANDOFF.md` §3 (`reference_annotator="claude-opus-5 (LLM, not human)"`,
   `cross_model_path=data/labels/run_qwen-a.json`). If G1 fails, stop and report the numbers; do not
   lower thresholds.
3. After rows 0–1999 are labeled by both models, start `primary-b` / `qwen-b` for `--start 2000
   --count 2000`. Target: 4,000 consensus-labeled reviews.
4. If a run shows growing `errors`, inspect the checkpoint's `errors` map (error type names only), fix
   the cause, add a test, and resume.

## 3. Phase B — first full training (as soon as ≥ 1,000 reviews have labels)
1. `train_all.py --stages labels --allow-non-human-reference --label-runs primary-a,qwen-a,crossmodel-qwen`
   Verify `labels_v1.jsonl` row count, star balance, `label_models` distribution in the log.
2. `train_all.py --stages crossfit,final` on the local RTX 2050 (`FinetuneConfig.small_gpu()`).
   Monitor for OOM/NaN losses. Check gate G2 in `reports/experience_export.json`:
   validation MAE < 0.50 and FP32 parity < 0.01. If MAE ≥ 0.50, investigate (label distribution,
   learning rate, epochs) before proceeding; document what you tried in DECISIONS.md.
3. `train_all.py --stages fusion,calibrate,evaluate,report`.
4. Sanity-check `reports/fusion_holdout.json`: VERA MAE must beat stars-as-prediction and
   experience-only MAE on the test split; if not, analyse feature importances and the ablation table
   rather than tuning on the test split.
5. Verify G3/G4 in `reports/evaluation_report.json` (G3: latency < 15 s per review on CPU;
   G4: VERA < stars-only with Wilcoxon p < 0.05, win rate ≥ 85%, 90% interval coverage ≥ 88%).
6. Run `python -m app.ml.models.loader --check` from `backend/` — all 8 artifacts must be present.
7. Retrain (`--force`, clearing `data/processed/crossfit/` and `data/processed/final_model/`) when
   labels reach 2,000 and again at 4,000. Keep a copy of each round's `reports/` in
   `reports/round_<n_labels>/` so results are comparable.

## 4. Phase C — Colab comparison model (optional, if the user uploads results)
`training/scripts/make_colab_bundle.py` → user runs `notebooks/04_finetune_experience.ipynb` on Colab
(512 tokens, AdamW) → put `experience_oof_colab.csv` in `data/labels/` → run
`training/scripts/compare_experience_models.py --a data/labels/experience_oof.csv --a-name local-384
--b data/labels/experience_oof_colab.csv --b-name colab-512`. Deploy whichever model has the lower
out-of-fold MAE (paired test), and record the decision.

## 5. Phase D — end-to-end verification locally
1. `cd backend; ..\.venv\Scripts\python.exe -m alembic upgrade head` (SQLite from `.env` or Docker Postgres).
2. Start Redis (`docker compose up -d redis`, or Upstash URL in `.env`), the API (uvicorn), the worker
   (`celery -A app.worker.celery_app worker --loglevel=info`), and the frontend (`npm run dev`).
3. Submit ≥ 10 real reviews from the test split with ASINs (at least 10 distinct products), confirm:
   status reaches `done` < 30 s, intervals contain the score, aspects render, `/products` ranks ≥ 10
   products, product detail pages load. Capture timings and peak worker RSS (PRD §22.2).
4. Build the Docker image (`docker build -f Dockerfile.backend -t vera-backend .`) and run `/health`.
   Fix anything that fails.
5. Add a minimal Playwright smoke test (`frontend/tests/smoke.spec.ts`: `/`, `/products`, `/about`
   render) or remove the unused `test` scripts from `package.json` — no dead scripts.

## 6. Phase E — deployment (confirm target with the user before creating accounts/resources)
- Worker + API need ≥ 2 GB RAM (two FP32 DeBERTa graphs ≈ 1.5 GB). Recommended free option: Hugging Face
  Docker Space (16 GB). Alternative: paid Render instance. Update `render.yaml`/docs accordingly and add
  a `Dockerfile.space` (or equivalent) that runs API + worker + outbox, downloading artifacts from
  `HF_MODEL_REPO` at startup.
- Upload artifacts with `vera_training.hub.upload_artifacts` (private repo) once the user provides
  `HF_TOKEN` and repo name.
- Database: Supabase session pooler URL; Redis: Upstash (note the Celery polling cost in DECISIONS.md)
  or Redis inside the Space.
- Frontend: Vercel with `API_URL` pointing at the backend.
- Configure UptimeRobot on `/health`. Verify PRD §22.2/§22.3 criteria against the live URLs.

## 7. Phase F — documentation and release hygiene
- Update `README.md` with real results: label counts, agreement table, OOF MAE, fusion hold-out MAE,
  CV comparison (mean ± std, win rate, p-value), coverage per alpha, ablation table, per-aspect F1,
  latency, memory — each linked to its `reports/*.json` source. Include the limitations (LLM-generated
  labels, non-human reference, English/earbud domain, FP32 memory footprint).
- Update `PRD.md` §23 with any new deviations and bump the version; add DECISIONS.md entries for every
  non-trivial choice (with the measured reason).
- Update `PROGRESS.md` and rewrite `HANDOFF.md` at the end of your session with exact next steps.
- Final check: full lint/type/test/build suite green; `git status` clean except ignored files.

## 8. Definition of done
All of PRD §22 is either met with evidence in `reports/` or explicitly documented as not met with the
reason (e.g. human-validated kappa cannot be claimed without human annotations). Deliver a short summary
to the user: what was trained, key metrics, what is deployed (URLs), what remains blocked on them.
