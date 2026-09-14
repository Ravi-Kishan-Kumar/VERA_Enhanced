"""Agent 2 fine-tuning — DeBERTa-v3-base regression head (PRD §12.2). Colab GPU.

Two outputs:

1. :func:`crossfit_predictions` — K product-grouped folds, each model predicts
   only reviews whose PRODUCTS it never trained on. These out-of-fold scores are
   the Agent 2 features for fusion training, calibration, and evaluation. (The
   PRD fed fusion the in-sample predictions of a model trained on the same
   labels, so fusion learned to over-trust an overfit signal.)
2. :func:`train_final` — one model on all labels (15% product-grouped
   validation for early stopping), exported to ONNX for production.

Every fold checkpoints to ``work_dir`` so a Colab disconnect resumes where it
stopped. torch/transformers are imported lazily; this module imports cleanly
in the production-pinned ``.venv``.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from app.ml.agents.experience_extractor import format_experience_input
from vera_training.splits import assert_disjoint, holdout


@dataclass(frozen=True)
class FinetuneConfig:
    base_model: str = "microsoft/deberta-v3-base"
    max_length: int = 512
    epochs: int = 5
    learning_rate: float = 2e-5
    train_batch_size: int = 8
    eval_batch_size: int = 16
    gradient_accumulation_steps: int = 1
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01
    early_stopping_patience: int = 2
    validation_fraction: float = 0.15
    seed: int = 42
    #: Memory savers for small GPUs (see :meth:`small_gpu`).
    gradient_checkpointing: bool = False
    optim: str = "adamw_torch"

    @classmethod
    def small_gpu(cls) -> FinetuneConfig:
        """4 GB VRAM profile (e.g. RTX 2050): Adafactor (no Adam moment buffers),
        gradient checkpointing, 384 tokens, batch 4 × 2 accumulation = effective 8."""
        return cls(
            max_length=384,
            train_batch_size=4,
            eval_batch_size=8,
            gradient_accumulation_steps=2,
            gradient_checkpointing=True,
            optim="adafactor",
            learning_rate=3e-5,
        )


def _dataset(frame: pd.DataFrame, tokenizer: Any, max_length: int) -> Any:
    from datasets import Dataset

    data = Dataset.from_dict(
        {
            "text": [format_experience_input(t) for t in frame["text"].astype(str)],
            "labels": frame["experience_score"].astype("float32").tolist(),
        }
    )
    # Dynamic padding (DataCollatorWithPadding) instead of padding to 512: ~2x faster.
    return data.map(
        lambda batch: tokenizer(batch["text"], truncation=True, max_length=max_length),
        batched=True,
        remove_columns=["text"],
    )


def train_regressor(
    train: pd.DataFrame, validation: pd.DataFrame, output_dir: str | Path, config: FinetuneConfig
) -> Path:
    """Fine-tune one regression model with early stopping; save model + fast tokenizer."""
    import torch
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        DataCollatorWithPadding,
        EarlyStoppingCallback,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    assert_disjoint(train["parent_asin"], validation["parent_asin"])
    set_seed(config.seed)
    output_dir = Path(output_dir)
    tokenizer = AutoTokenizer.from_pretrained(config.base_model, use_fast=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        config.base_model, num_labels=1, problem_type="regression"
    )

    def compute_metrics(eval_pred: Any) -> dict[str, float]:
        predictions, labels = eval_pred
        return {"mae": float(np.mean(np.abs(np.asarray(predictions).reshape(-1) - labels)))}

    args = TrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        num_train_epochs=config.epochs,
        learning_rate=config.learning_rate,
        per_device_train_batch_size=config.train_batch_size,
        per_device_eval_batch_size=config.eval_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        warmup_ratio=config.warmup_ratio,
        weight_decay=config.weight_decay,
        eval_strategy="epoch",  # `evaluation_strategy` (PRD) is deprecated in 4.45
        save_strategy="epoch",
        save_total_limit=1,
        load_best_model_at_end=True,
        metric_for_best_model="eval_mae",
        greater_is_better=False,
        # bf16 on Ampere+ (DeBERTa-v3 is prone to fp16 overflow); fp16 on older GPUs.
        bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
        fp16=torch.cuda.is_available() and not torch.cuda.is_bf16_supported(),
        gradient_checkpointing=config.gradient_checkpointing,
        optim=config.optim,
        dataloader_num_workers=0,  # Windows-safe
        logging_steps=20,
        report_to="none",
        seed=config.seed,
    )
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=_dataset(train, tokenizer, config.max_length),
        eval_dataset=_dataset(validation, tokenizer, config.max_length),
        data_collator=DataCollatorWithPadding(tokenizer),
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=config.early_stopping_patience)],
    )
    trainer.train()
    metrics = trainer.evaluate()

    final_dir = output_dir / "model"
    trainer.save_model(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))  # writes tokenizer.json (fast tokenizer)
    shutil.rmtree(output_dir / "checkpoints", ignore_errors=True)
    (final_dir / "vera_training.json").write_text(
        json.dumps({"config": asdict(config), "validation": metrics}, indent=2), encoding="utf-8"
    )
    return final_dir


def predict_texts(
    model_dir: str | Path, texts: list[str], batch_size: int = 16, max_length: int = 512
) -> np.ndarray:
    """Raw regression outputs from a saved PyTorch model."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), use_fast=True)
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir)).to(device).eval()
    outputs: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(texts), batch_size):
            batch = [format_experience_input(t) for t in texts[start : start + batch_size]]
            encoded = tokenizer(
                batch, truncation=True, max_length=max_length, padding=True, return_tensors="pt"
            ).to(device)
            outputs.append(model(**encoded).logits.float().cpu().numpy().reshape(-1))
    return np.concatenate(outputs) if outputs else np.empty(0)


def crossfit_predictions(
    frame: pd.DataFrame, work_dir: str | Path, config: FinetuneConfig, n_folds: int = 5
) -> np.ndarray:
    """Out-of-fold raw predictions aligned with ``frame`` rows (resumable per fold)."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    frame = frame.reset_index(drop=True)
    oof = np.full(len(frame), np.nan)

    for fold, (train_idx, test_idx) in enumerate(
        GroupKFold(n_splits=n_folds).split(frame, groups=frame["parent_asin"])
    ):
        fold_file = work_dir / f"fold_{fold}_oof.npz"
        if fold_file.exists():
            saved = np.load(fold_file)
            if not np.array_equal(saved["index"], test_idx):
                raise ValueError(f"{fold_file} belongs to a different split; delete work_dir")
            oof[test_idx] = saved["pred"]
            continue

        development, test = frame.iloc[train_idx], frame.iloc[test_idx]
        assert_disjoint(development["parent_asin"], test["parent_asin"])
        train, validation = holdout(development, config.validation_fraction, config.seed + fold)
        model_dir = train_regressor(train, validation, work_dir / f"fold_{fold}", config)
        predictions = predict_texts(
            model_dir, test["text"].astype(str).tolist(), max_length=config.max_length
        )
        np.savez(fold_file, index=test_idx, pred=predictions)
        oof[test_idx] = predictions
        shutil.rmtree(model_dir.parent, ignore_errors=True)  # fold models are disposable

    if np.isnan(oof).any():
        raise RuntimeError("Some rows have no out-of-fold prediction")
    return oof


def train_final(frame: pd.DataFrame, output_dir: str | Path, config: FinetuneConfig) -> Path:
    """Production model: all labels, product-grouped validation for early stopping."""
    train, validation = holdout(frame, config.validation_fraction, config.seed)
    return train_regressor(train, validation, output_dir, config)
