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


# ----------------------------------------------------------------------------
# Hyperparameter selection (product-grouped CV on TRAINING rows only)
# ----------------------------------------------------------------------------
#: Shared settings for tuned models. A low learning rate with early stopping lets
#: the number of trees adapt to the data size instead of a fixed 300.
TUNING_BASE: dict[str, Any] = {
    "learning_rate": 0.03,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "objective": "reg:squarederror",
    "tree_method": "hist",
    "n_jobs": 4,
}

#: Capacity grid: shallow trees and stronger leaf/L2 regularisation are what curb
#: memorisation on ~1–4K rows (the untuned depth-6 model had train MAE 0.12 vs test 0.32).
PARAM_GRID: tuple[dict[str, Any], ...] = tuple(
    {"max_depth": depth, "min_child_weight": child, "reg_lambda": l2}
    for depth in (2, 3, 4)
    for child in (1, 5, 15)
    for l2 in (1.0, 10.0)
)


def tune_fusion_params(
    X: np.ndarray,
    y: np.ndarray,
    groups: Sequence[str],
    *,
    grid: Sequence[dict[str, Any]] = PARAM_GRID,
    n_splits: int = 5,
    max_rounds: int = 2000,
    early_stopping_rounds: int = 60,
    balance: bool = True,
    seed: int = 42,
) -> dict[str, Any]:
    """Pick XGBoost capacity by product-grouped CV with early stopping.

    For every grid point, each fold trains until validation MAE stops improving;
    we record validation MAE and the train MAE at that iteration. The selected
    configuration minimises mean validation MAE; among configurations within one
    standard error of the best, the one with the smallest train/validation gap
    wins (the "one-standard-error rule" favours the simpler, less overfit model).

    Returns the chosen params (including a fixed ``n_estimators`` = median best
    iteration) plus the full results table for the report.
    """
    from sklearn.model_selection import GroupKFold

    X = np.asarray(X, dtype=np.float32)
    y = np.asarray(y, dtype=float)
    group_array = np.asarray(list(groups))
    weights = balanced_sample_weights(y) if balance else np.ones(len(y))
    folds = list(GroupKFold(n_splits=n_splits).split(X, y, group_array))

    table: list[dict[str, Any]] = []
    for point in grid:
        val_maes, train_maes, iterations = [], [], []
        for train_idx, val_idx in folds:
            model = xgb.XGBRegressor(
                **TUNING_BASE,
                **point,
                n_estimators=max_rounds,
                early_stopping_rounds=early_stopping_rounds,
                eval_metric="mae",
                random_state=seed,
            )
            model.fit(
                X[train_idx],
                y[train_idx],
                sample_weight=weights[train_idx],
                eval_set=[(X[val_idx], y[val_idx])],
                verbose=False,
            )
            best = int(model.best_iteration) + 1
            window = (0, best)
            val_pred = np.clip(
                model.predict(X[val_idx], iteration_range=window), SCORE_MIN, SCORE_MAX
            )
            train_pred = np.clip(
                model.predict(X[train_idx], iteration_range=window), SCORE_MIN, SCORE_MAX
            )
            val_maes.append(float(np.mean(np.abs(val_pred - y[val_idx]))))
            train_maes.append(float(np.mean(np.abs(train_pred - y[train_idx]))))
            iterations.append(best)
        table.append(
            {
                **point,
                "val_mae": float(np.mean(val_maes)),
                "val_mae_se": float(np.std(val_maes, ddof=1) / np.sqrt(len(val_maes))),
                "train_mae": float(np.mean(train_maes)),
                "gap": float(np.mean(val_maes) - np.mean(train_maes)),
                "n_estimators": int(np.median(iterations)),
            }
        )

    best_row = min(table, key=lambda row: row["val_mae"])
    tolerance = best_row["val_mae"] + best_row["val_mae_se"]
    candidates = [row for row in table if row["val_mae"] <= tolerance]
    chosen = min(candidates, key=lambda row: (row["gap"], row["val_mae"]))
    params = {
        **TUNING_BASE,
        **{k: chosen[k] for k in ("max_depth", "min_child_weight", "reg_lambda")},
        "n_estimators": max(chosen["n_estimators"], 20),
    }
    return {"params": params, "chosen": chosen, "best_by_val": best_row, "table": table}
