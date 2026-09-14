"""Download the raw Amazon Reviews 2023 Electronics files into data/raw/ (resumable).

    .venv\\Scripts\\python.exe training\\scripts\\download_corpus.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from huggingface_hub import hf_hub_download

from vera_training import paths

REPO = "McAuley-Lab/Amazon-Reviews-2023"
FILES = (
    "raw/meta_categories/meta_Electronics.jsonl",
    "raw/review_categories/Electronics.jsonl",
)


def main() -> None:
    paths.ensure_dirs()
    for repo_path in FILES:
        target = paths.RAW / Path(repo_path).name
        if target.exists():
            print(f"exists: {target} ({target.stat().st_size / 1e9:.2f} GB)", flush=True)
            continue
        started = time.time()
        print(f"downloading {repo_path} ...", flush=True)
        downloaded = Path(
            hf_hub_download(REPO, repo_path, repo_type="dataset", local_dir=paths.RAW)
        )
        downloaded.replace(target)
        print(f"done {target} in {(time.time() - started) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
