"""Tests for fusion capacity tuning, nested CV, learning curves and the aspect detector."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.ml.agents.aspect_detector import AspectDetector
from app.ml.constants import EARBUD_ASPECTS
from app.ml.features import N_FEATURES
from vera_training import evaluation
from vera_training.aspects import best_threshold, fit_aspect_detector
from vera_training.fusion import BootstrapEnsemble, tune_fusion_params


def _regression_data(n: int = 240, seed: int = 0) -> tuple[np.ndarray, np.ndarray, list[str]]:
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, N_FEATURES)).astype(np.float32)
    y = np.clip(3 + 0.8 * X[:, 1] + 0.3 * X[:, 2] + 0.2 * rng.normal(size=n), 1, 5)
    groups = [f"P{i % 60}" for i in range(n)]
    return X, y, groups


def test_tuning_prefers_regularised_model_and_reports_gap() -> None:
    X, y, groups = _regression_data()
    grid = [
        {"max_depth": 2, "min_child_weight": 5, "reg_lambda": 10.0},
        {"max_depth": 8, "min_child_weight": 1, "reg_lambda": 0.0},
    ]
    result = tune_fusion_params(X, y, groups, grid=grid, n_splits=3, max_rounds=300)
    assert len(result["table"]) == 2
    assert result["params"]["n_estimators"] >= 20
    assert all(row["gap"] >= -0.05 for row in result["table"])
    chosen = result["chosen"]
    assert (
        chosen["val_mae"] <= result["best_by_val"]["val_mae"] + result["best_by_val"]["val_mae_se"]
    )


def test_nested_cv_and_learning_curve_are_sane() -> None:
    X, y, groups = _regression_data(180)
    small_grid = [{"max_depth": 2, "min_child_weight": 5, "reg_lambda": 10.0}]
    import vera_training.fusion as fusion_module

    maes, details = evaluation.nested_cross_validated_mae(
        X, y, groups, n_members=3, n_splits=3, n_repeats=1, grid=small_grid
    )
    assert maes.shape == (3,) and len(details) == 3
    assert all(d["test_mae"] < 1.0 for d in details)

    params = {**fusion_module.TUNING_BASE, **small_grid[0], "n_estimators": 60}
    curve = evaluation.learning_curve(
        X[:120], y[:120], groups[:120], X[120:], y[120:], params, n_members=3
    )
    assert [row["fraction"] for row in curve] == [0.25, 0.5, 0.75, 1.0]
    assert curve[-1]["n_rows"] == 120
    assert curve[-1]["validation_mae"] <= curve[0]["validation_mae"] + 0.05


def test_bootstrap_ensemble_accepts_tuned_params() -> None:
    X, y, _ = _regression_data(100)
    params = {"max_depth": 2, "n_estimators": 30, "learning_rate": 0.1}
    mean, std = BootstrapEnsemble(n_members=3, params=params).fit(X, y).predict_with_std(X)
    assert mean.shape == std.shape == (100,)


def test_best_threshold_maximises_f1() -> None:
    y = np.array([0, 0, 1, 1, 1, 0])
    probabilities = np.array([0.1, 0.3, 0.6, 0.7, 0.9, 0.2])
    threshold, f1 = best_threshold(y, probabilities)
    assert f1 == 1.0 and 0.3 < threshold <= 0.6


def _aspect_frame(n: int = 200, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    phrases = {
        "sound_quality": "the sound is crisp",
        "bass": "bass hits hard",
        "battery_life": "battery lasts all day",
        "comfort": "comfortable for hours",
        "fit": "they stay in my ears",
        "build_quality": "the hinge snapped after a week",
        "connectivity": "bluetooth keeps dropping",
        "microphone": "callers hear me clearly",
        "noise_cancellation": "anc blocks the train",
        "value": "great for the price",
    }
    rows = []
    for i in range(n):
        mentioned = {a: bool(rng.random() < 0.35) for a in EARBUD_ASPECTS}
        text = " ".join(phrases[a] for a in EARBUD_ASPECTS if mentioned[a]) or "arrived on time"
        rows.append(
            {
                "review_id": f"r{i}",
                "parent_asin": f"P{i % 40}",
                "text": text,
                "aspects": {
                    a: {
                        "mentioned": mentioned[a],
                        "sentiment": "positive" if mentioned[a] else "not_mentioned",
                    }
                    for a in EARBUD_ASPECTS
                },
            }
        )
    return pd.DataFrame(rows)


def test_aspect_detector_learns_holdout_and_roundtrips(tmp_path: Path) -> None:
    frame = _aspect_frame()
    test_mask = frame.parent_asin.isin([f"P{i}" for i in range(8)]).to_numpy()
    path = tmp_path / "aspect_detector.joblib"
    report = fit_aspect_detector(frame, test_mask, path)

    assert report["n_test"] == int(test_mask.sum())
    assert report["test_macro_f1"] > 0.9  # phrases are unambiguous
    assert set(report["oof_mentions"]) == set(frame.review_id)
    detector = AspectDetector(path)
    decisions = detector.detect("bluetooth keeps dropping but great for the price")
    assert decisions["connectivity"] and decisions["value"]
    assert not decisions["bass"]


def test_aspect_detector_rejects_wrong_aspect_order(tmp_path: Path) -> None:
    import joblib

    path = tmp_path / "bad.joblib"
    joblib.dump(
        {"vectorizer": None, "models": {}, "thresholds": {}, "aspects": list(EARBUD_ASPECTS)[::-1]},
        path,
    )
    with pytest.raises(ValueError, match="aspect order"):
        AspectDetector(path)
