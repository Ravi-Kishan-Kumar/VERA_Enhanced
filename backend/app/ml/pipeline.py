"""VERA pipeline orchestrator (PRD §8.2).

Runs Agents 1–6, fuses their signals with Agent 7, and wraps the point estimate
in a conformal interval. Product-level Empirical Bayes aggregation runs
separately (``app.worker.tasks.aggregate_products_task``) because it needs every
review of every product.

Model policy: :class:`VERAPipeline` **hard-fails** at construction when any
artifact is missing (user decision, DECISIONS.md) — see
:mod:`app.ml.models.loader`.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.ml.agents.absa import ABSAModule
from app.ml.agents.aspect_detector import AspectDetector
from app.ml.agents.consistency import ConsistencyScorer
from app.ml.agents.domain_rating import DomainRatingModel
from app.ml.agents.experience_extractor import ExperienceExtractor
from app.ml.agents.fusion import FusionModel
from app.ml.agents.preprocessor import TextPreprocessor
from app.ml.agents.quality import QualityAssessor
from app.ml.calibration.conformal import ConformalPredictor
from app.ml.constants import EARBUD_ASPECTS
from app.ml.features import build_feature_vector
from app.ml.models.loader import ensure_models

logger = logging.getLogger(__name__)


@dataclass
class SignalAgents:
    """Agents 1–6. ``experience`` may be ``None`` when callers supply its output
    directly (offline training uses out-of-fold predictions)."""

    preprocessor: TextPreprocessor
    experience: ExperienceExtractor | None
    absa: ABSAModule
    consistency: ConsistencyScorer
    quality: QualityAssessor
    domain: DomainRatingModel


def extract_signals(
    agents: SignalAgents,
    *,
    text: str,
    star_rating: float,
    helpful_votes: int | None = None,
    verified_purchase: bool | None = None,
    timestamp_ms: int | None = None,
    product_title: str | None = "",
    experience_output: dict[str, Any] | None = None,
    aspect_mentions: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Run Agents 1–6 and return the ``agent_outputs`` mapping for fusion.

    Shared by production and the training notebooks so both build features
    through exactly the same code path. Training supplies out-of-fold
    ``experience_output`` and ``aspect_mentions``; production computes both.
    """
    pre = agents.preprocessor.process(text, product_title)
    clean = pre["clean_text"]

    if experience_output is None:
        if agents.experience is None:
            raise ValueError("experience_output is required when no ExperienceExtractor is loaded")
        experience_output = agents.experience.predict(clean)

    quality = agents.quality.process(
        helpful_votes=helpful_votes,
        verified=verified_purchase,
        timestamp_ms=timestamp_ms,
        word_count=pre["word_count"],
    )
    return {
        "preprocessor": pre,
        "experience_extractor": experience_output,
        "absa": agents.absa.process(clean, aspect_mentions),
        "consistency": agents.consistency.process(
            star_rating, experience_output["predicted_score"]
        ),
        "quality": quality,
        "domain_rating": agents.domain.process(clean),
        "star_rating": float(star_rating),
    }


def build_explanation(agent_outputs: dict[str, Any], corrected_score: float) -> str:
    """Human-readable summary for the ScoreCard (PRD §16.2)."""
    star = agent_outputs["star_rating"]
    cons = agent_outputs["consistency"]
    aspects = agent_outputs["absa"]["aspects"]
    pre = agent_outputs["preprocessor"]

    def names(sentiment: str) -> list[str]:
        return [a.replace("_", " ") for a in EARBUD_ASPECTS if aspects[a]["sentiment"] == sentiment]

    parts: list[str] = []
    if cons["star_inflated"]:
        parts.append(
            f"The text implies about {corrected_score:.1f} stars despite the {star:g}-star rating."
        )
    elif cons["star_deflated"]:
        parts.append(
            f"The text is more positive than the {star:g}-star rating suggests "
            f"(about {corrected_score:.1f})."
        )
    else:
        parts.append("The star rating and the review text broadly agree.")

    negatives, positives = names("negative"), names("positive")
    if negatives:
        parts.append(f"Concerns: {', '.join(negatives)}.")
    if positives:
        parts.append(f"Praised: {', '.join(positives)}.")
    if not pre["is_english"]:
        parts.append(f"Warning: detected language '{pre['language']}'; scores are English-trained.")
    if not pre["is_earbud"]:
        parts.append("Warning: this review may not be about earbuds or headphones.")
    return " ".join(parts)


class VERAPipeline:
    """End-to-end per-review inference. Construct once per worker process."""

    def __init__(self, model_dir: Path, hf_repo: str = "", hf_token: str = "") -> None:
        started = time.perf_counter()
        paths = ensure_models(model_dir, hf_repo=hf_repo, hf_token=hf_token)  # hard-fail

        self.fusion = FusionModel(paths["fusion_ensemble.json"])
        self.conformal = ConformalPredictor(paths["conformal_qhat.json"])
        self.agents = SignalAgents(
            preprocessor=TextPreprocessor(),
            experience=ExperienceExtractor(
                paths["experience_model.onnx"], paths["experience_tokenizer.json"]
            ),
            absa=ABSAModule(
                paths["absa_model.onnx"],
                paths["absa_tokenizer.json"],
                paths["absa_config.json"],
                detector=AspectDetector(paths["aspect_detector.joblib"]),
            ),
            consistency=ConsistencyScorer(),
            quality=QualityAssessor(imputation=self.fusion.imputation_means),
            domain=DomainRatingModel(paths["domain_tfidf.joblib"]),
        )
        logger.info("VERA pipeline loaded in %.1fs", time.perf_counter() - started)

    @classmethod
    def from_components(
        cls, agents: SignalAgents, fusion: FusionModel, conformal: ConformalPredictor
    ) -> VERAPipeline:
        """Assemble from pre-built parts (tests, notebooks)."""
        instance = cls.__new__(cls)
        instance.agents = agents
        instance.fusion = fusion
        instance.conformal = conformal
        return instance

    def process(
        self,
        *,
        text: str,
        star_rating: float,
        helpful_votes: int | None = None,
        verified_purchase: bool | None = None,
        product_title: str | None = "",
        timestamp_ms: int | None = None,
    ) -> dict[str, Any]:
        """Score one review (PRD §3.1 output contract)."""
        started = time.perf_counter()
        outputs = extract_signals(
            self.agents,
            text=text,
            star_rating=star_rating,
            helpful_votes=helpful_votes,
            verified_purchase=verified_purchase,
            timestamp_ms=timestamp_ms,
            product_title=product_title,
        )
        fused = self.fusion.predict(build_feature_vector(outputs))
        lower, upper, confidence = self.conformal.predict_interval(
            fused["score"], fused["ensemble_std"]
        )
        corrected = round(fused["score"], 3)

        pre, cons, qual = outputs["preprocessor"], outputs["consistency"], outputs["quality"]
        return {
            "corrected_score": corrected,
            "interval": [round(lower, 3), round(upper, 3)],
            "confidence": round(confidence, 3),
            "aspects": outputs["absa"]["aspects"],
            # Agent 4 definition: star − text-derived experience score (positive = inflated).
            "star_text_gap": cons["star_text_gap"],
            "review_quality": qual["quality_score"],
            "ensemble_std": round(fused["ensemble_std"], 4),
            "flags": {
                "language": pre["language"],
                "is_english": pre["is_english"],
                "is_earbud": pre["is_earbud"],
                "earbud_confidence": pre["earbud_confidence"],
                "has_url": pre["has_url"],
                "star_inflated": cons["star_inflated"],
                "star_deflated": cons["star_deflated"],
                "experience_score": round(outputs["experience_extractor"]["predicted_score"], 3),
                "domain_score": outputs["domain_rating"]["domain_score"],
                "imputed_fields": qual["imputed_fields"],
            },
            "explanation": build_explanation(outputs, corrected),
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }
