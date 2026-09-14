"""Offline training package tests (no network, no GPU)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import Ridge

from app.ml.agents.absa import ABSAModule
from app.ml.agents.consistency import ConsistencyScorer
from app.ml.agents.domain_rating import DomainRatingModel
from app.ml.agents.fusion import FusionModel
from app.ml.agents.preprocessor import TextPreprocessor
from app.ml.agents.quality import QualityAssessor
from app.ml.calibration.conformal import ConformalPredictor
from app.ml.constants import EARBUD_ASPECTS
from app.ml.features import N_FEATURES
from app.ml.pipeline import SignalAgents
from tests.artifact_factory import write_all
from vera_training import calibration, data, evaluation, fusion, labeling, signals, splits
from vera_training.agreement import paired_agreement
from vera_training.domain import train_domain_model

WORDS = "great sound bass battery terrible fit comfort price value mic calls broke".split()


def _corpus(n: int = 200, products: int = 40, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        rating = int(rng.integers(1, 6))
        words = rng.choice(WORDS, size=25).tolist() + (["great"] * rating)
        rows.append(
            {
                "review_id": f"r{i}",
                "parent_asin": f"P{i % products:03d}",
                "text": " ".join(words),
                "rating": rating,
                "product_title": "Wireless Earbuds",
                "helpful_vote": int(rng.integers(0, 20)),
                "verified_purchase": bool(rng.random() < 0.8),
                "timestamp": 1_600_000_000_000 + i * 86_400_000,
                "experience_score": float(np.clip(rating + rng.normal(0, 0.5), 1, 5) * 2 // 1 / 2),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------- data
def test_sampling_is_star_balanced_and_respects_global_product_cap() -> None:
    frame = _corpus(600, products=150)
    sample = data.sample_for_labeling(frame, n=100, product_cap=2)
    assert sample["rating"].value_counts().to_dict() == {s: 20 for s in range(1, 6)}
    assert sample["parent_asin"].value_counts().max() <= 2


def test_prepare_corpus_filters_non_earbuds_short_and_duplicates() -> None:
    long_text = "These earbuds have great sound and the battery lasts all day long " * 3
    metadata = [
        {"parent_asin": "E1", "title": "TWS Earbuds"},
        {"parent_asin": "K1", "title": "Kitchen Blender"},
    ]
    reviews = [
        {"parent_asin": "E1", "rating": 5.0, "text": long_text, "timestamp": 1},
        {"parent_asin": "E1", "rating": 5.0, "text": long_text + "<br/>", "timestamp": 2},
        {"parent_asin": "E1", "rating": 4.0, "text": "too short", "timestamp": 3},
        {"parent_asin": "K1", "rating": 5.0, "text": long_text + " blender", "timestamp": 4},
    ]
    frame = data.prepare_corpus(reviews, metadata)
    assert len(frame) == 1 and frame.loc[0, "parent_asin"] == "E1"


# ------------------------------------------------------------------------ labeling
def _valid_label(score: float = 4.0) -> str:
    aspects = {a: {"mentioned": False, "sentiment": "not_mentioned"} for a in EARBUD_ASPECTS}
    aspects["bass"] = {"mentioned": True, "sentiment": "positive"}
    return json.dumps(
        {
            "experience_score": score,
            "experience_rationale": "Bass praised.",
            "has_irony_or_sarcasm": False,
            "review_quality": "high",
            "aspects": aspects,
        }
    )


def test_label_run_validates_budgets_and_resumes(tmp_path: Path) -> None:
    frame = _corpus(4).drop(columns=["experience_score"])
    calls: list[int] = []

    def provider(system: str, prompt: str, seed: int) -> str:
        calls.append(seed)
        assert "rating" not in prompt.lower()  # star-blinded
        return "not json" if len(calls) == 1 else _valid_label()

    checkpoint = tmp_path / "run.json"
    kwargs: dict[str, Any] = {
        "provider_name": "fake",
        "model": "m",
        "run_id": "a",
        "seed": 1,
        "sleep": lambda _: None,
    }
    state = labeling.run_labels(frame, checkpoint, provider, max_requests=3, **kwargs)
    assert state["requests"] == 3 and len(state["labels"]) == 2  # 1 failure + 2 successes

    state = labeling.run_labels(frame, checkpoint, provider, max_requests=10, **kwargs)
    assert len(state["labels"]) == 4
    merged = labeling.merge_labels(frame, checkpoint)
    assert merged["experience_score"].eq(4.0).all()


def test_label_schema_rejects_off_grid_scores_and_inconsistent_aspects() -> None:
    with pytest.raises(ValueError):
        labeling.ExperienceLabel.model_validate_json(_valid_label(4.2))
    bad = json.loads(_valid_label())
    bad["aspects"]["fit"] = {"mentioned": True, "sentiment": "not_mentioned"}
    with pytest.raises(ValueError):
        labeling.ExperienceLabel.model_validate(bad)


def test_paired_agreement_perfect_and_invalid() -> None:
    scores = np.array([1.0, 2.5, 4.0, 5.0])
    assert paired_agreement(scores, scores) == {"n": 4, "kappa": 1.0, "mae": 0.0}
    with pytest.raises(ValueError):
        paired_agreement(np.array([1.2]), np.array([1.0]))


# -------------------------------------------------------------------------- splits
def test_splits_are_product_disjoint() -> None:
    frame = _corpus(300, products=60)
    parts = splits.train_cal_test(frame)
    splits.assert_disjoint(*(p["parent_asin"] for p in parts.values()))
    folds = list(splits.repeated_group_folds(frame["parent_asin"], 5, 3))
    assert len(folds) == 15
    with pytest.raises(ValueError, match="leakage"):
        splits.assert_disjoint(["A", "B"], ["B"])


# -------------------------------------------------------------------------- domain
def test_domain_model_excludes_held_out_asins_and_loads_in_production(tmp_path: Path) -> None:
    corpus = _corpus(300, products=30)
    held_out = {"P000", "P001"}
    path = tmp_path / "domain_tfidf.joblib"
    report = train_domain_model(corpus, held_out, path, min_df=2)

    assert report["n_excluded_labelled_product_rows"] == corpus["parent_asin"].isin(held_out).sum()
    model = DomainRatingModel(path)
    assert model.vectorizer.stop_words_ is None
    assert 1.0 <= model.process("great great great sound")["domain_score"] <= 5.0


# ------------------------------------------------------------- signals + fusion
@pytest.fixture(scope="module")
def model_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("artifacts")
    write_all(directory)
    return directory


def _agents(model_dir: Path, imputation: dict[str, float]) -> SignalAgents:
    return SignalAgents(
        preprocessor=TextPreprocessor(),
        experience=None,
        absa=ABSAModule(
            model_dir / "absa_model.onnx",
            model_dir / "absa_tokenizer.json",
            model_dir / "absa_config.json",
        ),
        consistency=ConsistencyScorer(),
        quality=QualityAssessor(imputation),
        domain=DomainRatingModel(model_dir / "domain_tfidf.joblib"),
    )


def test_feature_matrix_dropout_and_fusion_roundtrip(model_dir: Path, tmp_path: Path) -> None:
    frame = _corpus(80, products=20)
    means = signals.imputation_means(frame)
    agents = _agents(model_dir, means)
    oof = frame["experience_score"].to_numpy() + 0.1

    full, _ = signals.feature_matrix(frame, agents, oof, metadata_dropout=0.0)
    masked, outputs = signals.feature_matrix(frame, agents, oof, metadata_dropout=1.0)
    assert full.shape == masked.shape == (80, N_FEATURES)
    assert all(o["quality"]["imputed_fields"] for o in outputs)

    ensemble = fusion.BootstrapEnsemble(
        n_members=3, params={**fusion.DEFAULT_PARAMS, "n_estimators": 10}
    )
    ensemble.fit(full, frame["experience_score"].to_numpy())
    path = tmp_path / "fusion_ensemble.json"
    ensemble.save(path, means)

    production = FusionModel(path)
    mean, std = ensemble.predict_with_std(masked[:5])
    for row in range(5):
        prediction = production.predict(masked[row])
        assert prediction["score"] == pytest.approx(float(mean[row]), abs=1e-4)
        assert prediction["ensemble_std"] == pytest.approx(float(std[row]), abs=1e-4)


def test_balanced_weights_upweight_rare_labels() -> None:
    weights = fusion.balanced_sample_weights(np.array([5.0, 5.0, 5.0, 1.0]))
    assert weights[3] > weights[0] and weights.mean() == pytest.approx(1.0)


# --------------------------------------------------------------------- calibration
def test_conformal_quantile_is_finite_sample_exact() -> None:
    scores = np.arange(1, 20, dtype=float)  # n = 19, alpha = 0.1 -> k = 18
    assert calibration.conformal_quantile(scores, 0.10) == 18.0
    with pytest.raises(ValueError, match="calibration rows"):
        calibration.conformal_quantile(np.arange(5, dtype=float), 0.10)


def test_conformal_coverage_holds_on_fresh_data_and_loads_in_production(tmp_path: Path) -> None:
    rng = np.random.default_rng(1)

    def draw(n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        std = rng.uniform(0.1, 0.6, n)
        pred = rng.uniform(1.5, 4.5, n)
        return pred, std, pred + rng.normal(0, std)

    payload = calibration.fit_best_conformal(*draw(2000), alpha=0.10)
    test = calibration.interval_metrics(*draw(4000), payload)
    assert test["coverage"] >= 0.88
    assert payload["method"] == "normalized"  # heteroscedastic noise -> adaptive wins

    path = tmp_path / "conformal_qhat.json"
    calibration.save_conformal(payload, path, test_metrics=test)
    predictor = ConformalPredictor(path)
    lower, upper, confidence = predictor.predict_interval(3.0, 0.3)
    assert lower < 3.0 < upper and 0 <= confidence <= 1

    with pytest.raises(AssertionError, match="Coverage"):
        calibration.save_conformal(payload, tmp_path / "x.json", test_metrics={"coverage": 0.5})


# ---------------------------------------------------------------------- evaluation
def test_cv_comparison_and_ablation_detect_a_useful_feature() -> None:
    rng = np.random.default_rng(3)
    n = 300
    X = rng.normal(size=(n, N_FEATURES))
    y = 3 + X[:, 1] + 0.1 * rng.normal(size=n)  # column 1 = experience_score
    groups = [f"G{i % 60}" for i in range(n)]

    baseline = evaluation.cross_validated_mae(X[:, :1], y, groups, Ridge)
    full = evaluation.cross_validated_mae(X, y, groups, Ridge)
    comparison = evaluation.paired_comparison(baseline, full)
    assert comparison["win_rate"] == 1.0 and comparison["wilcoxon_p"] < 0.05

    table = evaluation.ablation_study(X, y, groups, Ridge, n_splits=3, n_repeats=1)
    assert table.loc[table.config == "+experience", "keep"].item() is True
    assert evaluation.gate_g4(comparison, coverage_90=0.9)["passed"] is True


def test_aspect_metrics_scores_detection_and_sentiment() -> None:
    label = {
        a: {"mentioned": a == "bass", "sentiment": "positive" if a == "bass" else "not_mentioned"}
        for a in EARBUD_ASPECTS
    }
    pred = {
        a: {"detected": a == "bass", "sentiment": "positive" if a == "bass" else "not_mentioned"}
        for a in EARBUD_ASPECTS
    }
    table = evaluation.aspect_metrics([label], [pred]).set_index("aspect")
    assert table.loc["bass", "detection_f1"] == 1.0
    assert table.loc["bass", "sentiment_accuracy"] == 1.0
