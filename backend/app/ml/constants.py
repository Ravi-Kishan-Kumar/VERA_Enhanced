"""Constants shared by production agents, the training package, and tests.

Aspect keys are snake_case everywhere (API, DB JSON, features, labels). The
natural-language phrase in :data:`ASPECT_PHRASES` is only used as the second
sentence fed to the ABSA model.
"""

from __future__ import annotations

from typing import Final, Literal

#: Canonical, ordered aspect keys. ORDER IS PART OF THE FUSION FEATURE CONTRACT —
#: never reorder without retraining the ensemble.
EARBUD_ASPECTS: Final[tuple[str, ...]] = (
    "sound_quality",
    "bass",
    "battery_life",
    "comfort",
    "fit",
    "build_quality",
    "connectivity",
    "microphone",
    "noise_cancellation",
    "value",
)

#: Aspect key -> phrase given to the ABSA model as the aspect sentence.
ASPECT_PHRASES: Final[dict[str, str]] = {key: key.replace("_", " ") for key in EARBUD_ASPECTS}

#: Keyword pre-filter per aspect. Matched on word boundaries at the START of a
#: word (so "isolat" matches "isolation" but "fit" does not match "benefit").
#: "cheap" is deliberately only under `value`: "cheap plastic" is still caught
#: by `build_quality` through "plastic".
ASPECT_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "sound_quality": (
        "sound",
        "audio",
        "music",
        "clarity",
        "treble",
        "highs",
        "mids",
        "tinny",
        "muddy",
    ),
    "bass": ("bass", "low end", "boom", "thump", "sub-bass", "subwoofer"),
    "battery_life": ("battery", "charge", "charging", "playtime", "endurance", "hours of"),
    "comfort": ("comfort", "uncomfortable", "ear pain", "hurt", "wear", "wearing", "sore"),
    "fit": ("fit", "fits", "stay in", "stays in", "fall out", "falls out", "ear tip", "seal"),
    # Durability counts as build quality in the labeling protocol ("broke after a week",
    # "connector bent"), which the original 7 keywords missed (train-split recall 0.35).
    "build_quality": (
        "build",
        "built",
        "construct",
        "durab",
        "sturd",
        "flims",
        "fragil",
        "well made",
        "well-made",
        "cheaply made",
        "poorly made",
        "plastic",
        "material",
        "hinge",
        "crack",
        "broke",
        "break",
        "snapped",
        "fell apart",
        "falling apart",
        "came apart",
        "cord",
        "cable",
        "wire",
        "jack",
        "connector",
        "stopped working",
        "quit working",
        "died",
        "defect",
        "peel",
        "wore out",
        "worn out",
    ),
    # "pair" / "range" were removed: "a pair of headphones" and "price range" made
    # connectivity precision 0.52 on the train split.
    "connectivity": (
        "bluetooth",
        "connect",
        "disconnect",
        "reconnect",
        "pairing",
        "paired",
        "pair with",
        "pair to",
        "latency",
        "lag",
        "delay",
        "drops out",
        "dropped out",
        "dropout",
        "cuts out",
        "cutting out",
        "signal",
        "out of range",
        "sync",
        "stutter",
        "multipoint",
    ),
    "microphone": ("mic", "microphone", "calls", "phone call", "voice", "recording"),
    "noise_cancellation": (
        "anc",
        "noise cancel",
        "noise-cancel",
        "passive isolation",
        "isolat",
        "block out",
        "blocks out",
        "transparency mode",
    ),
    "value": ("price", "value", "worth", "money", "cheap", "expensive", "cost", "budget"),
}

Sentiment = Literal["positive", "negative", "neutral", "not_mentioned"]

#: Numeric encoding of aspect sentiment for fusion features (PRD §10.1).
SENTIMENT_TO_NUMERIC: Final[dict[str, int]] = {
    "negative": -1,
    "neutral": 0,
    "positive": 1,
    "not_mentioned": 0,
}

#: Valid experience-score label values produced by the labeler (PRD §7.2).
LABEL_SCORE_VALUES: Final[tuple[float, ...]] = (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0)

SCORE_MIN: Final[float] = 1.0
SCORE_MAX: Final[float] = 5.0
#: Largest possible distance on the 1–5 scale.
SCORE_RANGE: Final[float] = SCORE_MAX - SCORE_MIN
