"""Evaluation protocol (PRD §13, §20.1 gate G4, §22.1).

Rules enforced here: every reported number comes from repeated product-grouped
cross-validation (never a single split), results are mean ± std with fold win
rate and a paired one-sided Wilcoxon test, and negative ablation results are
reported rather than hidden.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from sklearn.metrics import accuracy_score, f1_score

from app.ml.constants import EARBUD_ASPECTS
from app.ml.features import FEATURE_GROUPS, FEATURE_NAMES
from vera_training.fusion import column_indices
from vera_training.splits import repeated_group_folds


class Regressor(Protocol):
    def fit(self, X: np.ndarray, y: np.ndarray) -> Any: ...

    def predict(self, X: np.ndarray) -> np.ndarray: ...


def cross_validated_mae(
    X: np.ndarray,
    y: np.ndarray,
    groups: Sequence[str],
    factory: Callable[[], Regressor],
    *,
    n_splits: int = 5,
    n_repeats: int = 3,
    seed: int = 42,
) -> np.ndarray:
    """Per-fold MAE over repeated grouped folds (identical folds for identical seeds)."""
    X, y = np.asarray(X), np.asarray(y, dtype=float)
    maes = []
    for _, _, train, test in repeated_group_folds(groups, n_splits, n_repeats, seed):
        model = factory()
        model.fit(X[train], y[train])
        maes.append(float(np.mean(np.abs(model.predict(X[test]) - y[test]))))
    return np.asarray(maes)


def paired_comparison(baseline: np.ndarray, candidate: np.ndarray) -> dict[str, Any]:
    """Mean ± std, win rate, and one-sided Wilcoxon (H1: candidate MAE < baseline MAE)."""
    baseline, candidate = np.asarray(baseline, float), np.asarray(candidate, float)
    if baseline.shape != candidate.shape:
        raise ValueError("Folds must be paired")
    diff = baseline - candidate
    p_value = (
        float(wilcoxon(baseline, candidate, alternative="greater").pvalue) if np.any(diff) else 1.0
    )
    return {
        "baseline_mae_mean": float(baseline.mean()),
        "baseline_mae_std": float(baseline.std()),
        "candidate_mae_mean": float(candidate.mean()),
        "candidate_mae_std": float(candidate.std()),
        "win_rate": float(np.mean(diff > 0)),
        "wilcoxon_p": p_value,
        "n_folds": len(baseline),
    }


class ColumnSubset:
    """Wraps a regressor factory so it sees only selected feature columns."""

    def __init__(self, factory: Callable[[], Regressor], columns: Sequence[int]) -> None:
        self.model = factory()
        self.columns = list(columns)

    def fit(self, X: np.ndarray, y: np.ndarray) -> ColumnSubset:
        self.model.fit(X[:, self.columns], y)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict(X[:, self.columns])


#: Cumulative ablation ladder (PRD §13.2; the PRD listed "+absa" and "full_vera" identically).
ABLATION_LADDER: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("stars_only", ("star",)),
    ("+experience", ("star", "experience")),
    ("+domain", ("star", "experience", "domain")),
    ("+consistency", ("star", "experience", "domain", "consistency")),
    ("+quality", ("star", "experience", "domain", "consistency", "quality")),
    ("full_vera", ("star", "experience", "domain", "consistency", "quality", "absa")),
)


def ablation_study(
    X: np.ndarray,
    y: np.ndarray,
    groups: Sequence[str],
    factory: Callable[[], Regressor],
    **cv: Any,
) -> pd.DataFrame:
    """Each rung vs the previous rung; a component is kept only if it helps (win rate ≥ 60%)."""
    rows, previous = [], None
    for name, group_names in ABLATION_LADDER:
        features = [f for g in group_names for f in FEATURE_GROUPS[g]]
        columns = column_indices(FEATURE_NAMES, features)

        def subset_factory(selected: list[int] = columns) -> Regressor:
            return ColumnSubset(factory, selected)

        maes = cross_validated_mae(X, y, groups, subset_factory, **cv)
        row: dict[str, Any] = {
            "config": name,
            "n_features": len(columns),
            "mae_mean": maes.mean(),
            "mae_std": maes.std(),
        }
        if previous is not None:
            comparison = paired_comparison(previous, maes)
            row |= {
                "win_rate_vs_previous": comparison["win_rate"],
                "wilcoxon_p_vs_previous": comparison["wilcoxon_p"],
                "keep": comparison["win_rate"] >= 0.60,
            }
        rows.append(row)
        previous = maes
    return pd.DataFrame(rows)


def aspect_metrics(
    labels: Sequence[Mapping[str, Any]], predictions: Sequence[Mapping[str, Any]]
) -> pd.DataFrame:
    """Per-aspect detection F1 and sentiment accuracy on jointly detected mentions (PRD §13.4).

    ``labels[i][aspect]`` = ``{"mentioned", "sentiment"}`` (LLM label);
    ``predictions[i][aspect]`` = ``{"detected", "sentiment"}`` (Agent 3 output).
    """
    if len(labels) != len(predictions):
        raise ValueError("labels and predictions must align")
    rows = []
    for aspect in EARBUD_ASPECTS:
        truth = [bool(item[aspect]["mentioned"]) for item in labels]
        guess = [bool(item[aspect]["detected"]) for item in predictions]
        both = [i for i, (t, g) in enumerate(zip(truth, guess, strict=True)) if t and g]
        rows.append(
            {
                "aspect": aspect,
                "support": int(sum(truth)),
                "detection_f1": float(f1_score(truth, guess, zero_division=0)),
                "sentiment_accuracy": (
                    float(
                        accuracy_score(
                            [labels[i][aspect]["sentiment"] for i in both],
                            [predictions[i][aspect]["sentiment"] for i in both],
                        )
                    )
                    if both
                    else float("nan")
                ),
                "sentiment_n": len(both),
            }
        )
    return pd.DataFrame(rows)


def gate_g4(comparison: Mapping[str, Any], coverage_90: float) -> dict[str, Any]:
    """G4: VERA beats stars-only (Wilcoxon p < 0.05) and 90% intervals cover ≥ 88%."""
    checks = {
        "beats_baseline": comparison["candidate_mae_mean"] < comparison["baseline_mae_mean"],
        "significant": comparison["wilcoxon_p"] < 0.05,
        "win_rate_at_least_85pct": comparison["win_rate"] >= 0.85,
        "coverage_at_least_88pct": coverage_90 >= 0.88,
    }
    return {"gate": "G4", "passed": all(checks.values()), "checks": checks}


def nested_cross_validated_mae(
    X: np.ndarray,
    y: np.ndarray,
    groups: Sequence[str],
    *,
    n_members: int = 20,
    n_splits: int = 5,
    n_repeats: int = 3,
    seed: int = 42,
    grid: Sequence[dict[str, Any]] | None = None,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Per-fold MAE with hyperparameters re-tuned INSIDE every outer training fold.

    Tuning on the whole dataset and then cross-validating would leak the evaluation
    folds into model selection. Here each outer fold runs
    :func:`vera_training.fusion.tune_fusion_params` on its own training rows only.

    Returns:
        ``(fold_maes, fold_details)`` where details include the chosen params and the
        outer-fold train MAE (for the overfitting gap).
    """
    from vera_training.fusion import PARAM_GRID, BootstrapEnsemble, tune_fusion_params

    X, y = np.asarray(X), np.asarray(y, dtype=float)
    group_array = np.asarray(list(groups))
    maes: list[float] = []
    details: list[dict[str, Any]] = []
    for repeat, fold, train, test in repeated_group_folds(group_array, n_splits, n_repeats, seed):
        tuned = tune_fusion_params(
            X[train],
            y[train],
            group_array[train].tolist(),
            seed=seed,
            grid=PARAM_GRID if grid is None else grid,
        )
        model = BootstrapEnsemble(n_members=n_members, seed=seed, params=tuned["params"])
        model.fit(X[train], y[train])
        test_mae = float(np.mean(np.abs(model.predict(X[test]) - y[test])))
        train_mae = float(np.mean(np.abs(model.predict(X[train]) - y[train])))
        maes.append(test_mae)
        details.append(
            {
                "repeat": repeat,
                "fold": fold,
                "test_mae": test_mae,
                "train_mae": train_mae,
                "gap": test_mae - train_mae,
                "max_depth": tuned["params"]["max_depth"],
                "min_child_weight": tuned["params"]["min_child_weight"],
                "reg_lambda": tuned["params"]["reg_lambda"],
                "n_estimators": tuned["params"]["n_estimators"],
            }
        )
    return np.asarray(maes), details


def learning_curve(
    X_train: np.ndarray,
    y_train: np.ndarray,
    groups: Sequence[str],
    X_val: np.ndarray,
    y_val: np.ndarray,
    params: dict[str, Any],
    fractions: Sequence[float] = (0.25, 0.5, 0.75, 1.0),
    n_members: int = 10,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Train/validation MAE as the number of training PRODUCTS grows.

    Converging curves with a small gap = good fit; a large persistent gap = overfitting;
    both curves high and flat = underfitting; validation still falling = more data helps.
    """
    from vera_training.fusion import BootstrapEnsemble

    X_train, y_train = np.asarray(X_train), np.asarray(y_train, dtype=float)
    group_array = np.asarray(list(groups))
    products = np.unique(group_array)
    rng = np.random.default_rng(seed)
    order = rng.permutation(products)
    rows = []
    for fraction in fractions:
        keep = set(order[: max(2, int(round(fraction * len(products))))])
        mask = np.array([g in keep for g in group_array])
        model = BootstrapEnsemble(n_members=n_members, seed=seed, params=params)
        model.fit(X_train[mask], y_train[mask])
        rows.append(
            {
                "fraction": fraction,
                "n_rows": int(mask.sum()),
                "train_mae": float(np.mean(np.abs(model.predict(X_train[mask]) - y_train[mask]))),
                "validation_mae": float(np.mean(np.abs(model.predict(X_val) - y_val))),
            }
        )
    return rows
