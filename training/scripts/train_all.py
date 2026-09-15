"""End-to-end training after labeling: stages mirror notebooks 04–08 (resumable).

    .venv\\Scripts\\python.exe training\\scripts\\train_all.py --stages all
    .venv\\Scripts\\python.exe training\\scripts\\train_all.py --stages fusion,calibrate

Stages (in order): labels, crossfit, final, domain, aspects, fusion, calibrate, evaluate, report,
diagnostics.
A stage whose output already exists is skipped unless --force is given.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "training")]
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from vera_training import paths  # noqa: E402
from vera_training.io import atomic_json, validate_reviews  # noqa: E402
from vera_training.labeling import ExperienceLabel  # noqa: E402

STAGES = (
    "labels",
    "crossfit",
    "final",
    "domain",
    "aspects",
    "fusion",
    "calibrate",
    "evaluate",
    "report",
    "diagnostics",
)
FINAL_DIR = paths.PROCESSED / "final_model"
CROSSFIT_DIR = paths.PROCESSED / "crossfit"


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def load_labelled() -> pd.DataFrame:
    rows = [json.loads(line) for line in paths.LABELS_V1.open(encoding="utf-8")]
    return validate_reviews(pd.DataFrame(rows), labels=True)


# ---------------------------------------------------------------------------- stages
def stage_labels(run_ids: list[str], allow_non_human: bool) -> None:
    """Merge primary label runs into labels_v1.jsonl after checking gate G1."""
    report = json.loads(paths.AGREEMENT_REPORT.read_text(encoding="utf-8"))
    if report.get("passed") is not True:
        raise SystemExit(f"G1 failed: {json.dumps(report, indent=2)}")
    if not report.get("human_validated") and not allow_non_human:
        raise SystemExit("G1 used a non-human reference; pass --allow-non-human-reference")
    pool = pd.read_parquet(paths.LABELING_POOL)
    # One label per (review, model); runs listed first win for the same model.
    by_model: dict[str, dict[str, dict[str, Any]]] = {}
    for run_id in run_ids:
        state = json.loads((paths.LABELS / f"run_{run_id}.json").read_text(encoding="utf-8"))
        model_labels = by_model.setdefault(state["specification"]["model"], {})
        for review_id, label in state["labels"].items():
            model_labels.setdefault(review_id, ExperienceLabel.model_validate(label).model_dump())
    models = list(by_model)
    labels: dict[str, dict[str, Any]] = {}
    for review_id in sorted({r for m in by_model.values() for r in m}):
        available = [by_model[m][review_id] for m in models if review_id in by_model[m]]
        # Consensus target = mean of the models' scores (quarter-step when they differ by 0.5);
        # aspect labels come from the first listed model that labelled the review.
        base = dict(available[0])
        base["experience_score"] = float(np.mean([a["experience_score"] for a in available]))
        base["label_models"] = len(available)
        labels[review_id] = base
    frame = pool[pool.review_id.isin(labels)].copy()
    label_frame = pd.DataFrame([{"review_id": k, **v} for k, v in labels.items()])
    log(
        f"label sources: {models}; consensus rows: "
        f"{sum(v['label_models'] > 1 for v in labels.values())}/{len(labels)}"
    )
    merged = validate_reviews(
        frame.merge(label_frame, on="review_id", validate="one_to_one"), labels=True
    )
    with paths.LABELS_V1.open("w", encoding="utf-8") as stream:
        for record in merged.to_dict(orient="records"):
            stream.write(json.dumps(record, default=str) + "\n")
    log(f"labels_v1: {len(merged)} reviews, {merged.parent_asin.nunique()} products")
    log("label distribution: " + merged.experience_score.value_counts().sort_index().to_json())


def stage_crossfit(config: Any) -> None:
    from vera_training.finetune import crossfit_predictions

    labelled = load_labelled()
    oof = crossfit_predictions(labelled, CROSSFIT_DIR, config, n_folds=5)
    pd.DataFrame({"review_id": labelled.review_id, "experience_raw": oof}).to_csv(
        paths.EXPERIENCE_OOF, index=False
    )
    mae = float(np.abs(np.clip(oof, 1, 5) - labelled.experience_score).mean())
    atomic_json(paths.REPORTS / "experience_oof.json", {"oof_mae": mae, "n": len(oof)})
    log(f"out-of-fold experience MAE = {mae:.3f}")


def stage_final(config: Any) -> None:
    from vera_training.export import export_experience
    from vera_training.finetune import train_final

    labelled = load_labelled()
    model_dir = FINAL_DIR / "model"
    if not (model_dir / "config.json").exists():
        model_dir = train_final(labelled, FINAL_DIR, config)
    validation = json.loads((model_dir / "vera_training.json").read_text())["validation"]
    log(f"final model validation: {validation}")
    samples = labelled.sample(32, random_state=0).text.tolist()
    report = export_experience(
        model_dir, paths.MODELS, samples, paths.PROCESSED / "onnx_work", config.max_length
    )
    report["validation"] = validation
    report["g2_val_mae_below_0_50"] = validation.get("eval_mae", 9) < 0.50
    atomic_json(paths.REPORTS / "experience_export.json", report)
    log(f"experience export: {report}")


def stage_domain() -> None:
    from vera_training.domain import train_domain_model

    corpus = pd.read_parquet(paths.CORPUS)
    pool = pd.read_parquet(paths.LABELING_POOL)  # exclude every pool product, labelled or not
    report = train_domain_model(
        corpus, set(pool.parent_asin), paths.MODELS / "domain_tfidf.joblib", max_rows=600_000
    )
    atomic_json(paths.REPORTS / "domain_model.json", report)
    log(f"domain model: {report}")


SPLITS_FILE = paths.LABELS / "splits.json"
ASPECT_OOF_FILE = paths.LABELS / "aspect_oof_mentions.json"


def load_split_assignment(labelled: pd.DataFrame) -> dict[str, str]:
    """``review_id -> train|calibration|test``, created once per label set and then reused.

    Every stage (aspects, fusion, calibration, evaluation) must see the SAME split;
    persisting it removes any dependence on row order.
    """
    from vera_training import splits

    if SPLITS_FILE.exists():
        assignment: dict[str, str] = json.loads(SPLITS_FILE.read_text(encoding="utf-8"))
        if set(assignment) == set(labelled.review_id):
            return assignment
        log("labels changed since splits.json was written; regenerating splits")
    parts = splits.train_cal_test(labelled, seed=42)
    assignment = {rid: name for name, frame in parts.items() for rid in frame.review_id}
    atomic_json(SPLITS_FILE, assignment)
    return assignment


def stage_aspects() -> None:
    from vera_training.aspects import fit_aspect_detector

    labelled = load_labelled()
    assignment = load_split_assignment(labelled)
    test_mask = labelled.review_id.map(assignment).eq("test").to_numpy()
    report = fit_aspect_detector(labelled, test_mask, paths.MODELS / "aspect_detector.joblib")
    atomic_json(ASPECT_OOF_FILE, report.pop("oof_mentions"))
    atomic_json(paths.REPORTS / "aspect_detector.json", report)
    table = pd.DataFrame(report["per_aspect"])
    log("aspect detector (test split):\n" + table.to_string(index=False))
    log(
        f"macro F1 {report['test_macro_f1']} vs keywords-only "
        f"{report['test_macro_f1_keywords_only']}; "
        f"all >= 0.70: {report['all_aspects_at_least_0_70']}"
    )


def stage_fusion() -> None:
    from app.ml.agents.absa import ABSAModule
    from app.ml.agents.consistency import ConsistencyScorer
    from app.ml.agents.domain_rating import DomainRatingModel
    from app.ml.agents.preprocessor import TextPreprocessor
    from app.ml.agents.quality import QualityAssessor
    from app.ml.pipeline import SignalAgents
    from vera_training import signals
    from vera_training.fusion import BootstrapEnsemble, tune_fusion_params

    labelled = load_labelled()
    oof = pd.read_csv(paths.EXPERIENCE_OOF, dtype={"review_id": str})
    labelled = labelled.merge(oof, on="review_id", validate="one_to_one")
    assignment = load_split_assignment(labelled)
    parts = {
        name: labelled[labelled.review_id.map(assignment).eq(name)].reset_index(drop=True)
        for name in ("train", "calibration", "test")
    }
    aspect_oof: dict[str, dict[str, bool]] = json.loads(ASPECT_OOF_FILE.read_text(encoding="utf-8"))
    means = signals.imputation_means(parts["train"])
    absa = signals.CachedABSA(
        ABSAModule(
            paths.MODELS / "absa_model.onnx",
            paths.MODELS / "absa_tokenizer.json",
            paths.MODELS / "absa_config.json",
        ),
        paths.PROCESSED / "absa_cache.joblib",
        paths.MODELS / "absa_model.onnx",
    )
    log(f"ABSA cache: {len(absa.cache)} stored results")
    agents = SignalAgents(
        preprocessor=TextPreprocessor(),
        experience=None,
        absa=absa,  # duck-typed ABSAModule (memoized)
        consistency=ConsistencyScorer(),
        quality=QualityAssessor(means),
        domain=DomainRatingModel(paths.MODELS / "domain_tfidf.joblib"),
    )
    matrices: dict[str, dict[str, Any]] = {}
    for name, frame in parts.items():
        started = time.time()
        X, outputs = signals.feature_matrix(
            frame,
            agents,
            frame.experience_raw.to_numpy(),
            metadata_dropout=0.5 if name == "train" else 1.0,
            seed=42,
            aspect_mentions=[aspect_oof[rid] for rid in frame.review_id],
        )
        matrices[name] = {
            "X": X,
            "y": frame.experience_score.to_numpy(),
            "frame": frame,
            "aspects": [o["absa"]["aspects"] for o in outputs],
        }
        absa.save()
        log(f"features[{name}] {X.shape} in {time.time() - started:.0f}s")
    X_all, _ = signals.feature_matrix(
        labelled,
        agents,
        labelled.experience_raw.to_numpy(),
        metadata_dropout=0.5,
        seed=7,
        aspect_mentions=[aspect_oof[rid] for rid in labelled.review_id],
    )
    matrices["all"] = {"X": X_all, "y": labelled.experience_score.to_numpy(), "frame": labelled}

    # Capacity chosen by product-grouped CV on the TRAIN split only (see fusion.tune_fusion_params).
    tuning = tune_fusion_params(
        matrices["train"]["X"], matrices["train"]["y"], parts["train"].parent_asin.tolist()
    )
    atomic_json(paths.REPORTS / "fusion_tuning.json", tuning)
    log(f"fusion tuning chose {tuning['chosen']}")
    ensemble = BootstrapEnsemble(n_members=20, seed=42, params=tuning["params"]).fit(
        matrices["train"]["X"], matrices["train"]["y"]
    )
    ensemble.save(
        paths.MODELS / "fusion_ensemble.json",
        means,
        metadata={
            "n_train": len(parts["train"]),
            "labels": len(labelled),
            "params": tuning["params"],
        },
    )
    joblib.dump(
        {"matrices": matrices, "imputation_means": means, "fusion_params": tuning["params"]},
        paths.FUSION_CACHE,
    )
    summary: dict[str, dict[str, float]] = {}
    for split in ("train", "calibration", "test"):
        pred = ensemble.predict(matrices[split]["X"])
        summary[split] = {
            "vera_mae": float(np.abs(pred - matrices[split]["y"]).mean()),
            "star_as_prediction_mae": float(
                np.abs(matrices[split]["frame"].rating - matrices[split]["y"]).mean()
            ),
            "experience_only_mae": float(
                np.abs(
                    np.clip(matrices[split]["frame"].experience_raw, 1, 5) - matrices[split]["y"]
                ).mean()
            ),
        }
    atomic_json(paths.REPORTS / "fusion_holdout.json", summary)
    log(f"fusion hold-out: {summary}")


def stage_calibrate() -> None:
    from app.ml.agents.fusion import FusionModel
    from vera_training import calibration
    from vera_training.splits import assert_disjoint

    cache = joblib.load(paths.FUSION_CACHE)["matrices"]
    assert_disjoint(
        cache["train"]["frame"].parent_asin,
        cache["calibration"]["frame"].parent_asin,
        cache["test"]["frame"].parent_asin,
    )
    fusion = FusionModel(paths.MODELS / "fusion_ensemble.json")

    def predict(split: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        members = fusion.predict_members(cache[split]["X"])
        return members.mean(axis=0).clip(1, 5), members.std(axis=0), cache[split]["y"]

    cal, test = predict("calibration"), predict("test")
    rows = []
    production = production_test = None
    for alpha in (0.05, 0.10, 0.20):
        payload = calibration.fit_best_conformal(*cal, alpha=alpha)
        metrics = calibration.interval_metrics(*test, payload)
        rows.append(
            {"target": 1 - alpha, **{k: payload[k] for k in ("method", "q_hat")}, **metrics}
        )
        if alpha == 0.10:
            production, production_test = payload, metrics
    assert production is not None and production_test is not None
    calibration.save_conformal(
        production, paths.MODELS / "conformal_qhat.json", test_metrics=production_test
    )
    atomic_json(paths.REPORTS / "calibration.json", {"levels": rows, "production": production})
    log(f"calibration: {rows}")


def stage_evaluate() -> None:
    from sklearn.linear_model import Ridge

    from vera_training import evaluation
    from vera_training.fusion import BootstrapEnsemble

    cache = joblib.load(paths.FUSION_CACHE)
    data, params = cache["matrices"]["all"], cache["fusion_params"]
    X, y, groups = data["X"], data["y"], data["frame"].parent_asin.tolist()
    baseline = evaluation.cross_validated_mae(X[:, :1], y, groups, Ridge)
    # Nested CV: hyperparameters are re-tuned inside every outer training fold.
    vera, folds = evaluation.nested_cross_validated_mae(X, y, groups, n_members=20)
    comparison = evaluation.paired_comparison(baseline, vera)
    gaps = [f["gap"] for f in folds]
    comparison["nested_tuning"] = True
    comparison["mean_train_mae"] = float(np.mean([f["train_mae"] for f in folds]))
    comparison["mean_generalization_gap"] = float(np.mean(gaps))
    comparison["fold_details"] = folds
    comparison["fold_maes"] = {"stars_only": baseline.tolist(), "vera": vera.tolist()}
    atomic_json(paths.REPORTS / "cv_comparison.json", comparison)
    log(
        "CV: "
        + json.dumps(
            {k: v for k, v in comparison.items() if k not in ("fold_maes", "fold_details")}
        )
    )
    # Ablation compares feature groups under the train-split-tuned capacity.
    table = evaluation.ablation_study(
        X, y, groups, lambda: BootstrapEnsemble(n_members=10, params=params)
    )
    table.to_csv(paths.REPORTS / "ablation.csv", index=False)
    log("ablation:\n" + table.to_string())


def stage_report() -> None:
    from app.ml.agents.fusion import FusionModel
    from app.ml.pipeline import VERAPipeline
    from vera_training import calibration, evaluation

    cache = joblib.load(paths.FUSION_CACHE)["matrices"]
    comparison = json.loads((paths.REPORTS / "cv_comparison.json").read_text())
    conformal = json.loads((paths.MODELS / "conformal_qhat.json").read_text())
    fusion = FusionModel(paths.MODELS / "fusion_ensemble.json")
    members = fusion.predict_members(cache["test"]["X"])
    coverage = calibration.interval_metrics(
        members.mean(0).clip(1, 5), members.std(0), cache["test"]["y"], conformal
    )
    g4 = evaluation.gate_g4(comparison, coverage["coverage"])
    test_frame = cache["test"]["frame"]
    aspects = evaluation.aspect_metrics(test_frame.aspects.tolist(), cache["test"]["aspects"])

    pipeline = VERAPipeline(paths.MODELS)
    latencies = []
    for row in test_frame.head(10).itertuples():
        started = time.perf_counter()
        pipeline.process(text=row.text, star_rating=float(row.rating))
        latencies.append(time.perf_counter() - started)
    g3 = {
        "gate": "G3",
        "passed": max(latencies) < 15,
        "max_seconds": max(latencies),
        "mean_seconds": sum(latencies) / len(latencies),
    }
    agreement = json.loads(paths.AGREEMENT_REPORT.read_text())
    report = {
        "cv_comparison": {k: v for k, v in comparison.items() if k != "fold_maes"},
        "test_interval": coverage,
        "conformal": conformal,
        "aspects": aspects.to_dict(orient="records"),
        "aspect_f1_all_at_least_0_70": bool((aspects.detection_f1 >= 0.70).all()),
        "gates": {
            "G1": {k: agreement[k] for k in ("passed", "human_validated", "reference_annotator")},
            "G3": g3,
            "G4": g4,
        },
        "label_agreement": agreement,
    }
    atomic_json(paths.REPORTS / "evaluation_report.json", report)
    log(f"report: G3={g3['passed']} G4={g4['passed']} coverage={coverage}")
    log("aspects:\n" + aspects.to_string())


def stage_diagnostics() -> None:
    """Over/underfitting evidence: per-split quality metrics and a learning curve."""
    from vera_training import evaluation

    cache = joblib.load(paths.FUSION_CACHE)
    matrices, params = cache["matrices"], cache["fusion_params"]
    quality = subprocess_quality_report()
    curve = evaluation.learning_curve(
        matrices["train"]["X"],
        matrices["train"]["y"],
        matrices["train"]["frame"].parent_asin.tolist(),
        matrices["calibration"]["X"],
        matrices["calibration"]["y"],
        params,
    )
    report = {
        "quality": quality,
        "learning_curve_train_vs_calibration": curve,
        "interpretation": {
            "final_gap_calibration_minus_train": round(
                curve[-1]["validation_mae"] - curve[-1]["train_mae"], 4
            ),
            "validation_improvement_last_step": round(
                curve[-2]["validation_mae"] - curve[-1]["validation_mae"], 4
            ),
        },
    }
    atomic_json(paths.REPORTS / "diagnostics.json", report)
    log("learning curve:\n" + pd.DataFrame(curve).to_string(index=False))


def subprocess_quality_report() -> dict[str, Any]:
    """Run ``model_quality_report.py`` logic in-process and return its JSON."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "model_quality_report", ROOT / "training" / "scripts" / "model_quality_report.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()
    return json.loads((paths.REPORTS / "model_quality.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------- main
OUTPUTS = {
    "labels": paths.LABELS_V1,
    "crossfit": paths.EXPERIENCE_OOF,
    "final": paths.MODELS / "experience_model.onnx",
    "domain": paths.MODELS / "domain_tfidf.joblib",
    "aspects": paths.MODELS / "aspect_detector.joblib",
    "fusion": paths.FUSION_CACHE,
    "calibrate": paths.MODELS / "conformal_qhat.json",
    "evaluate": paths.REPORTS / "cv_comparison.json",
    "report": paths.REPORTS / "evaluation_report.json",
    "diagnostics": paths.REPORTS / "diagnostics.json",
}


def main() -> None:
    from vera_training.finetune import FinetuneConfig

    parser = argparse.ArgumentParser()
    parser.add_argument("--stages", default="all")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--label-runs", default="primary-a,qwen-a")
    parser.add_argument("--allow-non-human-reference", action="store_true")
    parser.add_argument(
        "--full-gpu", action="store_true", help="512 tokens + AdamW (>= 12 GB VRAM)"
    )
    args = parser.parse_args()
    paths.ensure_dirs()
    config = FinetuneConfig() if args.full_gpu else FinetuneConfig.small_gpu()
    selected = STAGES if args.stages == "all" else tuple(args.stages.split(","))
    for stage in STAGES:
        if stage not in selected:
            continue
        if OUTPUTS[stage].exists() and not args.force:
            log(f"skip {stage} (exists: {OUTPUTS[stage].name})")
            continue
        log(f"=== {stage} ===")
        started = time.time()
        if stage == "labels":
            stage_labels(args.label_runs.split(","), args.allow_non_human_reference)
        elif stage in ("crossfit", "final"):
            (stage_crossfit if stage == "crossfit" else stage_final)(config)
        else:
            {
                "domain": stage_domain,
                "aspects": stage_aspects,
                "fusion": stage_fusion,
                "diagnostics": stage_diagnostics,
                "calibrate": stage_calibrate,
                "evaluate": stage_evaluate,
                "report": stage_report,
            }[stage]()
        log(f"=== {stage} done in {(time.time() - started) / 60:.1f} min ===")


if __name__ == "__main__":
    main()
