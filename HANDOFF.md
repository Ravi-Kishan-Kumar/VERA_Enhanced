# Handoff — VERA

> Written by **Claude**, 2026-09-14 13:50, after training round 1. **Training released**: no GPU job is
> running and Codex may now read `reports/` and `data/models/` and verify gates. Labeling processes
> (`primary-a`, `qwen-a`) are still running in Claude's session — do not stop them or edit
> `data/labels/run_*.json`. Branch `feat/training-and-release`; nothing pushed.
> Read `PROGRESS.md`, `DECISIONS.md`, `docs/codex_notes.md`, PRD §23.

## 1. Round 1 results (1,059 consensus-labeled reviews, 878 products) — snapshot `reports/round_1059/`
| Metric | Value | Source |
|---|---|---|
| G1 label reliability | passed; self κ 0.979, reference κ 0.950 (Claude, **not human**), gpt-oss vs qwen κ 0.947 | `agreement_report.json` |
| Agent 2 out-of-fold MAE | **0.360** (stars-only regression 0.465, stars-as-prediction 0.495) | `experience_oof.json` |
| G2 final model | val MAE 0.355 < 0.50; FP32 ONNX parity 2.9e-6; INT8 rejected; max_length 384 | `experience_export.json` |
| Fusion hold-out test MAE | **0.315** (stars 0.501, experience-only 0.358) | `fusion_holdout.json` |
| 15-fold product-grouped CV | VERA **0.307 ± 0.015** vs stars-only 0.465 ± 0.022; win 15/15; Wilcoxon p = 3.1e-5 | `cv_comparison.json` |
| Conformal coverage (test n=214) | 95%→97.2%, 90%→**93.5%**, 80%→82.7% (normalized method) | `calibration.json` |
| G3 latency (CPU, 10 reviews) | max 6.7 s, mean 1.5 s | `evaluation_report.json` |
| G4 | **passed** (all checks) | `evaluation_report.json` |
| Ablation | +experience ✓, +domain ✓, +consistency ✗ (win 27%, no gain), +quality ✓, +absa ✓ | `ablation.csv` |
| Aspect detection F1 | 7/10 ≥ 0.70; **build_quality 0.54, connectivity 0.66, comfort 0.72 borderline** | `evaluation_report.json` |

All 8 artifacts present: `cd backend; ..\.venv\Scripts\python.exe -m app.ml.models.loader --check`.

## 2. Known gaps (report honestly)
- PRD §22.1 "aspect detection F1 ≥ 0.70 for all 10 aspects" is **not met** (build_quality, connectivity).
  Likely cause: keyword recall in `backend/app/ml/constants.py::ASPECT_KEYWORDS`. Fix using the TRAIN
  split's label mentions (never the test split), then re-run fusion→report (feature contract unchanged).
- Consistency features give no measurable gain (negative result; keep it in the report).
- Reference annotations are Claude's, not human → `human_validated=false`.
- Worker RAM ≈ 1.5 GB+ (two FP32 DeBERTa graphs) → 512 MB hosts cannot run it.

## 3. Code state notes
- Ruff, Black, mypy clean; `pytest -q` 54 passed at 11:25 (Claude fixed the two labeling.py mypy errors).
- The formatter-only diffs in `training/scripts/*`, `training/vera_training/export.py`, `train_all.py`
  are Claude's and safe to commit.
- The labeling system prompt's trailing whitespace is intentional (PRD §7.2 verbatim) — do not normalize.

## 4. Next steps
1. **Codex (released):** local end-to-end with real scoring (migrate, Redis, API, worker, frontend;
   submit ≥ 10 test-split reviews with ASINs; measure latency + worker peak RSS); build the Space image;
   README results section from `reports/round_1059/` (every number linked); commit (not `data/`/`reports/`).
2. **Claude:** labeling to 2,000 → round 2 retrain; then rows 2000–3999 (`primary-b`/`qwen-b`) → round 3.
   Before a retrain starts, Claude will re-announce the boundary (GPU, `training/**`, `backend/app/ml/**`).
3. **User:** `HF_TOKEN` + `HF_MODEL_REPO` in `.env` (artifact upload), Supabase `DATABASE_URL`, GitHub repo,
   deployment target choice, optional human annotation of `data/labels/claude_annotation_sheet.csv`.

## Status 2026-09-14 evening (round 2, paused by user)

- Local round-2 crossfit (384 tokens) was stopped during fold 5; the Colab model (512 tokens, AdamW, T4) is used instead.
  - Colab OOF MAE 0.319 on 2,022 consensus labels (R2 0.884, within +-0.5 80.5%, within +-1 96.5%); stars-as-prediction MAE 0.488.
  - On the same 1,059 reviews: round-1 local 0.359 vs Colab round-2 0.312. Final-model validation MAE 0.315.
- Installed: `colab_results/final_model_colab` -> `data/processed/final_model/model`; `experience_oof_colab.csv` -> `data/labels/experience_oof.csv` (round-1 OOF backed up as `experience_oof_round1_local.csv`).
- Done (`reports/round2_colab.log`):
  - `final`: FP32 ONNX exported, max abs diff 1.9e-6, deployed fp32. INT8 rejected (max diff 1.49).
  - `aspects`: test macro F1 0.801 vs 0.786 keywords; all aspects >= 0.70 (build_quality 0.705, connectivity 0.741). 8/10 aspects chose C=8 (grid edge), so widen the C grid.
- NOT done: fusion was stopped during signal extraction (CPU, ~30 min, no progress log, no partial cache).
  - Next: add a per-review signal cache/progress log, then run `train_all.py --full-gpu --force --stages fusion,calibrate,evaluate,report,diagnostics`. Do NOT rerun `final` without `--full-gpu` (384 vs 512 max_length).
- Labeling stopped. primary-a 1981, qwen-a 1997, primary-b 149, qwen-b 210 (union rows 0-1999 = 2000). Restart the `--until-done` daemons for rows 2000-3999.

## Round 2 COMPLETE 2026-09-15 (Colab experience model, 2,022 labels) — snapshot `reports/round2_colab/`

- Fusion stage now memoizes Agent 3 (ABSA) outputs in `data/processed/absa_cache.joblib` (keyed by clean text + mentions + model file); reruns are near-instant, stopped runs resume.
- Tuned fusion: depth 2, min_child_weight 15, reg_lambda 10, 314 trees; CV val 0.290, gap 0.042.
- Test split (415, unseen products): VERA MAE 0.284, RMSE 0.414, R2 0.907, within +-0.5 85.1%, +-1 97.6%. Stars 0.508; experience-only 0.328. Train 0.253 / calibration 0.273 (gap 0.031).
- Nested CV (15 folds, re-tuned per fold): 0.277 +- 0.009 vs stars 0.462 +- 0.024, 15/15 wins, p=3e-5, mean train-held-out gap 0.020.
- Ablation: experience gives nearly all gain (0.464 -> 0.278); domain and quality not individually significant; full model 0.277 (p=4e-4 vs previous step).
- Conformal coverage on test: 80% -> 80.5%, 90% -> 88.4% (width 1.00), 95% -> 92.8% (mild under-coverage; revisit with round-3 calibration set).
- Aspect detector: test macro F1 0.801, all aspects >= 0.70. Gates G2, G3, G4 pass.
- Learning curve (validation MAE 0.279 -> 0.272 at 25% -> 100% of train): flat-to-improving, train MAE rises toward validation (less memorization). More labels help mainly through the experience model.
- Labeling restarted 07:10; primary-b/qwen-b ~1,000/2,000 at 08:00. Gemini keys (9) added to `.env`, but Gemini multi-key pooling is not implemented.
- Next: finish rows 2000-3999, round 3 on Colab with all labels (cap 4 epochs), widen aspect C grid, re-check 95% coverage, update `frontend/src/content/benchmarks.ts` round 2 figures (Codex, frontend-only).

## Round 3 status 2026-09-15 12:30 (paused by user)

- Labels: `data/labels/labels_v1.jsonl` = 4,000 reviews / 2,705 products (3,990 two-model consensus). Round-2 labels backed up as `labels_v1_round2.jsonl`.
- Colab round-3 DeBERTa (512 tokens, AdamW): OOF MAE 0.285 (R2 0.904, within +-0.5 84.0%), folds 0.306/0.290/0.292/0.323/0.304, final val 0.283. On the same 2,022 reviews: round-2 0.318 vs round-3 0.289.
- Installed: round-3 model at `data/processed/final_model/model` (round 2 kept as `model_round2_colab`); `data/labels/experience_oof.csv` = round-3 OOF (round 2 kept as `experience_oof_round2_colab.csv`). Colab outputs in `colab_results/round3/`.
- Pipeline was stopped during `final` export. `data/models/` still holds the round-2 ONNX and fusion artifacts (consistent set). `experience_tokenizer.json` was rewritten but is identical in content (same base tokenizer, max_length 512).
- Resume: `train_all.py --force --full-gpu --stages final,aspects,fusion,calibrate,evaluate,report,diagnostics` (log `reports/round3.log`), then snapshot to `reports/round3/`.

## Round 3 COMPLETE 2026-09-15 15:46 (4,000 labels, Colab DeBERTa) — snapshot `reports/round3/`, log `reports/round3.log`

- Experience model: OOF MAE 0.285 (R2 0.904); final val 0.283; FP32 ONNX parity max diff 5e-6 (INT8 rejected).
- Aspect detector: test macro F1 0.803 vs 0.776 keywords; all aspects >= 0.70 (build_quality 0.712, connectivity 0.724). All 10 chose C=8 (grid edge): widen C grid.
- Fusion tuned: depth 2, min_child_weight 5, reg_lambda 10, 257 trees; CV val 0.261 +- 0.004, gap 0.017.
- Splits (fusion ensemble): train 0.247 (R2 0.938) / calibration 0.274 (R2 0.906) / test 0.252 (RMSE 0.357, R2 0.924, within +-0.5 88.2%, +-1 98.5%). Stars on test 0.496; experience-only 0.279.
- Nested CV (15 folds, re-tuned): 0.261 +- 0.007 vs stars 0.460 +- 0.015, 15/15, p=3e-5, mean gap 0.012.
- Ablation: experience 0.458 -> 0.264; domain/quality not individually significant; full 0.262 (15/15 vs previous step).
- Conformal on test (n=802): 80% -> 81.3%, 90% -> 91.0% (width 1.06), 95% -> 96.5%. Round-2 95% under-coverage resolved.
- Learning curve (validation MAE 0.287 -> 0.274 at 25% -> 100% of train; train 0.232 -> 0.247): converging, still improving with data.
- Next: update `frontend/src/content/benchmarks.ts` (rounds 2 and 3) from these reports; widen aspect C grid; test a trimmed feature set; HF upload + deploy.

## Deployment 2026-09-17

- Backend live on a free Hugging Face Gradio Space (ZeroGPU hardware): `https://prathvi9607-vera-api.hf.space`; models in private `prathvi9607/vera-models`; Supabase session pooler DB (migrations 001-002 applied). See `docs/deployment.md` and `deploy/hf-zerogpu/`.
- Fixed a wake-up race exposed by the remote DB: the API and outbox updated `jobs.last_dispatched_at` after publishing, holding the row lock while the worker (`skip_locked`) received the message, so jobs waited ~60 s for the outbox. Now the mark is committed before publishing and un-marked on publish failure (tests added). Reviews complete in 4-6 s.
- Pending: Vercel frontend (user), then set Space `CORS_ORIGINS` to the Vercel origin; UptimeRobot on `/ready`; rotate the Supabase password and HF tokens that were pasted in chat.
