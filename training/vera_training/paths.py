"""Canonical data/model locations shared by every notebook."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
LABELS = DATA / "labels"
MODELS = DATA / "models"
REPORTS = REPO_ROOT / "reports"

CORPUS = PROCESSED / "earbud_reviews.parquet"
LABELING_POOL = PROCESSED / "labeling_pool.parquet"
PRIMARY_RUN = LABELS / "run_primary.json"
CONSISTENCY_RUN = LABELS / "run_consistency.json"
HUMAN_SHEET = LABELS / "human_annotations.csv"
AGREEMENT_REPORT = LABELS / "agreement_report.json"
LABELS_V1 = LABELS / "labels_v1.jsonl"
EXPERIENCE_OOF = LABELS / "experience_oof.csv"
FUSION_CACHE = PROCESSED / "fusion_cache.joblib"


def ensure_dirs() -> None:
    for directory in (RAW, PROCESSED, LABELS, MODELS, REPORTS):
        directory.mkdir(parents=True, exist_ok=True)
