"""Overall model quality + over/underfitting diagnostics from the saved fusion cache and artifacts.

    .venv\\Scripts\\python.exe training\\scripts\\model_quality_report.py
Writes reports/model_quality.json. Uses only existing splits (train / calibration / test).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "training")]
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import joblib  # noqa: E402
import numpy as np  # noqa: E402

from app.ml.agents.fusion import FusionModel  # noqa: E402
from vera_training import paths  # noqa: E402
from vera_training.io import atomic_json  # noqa: E402


def metrics(pred: np.ndarray, y: np.ndarray) -> dict[str, float]:
    err = np.abs(pred - y)
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return {
        "mae": round(float(err.mean()), 3),
        "rmse": round(float(np.sqrt(np.mean((pred - y) ** 2))), 3),
        "r2": round(1 - ss_res / ss_tot, 3),
        "within_0_5_stars": round(float(np.mean(err <= 0.5)), 3),
        "within_1_0_star": round(float(np.mean(err <= 1.0)), 3),
        "n": len(y),
    }


def main() -> None:
    cache = joblib.load(paths.FUSION_CACHE)["matrices"]
    fusion = FusionModel(paths.MODELS / "fusion_ensemble.json")
    report: dict[str, dict[str, dict[str, float]]] = {}
    for split in ("train", "calibration", "test"):
        X, y, frame = cache[split]["X"], cache[split]["y"], cache[split]["frame"]
        vera = fusion.predict_members(X).mean(axis=0).clip(1, 5)
        report[split] = {
            "vera": metrics(vera, y),
            "text_model_out_of_fold": metrics(np.clip(frame.experience_raw.to_numpy(), 1, 5), y),
            "stars_as_prediction": metrics(frame.rating.to_numpy(dtype=float), y),
        }
    train_mae, test_mae = report["train"]["vera"]["mae"], report["test"]["vera"]["mae"]
    report["fit_diagnosis"] = {
        "train_minus_test_mae_gap": round(test_mae - train_mae, 3),
        "note": "train rows were seen by the fusion ensemble; calibration/test rows were not",
    }
    atomic_json(paths.REPORTS / "model_quality.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
