"""Pure-agent invariants that do not require production model artifacts."""

from __future__ import annotations

from app.ml.agents.preprocessor import TextPreprocessor
from app.ml.agents.quality import QualityAssessor


def test_preprocessor_handles_emoji_only_review_without_crashing() -> None:
    output = TextPreprocessor().process("👍👍👍", "Wireless earbuds")

    assert output["language"] == "en"
    assert output["is_earbud"] is True
    assert output["word_count"] == 1


def test_quality_uses_training_means_for_missing_metadata() -> None:
    assessor = QualityAssessor(
        {"helpfulness_score": 0.2, "freshness_score": 0.8, "verified_purchase": 0.6}
    )
    output = assessor.process(None, None, None, word_count=100)

    assert output["imputed_fields"] == ["helpful_votes", "timestamp", "verified_purchase"]
    assert output["quality_score"] > 0.05
