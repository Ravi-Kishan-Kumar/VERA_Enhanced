"""Agent 7 — Fusion (PRD §10.2).

A bootstrap ensemble of XGBoost regressors maps the 40 fusion features to the
corrected experience score. The ensemble mean is the point estimate; the
ensemble standard deviation feeds normalised conformal intervals.

Artifact format — ``fusion_ensemble.json`` (see DECISIONS.md: JSON instead of
the PRD's joblib pickle, because pickled XGBoost objects break across library
versions and unpickling is a code-execution risk)::

    {
      "format_version": 1,
      "feature_names": [...],            # must equal app.ml.features.FEATURE_NAMES
      "imputation_means": {...},         # Agent 5 training means
      "members": ["<xgboost JSON model>", ...],
      "metadata": {...}                  # free-form: n_train, xgboost_version, ...
    }
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

import numpy as np
import xgboost as xgb

from app.ml.agents.quality import IMPUTATION_KEYS
from app.ml.constants import SCORE_MAX, SCORE_MIN
from app.ml.features import FEATURE_NAMES, N_FEATURES

FORMAT_VERSION: Final = 1


def save_fusion_artifact(
    path: str | Path,
    members: Sequence[xgb.XGBRegressor | xgb.Booster],
    imputation_means: dict[str, float],
    metadata: dict[str, Any] | None = None,
) -> None:
    """Serialise an ensemble to the portable JSON artifact."""
    if not members:
        raise ValueError("ensemble needs at least one member")
    absent = [k for k in IMPUTATION_KEYS if k not in imputation_means]
    if absent:
        raise ValueError(f"imputation_means missing keys: {absent}")

    serialised = []
    for member in members:
        booster = member.get_booster() if isinstance(member, xgb.XGBRegressor) else member
        serialised.append(bytes(booster.save_raw(raw_format="json")).decode("utf-8"))

    payload = {
        "format_version": FORMAT_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "imputation_means": {k: float(v) for k, v in imputation_means.items()},
        "members": serialised,
        "metadata": {"xgboost_version": xgb.__version__, **(metadata or {})},
    }
    Path(path).write_text(json.dumps(payload), encoding="utf-8")


class FusionModel:
    """Agent 7: loads the ensemble and predicts mean ± std."""

    def __init__(self, artifact_path: str | Path) -> None:
        payload = json.loads(Path(artifact_path).read_text(encoding="utf-8"))

        if payload.get("format_version") != FORMAT_VERSION:
            raise ValueError(f"Unsupported fusion artifact version {payload.get('format_version')}")
        if tuple(payload["feature_names"]) != FEATURE_NAMES:
            raise ValueError(
                "Fusion artifact feature_names differ from app.ml.features.FEATURE_NAMES — "
                "retrain the ensemble with the current feature contract."
            )

        self.imputation_means: dict[str, float] = payload["imputation_means"]
        self.metadata: dict[str, Any] = payload.get("metadata", {})
        self.members: list[xgb.Booster] = []
        for raw in payload["members"]:
            booster = xgb.Booster()
            booster.load_model(bytearray(raw.encode("utf-8")))
            if booster.num_features() != N_FEATURES:
                raise ValueError(
                    f"member expects {booster.num_features()} features, not {N_FEATURES}"
                )
            self.members.append(booster)
        if not self.members:
            raise ValueError("fusion artifact contains no members")

    def predict_members(self, features: np.ndarray) -> np.ndarray:
        """Raw member predictions, shape ``(n_members, n_rows)``."""
        matrix = np.atleast_2d(np.asarray(features, dtype=np.float32))
        return np.stack([np.asarray(m.inplace_predict(matrix)) for m in self.members])

    def predict(self, features: np.ndarray) -> dict[str, float]:
        """Predict one review: clipped ensemble mean and member std."""
        preds = self.predict_members(features)[:, 0]
        return {
            "score": float(np.clip(preds.mean(), SCORE_MIN, SCORE_MAX)),
            "raw_mean": float(preds.mean()),
            "ensemble_std": float(preds.std()),
        }
