"""Production split-conformal interval predictor (PRD §10.3).

Reads the pre-fitted quantile from ``conformal_qhat.json`` — no MAPIE, no
sklearn, only ``json`` + ``numpy`` (PRD weakness #16). Fitting happens offline
in ``training/vera_training/calibration.py`` (notebook 06).

Two nonconformity methods are supported (see DECISIONS.md):

* ``absolute``   — score ``|y − ŷ|``; interval ``ŷ ± q̂``. Constant width, so
  "confidence" only varies through clipping at the scale edges.
* ``normalized`` — score ``|y − ŷ| / (σ̂ + floor)`` with σ̂ = ensemble std;
  interval ``ŷ ± q̂·(σ̂ + floor)``. Same finite-sample coverage guarantee, but
  widths adapt per review, which makes the confidence value informative.

JSON schema::

    {"method": "absolute"|"normalized", "q_hat": float, "alpha": float,
     "nominal_coverage": float, "empirical_coverage": float,
     "calibration_n": int, "sigma_floor": float (normalized only)}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import numpy as np

from app.ml.constants import SCORE_MAX, SCORE_MIN, SCORE_RANGE

METHODS: Final = frozenset({"absolute", "normalized"})


def interval_confidence(lower: float, upper: float) -> float:
    """Map interval width to [0, 1]: a 0.5-wide interval -> 0.875, 2-wide -> 0.5."""
    return float(np.clip(1.0 - (upper - lower) / SCORE_RANGE, 0.0, 1.0))


class ConformalPredictor:
    """Online conformal predictor; loaded once per worker process."""

    def __init__(self, qhat_path: str | Path) -> None:
        data: dict[str, Any] = json.loads(Path(qhat_path).read_text(encoding="utf-8"))
        self.method: str = data.get("method", "absolute")
        if self.method not in METHODS:
            raise ValueError(f"Unknown conformal method {self.method!r}")
        self.q_hat = float(data["q_hat"])
        if not np.isfinite(self.q_hat) or self.q_hat < 0:
            raise ValueError(f"q_hat must be a finite non-negative float, got {self.q_hat}")
        self.nominal_coverage = float(data["nominal_coverage"])
        self.sigma_floor = float(data.get("sigma_floor", 0.0))
        if self.method == "normalized" and self.sigma_floor <= 0:
            raise ValueError("normalized conformal requires sigma_floor > 0")
        self._meta = data

    def half_width(self, ensemble_std: float = 0.0) -> float:
        """Interval half-width for one prediction."""
        if self.method == "normalized":
            return self.q_hat * (max(float(ensemble_std), 0.0) + self.sigma_floor)
        return self.q_hat

    def predict_interval(
        self, base_pred: float, ensemble_std: float = 0.0
    ) -> tuple[float, float, float]:
        """Return ``(lower, upper, confidence)`` clipped to the 1–5 scale."""
        hw = self.half_width(ensemble_std)
        lower = float(np.clip(base_pred - hw, SCORE_MIN, SCORE_MAX))
        upper = float(np.clip(base_pred + hw, SCORE_MIN, SCORE_MAX))
        return lower, upper, interval_confidence(lower, upper)

    def health_info(self) -> dict[str, Any]:
        """Calibration metadata for diagnostics."""
        return {
            "method": self.method,
            "q_hat": self.q_hat,
            "nominal_coverage": self.nominal_coverage,
            "empirical_coverage": self._meta.get("empirical_coverage"),
            "calibration_n": self._meta.get("calibration_n"),
        }
