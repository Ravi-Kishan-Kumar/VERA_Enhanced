"""Resumable LLM labeling driver (notebooks 02–03 equivalent for long unattended runs).

Examples (from repo root):
    # 1. Build the balanced-order pool once
    .venv\\Scripts\\python.exe training\\scripts\\run_labeling.py pool --size 4000

    # 2. Primary labels for pool rows [0, 2000)
    .venv\\Scripts\\python.exe training\\scripts\\run_labeling.py label --run-id primary-a \\
        --start 0 --count 2000 --model openai/gpt-oss-120b --seed 1

Each (run-id) has its own checkpoint in data/labels/; re-running resumes. The run stops
cleanly (exit 0, checkpoint saved) when all keys exhaust their daily quota.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "training")]
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pandas as pd  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from vera_training import labeling, paths  # noqa: E402
from vera_training.data import sample_for_labeling  # noqa: E402

load_dotenv(ROOT / ".env")


def build_pool(size: int, seed: int) -> None:
    if paths.LABELING_POOL.exists():
        sys.exit(f"{paths.LABELING_POOL} exists; refusing to resample (it would orphan labels)")
    corpus = pd.read_parquet(paths.CORPUS)
    pool = sample_for_labeling(corpus, n=size, seed=seed, product_cap=5, balanced_order=True)
    pool.to_parquet(paths.LABELING_POOL, index=False)
    print(f"pool: {len(pool)} rows, {pool.parent_asin.nunique()} products")
    print(pool.rating.value_counts().sort_index().to_string())


def label_until_done(*args: Any, pause_seconds: int = 1800) -> None:
    """Repeat :func:`label` across quota cooldowns until every row is labelled."""
    while True:
        remaining = label(*args)
        if remaining == 0:
            return
        print(
            f"{remaining} rows left; quota cooling down, retrying in {pause_seconds}s", flush=True
        )
        time.sleep(pause_seconds)


def label(run_id: str, start: int, count: int, model: str, seed: int, rows: str | None) -> int:
    """Label a pool slice (or explicit ids); returns how many rows are still unlabelled."""
    pool = pd.read_parquet(paths.LABELING_POOL)
    if rows:  # explicit review_id list (agreement subsets)
        ids = Path(rows).read_text(encoding="utf-8").split()
        frame = pool.set_index("review_id").loc[ids].reset_index()
    else:
        frame = pool.iloc[start : start + count]
    provider = labeling.GroqPool(model, labeling.groq_keys_from_env())
    checkpoint = paths.LABELS / f"run_{run_id}.json"
    state = labeling.run_labels(
        frame,
        checkpoint,
        provider,
        provider_name="groq",
        model=model,
        run_id=run_id,
        seed=seed,
        max_requests=int(len(frame) * 1.3) + 10,
        requests_per_minute=600,  # GroqPool paces by tokens; this only adds a tiny gap
        retries=3,
    )
    print(
        f"{run_id}: {len(state['labels'])}/{len(frame)} labelled, "
        f"{state['requests']} requests, {len(state['errors'])} rows with errors",
        flush=True,
    )
    return len(frame) - len(state["labels"])


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    pool = sub.add_parser("pool")
    pool.add_argument("--size", type=int, default=4000)
    pool.add_argument("--seed", type=int, default=42)
    run = sub.add_parser("label")
    run.add_argument("--run-id", required=True)
    run.add_argument("--start", type=int, default=0)
    run.add_argument("--count", type=int, default=2000)
    run.add_argument("--model", default="openai/gpt-oss-120b")
    run.add_argument("--seed", type=int, default=1)
    run.add_argument("--rows", help="file with whitespace-separated review_ids")
    run.add_argument("--until-done", action="store_true", help="keep retrying across cooldowns")
    args = parser.parse_args()
    if args.command == "pool":
        build_pool(args.size, args.seed)
        return
    call = (args.run_id, args.start, args.count, args.model, args.seed, args.rows)
    if args.until_done:
        label_until_done(*call)
    else:
        label(*call)


if __name__ == "__main__":
    main()
