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
