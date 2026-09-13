"""Fusion feature contract (PRD §10.1).

This module is the SINGLE source of truth for the 40-dimensional feature vector.
Notebook 05 (training), notebook 06 (calibration), and the production pipeline
all call :func:`build_feature_vector`, so train/serve skew is impossible by
construction. Changing the order or meaning of any feature requires retraining
the ensemble and re-fitting the calibrator.

Imputation of missing metadata happens upstream in Agent 5
(:class:`~app.ml.agents.quality.QualityAssessor`); the PRD's
``build_feature_vector(imputation=...)`` parameter was never actually used.
"""

from __future__ import annotations

from typing import Any, Final

import numpy as np

from app.ml.constants import EARBUD_ASPECTS, SENTIMENT_TO_NUMERIC

FEATURE_NAMES: Final[tuple[str, ...]] = (
    # Base signals (3)
    "star_rating",
    "experience_score",
    "domain_score",
    # Consistency signals (4)
    "star_text_gap",
    "absolute_gap",
    "star_inflated",
    "consistency_score",
    # Quality signals (4)
    "quality_score",
    "helpfulness_score",
    "freshness_score",
    "verified_purchase",
    # Text quality signals (4)
    "word_count_norm",
    "vocab_richness",
    "avg_sentence_length_norm",
    "experience_model_uncertainty",
    # Aspect detection (10) + aspect sentiment (10)
    *(f"aspect_detected__{a}" for a in EARBUD_ASPECTS),
    *(f"aspect_sentiment__{a}" for a in EARBUD_ASPECTS),
    # Interactions (5)
    "star_x_experience",
    "abs_star_minus_domain",
    "experience_x_quality",
    "consistency_x_trust",
    "domain_confidence_x_domain_score",
)

N_FEATURES: Final = len(FEATURE_NAMES)

#: Feature-name groups used by the ablation study (PRD §13.2).
FEATURE_GROUPS: Final[dict[str, tuple[str, ...]]] = {
    "star": ("star_rating",),
    "experience": ("experience_score", "experience_model_uncertainty", "star_x_experience"),
    "domain": ("domain_score", "abs_star_minus_domain", "domain_confidence_x_domain_score"),
    "consistency": ("star_text_gap", "absolute_gap", "star_inflated", "consistency_score"),
    "quality": (
        "quality_score",
        "helpfulness_score",
        "freshness_score",
        "verified_purchase",
        "word_count_norm",
        "vocab_richness",
        "avg_sentence_length_norm",
        "experience_x_quality",
        "consistency_x_trust",
    ),
    "absa": tuple(n for n in FEATURE_NAMES if n.startswith("aspect_")),
}


def build_feature_vector(agent_outputs: dict[str, Any]) -> np.ndarray:
    """Assemble the fusion features from Agents 1–6.

    Args:
        agent_outputs: Mapping with keys ``preprocessor``, ``experience_extractor``,
            ``absa``, ``consistency``, ``quality``, ``domain_rating`` (each the
            agent's ``process``/``predict`` output) and ``star_rating``.

    Returns:
        ``float32`` array of shape ``(N_FEATURES,)``.
    """
    pre = agent_outputs["preprocessor"]
    exp = agent_outputs["experience_extractor"]
    absa = agent_outputs["absa"]["aspects"]
    cons = agent_outputs["consistency"]
    qual = agent_outputs["quality"]
    dom = agent_outputs["domain_rating"]
    star = float(agent_outputs["star_rating"])

    feats: list[float] = [
        star,
        exp["predicted_score"],
        dom["domain_score"],
        cons["star_text_gap"],
        cons["absolute_gap"],
        float(cons["star_inflated"]),
        cons["consistency_score"],
        qual["quality_score"],
        qual["helpfulness_score"],
        qual["freshness_score"],
        float(qual["verified_purchase"]),
        pre["word_count"] / 500,
        pre["vocab_richness"],
        pre["avg_sentence_length"] / 20,
        exp["model_uncertainty"],
    ]
    feats += [float(absa[a]["detected"]) for a in EARBUD_ASPECTS]
    feats += [float(SENTIMENT_TO_NUMERIC[absa[a]["sentiment"]]) for a in EARBUD_ASPECTS]
    feats += [
        star * exp["predicted_score"],
        abs(star - dom["domain_score"]),
        exp["predicted_score"] * qual["quality_score"],
        cons["consistency_score"] * qual["trust_weight"],
        dom["domain_confidence"] * dom["domain_score"],
    ]

    vector = np.asarray(feats, dtype=np.float32)
    if vector.shape != (N_FEATURES,):  # guards against silent contract drift
        raise AssertionError(f"feature vector has {vector.shape[0]} dims, expected {N_FEATURES}")
    return vector
