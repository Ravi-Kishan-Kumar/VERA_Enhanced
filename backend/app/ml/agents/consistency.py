"""Agent 4 — Star-Text Consistency Scorer (PRD §9, Agent 4).

Measures how far the clicked star rating is from the text-derived experience
score. A large gap means the star is unreliable.
"""

from __future__ import annotations

from typing import Any, Final

from app.ml.constants import SCORE_RANGE

#: Gap (in stars) beyond which the star is flagged as inflated / deflated.
INFLATION_THRESHOLD: Final = 1.0


class ConsistencyScorer:
    """Agent 4: star vs text agreement."""

    @staticmethod
    def process(star_rating: float, experience_score: float) -> dict[str, Any]:
        """Compare the star with Agent 2's score.

        Returns:
            ``star_text_gap`` (positive = star higher than text), its absolute
            value, inflation/deflation flags, ``consistency_score`` in [0, 1]
            (1 = perfect agreement; max gap on a 1–5 scale is 4), and
            ``star_trust_weight`` = consistency² (downweights stars harder).
        """
        gap = float(star_rating) - float(experience_score)
        abs_gap = abs(gap)
        consistency = max(0.0, 1.0 - abs_gap / SCORE_RANGE)
        return {
            "star_text_gap": round(gap, 3),
            "absolute_gap": round(abs_gap, 3),
            "star_inflated": gap > INFLATION_THRESHOLD,
            "star_deflated": gap < -INFLATION_THRESHOLD,
            "consistency_score": round(consistency, 3),
            "star_trust_weight": round(consistency**2, 3),
        }
