"""Agent 1 — Text Preprocessor (PRD §9, Agent 1).

Gates downstream agents with clean text, language detection, an earbud
contamination check, and text-quality metrics.

DESIGN CONSTRAINT: zero torch / transformers imports. Loading
SentenceTransformer here would add ~350 MB RAM and blow Render's 512 MB limit.
Instead: ``langdetect`` (pure Python) + a tiny sklearn TF-IDF over anchor
phrases + word-boundary keyword matching.
"""

from __future__ import annotations

import html
import re
from typing import Any, Final

from langdetect import DetectorFactory, detect
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DetectorFactory.seed = 42  # make langdetect deterministic

_URL_RE: Final = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_BREAK_TAG_RE: Final = re.compile(r"<\s*(?:br|/p|p)\s*/?\s*>", re.IGNORECASE)
_TAG_RE: Final = re.compile(r"<[^>]+>")
_WS_RE: Final = re.compile(r"\s+")
_SENTENCE_SPLIT_RE: Final = re.compile(r"[.!?]+")

#: Minimum characters for langdetect to be meaningful (PRD weakness #14).
MIN_LANGDETECT_CHARS: Final = 10
#: TF-IDF cosine threshold for the body-text earbud check.
EARBUD_SIMILARITY_THRESHOLD: Final = 0.25


class TextPreprocessor:
    """Agent 1: clean, validate, and characterise review text."""

    EARBUD_KEYWORDS: Final[tuple[str, ...]] = (
        "earbud",
        "earbuds",
        "earphone",
        "earphones",
        "in-ear",
        "headphone",
        "headphones",
        "headset",
        "tws",
        "true wireless",
        "noise cancel",
        "noise cancelling",
        "noise canceling",
        "airpod",
        "airpods",
        "bluetooth ear",
        "over-ear",
        "on-ear",
        "anc",
        "wireless ear",
    )

    #: Anchor phrases for the TF-IDF cosine fallback (no model download).
    _ANCHORS: Final[tuple[str, ...]] = (
        "sound quality is great",
        "bass is powerful",
        "noise cancellation works",
        "battery life lasts hours",
        "fit in my ear comfortably",
        "earbud fell out",
        "earphone sounds",
        "in-ear headphone",
        "bluetooth connection drops",
        "microphone quality for calls",
        "charging case",
        "pairing device",
    )

    def __init__(self) -> None:
        # Tiny TF-IDF fitted once on the anchors (~KBs of RAM).
        self._vec = TfidfVectorizer(ngram_range=(1, 2), max_features=2000)
        self._vec.fit(self._ANCHORS)
        self._anchor_matrix = self._vec.transform(self._ANCHORS)
        # Word-boundary match: "anc" must not fire on "dance" / "balance".
        self._keyword_re = re.compile(
            r"\b(?:" + "|".join(re.escape(k) for k in self.EARBUD_KEYWORDS) + r")\b",
            re.IGNORECASE,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def clean_text(text: str) -> str:
        """Strip URLs and HTML, unescape entities, and normalise whitespace.

        Line-break tags become spaces first — Amazon reviews use ``<br />``
        heavily and removing it outright glues adjacent words together.
        """
        text = html.unescape(text or "")
        text = _URL_RE.sub(" ", text)
        text = _BREAK_TAG_RE.sub(" ", text)
        text = _TAG_RE.sub(" ", text)
        return _WS_RE.sub(" ", text).strip()

    @staticmethod
    def detect_language(text: str) -> str:
        """Return an ISO 639-1 code; fail open to ``'en'``.

        langdetect raises on very short, emoji-only, or punctuation-only text.
        Those are expected inputs, not retryable errors, so they must never
        crash a Celery task (PRD weakness #14).
        """
        cleaned = text.strip()
        if len(cleaned) < MIN_LANGDETECT_CHARS:
            return "en"
        try:
            return str(detect(cleaned[:500]))
        except Exception:
            return "en"

    def is_earbud_content(self, text: str, title: str | None) -> tuple[bool, float]:
        """Two-stage contamination filter.

        Stage 1: word-boundary keyword match on title + first 200 body chars.
        Stage 2: max TF-IDF cosine between body text and earbud anchor phrases.

        Returns:
            ``(is_earbud, confidence)`` where confidence is 1.0 for a keyword hit.
        """
        combined = f"{title or ''} {text[:200]}"
        if self._keyword_re.search(combined):
            return True, 1.0

        text_vec = self._vec.transform([text[:500]])
        max_sim = float(cosine_similarity(text_vec, self._anchor_matrix)[0].max())
        return max_sim > EARBUD_SIMILARITY_THRESHOLD, round(max_sim, 4)

    @staticmethod
    def quality_metrics(text: str) -> dict[str, Any]:
        """Length and lexical-diversity metrics on cleaned text."""
        words = text.split()
        sentences = [s for s in (p.strip() for p in _SENTENCE_SPLIT_RE.split(text)) if len(s) > 3]
        n_words = len(words)
        n_sentences = max(len(sentences), 1)
        return {
            "word_count": n_words,
            "sentence_count": n_sentences,
            "avg_sentence_length": n_words / n_sentences,
            "vocab_richness": len({w.lower() for w in words}) / max(n_words, 1),
        }

    def process(self, text: str, title: str | None = "") -> dict[str, Any]:
        """Run Agent 1 on raw review text.

        ``has_url`` is computed on the RAW text: the PRD computed it after URLs
        were stripped, so it was always ``False``.
        """
        raw = text or ""
        clean = self.clean_text(raw)
        lang = self.detect_language(clean)
        is_earbud, earbud_conf = self.is_earbud_content(clean, title)
        return {
            "clean_text": clean,
            "language": lang,
            "is_english": lang == "en",
            "is_earbud": is_earbud,
            "earbud_confidence": earbud_conf,
            "has_url": bool(_URL_RE.search(raw)),
            **self.quality_metrics(clean),
        }
