"""Agent 5 — Review Quality Assessor (PRD §9, Agent 5).

Interpretable heuristics (not a learned model) scoring how trustworthy a review
is as a signal. The result weights reviews in product aggregation.

Fixes vs the PRD sketch (see DECISIONS.md):
* The PRD formula referenced ``quality_score`` inside its own definition via a
  ``'quality_score' in dir()`` hack (always False there) and double-counted the
  verified flag. The composite is now a plain weighted average.
* ``exp(-age/730)`` is an e-folding time, not a "2-year half-life".
  Freshness now uses ``0.5 ** (age / 730)``, and future dates clip to age 0
  (previously produced freshness > 1).
* Missing metadata (``None``) is imputed with training-set means stored in the
  fusion artifact, never hard zeros (PRD §10.1, weakness #15).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any, Final

#: Dataset end date — freshness reference point for timestamped corpus reviews.
CUTOFF_DATE: Final = datetime(2023, 9, 1, tzinfo=UTC)
FRESHNESS_HALF_LIFE_DAYS: Final = 730.0
HELPFUL_VOTES_SATURATION: Final = 100
LENGTH_SATURATION_WORDS: Final = 500

WEIGHTS: Final[dict[str, float]] = {
    "helpfulness": 0.35,
    "freshness": 0.25,
    "length": 0.25,
    "verified": 0.15,
}
QUALITY_FLOOR: Final = 0.05

#: Keys the imputation mapping must provide (training-set means of the agent outputs).
IMPUTATION_KEYS: Final[tuple[str, ...]] = (
    "helpfulness_score",
    "freshness_score",
    "verified_purchase",
)


def _clip01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


class QualityAssessor:
    """Agent 5: metadata -> trust weight."""

    def __init__(self, imputation: dict[str, float] | None = None) -> None:
        """
        Args:
            imputation: Training-set means for :data:`IMPUTATION_KEYS`, loaded
                from ``fusion_ensemble.json``. May be ``None`` only when every
                review carries full metadata (the offline training corpus).
        """
        if imputation is not None:
            absent = [k for k in IMPUTATION_KEYS if k not in imputation]
            if absent:
                raise ValueError(f"imputation mapping missing keys: {absent}")
        self.imputation = imputation

    def _impute(self, key: str) -> float:
        if self.imputation is None:
            raise ValueError(
                f"Metadata for {key!r} is missing and no imputation means were provided"
            )
        return float(self.imputation[key])

    @staticmethod
    def helpfulness(helpful_votes: int) -> float:
        """Log-normalised helpful votes, saturating at 100 votes."""
        votes = max(int(helpful_votes), 0)
        return _clip01(math.log1p(votes) / math.log1p(HELPFUL_VOTES_SATURATION))

    @staticmethod
    def freshness(timestamp_ms: int) -> float:
        """True half-life decay relative to :data:`CUTOFF_DATE`."""
        review_date = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
        age_days = max((CUTOFF_DATE - review_date).days, 0)
        return float(0.5 ** (age_days / FRESHNESS_HALF_LIFE_DAYS))

    def process(
        self,
        helpful_votes: int | None,
        verified: bool | None,
        timestamp_ms: int | None,
        word_count: int,
    ) -> dict[str, Any]:
        """Score one review; ``None`` inputs are imputed with training means."""
        imputed: list[str] = []

        if helpful_votes is None:
            help_score = self._impute("helpfulness_score")
            imputed.append("helpful_votes")
        else:
            help_score = self.helpfulness(helpful_votes)

        if timestamp_ms is None:
            fresh_score = self._impute("freshness_score")
            imputed.append("timestamp")
        else:
            fresh_score = self.freshness(timestamp_ms)

        if verified is None:
            verified_score = self._impute("verified_purchase")
            imputed.append("verified_purchase")
        else:
            verified_score = 1.0 if verified else 0.0

        length_score = _clip01(max(word_count, 0) / LENGTH_SATURATION_WORDS)

        quality = (
            WEIGHTS["helpfulness"] * help_score
            + WEIGHTS["freshness"] * fresh_score
            + WEIGHTS["length"] * length_score
            + WEIGHTS["verified"] * verified_score
        )
        quality = min(max(quality, QUALITY_FLOOR), 1.0)

        return {
            "helpfulness_score": round(help_score, 3),
            "freshness_score": round(fresh_score, 3),
            "length_score": round(length_score, 3),
            "verified_purchase": round(verified_score, 3),
            "quality_score": round(quality, 3),
            "trust_weight": round(quality, 3),
            "imputed_fields": imputed,
        }
