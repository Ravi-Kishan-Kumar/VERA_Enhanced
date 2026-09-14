"""Agent 6 training — TF-IDF → Ridge on the UNLABELED corpus (PRD §9 Agent 6).

LEAKAGE GUARD (PRD weakness #6): every product that appears in the labelled
set is excluded *before* the vocabulary and coefficients are fitted. The PRD
excluded only test ASINs; excluding all labelled ASINs is strictly safer
because the labelled set is re-split many times during cross-validation.

Run this in the production-pinned ``.venv`` (not Colab): the joblib pickle must
be created with the same numpy/scikit-learn versions the worker uses.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge

from vera_training.splits import assert_disjoint, holdout


def train_domain_model(
    unlabeled: pd.DataFrame,
    held_out_asins: Iterable[str],
    output_path: str | Path,
    *,
    max_features: int = 50_000,
    min_df: int = 5,
    alpha: float = 10.0,
    max_rows: int | None = None,
    seed: int = 42,
) -> dict[str, Any]:
    """Fit and save the domain model; return training diagnostics.

    Args:
        unlabeled: Columns ``parent_asin``, ``text`` (already cleaned), ``rating``.
        held_out_asins: ASINs that must never influence the model (all labelled ASINs).
        output_path: Destination ``domain_tfidf.joblib``.
        max_rows: Optional reproducible random subsample after the leakage guard.
            Bigram vocabulary counting on ~2M reviews needs >16 GB RAM.
    """
    held_out = {str(a) for a in held_out_asins}
    safe = unlabeled[~unlabeled["parent_asin"].astype(str).isin(held_out)]
    assert_disjoint(safe["parent_asin"].astype(str), held_out)
    n_excluded = len(unlabeled) - len(safe)
    if max_rows is not None and len(safe) > max_rows:
        safe = safe.sample(n=max_rows, random_state=seed)
    if len(safe) < min_df * 10:
        raise ValueError(f"Only {len(safe)} unlabeled rows remain after the leakage guard")
    # Product-grouped 5% validation split: an honest error estimate for the proxy task.
    safe, validation = holdout(safe.reset_index(drop=True), 0.05, seed)

    vectorizer = TfidfVectorizer(
        max_features=max_features,
        ngram_range=(1, 2),
        min_df=min_df,
        max_df=0.95,
        sublinear_tf=True,
        dtype=np.float32,
    )
    features = vectorizer.fit_transform(safe["text"].astype(str))
    target = safe["rating"].to_numpy(dtype=float)
    model = Ridge(alpha=alpha).fit(features, target)

    # `stop_words_` stores every pruned n-gram (often hundreds of MB) and is not
    # needed for transform(); dropping it keeps the artifact small.
    vectorizer.stop_words_ = None

    joblib.dump(
        {
            "vectorizer": vectorizer,
            "model": model,
            "sklearn_version": sklearn.__version__,
            "numpy_version": np.__version__,
            "n_train": len(safe),
            "n_excluded": n_excluded,
        },
        output_path,
        compress=3,
    )
    val_features = vectorizer.transform(validation["text"].astype(str))
    val_target = validation["rating"].to_numpy(dtype=float)
    val_pred = np.clip(model.predict(val_features), 1.0, 5.0)
    return {
        "n_train": len(safe),
        "n_validation": len(validation),
        "n_excluded_labelled_product_rows": n_excluded,
        "vocabulary_size": len(vectorizer.vocabulary_),
        "train_r2": float(model.score(features, target)),
        "validation_r2": float(model.score(val_features, val_target)),
        "validation_mae_vs_stars": float(np.abs(val_pred - val_target).mean()),
    }
