"""Compare two Agent-2 fine-tunes (e.g. local RTX 2050 vs Colab T4) on identical folds.

    .venv\\Scripts\\python.exe training\\scripts\\compare_experience_models.py \\
        --a data/labels/experience_oof.csv --a-name local-384 \\
        --b data/labels/experience_oof_colab.csv --b-name colab-512

Both CSVs hold out-of-fold predictions from ``crossfit_predictions`` (deterministic
GroupKFold on the same labels_v1.jsonl), so each review was predicted by a model that
never saw its product in both runs — a fair paired comparison.
Writes reports/experience_model_comparison.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "training")]
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import wilcoxon  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402

from vera_training import paths  # noqa: E402
from vera_training.io import atomic_json, validate_reviews  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a", required=True)
    parser.add_argument("--b", required=True)
    parser.add_argument("--a-name", default="A")
    parser.add_argument("--b-name", default="B")
    args = parser.parse_args()

    labels = validate_reviews(
        pd.DataFrame([json.loads(line) for line in paths.LABELS_V1.open(encoding="utf-8")]),
        labels=True,
    )
    a = pd.read_csv(args.a, dtype={"review_id": str}).rename(columns={"experience_raw": "a"})
    b = pd.read_csv(args.b, dtype={"review_id": str}).rename(columns={"experience_raw": "b"})
    frame = labels.merge(a, on="review_id", validate="one_to_one").merge(
        b, on="review_id", validate="one_to_one"
    )
    if len(frame) != len(labels):
        raise SystemExit("Both OOF files must cover exactly the labels_v1 reviews")

    y = frame.experience_score.to_numpy()
    err_a = np.abs(np.clip(frame.a, 1, 5) - y)
    err_b = np.abs(np.clip(frame.b, 1, 5) - y)
    folds = GroupKFold(n_splits=5).split(frame, groups=frame.parent_asin)
    fold_a, fold_b = [], []
    for _, test in folds:
        fold_a.append(float(err_a.iloc[test].mean()))
        fold_b.append(float(err_b.iloc[test].mean()))
    report = {
        args.a_name: {"oof_mae": float(err_a.mean()), "fold_mae": fold_a},
        args.b_name: {"oof_mae": float(err_b.mean()), "fold_mae": fold_b},
        "per_review_wilcoxon_p_two_sided": float(wilcoxon(err_a, err_b).pvalue),
        "better": args.a_name if err_a.mean() < err_b.mean() else args.b_name,
        "stars_as_prediction_mae": float(np.abs(frame.rating - y).mean()),
        "n": len(frame),
    }
    atomic_json(paths.REPORTS / "experience_model_comparison.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
