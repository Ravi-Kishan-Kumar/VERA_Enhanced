"""Interim agreement statistics on whatever labels exist so far (no gate decision).

    .venv\\Scripts\\python.exe training\\scripts\\agreement_preview.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "training")]
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from vera_training import paths  # noqa: E402
from vera_training.agreement import paired_agreement  # noqa: E402
from vera_training.labeling import ExperienceLabel  # noqa: E402


def scores(*run_ids: str) -> dict[str, float]:
    merged: dict[str, float] = {}
    for run_id in run_ids:
        path = paths.LABELS / f"run_{run_id}.json"
        if path.exists():
            for key, value in json.loads(path.read_text(encoding="utf-8"))["labels"].items():
                merged.setdefault(key, ExperienceLabel.model_validate(value).experience_score)
    return merged


def compare(name: str, left: dict[str, float], right: dict[str, float]) -> None:
    ids = sorted(set(left) & set(right))
    if len(ids) < 10:
        print(f"{name:34s} n={len(ids)} (too few)")
        return
    result = paired_agreement(np.array([left[i] for i in ids]), np.array([right[i] for i in ids]))
    print(f"{name:34s} n={result['n']:4d} kappa={result['kappa']:.3f} mae={result['mae']:.3f}")


def main() -> None:
    gpt, qwen, repeat = (
        scores("primary-a"),
        scores("qwen-a", "crossmodel-qwen"),
        scores("consistency"),
    )
    reference = dict(
        pd.read_csv(paths.LABELS / "reference_annotations_claude.csv", dtype={"review_id": str})
        .astype({"experience_score": float})
        .values
    )
    compare("gpt-oss self-consistency", gpt, repeat)
    compare("gpt-oss vs reference (Claude)", gpt, reference)
    compare("qwen vs reference (Claude)", qwen, reference)
    compare("gpt-oss vs qwen", gpt, qwen)
    print("G1 thresholds: self kappa > 0.70 & MAE < 0.40; reference kappa > 0.55 & MAE < 0.60")


if __name__ == "__main__":
    main()
