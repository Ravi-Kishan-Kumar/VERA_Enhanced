"""Independent labeling rounds and blinded reference-agreement gates (PRD G1)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

from vera_training.io import atomic_json
from vera_training.labeling import ExperienceLabel


def paired_agreement(left: np.ndarray, right: np.ndarray) -> dict[str, Any]:
    left, right = np.asarray(left, float), np.asarray(right, float)
    if left.shape != right.shape or left.ndim != 1 or not len(left):
        raise ValueError("Agreement requires nonempty aligned score vectors")
    valid = np.arange(1, 5.01, 0.5)
    if not np.isin(left, valid).all() or not np.isin(right, valid).all():
        raise ValueError("Agreement scores must be half-step labels in [1, 5]")
    kappa = float(
        cohen_kappa_score((left * 2).astype(int), (right * 2).astype(int), weights="quadratic")
    )
    return {
        "n": len(left),
        "kappa": kappa if np.isfinite(kappa) else None,
        "mae": float(np.abs(left - right).mean()),
    }


def export_human_sheet(pool: pd.DataFrame, path: str | Path, n: int = 200, seed: int = 42) -> None:
    if len(pool) < n:
        raise ValueError(f"Need {n} reviews for blinded human validation")
    sample = pool.sample(n=n, random_state=seed)
    sheet = sample[["review_id", "product_title", "text"]].copy()
    sheet["experience_score"] = ""
    # No stars or Gemini labels are exported to the human annotator.
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if Path(path).exists():
        raise FileExistsError("Human sheet already exists; refusing to overwrite annotations")
    sheet.to_csv(path, index=False)


def _run_scores(state: dict[str, Any]) -> dict[str, float]:
    return {
        k: ExperienceLabel.model_validate(v).experience_score for k, v in state["labels"].items()
    }


def agreement_report(
    first_path: str | Path,
    second_path: str | Path,
    reference_path: str | Path,
    output: str | Path,
    minimum_n: int = 200,
    *,
    reference_annotator: str = "unspecified reference (not verified human)",
    cross_model_path: str | Path | None = None,
) -> dict[str, Any]:
    """Gate G1 evidence: self-consistency, reference-annotator agreement, optional cross-model.

    Args:
        first_path / second_path: Two runs of the SAME model and prompt with different seeds.
        reference_path: CSV ``review_id, experience_score`` from the reference annotator.
        reference_annotator: ``"human"`` only when a person supplied the annotations, or
            a description of a non-human reference (e.g. ``"claude-opus-5 (LLM, not human)"``).
            The report sets ``human_validated`` only for an explicit ``"human"`` value.
        cross_model_path: Optional run from a DIFFERENT model family on the same prompt.
    """
    if not reference_annotator.strip():
        raise ValueError("Reference annotator must be identified")
    first = json.loads(Path(first_path).read_text(encoding="utf-8"))
    second = json.loads(Path(second_path).read_text(encoding="utf-8"))
    one, two = first["specification"], second["specification"]
    if one["run_id"] == two["run_id"] or one["seed"] == two["seed"]:
        raise ValueError("Self-consistency needs distinct run IDs AND seeds")
    for key in ("provider", "model", "prompt_hash"):
        if one[key] != two[key]:
            raise ValueError(f"Self-consistency requires matching {key}")
    common = sorted(set(first["labels"]) & set(second["labels"]))
    if len(common) < minimum_n:
        raise ValueError(f"Need {minimum_n} independently completed review pairs")
    scores_one = {
        k: ExperienceLabel.model_validate(v).experience_score for k, v in first["labels"].items()
    }
    scores_two = {
        k: ExperienceLabel.model_validate(v).experience_score for k, v in second["labels"].items()
    }
    self_metrics = paired_agreement(
        np.array([scores_one[k] for k in common]), np.array([scores_two[k] for k in common])
    )
    reference = pd.read_csv(reference_path, dtype={"review_id": str})
    if reference.review_id.duplicated().any() or reference.experience_score.isna().any():
        raise ValueError("Reference annotations contain duplicate IDs or unfilled scores")
    if len(reference) < minimum_n or not set(reference.review_id) <= set(scores_one):
        raise ValueError("Reference annotations must cover at least the minimum completed labels")
    reference_metrics = paired_agreement(
        reference.experience_score.to_numpy(float),
        reference.review_id.map(scores_one).to_numpy(float),
    )
    passed = (
        self_metrics["kappa"] is not None
        and self_metrics["kappa"] > 0.70
        and reference_metrics["kappa"] is not None
        and reference_metrics["kappa"] > 0.55
        and self_metrics["mae"] < 0.40
        and reference_metrics["mae"] < 0.60
    )
    cross_metrics = None
    if cross_model_path is not None:
        cross = json.loads(Path(cross_model_path).read_text(encoding="utf-8"))
        if cross["specification"]["prompt_hash"] != one["prompt_hash"]:
            raise ValueError("Cross-model run must use the same prompt")
        cross_scores = _run_scores(cross)
        shared = sorted(set(cross_scores) & set(scores_one))
        cross_metrics = {
            "model": cross["specification"]["model"],
            **paired_agreement(
                np.array([scores_one[k] for k in shared]),
                np.array([cross_scores[k] for k in shared]),
            ),
        }
    human_validated = reference_annotator.strip().casefold() == "human"
    report = {
        "gate": "G1",
        "passed": bool(passed),
        "human_validated": human_validated,
        "reference_annotator": reference_annotator,
        "self_consistency": self_metrics,
        "reference_agreement": reference_metrics,
        "cross_model_agreement": cross_metrics,
        "label_specification": one,
        "noise_floor_note": (
            "Reference-annotator disagreement is a reference, not latent truth."
            if human_validated
            else "G1 thresholds were checked against a non-human or unverified reference "
            "annotator. Do not report this as human-validated."
        ),
    }
    atomic_json(output, report)
    return report


def get_reference_agreement(report: Mapping[str, Any]) -> dict[str, Any]:
    """Return reference metrics, safely reading pre-rename non-human reports.

    Older reports used ``human_agreement`` even when ``human_validated`` was false.
    Interpret that legacy field as reference agreement only when its metadata explicitly
    records a non-human annotator; ambiguous legacy reports must be regenerated.
    """
    metrics = report.get("reference_agreement")
    if isinstance(metrics, dict):
        return metrics
    annotator = report.get("reference_annotator")
    if (
        report.get("human_validated") is False
        and isinstance(annotator, str)
        and annotator.strip()
        and annotator.strip().casefold() != "human"
        and isinstance(report.get("human_agreement"), dict)
    ):
        return report["human_agreement"]
    raise ValueError("Agreement report has no unambiguous reference-agreement metrics")


def require_label_gate(
    path: str | Path, *, label_specification: dict[str, Any] | None = None
) -> None:
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    if report.get("gate") != "G1" or report.get("passed") is not True:
        raise ValueError("Label reliability gate G1 has not passed")
    if label_specification is not None and report.get("label_specification") != label_specification:
        raise ValueError("Agreement evidence does not belong to this label run")
