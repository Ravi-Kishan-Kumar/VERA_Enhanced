"""Build tiny but REAL model artifacts for tests.

Every file uses the exact production format (ONNX graph, ``tokenizer.json``,
joblib domain model, JSON fusion ensemble, conformal JSON), so tests exercise
onnxruntime sessions, the Rust tokenizer, XGBoost loading, and the hard-fail
artifact check — without any trained weights. NEVER copy these into MODEL_DIR:
they produce meaningless scores.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import onnx
import xgboost as xgb
from onnx import TensorProto, helper
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace
from tokenizers.processors import TemplateProcessing

from app.ml.agents.fusion import save_fusion_artifact
from app.ml.features import N_FEATURES

VOCAB_WORDS = (
    "the sound quality is great bass battery life lasts hours comfort fit build "
    "bluetooth connection drops mic calls noise cancellation value price earbuds "
    "terrible bad good love hate"
).split()


def write_tokenizer(path: Path) -> None:
    """Word-level tokenizer with DeBERTa-style special tokens and pair template."""
    vocab = {"[PAD]": 0, "[UNK]": 1, "[CLS]": 2, "[SEP]": 3}
    for word in VOCAB_WORDS:
        vocab.setdefault(word, len(vocab))
    tok = Tokenizer(WordLevel(vocab, unk_token="[UNK]"))
    tok.pre_tokenizer = Whitespace()
    tok.post_processor = TemplateProcessing(
        single="[CLS] $A [SEP]",
        pair="[CLS] $A [SEP] $B:1 [SEP]:1",
        special_tokens=[("[CLS]", 2), ("[SEP]", 3)],
    )
    tok.save(str(path))


def write_onnx(path: Path, n_outputs: int) -> None:
    """Graph: logits[:, k] = (k+1) * mean(attention_mask) — no token_type_ids input,
    mirroring the DeBERTa-v3 export."""
    ids = helper.make_tensor_value_info("input_ids", TensorProto.INT64, ["batch", "seq"])
    mask = helper.make_tensor_value_info("attention_mask", TensorProto.INT64, ["batch", "seq"])
    out = helper.make_tensor_value_info("logits", TensorProto.FLOAT, ["batch", n_outputs])
    scale = helper.make_tensor(
        "scale", TensorProto.FLOAT, [n_outputs], [float(k + 1) for k in range(n_outputs)]
    )
    nodes = [
        helper.make_node("Cast", ["attention_mask"], ["mask_f"], to=TensorProto.FLOAT),
        helper.make_node("ReduceMean", ["mask_f"], ["mean"], axes=[1], keepdims=1),
        helper.make_node("Mul", ["mean", "scale"], ["logits"]),
    ]
    # input_ids is declared (as real exports do) but unused by this toy graph.
    graph = helper.make_graph(nodes, "toy", [ids, mask], [out], initializer=[scale])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    onnx.checker.check_model(model)
    onnx.save(model, str(path))


#: One phrase per aspect (same order as EARBUD_ASPECTS) that trips its keyword list.
ASPECT_PHRASES_FOR_TESTS = (
    "the sound quality",
    "deep bass",
    "battery life",
    "comfortable to wear",
    "they fit well",
    "cheap plastic broke",
    "bluetooth connection drops",
    "the mic on calls",
    "noise cancellation",
    "worth the price",
)


def write_aspect_detector(path: Path) -> None:
    """Tiny real detector: each aspect is 'mentioned' when its phrase appears."""
    from sklearn.linear_model import LogisticRegression

    from app.ml.agents.aspect_detector import detector_features
    from app.ml.constants import EARBUD_ASPECTS

    texts, labels = [], []
    for i in range(len(EARBUD_ASPECTS)):
        for j in range(len(EARBUD_ASPECTS)):
            if i != j:
                texts.append(f"{ASPECT_PHRASES_FOR_TESTS[i]} and {ASPECT_PHRASES_FOR_TESTS[j]}")
                labels.append([k in (i, j) for k in range(len(EARBUD_ASPECTS))])
    label_matrix = np.array(labels)
    vectorizer = TfidfVectorizer().fit(texts)
    features = detector_features(vectorizer, texts)
    models = {
        aspect: LogisticRegression(C=10.0, max_iter=2000).fit(features, label_matrix[:, k])
        for k, aspect in enumerate(EARBUD_ASPECTS)
    }
    joblib.dump(
        {
            "vectorizer": vectorizer,
            "models": models,
            "thresholds": {aspect: 0.5 for aspect in EARBUD_ASPECTS},
            "aspects": list(EARBUD_ASPECTS),
        },
        path,
    )


def write_all(model_dir: Path, n_members: int = 3) -> None:
    """Write every artifact in ``REQUIRED_ARTIFACTS`` to ``model_dir``."""
    model_dir.mkdir(parents=True, exist_ok=True)
    write_tokenizer(model_dir / "experience_tokenizer.json")
    write_tokenizer(model_dir / "absa_tokenizer.json")
    write_onnx(model_dir / "experience_model.onnx", n_outputs=1)
    write_onnx(model_dir / "absa_model.onnx", n_outputs=3)
    (model_dir / "absa_config.json").write_text(
        json.dumps({"id2label": {"0": "Negative", "1": "Neutral", "2": "Positive"}}),
        encoding="utf-8",
    )

    texts = ["great sound love", "terrible battery hate", "good fit", "bad mic calls"] * 5
    vectorizer = TfidfVectorizer().fit(texts)
    ridge = Ridge().fit(vectorizer.transform(texts), [5, 1, 4, 2] * 5)
    joblib.dump({"vectorizer": vectorizer, "model": ridge}, model_dir / "domain_tfidf.joblib")

    write_aspect_detector(model_dir / "aspect_detector.joblib")

    rng = np.random.default_rng(0)
    features = rng.normal(size=(60, N_FEATURES)).astype(np.float32)
    target = np.clip(3 + features[:, 0], 1, 5)
    members = [
        xgb.XGBRegressor(n_estimators=5, max_depth=2, random_state=seed).fit(features, target)
        for seed in range(n_members)
    ]
    save_fusion_artifact(
        model_dir / "fusion_ensemble.json",
        members,
        {"helpfulness_score": 0.1, "freshness_score": 0.5, "verified_purchase": 0.8},
        metadata={"purpose": "unit-test"},
    )
    (model_dir / "conformal_qhat.json").write_text(
        json.dumps(
            {
                "method": "normalized",
                "q_hat": 1.5,
                "alpha": 0.1,
                "nominal_coverage": 0.9,
                "empirical_coverage": 0.91,
                "calibration_n": 400,
                "sigma_floor": 0.1,
            }
        ),
        encoding="utf-8",
    )
