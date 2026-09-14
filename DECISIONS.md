# Architecture Decisions

Immutable log of WHY things are built the way they are. Newest entries at the bottom.
Each entry that deviates from PRD v1.0 is mirrored in PRD.md §23.

---

## 2026-09-13: Production inference fails closed when artifacts are absent
**Decision:** Workers load only the artifacts in `app.ml.models.loader.REQUIRED_ARTIFACTS`
and exit at startup if any is missing or empty. No heuristic fallback. (User decision.)
**Why:** A fallback would silently change the calibrated score contract and invalidate the
displayed uncertainty. The API stays up and `/health` reports artifact status.

## 2026-09-13: Portable JSON fusion artifacts
**Decision:** The XGBoost bootstrap ensemble is saved as versioned JSON
(`fusion_ensemble.json`: feature names, imputation means, member models), not a pickle.
**Why:** Pickled XGBoost objects break across versions and unpickling executes code. The
loader also rejects artifacts whose `feature_names` differ from `app.ml.features`.

## 2026-09-13: Population-level EB aggregation under one lock
**Decision:** Every aggregation recomputes all products (prior + ranks) atomically.
**Why:** The EB prior and ranks are population quantities; per-ASIN recomputes with
different priors publish inconsistent scores. The PRD's per-ASIN lock allowed that.

## 2026-09-13: Conservative variance for one-review products
**Decision:** A single review cannot estimate its own variance; it uses the pooled
within-product variance (never below the 0.05 floor).
**Why:** Prevents an isolated 5.0 from outranking a well-supported 4.6.

## 2026-09-13: Empirical Bayes formulas corrected
**Decision:** τ² = between-product variance by method of moments
(`Var(product means) − mean(sampling variance)`), Kish effective sample size for weighted
means, uncertainty = posterior sd `sqrt(B·τ²)`.
**Why:** PRD v1.0 set τ² to the variance of individual review scores (total variance) and
reported an ad-hoc `sqrt(σ²/n + B²τ²)`.

## 2026-09-13: Python 3.12 only
**Decision:** Pinned `.venv` built with `uv` on CPython 3.12.
**Why:** numpy 1.26.4 / onnxruntime 1.19.0 have no wheels for 3.13+ (the machine's default is 3.14).

## 2026-09-13: Production requirements fixed
**Decision:** MAPIE moved to `requirements-dev.txt`; added `pydantic-settings` (typed config) and
an explicit `huggingface_hub` pin (model download). Test-only `onnx`/`scipy` live in
`backend/requirements-test.txt`.
**Why:** PRD §10.3 forbids MAPIE in production yet §4.4 installed it there.

## 2026-09-13: Tokenizer loads local `tokenizer.json`, dynamic padding
**Decision:** `LightTokenizer` reads the `tokenizer.json` shipped with each ONNX model, pads to
the longest sequence (not 512), reads the pad id from the vocabulary, and truncates only the
review (never the aspect) for pairs.
**Why:** `microsoft/deberta-v3-base` has no `tokenizer.json`; hub downloads at inference are
fragile; padding to 512 made ABSA ~10× slower on a shared CPU.

## 2026-09-13: ONNX inputs follow the graph
**Decision:** `build_feed` sends exactly the inputs the ONNX graph declares.
**Why:** DeBERTa-v3 (`type_vocab_size=0`) exports without `token_type_ids`; PRD code passed it
and onnxruntime rejects undeclared inputs.

## 2026-09-13: Agent fixes
- Agent 1: `has_url` was computed after URLs were stripped (always False); `<br />` removal glued
  words; keyword substrings matched inside words ("anc" in "balance"). Now raw-text URL check,
  break tags → spaces, word-boundary regexes.
- Agent 2: PRD inferred on `"{title} [SEP] {text}"` but trained on text only (train/serve skew).
  Both use `format_experience_input(clean_text)`.
- Agent 3: one batched ONNX call for all detected aspects; stable softmax (PRD overflowed);
  label map read from exported `absa_config.json`; "cheap" only under `value`.
- Agent 5: PRD formula referenced `quality_score` inside its own definition and double-counted
  the verified flag; "2-year half-life" used `exp(-t/730)` (e-folding). Now a weighted average
  with a true half-life; future dates clip to age 0; missing metadata imputed from training
  means stored in the fusion artifact (never hardcoded).

## 2026-09-13: Normalized split-conformal intervals, exact finite-sample quantile
**Decision:** Support `absolute` (|y−ŷ|) and `normalized` (|y−ŷ|/(σ_ensemble+floor)) scores; notebook 06
keeps the narrower valid one. Quantile = ⌈(n+1)(1−α)⌉-th smallest score.
**Why:** With a constant q̂ the "confidence" value never varied. PRD's
`np.quantile(s, (1−α)(1+1/n))` interpolates and raises when the level exceeds 1.

## 2026-09-14: Transactional outbox for background jobs (Codex design, finished by Claude)
**Decision:** The API writes the review and a `jobs` row in one transaction, then sends a
best-effort Celery wake-up. The DB owns attempts/back-off/completion; an outbox dispatcher
thread (started with the worker) re-sends unfinished jobs. Reviews never fail with 503 when
Redis is briefly down.
**Why:** Postgres and Redis cannot commit atomically; PRD's `commit` then `.delay()` could lose
jobs, and its retry path left reviews marked `failed` while still retrying.

## 2026-09-14: Products FK kept, product shell created on submit
**Decision:** `reviews.product_asin` keeps its FK; `POST /api/reviews` creates a product shell first.
**Why:** PRD schema made every first review of a new ASIN fail its insert.

## 2026-09-14: Out-of-fold experience features (cross-fitting)
**Decision:** Agent 2 features for fusion/calibration/evaluation come from 5 product-grouped
cross-fitted DeBERTa models; the production model is trained on all labels.
**Why:** PRD trained fusion on in-sample predictions of a model fitted to the same labels, so
fusion would over-trust an overfit signal and CV numbers would be inflated.

## 2026-09-14: Metadata dropout mirrors API inputs
**Decision:** Training features hide metadata with p=0.5; calibration/test features hide all of it.
**Why:** API reviews have no timestamp and often no votes/verified flag (PRD weakness #15).

## 2026-09-14: Domain model excludes ALL labelled products; trained in the pinned `.venv`
**Decision:** Leakage guard drops every labelled ASIN (not just test ASINs); pickle stores
sklearn/numpy versions and is validated on load; notebooks 05–08 run locally, only 04 on Colab.
**Why:** Labels are re-split many times in CV; Colab's numpy 2 pickles cannot load under numpy 1.26.

## 2026-09-14: Evaluation folds
**Decision:** 5 folds × 3 repeats = 15 product-grouped folds (custom implementation).
**Why:** `sklearn.model_selection.RepeatedGroupKFold` (PRD §13.1) does not exist.

## 2026-09-14: Gemini SDK and model
**Decision:** `google-genai` client, model from `GEMINI_MODEL` (default `gemini-2.5-flash`).
**Why:** `google-generativeai` is deprecated and Gemini 1.5 Flash has been retired.

## 2026-09-14: Frontend on Next.js 16 / React 19 (Codex choice), TypeScript 6, ESLint 9
**Decision:** Keep Codex's Next 16 stack; pin TypeScript 6.0.3 and ESLint 9.39.5; hand-written
components instead of shadcn/d3.
**Why:** Next 14 is out of support by 2026. typescript-eslint does not support TS 7, and
eslint-plugin-react crashes on ESLint 10. The confidence bar is plain SVG (PRD §16.2 asks for
a custom SVG), so d3 was unnecessary weight.

## 2026-09-14: Render free tier runs API + worker in one service
**Decision:** `backend/scripts/start_web_with_worker.sh` starts Celery (solo pool) and uvicorn
together; migrations run at start. A paid dedicated worker block is provided in `render.yaml`.
**Why:** Render background workers are not free, and PRD's `fromDatabase: vera-db` contradicted
the Supabase design. Note: Celery's 2 s broker polling alone exceeds Upstash's 10K commands/day
(~43K/day); expect a paid Upstash plan or local Redis for sustained use.

## 2026-09-14: Real corpus filter = title keyword AND headphone category
**Decision:** A product qualifies if its title matches the earbud keywords AND its Amazon category
path contains "Headphones & Earbuds" (or, with no category, its title has no accessory words).
**Why:** Measured on the first 400K metadata rows: keywords alone admitted FPV goggles, webcams and
radios; the category alone admitted cases, ear pads and mis-filed items. Result: 1,983,070 reviews
(>= 20 words) across 46,095 products — far more than PRD's 144K estimate (the 2023 dump is larger).

## 2026-09-14: Groq as labeler; quota is per organization
**Decision:** Primary labels from `openai/gpt-oss-120b` (Groq), cross-model check with
`qwen/qwen3.8-27b`, self-consistency with a second seed. `GroqPool` paces from Groq's rate-limit
headers and stops cleanly when the daily quota ends; runs resume from checkpoints.
**Why:** No Gemini key was provided. Measured limits: 1,000 requests/day, 8K tokens/min and ~1K
output tokens/min PER MODEL PER ORGANIZATION — the two supplied keys belong to one organization, so
throughput is ~2.5 labels/min and ~1,000 labels/day per model. Keys from other Groq accounts add capacity.

## 2026-09-14: No human annotator available — Claude is the (declared) reference annotator
**Decision:** The user could not annotate. Claude annotated 200 blinded reviews (text + product
title only; no stars, no model labels, scores fixed before any model label was viewed). Reports carry
`human_validated: false` and `reference_annotator: "claude-opus-5 (LLM, not human)"`.
**Why:** Fabricating "human" labels would be dishonest. An independent model family as reference is
the best available substitute; it must never be described as human validation.

## 2026-09-14: DeBERTa-v3 cannot be INT8-quantized without breaking it — deploy FP32 ONNX
**Decision:** Export tries INT8 but deploys it only if >= 99% argmax agreement AND mean probability
drift <= 0.02 on >= 32 samples (ABSA uses 100 text x aspect pairs); otherwise the exact FP32 graph.
**Why:** Measured on the ABSA model vs FP32 (100 pairs): default dynamic INT8 17% agreement;
MatMul-only 21%; weight-only MatMul 21%; per-channel + reduce-range 76%; 4-bit block-32 weight-only
92% (509 MB). FP32 ONNX matches PyTorch to 5e-6. A 10-sample gate once showed "100%" by luck.
**Consequence:** Each DeBERTa-v3-base graph is ~740 MB (the 128K-token embedding alone is ~394 MB).
PRD's "~90 MB INT8" and the 512 MB Render budget are not achievable at acceptable accuracy.
Deploy the worker on >= 2 GB RAM (e.g. a free Hugging Face Docker Space with 16 GB, or a paid Render
instance). Future option: prune the embedding to the vocabulary actually seen in reviews.

## 2026-09-14: Local GPU fine-tuning profile (RTX 2050, 4 GB)
**Decision:** `FinetuneConfig.small_gpu()`: 384 tokens, Adafactor, gradient checkpointing, bf16,
batch 4 x 2. The exported `tokenizer.json` stores the training `max_length` so serving truncates
identically. Notebook 04 trains the full profile (512 tokens, AdamW) on Colab for comparison via
`training/scripts/compare_experience_models.py` (same deterministic folds).
**Why:** AdamW moments + FP32 master weights do not fit 4 GB; fp16 overflows on DeBERTa-v3 while
the RTX 2050 (Ampere) supports bf16.

## 2026-09-14: Two-model consensus labels (gpt-oss-120b + qwen3.8-27b)
**Decision:** Both models label the same pool rows (`run_primary-a`, `run_qwen-a`). The training
target is the mean of the available model scores (quarter-step when they differ by 0.5); aspect
labels come from gpt-oss-120b when present. `label_models` records 1 or 2 per review.
**Why:** Early agreement was very high (gpt-oss vs Claude reference kappa 0.946, qwen vs reference
0.969, gpt-oss vs qwen 0.957), so the labelers are interchangeable in quality; averaging two model
families reduces labeler noise, and each model has its own Groq quota, doubling throughput.
The user supplied keys from 5 distinct Groq organizations (7 keys; 3 share one organization).

## 2026-09-14: Agreement schema calls Claude comparisons reference agreement
**Decision:** New reports use `reference_agreement`; `human_validated` is true only when the annotator
is explicitly identified as `human`. A compatibility reader interprets the legacy `human_agreement`
field only when the report explicitly records a non-human annotator and `human_validated: false`.
**Why:** A field name must not imply human validation when its reference annotations came from an LLM.
Do not rewrite active reports or checkpoints while Claude owns `data/` and `reports/`.

## 2026-09-14: Fusion capacity tuned by product-grouped CV (fixes overfitting)
**Decision:** `vera_training.fusion.tune_fusion_params` selects XGBoost depth / min_child_weight /
L2 by 5-fold product-grouped CV with early stopping on TRAINING rows only, using the one-standard-error
rule (among configurations within 1 SE of the best validation MAE, prefer the smallest train/validation gap).
The evaluation stage re-tunes inside every outer fold (nested CV) so model selection never sees its test fold.
**Why:** Round-1 fusion (fixed depth 6, 300 trees) had train MAE 0.12 vs test 0.315 — memorisation. On the
same split, tuned capacity (depth 3, min_child_weight 15, 143 trees) gave train 0.247 / test 0.317: equal
generalisation, gap cut from 0.195 to 0.07, less over-confident member spread.

## 2026-09-14: Learned aspect detector replaces keyword-only mention detection
**Decision:** New artifact `aspect_detector.joblib` (required): per-aspect logistic regression on word
1–2-gram TF-IDF + keyword indicators, C and threshold tuned by product-grouped out-of-fold F1 on non-test rows;
test rows scored by a detector trained on non-test rows only. Fusion features use these out-of-fold / holdout
decisions. Keyword lists were also fixed (durability terms for build quality; removed "pair"/"range" from
connectivity).
**Why:** Keyword detection missed PRD §22.1 (F1 ≥ 0.70 for all aspects): build quality 0.54 (recall 0.35),
connectivity 0.66 (precision 0.52). Exploratory round-1 test F1 with the learned detector: build quality 0.69,
connectivity 0.77, comfort 0.82, macro 0.805 (keywords 0.766). More labels (round 2) are expected to lift the
remaining borderline aspects; results are reported per aspect, including any still below 0.70.

## 2026-09-14: Diagnostics stage (over/underfitting evidence every round)
**Decision:** `train_all.py --stages diagnostics` writes `reports/model_quality.json` (MAE, RMSE, R²,
within ±0.5/±1 star for train / calibration / test vs baselines) and a learning curve (train vs calibration MAE
at 25/50/75/100% of training products) in `reports/diagnostics.json`.
