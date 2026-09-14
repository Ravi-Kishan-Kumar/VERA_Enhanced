"""Zip everything notebook 04 needs on Colab: code + frozen labels (no secrets, no raw data).

    .venv\\Scripts\\python.exe training\\scripts\\make_colab_bundle.py
    -> dist/vera_colab_bundle.zip  (upload to Colab's /content, or to Drive MyDrive/vera/)
"""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INCLUDE_DIRS = ("backend/app", "training/vera_training", "training/scripts")
INCLUDE_FILES = (
    "training/requirements-colab.txt",
    "data/labels/labels_v1.jsonl",
    "PRD.md",
)


def main() -> None:
    target = ROOT / "dist" / "vera_colab_bundle.zip"
    target.parent.mkdir(exist_ok=True)
    missing = [f for f in INCLUDE_FILES if not (ROOT / f).exists()]
    if missing:
        raise SystemExit(f"Missing (run labeling + train_all --stages labels first): {missing}")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for directory in INCLUDE_DIRS:
            for path in (ROOT / directory).rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts:
                    archive.write(path, path.relative_to(ROOT))
        for name in INCLUDE_FILES:
            archive.write(ROOT / name, name)
    print(f"wrote {target} ({target.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
