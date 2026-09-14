"""Build data/processed/earbud_reviews.parquet from the raw JSONL files (notebook 01, step 2).

    .venv\\Scripts\\python.exe training\\scripts\\prepare_corpus.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "training")]

from vera_training import paths  # noqa: E402
from vera_training.data import prepare_corpus_from_files  # noqa: E402


def main() -> None:
    paths.ensure_dirs()
    started = time.time()
    corpus = prepare_corpus_from_files(
        paths.RAW / "Electronics.jsonl", paths.RAW / "meta_Electronics.jsonl", min_words=20
    )
    corpus.to_parquet(paths.CORPUS, index=False)
    stats = {
        "reviews": len(corpus),
        "products": int(corpus.parent_asin.nunique()),
        "star_share": corpus.rating.value_counts(normalize=True).sort_index().round(4).to_dict(),
        "minutes": round((time.time() - started) / 60, 1),
    }
    (paths.REPORTS / "corpus_stats.json").write_text(json.dumps(stats, indent=2, default=str))
    print(json.dumps(stats, indent=2, default=str), flush=True)


if __name__ == "__main__":
    main()
