"""Agent 2 — Experience Extractor (PRD §9, Agent 2).

Fine-tuned DeBERTa-v3-base regression head, exported to INT8 ONNX, estimates
the experience score (1–5) from review text alone.

The model input is produced by :func:`format_experience_input`, which the
fine-tuning notebook imports too — training and serving must see identical
text. (The PRD prepended ``"{title} [SEP]"`` at inference but trained on the
bare text: a train/serve skew. Both now use the bare cleaned text.)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from app.ml.constants import SCORE_MAX, SCORE_MIN
from app.ml.models.onnx_session import InferenceSessionLike, build_feed, create_session
from app.ml.models.tokenizer_wrapper import LightTokenizer

MAX_LENGTH = 512


def format_experience_input(clean_text: str) -> str:
    """Canonical model input text. Shared with ``vera_training.finetune``."""
    return clean_text.strip()


class ExperienceExtractor:
    """Agent 2: text -> predicted experience score."""

    def __init__(
        self,
        model_path: str | Path,
        tokenizer_path: str | Path,
        *,
        session: InferenceSessionLike | None = None,
        tokenizer: LightTokenizer | None = None,
    ) -> None:
        """Load the ONNX session and tokenizer.

        ``session`` / ``tokenizer`` may be injected (tests); otherwise they are
        built from the paths.
        """
        self.tokenizer = tokenizer or LightTokenizer(tokenizer_path, max_length=MAX_LENGTH)
        self.session = session or create_session(model_path)

    def predict_raw(self, texts: list[str]) -> np.ndarray:
        """Return unclipped regression outputs, shape ``(len(texts),)``."""
        encoded = self.tokenizer.encode_batch([format_experience_input(t) for t in texts])
        outputs = self.session.run(None, build_feed(self.session, encoded))
        logits = np.asarray(outputs[0], dtype=np.float64)
        return logits.reshape(len(texts), -1)[:, 0]

    def predict(self, clean_text: str) -> dict[str, Any]:
        """Predict one review.

        Returns:
            ``predicted_score`` clipped to [1, 5], the ``raw_score``, and
            ``model_uncertainty`` — distance of the raw output from the nearest
            0.5 label step (a fixed proxy feature defined by the PRD; the
            calibrated uncertainty comes from conformal prediction, not this).
        """
        raw_score = float(self.predict_raw([clean_text])[0])
        nearest_half = round(raw_score * 2) / 2
        return {
            "predicted_score": float(np.clip(raw_score, SCORE_MIN, SCORE_MAX)),
            "raw_score": raw_score,
            "model_uncertainty": abs(raw_score - nearest_half),
        }
