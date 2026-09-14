"""Export Agent 3 (pre-trained ABSA) to INT8 ONNX with parity checks (notebook 04, ABSA section).

    .venv\\Scripts\\python.exe training\\scripts\\export_absa.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "training")]
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from vera_training import paths  # noqa: E402
from vera_training.export import export_absa  # noqa: E402

SAMPLES = [
    ("The sound quality is incredible but the battery barely lasts two hours.", "battery life"),
    ("The sound quality is incredible but the battery barely lasts two hours.", "sound quality"),
    ("They fall out of my ears every time I run, the fit is terrible.", "fit"),
    ("Great value for the price, I would buy again.", "value"),
    ("Bluetooth keeps disconnecting from my phone.", "connectivity"),
    ("Mic is okay for calls, nothing special.", "microphone"),
    ("Noise cancellation blocks out the train completely, amazing.", "noise cancellation"),
    ("Bass is muddy and overpowering, drowns the vocals.", "bass"),
    ("Comfortable enough to wear all day at work.", "comfort"),
    ("Cheap plastic, the hinge broke after a week.", "build quality"),
]


def main() -> None:
    paths.ensure_dirs()
    # Every sample text paired with every aspect phrase: 10 x 10 = 100 parity pairs.
    texts = [t for t, _ in SAMPLES]
    phrases = sorted({a for _, a in SAMPLES})
    pairs = [(t, a) for t in texts for a in phrases]
    report = export_absa(
        paths.MODELS,
        [t for t, _ in pairs],
        [a for _, a in pairs],
        work_dir=paths.PROCESSED / "onnx_work",
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
