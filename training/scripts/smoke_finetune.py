"""GPU smoke test: 1-epoch fine-tune on whatever primary labels exist (checks VRAM + pipeline).

    .venv\\Scripts\\python.exe training\\scripts\\smoke_finetune.py
Writes nothing into data/models; uses data/processed/smoke_finetune/ (deleted afterwards).
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "training")]
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pandas as pd  # noqa: E402
import torch  # noqa: E402

from vera_training import paths  # noqa: E402
from vera_training.finetune import FinetuneConfig, predict_texts, train_regressor  # noqa: E402
from vera_training.labeling import ExperienceLabel  # noqa: E402
from vera_training.splits import holdout  # noqa: E402


def main() -> None:
    state = json.loads((paths.LABELS / "run_primary-a.json").read_text(encoding="utf-8"))
    scores = {k: ExperienceLabel.model_validate(v).experience_score for k, v in state["labels"].items()}
    pool = pd.read_parquet(paths.LABELING_POOL)
    frame = pool[pool.review_id.isin(scores)].copy()
    frame["experience_score"] = frame.review_id.map(scores)
    train, validation = holdout(frame.reset_index(drop=True), 0.2, 0)
    config = dataclasses.replace(FinetuneConfig.small_gpu(), epochs=1)
    work = paths.PROCESSED / "smoke_finetune"
    torch.cuda.reset_peak_memory_stats()
    started = time.time()
    model_dir = train_regressor(train, validation, work, config)
    preds = predict_texts(model_dir, validation.text.tolist()[:16], max_length=config.max_length)
    print(json.dumps({
        "train_rows": len(train),
        "seconds": round(time.time() - started, 1),
        "seconds_per_train_row": round((time.time() - started) / max(len(train), 1), 3),
        "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
        "sample_predictions": [round(float(p), 2) for p in preds[:5]],
        "validation": json.loads((model_dir / "vera_training.json").read_text())["validation"],
    }, indent=2))
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
