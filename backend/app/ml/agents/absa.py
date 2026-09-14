"""Agent 3 — Aspect-Based Sentiment Analysis (PRD §9, Agent 3).

Uses ``yangheng/deberta-v3-base-absa-v1.1`` exported to ONNX, unchanged (no
fine-tuning). A word-boundary keyword pre-filter decides which of the 10 earbud
aspects are mentioned; the model then classifies sentiment for those aspects in
ONE batched inference call.

Input format: ``[CLS] review_text [SEP] aspect [SEP]`` — review FIRST, aspect
SECOND (PRD weakness #4). Only the review is ever truncated.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np

from app.ml.constants import ASPECT_KEYWORDS, ASPECT_PHRASES, EARBUD_ASPECTS
from app.ml.models.onnx_session import InferenceSessionLike, build_feed, create_session, softmax
from app.ml.models.tokenizer_wrapper import LightTokenizer

_VALID_SENTIMENTS = frozenset({"negative", "neutral", "positive"})


def _compile_keyword_patterns() -> dict[str, re.Pattern[str]]:
    """One regex per aspect; keywords must start at a word boundary."""
    return {
        aspect: re.compile(
            r"\b(?:" + "|".join(re.escape(kw) for kw in ASPECT_KEYWORDS[aspect]) + r")",
            re.IGNORECASE,
        )
        for aspect in EARBUD_ASPECTS
    }


_KEYWORD_PATTERNS = _compile_keyword_patterns()


def load_id2label(config_path: str | Path) -> dict[int, str]:
    """Read the ABSA label mapping written by the export notebook.

    The PRD hardcoded ``{0: negative, 1: neutral, 2: positive}``; reading the
    exported ``config.id2label`` removes the risk of a silent label swap.
    """
    with open(config_path, encoding="utf-8") as fh:
        raw = json.load(fh)["id2label"]
    mapping = {int(k): str(v).strip().lower() for k, v in raw.items()}
    if set(mapping.values()) != _VALID_SENTIMENTS:
        raise ValueError(f"absa_config.json id2label must cover {_VALID_SENTIMENTS}, got {mapping}")
    return mapping


def not_mentioned() -> dict[str, Any]:
    """Aspect result for an aspect the review does not mention."""
    return {"detected": False, "sentiment": "not_mentioned", "confidence": 0.0}


class ABSAModule:
    """Agent 3: per-aspect detection + sentiment."""

    def __init__(
        self,
        model_path: str | Path,
        tokenizer_path: str | Path,
        config_path: str | Path,
        *,
        session: InferenceSessionLike | None = None,
        tokenizer: LightTokenizer | None = None,
        id2label: dict[int, str] | None = None,
    ) -> None:
        self.id2label = id2label or load_id2label(config_path)
        self.tokenizer = tokenizer or LightTokenizer(tokenizer_path)
        self.session = session or create_session(model_path)

    @staticmethod
    def keyword_detect(text: str, aspect: str) -> bool:
        """Fast pre-filter: is the aspect plausibly mentioned?"""
        return bool(_KEYWORD_PATTERNS[aspect].search(text))

    def classify_aspects(self, text: str, aspects: list[str]) -> dict[str, dict[str, Any]]:
        """Classify sentiment for several aspects of one review in a single batch."""
        if not aspects:
            return {}
        encoded = self.tokenizer.encode_pairs([(text, ASPECT_PHRASES[a]) for a in aspects])
        logits = np.asarray(self.session.run(None, build_feed(self.session, encoded))[0])
        probs = softmax(logits.astype(np.float64), axis=-1)

        label2id = {label: idx for idx, label in self.id2label.items()}
        results: dict[str, dict[str, Any]] = {}
        for row, aspect in zip(probs, aspects, strict=True):
            pred_idx = int(np.argmax(row))
            results[aspect] = {
                "detected": True,
                "sentiment": self.id2label[pred_idx],
                "confidence": round(float(row[pred_idx]), 4),
                "prob_neg": round(float(row[label2id["negative"]]), 4),
                "prob_neu": round(float(row[label2id["neutral"]]), 4),
                "prob_pos": round(float(row[label2id["positive"]]), 4),
            }
        return results

    def process(self, clean_text: str) -> dict[str, Any]:
        """Return ``{"aspects": {aspect_key: result}}`` for all 10 aspects, in canonical order."""
        detected = [a for a in EARBUD_ASPECTS if self.keyword_detect(clean_text, a)]
        classified = self.classify_aspects(clean_text, detected)
        return {"aspects": {a: classified.get(a, not_mentioned()) for a in EARBUD_ASPECTS}}
