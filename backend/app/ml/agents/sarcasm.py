"""Agent 4 — Sarcasm & Rhetorical Irony Detector (Improvements §7.3).

Identifies deceptive praise where positive lexical phrases (e.g., 'masterpiece',
'worth the money', 'worth every penny', 'oh great', 'just what I needed', 'love how/the',
'can't wait to buy another') are contradicted by explicit product failure reports
('went silent', 'underwater', 'squeezes like a vice', 'cutting out', 'disconnect',
'dies', 'crashes', 'stopped working', 'disappointed twice').

When sarcasm is detected, it prevents the model from being misled by literal positive words,
calibrates aspect sentiment to reflect the true defects reported, and applies a calibrated
downgrade penalty to reflect true user dissatisfaction.
"""

from __future__ import annotations

import re
from typing import Any, Final


class SarcasmDetector:
    """Agent 4: Detect rhetorical irony and prevent positive score hijacking."""

    SARCASTIC_MARKERS: Final[tuple[re.Pattern[str], ...]] = (
        re.compile(r"\b(?:wow,?\s+)?what\s+a\s+(?:masterpiece|gem|treat|joke|disaster)\b", re.IGNORECASE),
        re.compile(r"\bmasterpiece\b", re.IGNORECASE),
        re.compile(r"\bwork\s+of\s+art\b", re.IGNORECASE),
        re.compile(r"\boh\s+great\b", re.IGNORECASE),
        re.compile(r"\bjust\s+what\s+i\s+needed\b", re.IGNORECASE),
        re.compile(r"\bthanks\s+for\s+nothing\b", re.IGNORECASE),
        re.compile(r"\b(?:especially|just|really)?\s*love\s+(?:how|when|that|the|it)\b", re.IGNORECASE),
        re.compile(r"\bso\s+glad\b", re.IGNORECASE),
        re.compile(r"\bwhat\s+a\s+joke\b", re.IGNORECASE),
        re.compile(r"\bwhat\s+a\s+treat\b", re.IGNORECASE),
        re.compile(r"\btruly\s+a\s+premium\b", re.IGNORECASE),
        re.compile(r"\b(?:absolutely\s+)?worth\s+(?:every\s+penny|the\s+money|it)\b", re.IGNORECASE),
        re.compile(r"\bcan[\'’]?t\s+wait\s+to\s+(?:buy\s+(?:a\s+second|another)|replace|be\s+disappointed|throw|return)\b", re.IGNORECASE),
        re.compile(r"\bdisappointed\s+(?:twice|again)\b", re.IGNORECASE),
        re.compile(r"\ba\s+joy\s+to\s+use\b", re.IGNORECASE),
        re.compile(r"\bbest\s+purchase\s+ever\b", re.IGNORECASE),
        re.compile(r"\babsolute\s+perfection\b", re.IGNORECASE),
        re.compile(r"\bwhat\s+more\s+could\s+you\s+ask\s+for\b", re.IGNORECASE),
    )

    DEFECT_MARKERS: Final[tuple[re.Pattern[str], ...]] = (
        re.compile(r"\bwent\s+silent\b", re.IGNORECASE),
        re.compile(r"\bno\s+sound\b", re.IGNORECASE),
        re.compile(r"\bsilent\b", re.IGNORECASE),
        re.compile(r"\bunderwater\b", re.IGNORECASE),
        re.compile(r"\bmuffled\b", re.IGNORECASE),
        re.compile(r"\bdistort(?:ed|ion)?\b", re.IGNORECASE),
        re.compile(r"\bsqueez(?:es|ed|ing)?\b", re.IGNORECASE),
        re.compile(r"\blike\s+a\s+vice\b", re.IGNORECASE),
        re.compile(r"\bclamp(?:ing)?\b", re.IGNORECASE),
        re.compile(r"\bhurts?\b", re.IGNORECASE),
        re.compile(r"\bpainful\b", re.IGNORECASE),
        re.compile(r"\bcut(?:s|ting)?\s+out\b", re.IGNORECASE),
        re.compile(r"\bdisconnect(?:s|ed|ing)?\b", re.IGNORECASE),
        re.compile(r"\bdie(?:s|d|ing)?\b", re.IGNORECASE),
        re.compile(r"\bcrash(?:es|ed|ing)?\b", re.IGNORECASE),
        re.compile(r"\bstopped\s+working\b", re.IGNORECASE),
        re.compile(r"\bquit\s+working\b", re.IGNORECASE),
        re.compile(r"\bbroke(?:n)?\b", re.IGNORECASE),
        re.compile(r"\bgarbage\b", re.IGNORECASE),
        re.compile(r"\btrash\b", re.IGNORECASE),
        re.compile(r"\bjunk\b", re.IGNORECASE),
        re.compile(r"\bdefective?\b", re.IGNORECASE),
        re.compile(r"\bdropping\s+connection\b", re.IGNORECASE),
        re.compile(r"\bunusable\b", re.IGNORECASE),
        re.compile(r"\bwaste\s+of\s+money\b", re.IGNORECASE),
        re.compile(r"\breturn(?:ed|ing)?\b", re.IGNORECASE),
        re.compile(r"\bdisappoint(?:ed|ing|ment)\b", re.IGNORECASE),
        re.compile(r"\bterrible\b", re.IGNORECASE),
        re.compile(r"\bhorrible\b", re.IGNORECASE),
        re.compile(r"\bawful\b", re.IGNORECASE),
        re.compile(r"\buseless\b", re.IGNORECASE),
    )

    ASPECT_DEFECT_MAP: Final[dict[str, tuple[re.Pattern[str], ...]]] = {
        "sound_quality": (
            re.compile(r"\b(?:left|right|one)?\s*(?:ear\s*cup|earbud|side)?\s*went\s+silent\b", re.IGNORECASE),
            re.compile(r"\bno\s+sound\b", re.IGNORECASE),
            re.compile(r"\bsilent\b", re.IGNORECASE),
            re.compile(r"\bstatic\b", re.IGNORECASE),
            re.compile(r"\bmuffled\b", re.IGNORECASE),
            re.compile(r"\bdistort(?:ed|ion)?\b", re.IGNORECASE),
            re.compile(r"\btinny\b", re.IGNORECASE),
            re.compile(r"\bmuddy\b", re.IGNORECASE),
        ),
        "comfort": (
            re.compile(r"\bsqueez(?:es|ed|ing)?\b", re.IGNORECASE),
            re.compile(r"\blike\s+a\s+vice\b", re.IGNORECASE),
            re.compile(r"\bclamp(?:ing)?\b", re.IGNORECASE),
            re.compile(r"\bhurts?\b", re.IGNORECASE),
            re.compile(r"\bpain(?:ful)?\b", re.IGNORECASE),
            re.compile(r"\bpressure\b", re.IGNORECASE),
            re.compile(r"\bsore\b", re.IGNORECASE),
            re.compile(r"\buncomfortable\b", re.IGNORECASE),
            re.compile(r"\bheavy\b", re.IGNORECASE),
        ),
        "fit": (
            re.compile(r"\bsqueez(?:es|ed|ing)?\b", re.IGNORECASE),
            re.compile(r"\blike\s+a\s+vice\b", re.IGNORECASE),
            re.compile(r"\bfall(?:s|ing)?\s+out\b", re.IGNORECASE),
            re.compile(r"\bloose\b", re.IGNORECASE),
            re.compile(r"\bwon[\'’]?t\s+stay\b", re.IGNORECASE),
        ),
        "connectivity": (
            re.compile(r"\bcut(?:s|ting)?\s+out\b", re.IGNORECASE),
            re.compile(r"\bdisconnect(?:s|ed|ing)?\b", re.IGNORECASE),
            re.compile(r"\bdropping\s+connection\b", re.IGNORECASE),
            re.compile(r"\bbluetooth\b", re.IGNORECASE),
            re.compile(r"\blatency\b", re.IGNORECASE),
            re.compile(r"\blag\b", re.IGNORECASE),
            re.compile(r"\bstutter(?:s|ing)?\b", re.IGNORECASE),
        ),
        "microphone": (
            re.compile(r"\bunderwater\b", re.IGNORECASE),
            re.compile(r"\bcan[\'’]?t\s+hear\s+me\b", re.IGNORECASE),
            re.compile(r"\bmuffled\b", re.IGNORECASE),
            re.compile(r"\becho(?:ing)?\b", re.IGNORECASE),
            re.compile(r"\bmic(?:rophone)?\b", re.IGNORECASE),
        ),
        "battery_life": (
            re.compile(r"\bdie(?:s|d|ing)?\b", re.IGNORECASE),
            re.compile(r"\bbattery\b", re.IGNORECASE),
            re.compile(r"\bdrain\b", re.IGNORECASE),
            re.compile(r"\bwon[\'’]?t\s+charge\b", re.IGNORECASE),
        ),
        "build_quality": (
            re.compile(r"\bbroke(?:n)?\b", re.IGNORECASE),
            re.compile(r"\bcrack(?:ed)?\b", re.IGNORECASE),
            re.compile(r"\bfell\s+apart\b", re.IGNORECASE),
            re.compile(r"\bflimsy\b", re.IGNORECASE),
            re.compile(r"\bdefective?\b", re.IGNORECASE),
        ),
        "value": (
            re.compile(r"\bdisappoint(?:ed|ing|ment)\b", re.IGNORECASE),
            re.compile(r"\bwaste\s+of\s+money\b", re.IGNORECASE),
            re.compile(r"\bworth\b", re.IGNORECASE),
            re.compile(r"\bmoney\b", re.IGNORECASE),
            re.compile(r"\bcan[\'’]?t\s+wait\s+to\s+buy\b", re.IGNORECASE),
            re.compile(r"\bmasterpiece\b", re.IGNORECASE),
        ),
    }

    def process(self, text: str, star_rating: float | None = None) -> dict[str, Any]:
        """Detect sarcasm in review text, flag defect categories, and assess downgrade penalty."""
        sarcasm_matches = [
            p.pattern.replace(r"\b", "").replace(r"\s+", " ").replace("(?:", "").replace(")?", "").replace("(", "").replace(")", "").replace("wow,?\\s+", "")
            for p in self.SARCASTIC_MARKERS
            if p.search(text)
        ]
        defect_matches = [
            p.pattern.replace(r"\b", "").replace(r"\s+", " ").replace("(?:", "").replace(")?", "").replace("(", "").replace(")", "")
            for p in self.DEFECT_MARKERS
            if p.search(text)
        ]

        n_sarcastic = len(sarcasm_matches)
        n_defects = len(defect_matches)

        # Check aspect-specific defect indicators
        affected_aspects: list[str] = []
        for aspect, patterns in self.ASPECT_DEFECT_MAP.items():
            if any(p.search(text) for p in patterns):
                affected_aspects.append(aspect)

        # Sarcasm condition:
        # 1. Sarcastic marker + defect marker
        # 2. Or high star rating (>= 4.0) with multiple severe defect mentions
        # 3. Or hyperbole positive words ("masterpiece", "love the bluetooth") + negative outcome ("disappointed twice", "went silent")
        is_sarcastic = False
        confidence = 0.0

        if n_sarcastic >= 1 and n_defects >= 1:
            is_sarcastic = True
            confidence = min(0.98, 0.75 + 0.06 * (n_sarcastic + n_defects))
        elif n_sarcastic >= 1 and len(affected_aspects) >= 2:
            is_sarcastic = True
            confidence = 0.88
        elif star_rating is not None and star_rating >= 4.0 and n_defects >= 2:
            is_sarcastic = True
            confidence = 0.86

        # If sarcastic, the true experience score is deeply negative (1.20 - 1.45)
        calibrated_score = 1.25 if (is_sarcastic and n_defects >= 2) else (1.45 if is_sarcastic else None)

        return {
            "has_irony_or_sarcasm": is_sarcastic,
            "confidence": round(confidence, 3),
            "sarcastic_markers": sarcasm_matches[:5],
            "defect_mentions": defect_matches[:5],
            "affected_aspects": affected_aspects,
            "calibrated_score": calibrated_score,
            "explanation": (
                f"Sarcasm detected ({round(confidence * 100)}% conf): {n_sarcastic} rhetorical praise marker(s) "
                f"contradicted by {n_defects} defect report(s)."
                if is_sarcastic
                else None
            ),
        }
