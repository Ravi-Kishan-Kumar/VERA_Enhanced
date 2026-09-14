"""End-to-end pipeline tests on tiny real artifacts (see ``artifact_factory``)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.ml.agents.absa import ABSAModule
from app.ml.agents.experience_extractor import ExperienceExtractor
from app.ml.agents.fusion import FusionModel
from app.ml.constants import EARBUD_ASPECTS
from app.ml.features import FEATURE_NAMES, N_FEATURES, build_feature_vector
from app.ml.models.loader import ModelArtifactsMissingError, artifact_status
from app.ml.models.tokenizer_wrapper import LightTokenizer
from app.ml.pipeline import VERAPipeline
from tests.artifact_factory import write_all

REVIEW = (
    "The sound quality is great and the bass hits hard, but the battery life is terrible "
    "and bluetooth connection drops during calls."
)


@pytest.fixture(scope="module")
def model_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("models")
    write_all(directory)
    return directory


def test_missing_artifacts_hard_fail(tmp_path: Path) -> None:
    with pytest.raises(ModelArtifactsMissingError) as info:
        VERAPipeline(tmp_path)
    assert "fusion_ensemble.json" in info.value.missing
    assert not any(artifact_status(tmp_path).values())


def test_empty_artifact_counts_as_missing(model_dir: Path, tmp_path: Path) -> None:
    for source in model_dir.iterdir():
        (tmp_path / source.name).write_bytes(source.read_bytes())
    (tmp_path / "conformal_qhat.json").write_bytes(b"")
    with pytest.raises(ModelArtifactsMissingError) as info:
        VERAPipeline(tmp_path)
    assert info.value.missing == ["conformal_qhat.json"]


def test_tokenizer_pads_batches_and_never_truncates_aspect(model_dir: Path) -> None:
    tok = LightTokenizer(model_dir / "absa_tokenizer.json", max_length=8)
    batch = tok.encode_pairs([(" ".join(["great"] * 50), "battery life"), ("good", "fit")])

    assert batch["input_ids"].shape == (2, 8)
    assert batch["input_ids"].dtype == np.int64
    # Last tokens of the truncated row must be: battery life [SEP]
    battery_id = tok._tok.token_to_id("battery")
    life_id = tok._tok.token_to_id("life")
    assert list(batch["input_ids"][0, -3:-1]) == [battery_id, life_id]
    assert batch["attention_mask"][1].sum() < 8  # shorter row is padded


def test_onnx_agents_run_without_token_type_ids_input(model_dir: Path) -> None:
    experience = ExperienceExtractor(
        model_dir / "experience_model.onnx", model_dir / "experience_tokenizer.json"
    )
    result = experience.predict(REVIEW)
    assert 1.0 <= result["predicted_score"] <= 5.0

    absa = ABSAModule(
        model_dir / "absa_model.onnx",
        model_dir / "absa_tokenizer.json",
        model_dir / "absa_config.json",
    )
    aspects = absa.process(REVIEW)["aspects"]
    assert list(aspects) == list(EARBUD_ASPECTS)
    assert aspects["battery_life"]["detected"] and aspects["connectivity"]["detected"]
    assert aspects["fit"] == {"detected": False, "sentiment": "not_mentioned", "confidence": 0.0}
    probs = [aspects["bass"][k] for k in ("prob_neg", "prob_neu", "prob_pos")]
    assert pytest.approx(sum(probs), abs=1e-3) == 1.0


def test_absa_keywords_respect_word_boundaries() -> None:
    assert not ABSAModule.keyword_detect("a real benefit for dancers", "fit")
    assert not ABSAModule.keyword_detect("perfect balance", "noise_cancellation")
    assert ABSAModule.keyword_detect("the ANC is superb", "noise_cancellation")
    assert ABSAModule.keyword_detect("excellent isolation", "noise_cancellation")


def test_full_pipeline_output_contract(model_dir: Path) -> None:
    pipeline = VERAPipeline(model_dir)
    result = pipeline.process(text=REVIEW, star_rating=5.0, product_title="Wireless Earbuds")

    lower, upper = result["interval"]
    assert 1.0 <= lower <= result["corrected_score"] <= upper <= 5.0
    assert 0.0 <= result["confidence"] <= 1.0
    assert set(result["aspects"]) == set(EARBUD_ASPECTS)
    assert result["flags"]["is_earbud"] is True
    assert result["flags"]["imputed_fields"] == ["helpful_votes", "timestamp", "verified_purchase"]
    assert isinstance(result["explanation"], str) and result["explanation"]


def test_emoji_only_review_completes(model_dir: Path) -> None:
    """PRD weakness #14: langdetect edge cases must not crash a task."""
    result = VERAPipeline(model_dir).process(text="👍👍👍", star_rating=5.0)
    assert result["flags"]["language"] == "en"


def test_feature_contract_is_40_dims_and_fusion_rejects_drift(model_dir: Path) -> None:
    assert N_FEATURES == len(FEATURE_NAMES) == 40
    fusion = FusionModel(model_dir / "fusion_ensemble.json")
    assert len(fusion.members) == 3

    pipeline = VERAPipeline(model_dir)
    from app.ml.pipeline import extract_signals

    vector = build_feature_vector(extract_signals(pipeline.agents, text=REVIEW, star_rating=3))
    assert vector.shape == (40,) and vector.dtype == np.float32

    import json

    payload = json.loads((model_dir / "fusion_ensemble.json").read_text(encoding="utf-8"))
    payload["feature_names"] = payload["feature_names"][::-1]
    broken = model_dir.parent / "broken_fusion.json"
    broken.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="feature_names"):
        FusionModel(broken)
