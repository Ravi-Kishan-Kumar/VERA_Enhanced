"""Agent 6 — Domain Rating Model (PRD §9, Agent 6).

TF-IDF -> Ridge regression trained on the UNLABELED earbud corpus, using its
star ratings as a noisy proxy target. Training lives offline in
``training/vera_training/domain.py`` (with the held-out ASIN leakage guard);
this module only loads and applies the artifact.

SECURITY: the artifact is a joblib pickle. Only load files produced by the VERA
training notebooks from your own HF repo — unpickling untrusted files executes code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import sklearn

from app.ml.constants import SCORE_MAX, SCORE_MIN


class DomainRatingModel:
    """Agent 6: text -> implied rating from domain vocabulary."""

    def __init__(self, model_path: str | Path) -> None:
        try:
            artifacts = joblib.load(model_path)
        except ModuleNotFoundError as exc:  # e.g. "numpy._core" from a numpy-2 pickle
            raise ValueError(
                f"{model_path} was pickled with incompatible library versions ({exc}). "
                "Retrain it in the production-pinned .venv (see notebooks/05)."
            ) from exc
        if not {"vectorizer", "model"} <= set(artifacts):
            raise ValueError(f"{model_path} must contain 'vectorizer' and 'model'")
        trained_with = artifacts.get("sklearn_version")
        if trained_with is not None and trained_with != sklearn.__version__:
            raise ValueError(
                f"{model_path} trained with scikit-learn {trained_with}, runtime has "
                f"{sklearn.__version__}; retrain with the pinned version."
            )
        self.vectorizer = artifacts["vectorizer"]
        self.model = artifacts["model"]

    @classmethod
    def from_components(cls, vectorizer: Any, model: Any) -> DomainRatingModel:
        """Build from in-memory objects (training notebooks and tests)."""
        instance = cls.__new__(cls)
        instance.vectorizer = vectorizer
        instance.model = model
        return instance

    def process(self, clean_text: str) -> dict[str, Any]:
        """Predict the implied rating.

        ``domain_confidence`` is the PRD's proxy: 1 − distance to the nearest
        integer star (Ridge gives no native uncertainty).
        """
        features = self.vectorizer.transform([clean_text])
        raw_score = float(self.model.predict(features)[0])
        domain_score = float(np.clip(raw_score, SCORE_MIN, SCORE_MAX))
        domain_confidence = 1.0 - abs(domain_score - round(domain_score))
        return {
            "domain_score": round(domain_score, 3),
            "domain_confidence": round(domain_confidence, 3),
        }
