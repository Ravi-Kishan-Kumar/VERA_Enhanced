"""Agent 7 training — bootstrap XGBoost ensemble (PRD §10.2).

Differences from the PRD sketch (see DECISIONS.md):
* ``eval_set=[(X, y)]`` evaluated on the training data itself and did nothing
  useful; it is removed.
* Optional inverse-frequency sample weights over half-star label bins address
  label imbalance (PRD weakness #10 promises "class-weighted XGBoost").
* The artifact is portable JSON (:func:`app.ml.agents.fusion.save_fusion_artifact`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import xgboost as xgb

from app.ml.agents.fusion import save_fusion_artifact
from app.ml.constants import SCORE_MAX, SCORE_MIN
from app.ml.features import N_FEATURES

DEFAULT_PARAMS: dict[str, Any] = {
    "n_estimators": 300,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "objective": "reg:squarederror",
    "tree_method": "hist",
    "n_jobs": 2,
}


def balanced_sample_weights(y: np.ndarray) -> np.ndarray:
    """Inverse-frequency weights over half-star bins, normalised to mean 1."""
    bins = np.round(np.asarray(y, dtype=float) * 2).astype(int)
    values, counts = np.unique(bins, return_counts=True)
    frequency = dict(zip(values.tolist(), counts.tolist(), strict=True))
    weights = np.array([1.0 / frequency[b] for b in bins.tolist()])
    return weights / weights.mean()


@dataclass
class BootstrapEnsemble:
    """sklearn-style regressor: ``fit`` / ``predict`` / ``predict_with_std``."""

    n_members: int = 20
    seed: int = 42
    balance: bool = True
    params: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_PARAMS))
    members: list[xgb.XGBRegressor] = field(default_factory=list, init=False)

    def fit(self, X: np.ndarray, y: np.ndarray) -> BootstrapEnsemble:
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y, dtype=float)
        if X.ndim != 2 or len(X) != len(y) or len(X) < 2:
            raise ValueError("X must be 2-D with one row per target and at least two rows")
        weights = balanced_sample_weights(y) if self.balance else np.ones(len(y))
        rng = np.random.default_rng(self.seed)
        self.members = []
        for index in range(self.n_members):
            rows = rng.integers(0, len(X), size=len(X))  # bootstrap resample
            model = xgb.XGBRegressor(**self.params, random_state=self.seed + index)
            model.fit(X[rows], y[rows], sample_weight=weights[rows], verbose=False)
            self.members.append(model)
        return self

    def member_predictions(self, X: np.ndarray) -> np.ndarray:
        if not self.members:
            raise RuntimeError("fit() the ensemble first")
        matrix = np.asarray(X, dtype=np.float32)
        return np.stack([m.predict(matrix) for m in self.members])

    def predict_with_std(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Clipped ensemble mean and member standard deviation per row."""
        preds = self.member_predictions(X)
        return np.clip(preds.mean(axis=0), SCORE_MIN, SCORE_MAX), preds.std(axis=0)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.predict_with_std(X)[0]

    def save(
        self,
        path: str | Path,
        imputation_means: dict[str, float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Write ``fusion_ensemble.json`` (only full 40-feature ensembles are deployable)."""
        if self.members and self.members[0].n_features_in_ != N_FEATURES:
            raise ValueError("Only an ensemble trained on all fusion features can be saved")
        save_fusion_artifact(
            path,
            self.members,
            imputation_means,
            metadata={"n_members": self.n_members, "seed": self.seed, **(metadata or {})},
        )


def column_indices(feature_names: Sequence[str], selected: Sequence[str]) -> list[int]:
    """Indices of ``selected`` features inside ``feature_names`` (for ablations)."""
    lookup = {name: index for index, name in enumerate(feature_names)}
    missing = [name for name in selected if name not in lookup]
    if missing:
        raise KeyError(f"Unknown features: {missing}")
    return [lookup[name] for name in selected]
