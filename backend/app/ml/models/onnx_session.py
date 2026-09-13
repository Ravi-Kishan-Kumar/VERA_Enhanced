"""Thin onnxruntime helpers shared by the transformer agents (Agents 2 and 3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import numpy as np


class InferenceSessionLike(Protocol):
    """Subset of ``onnxruntime.InferenceSession`` the agents rely on (eases testing)."""

    def get_inputs(self) -> list[Any]: ...

    def run(
        self, output_names: list[str] | None, input_feed: dict[str, np.ndarray]
    ) -> list[Any]: ...


def create_session(model_path: str | Path, intra_op_threads: int = 2) -> InferenceSessionLike:
    """Create a CPU inference session with full graph optimisation."""
    import onnxruntime as ort  # local import keeps module import cheap for tests

    path = Path(model_path)
    if not path.is_file():
        raise FileNotFoundError(f"ONNX model not found: {path}")
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = intra_op_threads
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session: InferenceSessionLike = ort.InferenceSession(
        str(path), sess_options=opts, providers=["CPUExecutionProvider"]
    )
    return session


def build_feed(
    session: InferenceSessionLike, encoded: dict[str, np.ndarray]
) -> dict[str, np.ndarray]:
    """Select exactly the inputs the graph declares.

    DeBERTa-v3 has ``type_vocab_size=0``, so its ONNX export has no
    ``token_type_ids`` input; feeding an undeclared input makes onnxruntime
    raise ``INVALID_ARGUMENT``. Conversely, BERT-style exports require it.
    """
    feed: dict[str, np.ndarray] = {}
    for spec in session.get_inputs():
        name = spec.name
        if name in encoded:
            feed[name] = encoded[name].astype(np.int64, copy=False)
        elif name == "token_type_ids":
            feed[name] = np.zeros_like(encoded["input_ids"], dtype=np.int64)
        else:
            raise KeyError(f"ONNX graph expects unsupported input {name!r}")
    return feed


def softmax(logits: np.ndarray, axis: int = -1) -> np.ndarray:
    """Numerically stable softmax (the PRD's ``exp(x)/sum(exp(x))`` overflows for large logits)."""
    shifted = logits - np.max(logits, axis=axis, keepdims=True)
    exp = np.exp(shifted)
    result: np.ndarray = exp / np.sum(exp, axis=axis, keepdims=True)
    return result
