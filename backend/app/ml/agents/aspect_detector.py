"""Learned aspect detector — decides WHICH of the 10 earbud aspects a review mentions.

Replaces the keyword-only pre-filter of Agent 3 (PRD §9). Keyword lists alone
reached detection F1 0.54 (build quality) and 0.66 (connectivity) on the round-1
test split: durability phrasings were missed and generic words ("pair of
headphones") fired falsely.

Model, per aspect: logistic regression on word 1–2-gram TF-IDF features plus
the keyword hits of ALL aspects as extra features, with a decision threshold
chosen by product-grouped out-of-fold F1 on training rows only
(``training/vera_training/aspects.py``). Features are built by
:func:`detector_features`, shared by training and serving.

SECURITY: the artifact is a joblib pickle — only load files produced by the VERA
training pipeline.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

import joblib
import numpy as np
import scipy.sparse as sp
import sklearn

from app.ml.agents.absa import ABSAModule
from app.ml.constants import EARBUD_ASPECTS

#: Scale of the keyword indicator columns relative to TF-IDF values (≈ unit-norm rows).
KEYWORD_FEATURE_WEIGHT: Final = 3.0
ARTIFACT_KEYS: Final = frozenset({"vectorizer", "models", "thresholds", "aspects"})


def keyword_matrix(texts: Sequence[str]) -> np.ndarray:
    """``(n_texts, 10)`` float matrix of keyword hits in canonical aspect order."""
    return np.array(
        [[ABSAModule.keyword_detect(text, aspect) for aspect in EARBUD_ASPECTS] for text in texts],
        dtype=np.float64,
    )


def detector_features(vectorizer: Any, texts: Sequence[str]) -> sp.csr_matrix:
    """TF-IDF features concatenated with weighted keyword indicators."""
    tfidf = vectorizer.transform(list(texts))
    keywords = sp.csr_matrix(keyword_matrix(texts) * KEYWORD_FEATURE_WEIGHT)
    return sp.hstack([tfidf, keywords]).tocsr()


class AspectDetector:
    """Per-aspect probabilities and thresholded mention decisions."""

    def __init__(self, artifact_path: str | Path) -> None:
        artifacts = joblib.load(artifact_path)
        self._init_from(artifacts, source=str(artifact_path))

    @classmethod
    def from_components(
        cls,
        vectorizer: Any,
        models: dict[str, Any],
        thresholds: dict[str, float],
    ) -> AspectDetector:
        """Build from in-memory objects (training code and tests)."""
        instance = cls.__new__(cls)
        instance._init_from(
            {
                "vectorizer": vectorizer,
                "models": models,
                "thresholds": thresholds,
                "aspects": list(EARBUD_ASPECTS),
            },
            source="memory",
        )
        return instance

    def _init_from(self, artifacts: dict[str, Any], source: str) -> None:
        missing = ARTIFACT_KEYS - set(artifacts)
        if missing:
            raise ValueError(f"{source} is missing keys {sorted(missing)}")
        if tuple(artifacts["aspects"]) != EARBUD_ASPECTS:
            raise ValueError(f"{source} aspect order differs from EARBUD_ASPECTS; retrain it")
        trained_with = artifacts.get("sklearn_version")
        if trained_with is not None and trained_with != sklearn.__version__:
            raise ValueError(
                f"{source} trained with scikit-learn {trained_with}, runtime has "
                f"{sklearn.__version__}; retrain with the pinned version."
            )
        self.vectorizer = artifacts["vectorizer"]
        self.models: dict[str, Any] = artifacts["models"]
        self.thresholds: dict[str, float] = {
            k: float(v) for k, v in artifacts["thresholds"].items()
        }

    def probabilities(self, texts: Sequence[str]) -> np.ndarray:
        """``(n_texts, 10)`` mention probabilities in canonical aspect order."""
        features = detector_features(self.vectorizer, texts)
        return np.column_stack(
            [self.models[aspect].predict_proba(features)[:, 1] for aspect in EARBUD_ASPECTS]
        )

    def decide(self, probabilities: np.ndarray) -> list[dict[str, bool]]:
        """Apply per-aspect thresholds to a probability matrix."""
        return [
            {
                aspect: bool(row[i] >= self.thresholds[aspect])
                for i, aspect in enumerate(EARBUD_ASPECTS)
            }
            for row in np.atleast_2d(probabilities)
        ]

    def detect(self, text: str) -> dict[str, bool]:
        """Mention decisions for one review."""
        return self.decide(self.probabilities([text]))[0]
