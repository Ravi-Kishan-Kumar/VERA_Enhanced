# Architecture Decisions

## 2026-09-13: Production inference fails closed when artifacts are absent

**Decision:** Workers load only the exported ONNX, tokenizer, domain, fusion, and
conformal artifacts listed in `app.ml.models.loader.REQUIRED_ARTIFACTS`; they do
not substitute a heuristic or a different model.

**Why:** A fallback would silently change the calibrated score contract and make
the displayed uncertainty invalid.

## 2026-09-13: Portable JSON fusion artifacts

**Decision:** Store the XGBoost bootstrap ensemble as versioned JSON rather than
a pickle.

**Why:** JSON avoids unsafe unpickling and is stable across worker deployments.

## 2026-09-13: Global lock for EB aggregation

**Decision:** Recompute all completed product aggregates under one short Redis
lock whenever a completed review is added.

**Why:** The EB prior and rankings are population-level quantities. A per-ASIN
lock alone permits interleaved calculations with different priors and inconsistent
ranks.

## 2026-09-13: Conservative variance for one-review products

**Decision:** A product with exactly one review uses at least `0.5` as its
within-product variance, rather than inheriting a potentially near-zero pooled
variance from unanimous multi-review products.

**Why:** A single observation cannot estimate its own variance. This preserves
the stated ranking goal: an isolated 5.0 does not outrank a well-supported 4.6
merely because existing multi-review products happen to be unanimous.
