"""Training for the learned aspect detector (Agent 3 mention detection).

Protocol (no test leakage, no in-sample features):

1. ``labels`` = the LLM ``mentioned`` flags (first listed labeler, i.e. gpt-oss-120b when present).
2. NON-TEST rows: 5-fold product-grouped cross-fitting gives out-of-fold probabilities;
   per aspect, ``C`` and the decision threshold maximise that out-of-fold F1.
3. TEST rows: scored by a detector trained on all non-test rows (a true holdout, like
   production). Test labels never influence any choice.
4. Fusion features use these out-of-fold / holdout decisions, never in-sample ones.
5. The production detector is refit on all labelled reviews with the chosen settings.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.model_selection import GroupKFold

from app.ml.agents.aspect_detector import AspectDetector, detector_features, keyword_matrix
from app.ml.constants import EARBUD_ASPECTS

C_GRID: tuple[float, ...] = (0.5, 2.0, 8.0)
THRESHOLD_GRID = np.round(np.linspace(0.10, 0.90, 81), 2)


def mention_labels(frame: pd.DataFrame) -> np.ndarray:
    """``(n, 10)`` boolean matrix of LLM ``mentioned`` flags."""
    return np.array(
        [[bool(aspects[a]["mentioned"]) for a in EARBUD_ASPECTS] for aspects in frame["aspects"]]
    )


def new_vectorizer() -> TfidfVectorizer:
    """Word 1–2-gram TF-IDF; vocabulary is refit inside every fold (no leakage)."""
    return TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=40_000, sublinear_tf=True)


def _logreg(c: float) -> LogisticRegression:
    return LogisticRegression(C=c, class_weight="balanced", max_iter=3000)


def best_threshold(y: np.ndarray, probabilities: np.ndarray) -> tuple[float, float]:
    """Threshold maximising F1 (ties → the threshold closest to 0.5); returns (threshold, F1)."""
    scores = np.array([f1_score(y, probabilities >= t, zero_division=0) for t in THRESHOLD_GRID])
    top = np.flatnonzero(scores >= scores.max() - 1e-12)
    choice = top[np.argmin(np.abs(THRESHOLD_GRID[top] - 0.5))]
    return float(THRESHOLD_GRID[choice]), float(scores[choice])


def crossfit_probabilities(
    texts: Sequence[str], labels: np.ndarray, groups: Sequence[str], n_folds: int = 5
) -> dict[float, np.ndarray]:
    """Out-of-fold probabilities ``(n, 10)`` for each C in :data:`C_GRID`."""
    texts = list(texts)
    group_array = np.asarray(list(groups))
    out = {c: np.zeros(labels.shape, dtype=float) for c in C_GRID}
    for train_idx, val_idx in GroupKFold(n_splits=n_folds).split(texts, labels, group_array):
        vectorizer = new_vectorizer().fit([texts[i] for i in train_idx])
        x_train = detector_features(vectorizer, [texts[i] for i in train_idx])
        x_val = detector_features(vectorizer, [texts[i] for i in val_idx])
        for j in range(len(EARBUD_ASPECTS)):
            y_train = labels[train_idx, j]
            for c in C_GRID:
                if y_train.all() or not y_train.any():  # degenerate fold: constant prediction
                    out[c][val_idx, j] = float(y_train.mean())
                    continue
                model = _logreg(c).fit(x_train, y_train)
                out[c][val_idx, j] = model.predict_proba(x_val)[:, 1]
    return out


def fit_aspect_detector(
    frame: pd.DataFrame,
    test_mask: np.ndarray,
    output_path: str | Path,
    n_folds: int = 5,
) -> dict[str, Any]:
    """Cross-fit, tune on non-test rows, evaluate on test rows, and save the production detector.

    Args:
        frame: Labelled reviews with ``text``, ``parent_asin``, ``aspects``, ``review_id``.
        test_mask: Boolean array marking the held-out TEST rows (never used for tuning).
        output_path: Destination ``aspect_detector.joblib``.

    Returns:
        Report dict with per-aspect settings and metrics, plus ``oof_mentions``: a
        ``review_id -> {aspect: bool}`` mapping of out-of-fold decisions for fusion.
    """
    texts = frame["text"].astype(str).tolist()
    labels = mention_labels(frame)
    test_mask = np.asarray(test_mask, dtype=bool)
    tune_idx, test_idx = np.flatnonzero(~test_mask), np.flatnonzero(test_mask)
    tune_texts = [texts[i] for i in tune_idx]
    keywords = keyword_matrix(texts).astype(bool)

    # (a) Out-of-fold probabilities among NON-TEST rows only (tuning never sees test labels).
    tune_probabilities = crossfit_probabilities(
        tune_texts, labels[tune_idx], frame["parent_asin"].iloc[tune_idx].tolist(), n_folds
    )
    # (b) Holdout detector on all non-test rows scores the test rows (mirrors production).
    holdout_vectorizer = new_vectorizer().fit(tune_texts)
    x_tune = detector_features(holdout_vectorizer, tune_texts)
    x_test = detector_features(holdout_vectorizer, [texts[i] for i in test_idx])

    chosen_c: dict[str, float] = {}
    thresholds: dict[str, float] = {}
    rows = []
    oof = np.zeros(labels.shape, dtype=float)
    for j, aspect in enumerate(EARBUD_ASPECTS):
        best: tuple[float, float, float] | None = None  # (f1, c, threshold)
        for c in C_GRID:
            threshold, score = best_threshold(labels[tune_idx, j], tune_probabilities[c][:, j])
            if best is None or score > best[0] + 1e-9:
                best = (score, c, threshold)
        assert best is not None
        tune_f1, c, threshold = best
        chosen_c[aspect], thresholds[aspect] = c, threshold
        oof[tune_idx, j] = tune_probabilities[c][:, j]
        if len(test_idx):
            holdout = _logreg(c).fit(x_tune, labels[tune_idx, j])
            oof[test_idx, j] = holdout.predict_proba(x_test)[:, 1]
        predicted = oof[:, j] >= threshold
        y_test = labels[test_mask, j]
        rows.append(
            {
                "aspect": aspect,
                "C": c,
                "threshold": threshold,
                "tuning_oof_f1": round(tune_f1, 4),
                "test_support": int(y_test.sum()),
                "test_f1": round(float(f1_score(y_test, predicted[test_mask], zero_division=0)), 4),
                "test_precision": round(
                    float(precision_score(y_test, predicted[test_mask], zero_division=0)), 4
                ),
                "test_recall": round(
                    float(recall_score(y_test, predicted[test_mask], zero_division=0)), 4
                ),
                "test_f1_keywords_only": round(
                    float(f1_score(y_test, keywords[test_mask, j], zero_division=0)), 4
                ),
            }
        )

    # Production detector: all labelled reviews, chosen C per aspect.
    vectorizer = new_vectorizer().fit(texts)
    features = detector_features(vectorizer, texts)
    models = {
        aspect: _logreg(chosen_c[aspect]).fit(features, labels[:, j])
        for j, aspect in enumerate(EARBUD_ASPECTS)
    }
    joblib.dump(
        {
            "vectorizer": vectorizer,
            "models": models,
            "thresholds": thresholds,
            "aspects": list(EARBUD_ASPECTS),
            "sklearn_version": sklearn.__version__,
            "n_train": len(frame),
        },
        output_path,
        compress=3,
    )
    AspectDetector(output_path)  # round-trip check of the saved artifact

    table = pd.DataFrame(rows)
    decisions = oof >= np.array([thresholds[a] for a in EARBUD_ASPECTS])
    return {
        "n_labelled": len(frame),
        "n_test": int(test_mask.sum()),
        "per_aspect": rows,
        "test_macro_f1": round(float(table.test_f1.mean()), 4),
        "test_macro_f1_keywords_only": round(float(table.test_f1_keywords_only.mean()), 4),
        "all_aspects_at_least_0_70": bool((table.test_f1 >= 0.70).all()),
        "oof_mentions": {
            review_id: {a: bool(decisions[i, j]) for j, a in enumerate(EARBUD_ASPECTS)}
            for i, review_id in enumerate(frame["review_id"])
        },
    }
