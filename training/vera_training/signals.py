"""Fusion feature matrices for labelled reviews, built through PRODUCTION code.

Features come from :func:`app.ml.pipeline.extract_signals` and
:func:`app.ml.features.build_feature_vector` — the same functions the worker
calls — so there is no train/serve skew.

Two training-specific inputs:

* **Out-of-fold experience scores.** Agent 2 must not score reviews it was
  fine-tuned on, or fusion would learn to trust an overfit signal. Pass raw
  predictions from :func:`vera_training.finetune.crossfit_predictions`.
* **Metadata dropout (PRD §10.1, weakness #15).** API submissions never carry a
  timestamp and often lack votes / verified flags, so production always imputes
  some metadata. Training rows are masked with probability ``metadata_dropout``
  and calibration rows use ``metadata_dropout=1.0``, making the calibration
  distribution match production inputs.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from app.ml.agents.experience_extractor import ExperienceExtractor
from app.ml.agents.quality import IMPUTATION_KEYS, QualityAssessor
from app.ml.features import FEATURE_NAMES, build_feature_vector
from app.ml.pipeline import SignalAgents, extract_signals


def _optional_int(value: Any) -> int | None:
    return None if value is None or pd.isna(value) else int(value)


def _optional_bool(value: Any) -> bool | None:
    return None if value is None or pd.isna(value) else bool(value)


def imputation_means(frame: pd.DataFrame) -> dict[str, float]:
    """Training-set means of Agent 5's metadata components (stored in the fusion artifact)."""
    assessor = QualityAssessor(imputation=None)
    rows = []
    for row in frame.itertuples(index=False):
        votes = _optional_int(getattr(row, "helpful_vote", None))
        verified = _optional_bool(getattr(row, "verified_purchase", None))
        timestamp = _optional_int(getattr(row, "timestamp", None))
        if votes is None or verified is None or timestamp is None:
            continue  # means come only from fully observed rows
        rows.append(assessor.process(votes, verified, timestamp, word_count=0))
    if not rows:
        raise ValueError("No rows with complete metadata to compute imputation means")
    return {key: float(np.mean([r[key] for r in rows])) for key in IMPUTATION_KEYS}


def feature_matrix(
    frame: pd.DataFrame,
    agents: SignalAgents,
    experience_raw: Sequence[float],
    *,
    metadata_dropout: float,
    seed: int = 42,
    aspect_mentions: Sequence[dict[str, bool]] | None = None,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Build ``(X, agent_outputs)`` for every row of ``frame``.

    Args:
        frame: Columns ``text``, ``rating``, optional ``helpful_vote``,
            ``verified_purchase``, ``timestamp``, ``product_title``.
        agents: Agents with ``quality`` built from :func:`imputation_means`;
            ``experience`` may be ``None``.
        experience_raw: Out-of-fold raw Agent 2 outputs aligned with ``frame``.
        metadata_dropout: Probability of hiding a row's metadata (0 = never, 1 = always).
        aspect_mentions: Out-of-fold aspect detector decisions aligned with ``frame``;
            ``None`` lets Agent 3 detect mentions itself.
    """
    if len(experience_raw) != len(frame):
        raise ValueError("experience_raw must align with frame rows")
    if aspect_mentions is not None and len(aspect_mentions) != len(frame):
        raise ValueError("aspect_mentions must align with frame rows")
    if not 0.0 <= metadata_dropout <= 1.0:
        raise ValueError("metadata_dropout must be in [0, 1]")
    rng = np.random.default_rng(seed)

    vectors: list[np.ndarray] = []
    outputs: list[dict[str, Any]] = []
    for index, (row, raw) in enumerate(
        zip(frame.itertuples(index=False), experience_raw, strict=True)
    ):
        hide = bool(rng.random() < metadata_dropout)
        signals = extract_signals(
            agents,
            text=str(row.text),
            star_rating=float(getattr(row, "rating")),  # noqa: B009  (typed as Any)
            helpful_votes=None if hide else _optional_int(getattr(row, "helpful_vote", None)),
            verified_purchase=(
                None if hide else _optional_bool(getattr(row, "verified_purchase", None))
            ),
            timestamp_ms=None if hide else _optional_int(getattr(row, "timestamp", None)),
            product_title=str(getattr(row, "product_title", "") or ""),
            experience_output=ExperienceExtractor.output_from_raw(float(raw)),
            aspect_mentions=None if aspect_mentions is None else aspect_mentions[index],
        )
        vectors.append(build_feature_vector(signals))
        outputs.append(signals)
    matrix = np.vstack(vectors) if vectors else np.empty((0, len(FEATURE_NAMES)), np.float32)
    return matrix, outputs
