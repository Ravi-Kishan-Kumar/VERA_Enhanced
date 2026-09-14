"""Offline split-conformal fitting (PRD §10.3). Produces ``conformal_qhat.json``.

Production reads the result with :class:`app.ml.calibration.conformal.ConformalPredictor`.

Correct finite-sample quantile: with ``n`` calibration scores, use the
``k = ⌈(n + 1)(1 − α)⌉``-th smallest score. The PRD's
``np.quantile(scores, (1 − α)(1 + 1/n))`` interpolates (breaking the
guarantee) and raises once the level exceeds 1 for small ``n``.

Calibration inputs must be (a) product-disjoint from the ensemble's training
rows and (b) built with ``metadata_dropout=1.0`` so they match API inputs.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Literal

import numpy as np

from app.ml.constants import SCORE_MAX, SCORE_MIN
from vera_training.io import atomic_json

Method = Literal["absolute", "normalized"]


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    """The ``⌈(n+1)(1−α)⌉``-th smallest nonconformity score."""
    values = np.sort(np.asarray(scores, dtype=float))
    n = len(values)
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    k = math.ceil((n + 1) * (1 - alpha))
    if n == 0 or k > n:
        minimum = math.ceil((1 - alpha) / alpha)
        raise ValueError(f"Need at least {minimum} calibration rows for alpha={alpha}, got {n}")
    return float(values[k - 1])


def _half_widths(std: np.ndarray, q_hat: float, method: Method, sigma_floor: float) -> np.ndarray:
    if method == "normalized":
        return q_hat * (np.maximum(std, 0.0) + sigma_floor)
    return np.full_like(std, q_hat, dtype=float)


def interval_metrics(
    pred: np.ndarray, std: np.ndarray, y: np.ndarray, payload: dict[str, Any]
) -> dict[str, float]:
    """Empirical coverage and mean width of clipped intervals on any split."""
    pred, std, y = (np.asarray(a, dtype=float) for a in (pred, std, y))
    hw = _half_widths(std, payload["q_hat"], payload["method"], payload.get("sigma_floor", 0.0))
    lower = np.clip(pred - hw, SCORE_MIN, SCORE_MAX)
    upper = np.clip(pred + hw, SCORE_MIN, SCORE_MAX)
    return {
        "coverage": float(np.mean((y >= lower) & (y <= upper))),
        "mean_width": float(np.mean(upper - lower)),
        "n": len(y),
    }


def fit_conformal(
    pred: np.ndarray,
    std: np.ndarray,
    y: np.ndarray,
    *,
    alpha: float = 0.10,
    method: Method = "normalized",
    sigma_floor: float | None = None,
) -> dict[str, Any]:
    """Fit one conformal method on the calibration split.

    ``sigma_floor`` (normalized only) defaults to the median ensemble std, so no
    interval collapses to zero width when the members happen to agree.
    """
    pred, std, y = (np.asarray(a, dtype=float) for a in (pred, std, y))
    if not len(pred) == len(std) == len(y):
        raise ValueError("pred, std and y must align")
    payload: dict[str, Any] = {"method": method, "alpha": alpha, "nominal_coverage": 1 - alpha}
    if method == "normalized":
        floor = float(np.median(std)) if sigma_floor is None else float(sigma_floor)
        floor = max(floor, 1e-3)
        scores = np.abs(y - pred) / (std + floor)
        payload["sigma_floor"] = floor
    else:
        scores = np.abs(y - pred)
    payload["q_hat"] = conformal_quantile(scores, alpha)
    metrics = interval_metrics(pred, std, y, payload)
    payload.update(
        empirical_coverage=metrics["coverage"],
        mean_width=metrics["mean_width"],
        calibration_n=len(y),
    )
    return payload


def fit_best_conformal(
    pred: np.ndarray, std: np.ndarray, y: np.ndarray, *, alpha: float = 0.10
) -> dict[str, Any]:
    """Fit both methods; keep the narrower one (both carry the same guarantee)."""
    methods: tuple[Method, ...] = ("absolute", "normalized")
    candidates = [fit_conformal(pred, std, y, alpha=alpha, method=m) for m in methods]
    best = min(candidates, key=lambda c: c["mean_width"])
    best["alternatives"] = {c["method"]: c["mean_width"] for c in candidates}
    return best


def save_conformal(
    payload: dict[str, Any],
    path: str | Path,
    *,
    test_metrics: dict[str, float] | None = None,
    tolerance: float = 0.02,
) -> None:
    """Assert coverage ≥ nominal − tolerance (on test data when given), then write JSON."""
    check = test_metrics["coverage"] if test_metrics else payload["empirical_coverage"]
    if check < payload["nominal_coverage"] - tolerance:
        raise AssertionError(
            f"Coverage {check:.3f} below nominal {payload['nominal_coverage']:.3f} - {tolerance}. "
            "Enlarge the calibration set or re-check its feature distribution."
        )
    atomic_json(path, {**payload, **({"test": test_metrics} if test_metrics else {})})


def record_checkpoint(payload: dict[str, Any]) -> int:
    """Insert a ``calibration_checkpoints`` row (requires DATABASE_URL). Returns its id."""
    from app.database import SessionLocal
    from app.models.calibration import CalibrationCheckpoint

    with SessionLocal() as db:
        row = CalibrationCheckpoint(
            method=payload["method"],
            q_hat=payload["q_hat"],
            empirical_coverage=payload["empirical_coverage"],
            nominal_coverage=payload["nominal_coverage"],
            calibration_set_size=payload["calibration_n"],
        )
        db.add(row)
        db.commit()
        return int(row.id)
