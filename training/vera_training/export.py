"""ONNX export + INT8 quantisation for Agents 2 and 3 (PRD §12.3, gate G2).

Produces the transformer artifacts listed in ``app.ml.models.loader``:
``experience_model.onnx``, ``experience_tokenizer.json``, ``absa_model.onnx``,
``absa_tokenizer.json``, ``absa_config.json``.

Parity is checked through the PRODUCTION tokenizer + session helpers, so a
tokenizer mismatch is caught here instead of in deployment. Gate G2 compares
PyTorch with the FP32 ONNX graph (< 0.01); INT8 drift is reported separately
because quantisation legitimately moves outputs.

Quantisation uses ``onnxruntime.quantization.quantize_dynamic`` rather than the
PRD's ``ORTQuantizer.avx512_vnni`` config, which targets AVX-512 VNNI CPUs —
Render's shared CPUs are not guaranteed to have it.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from app.ml.agents.experience_extractor import format_experience_input
from app.ml.models.onnx_session import build_feed, create_session, softmax
from app.ml.models.tokenizer_wrapper import LightTokenizer

ABSA_MODEL_ID = "yangheng/deberta-v3-base-absa-v1.1"
G2_TOLERANCE = 0.01


def export_fp32(model_name_or_path: str | Path, output_dir: str | Path, opset: int = 14) -> Path:
    """Export a sequence-classification model to ``output_dir/model.onnx``."""
    from optimum.exporters.onnx import main_export

    output_dir = Path(output_dir)
    main_export(
        model_name_or_path=str(model_name_or_path),
        output=output_dir,
        task="text-classification",
        opset=opset,
    )
    return output_dir / "model.onnx"


def quantize_int8(fp32_path: str | Path, int8_path: str | Path) -> Path:
    """Dynamic INT8 quantisation (per-channel, reduced range — the least lossy dynamic variant).

    Measured on DeBERTa-v3 ABSA (see DECISIONS.md): per-tensor INT8 kept only 17–21% of
    FP32 argmax predictions and per-channel 76%, so :func:`select_deployable` normally
    rejects it in favour of FP32.
    """
    from onnxruntime.quantization import QuantType, quantize_dynamic

    quantize_dynamic(
        str(fp32_path),
        str(int8_path),
        weight_type=QuantType.QInt8,
        op_types_to_quantize=["MatMul"],
        per_channel=True,
        reduce_range=True,
    )
    return Path(int8_path)


#: A quantised graph is deployed only if it reproduces FP32 this closely.
MIN_ARGMAX_AGREEMENT = 0.99  # classification (ABSA) ...
MAX_PROB_DRIFT = 0.02  # ... and mean |Δ probability| (argmax alone is too coarse)
#: Fewer samples made a broken INT8 graph look perfect (10/10 agreement by luck).
MIN_PARITY_SAMPLES = 32
MAX_REGRESSION_DRIFT = 0.05  # mean |Δ score| on the 1–5 scale (experience model)


def _torch_logits(
    model_name_or_path: str | Path, texts: list[str], pairs: list[str] | None, max_length: int
) -> np.ndarray:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(model_name_or_path), use_fast=True)
    model = AutoModelForSequenceClassification.from_pretrained(str(model_name_or_path)).eval()
    rows = []
    with torch.no_grad():
        for index, text in enumerate(texts):
            encoded = tokenizer(
                text,
                pairs[index] if pairs else None,
                truncation="only_first" if pairs else True,
                max_length=max_length,
                return_tensors="pt",
            )
            rows.append(model(**encoded).logits.float().numpy()[0])
    return np.vstack(rows)


def _onnx_logits(
    onnx_path: Path, tokenizer_json: Path, texts: list[str], pairs: list[str] | None
) -> np.ndarray:
    tokenizer = LightTokenizer(tokenizer_json)
    session = create_session(onnx_path)
    rows = []
    for index, text in enumerate(texts):
        encoded = tokenizer(text, pairs[index] if pairs else None)
        rows.append(np.asarray(session.run(None, build_feed(session, encoded))[0])[0])
    return np.vstack(rows).astype(np.float64)


def parity_report(
    model_name_or_path: str | Path,
    fp32: Path,
    int8: Path,
    tokenizer_json: Path,
    texts: list[str],
    pairs: list[str] | None = None,
    max_length: int = 512,
) -> dict[str, Any]:
    """Max |Δ| between PyTorch and FP32 / INT8 ONNX outputs (+ argmax agreement for ABSA)."""
    reference = _torch_logits(model_name_or_path, texts, pairs, max_length)
    fp32_out = _onnx_logits(fp32, tokenizer_json, texts, pairs)
    int8_out = _onnx_logits(int8, tokenizer_json, texts, pairs)
    report: dict[str, Any] = {
        "n": len(texts),
        "fp32_max_abs_diff": float(np.max(np.abs(reference - fp32_out))),
        "int8_max_abs_diff": float(np.max(np.abs(reference - int8_out))),
        "int8_mean_abs_diff": float(np.mean(np.abs(reference - int8_out))),
    }
    if reference.shape[1] > 1:
        ref_probs, int8_probs = softmax(reference), softmax(int8_out)
        report["int8_argmax_agreement"] = float(
            np.mean(ref_probs.argmax(1) == int8_probs.argmax(1))
        )
        report["int8_mean_prob_diff"] = float(np.mean(np.abs(ref_probs - int8_probs)))
    report["g2_passed"] = report["fp32_max_abs_diff"] < G2_TOLERANCE
    return report


def _export(
    source: str | Path,
    work_dir: Path,
    out_dir: Path,
    prefix: str,
    texts: list[str],
    pairs: list[str] | None,
    max_length: int = 512,
) -> dict[str, Any]:
    from tokenizers import Tokenizer
    from transformers import AutoTokenizer

    fp32 = export_fp32(source, work_dir / f"{prefix}_fp32")
    tokenizer_json = out_dir / f"{prefix}_tokenizer.json"
    AutoTokenizer.from_pretrained(str(source), use_fast=True).save_pretrained(
        str(work_dir / f"{prefix}_tokenizer")
    )
    # Persist the training truncation length inside tokenizer.json so production's
    # LightTokenizer truncates exactly like fine-tuning did.
    fast = Tokenizer.from_file(str(work_dir / f"{prefix}_tokenizer" / "tokenizer.json"))
    fast.no_padding()
    fast.enable_truncation(max_length=max_length)
    fast.save(str(tokenizer_json))
    int8 = quantize_int8(fp32, work_dir / f"{prefix}_int8.onnx")
    report = parity_report(source, fp32, int8, tokenizer_json, texts, pairs, max_length)
    report["max_length"] = max_length
    report["int8_size_mb"] = round(int8.stat().st_size / 1e6, 1)
    report["fp32_size_mb"] = round(fp32.stat().st_size / 1e6, 1)

    # Deploy INT8 only when it preserves predictions; otherwise ship the exact FP32 graph.
    if len(texts) < MIN_PARITY_SAMPLES:
        raise ValueError(f"Parity needs >= {MIN_PARITY_SAMPLES} samples, got {len(texts)}")
    if "int8_argmax_agreement" in report:
        int8_ok = (
            report["int8_argmax_agreement"] >= MIN_ARGMAX_AGREEMENT
            and report["int8_mean_prob_diff"] <= MAX_PROB_DRIFT
        )
    else:
        int8_ok = report["int8_mean_abs_diff"] <= MAX_REGRESSION_DRIFT
    chosen = int8 if int8_ok else fp32
    shutil.copyfile(chosen, out_dir / f"{prefix}_model.onnx")
    report["deployed_precision"] = "int8" if int8_ok else "fp32"
    report["deployed_size_mb"] = round((out_dir / f"{prefix}_model.onnx").stat().st_size / 1e6, 1)
    (out_dir / f"{prefix}_export_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    if not report["g2_passed"]:
        raise AssertionError(f"G2 parity failed for {prefix}: {report}")
    return report


def export_experience(
    finetuned_dir: str | Path,
    out_dir: str | Path,
    sample_texts: list[str],
    work_dir: str | Path,
    max_length: int = 512,
) -> dict[str, Any]:
    """Export the fine-tuned Agent 2 model and verify parity.

    ``max_length`` must equal the fine-tuning ``FinetuneConfig.max_length``.
    """
    out, work = Path(out_dir), Path(work_dir)
    out.mkdir(parents=True, exist_ok=True)
    texts = [format_experience_input(t) for t in sample_texts]
    return _export(finetuned_dir, work, out, "experience", texts, None, max_length)


def export_absa(
    out_dir: str | Path,
    sample_texts: list[str],
    sample_aspects: list[str],
    work_dir: str | Path,
    model_id: str = ABSA_MODEL_ID,
) -> dict[str, Any]:
    """Export the pre-trained ABSA model, its label map, and verify parity."""
    from transformers import AutoConfig

    out, work = Path(out_dir), Path(work_dir)
    out.mkdir(parents=True, exist_ok=True)
    id2label = {str(k): v for k, v in AutoConfig.from_pretrained(model_id).id2label.items()}
    (out / "absa_config.json").write_text(
        json.dumps({"model_id": model_id, "id2label": id2label}, indent=2), encoding="utf-8"
    )
    return _export(model_id, work, out, "absa", sample_texts, sample_aspects)
