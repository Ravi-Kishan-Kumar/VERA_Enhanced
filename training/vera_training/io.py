"""Strict input handling and atomic checkpoints for offline workflows."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import pandas as pd


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


#: Windows refuses to replace a file another process has open (a reader, antivirus, indexer).
REPLACE_ATTEMPTS = 20
REPLACE_BACKOFF_SECONDS = 0.25


def atomic_json(path: str | Path, value: Any) -> None:
    """Write JSON via temp file + ``os.replace`` so readers never see a partial file.

    ``os.replace`` is retried on ``PermissionError`` for up to ~5 s: on Windows a
    concurrent reader (e.g. ``label_status.py``) briefly locks the destination.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(REPLACE_ATTEMPTS):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(REPLACE_BACKOFF_SECONDS)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError as error:
                    raise ValueError(f"Invalid JSON in {path}, line {line_number}") from error
    return rows


def load_frame(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".csv":
        return pd.read_csv(path, dtype={"review_id": str, "parent_asin": str})
    return pd.DataFrame(read_jsonl(path))


def validate_reviews(frame: pd.DataFrame, *, labels: bool = False) -> pd.DataFrame:
    required = {"review_id", "parent_asin", "text", "rating"}
    if labels:
        required.add("experience_score")
    if missing := required - set(frame.columns):
        raise ValueError(f"Missing review columns: {sorted(missing)}")
    frame = frame.copy().reset_index(drop=True)
    if frame.empty or frame[list(required)].isna().any().any():
        raise ValueError("Reviews must be nonempty and required values must not be null")
    for name in ("review_id", "parent_asin", "text"):
        frame[name] = frame[name].astype(str).str.strip()
        if frame[name].eq("").any():
            raise ValueError(f"Empty {name}")
    if frame.review_id.duplicated().any():
        raise ValueError("Duplicate review_id")
    frame["rating"] = pd.to_numeric(frame.rating, errors="raise")
    if not frame.rating.isin([1, 2, 3, 4, 5]).all():
        raise ValueError("Ratings must be integer stars in [1, 5]")
    # Raw LLM labels are half-steps; a two-model consensus mean can be a quarter-step.
    if labels and not frame.experience_score.isin([1 + i / 4 for i in range(17)]).all():
        raise ValueError("Experience labels must be quarter-step scores in [1, 5]")
    return frame
