"""Torch-free tokenizer (PRD §4.4).

Drop-in replacement for ``transformers.AutoTokenizer`` in production. The
HuggingFace ``tokenizers`` library is a small Rust extension that reads the same
``tokenizer.json`` a fine-tuned model ships with, but never imports torch.

Differences from the PRD sketch (see DECISIONS.md):
* Loads from a local ``tokenizer.json`` file (downloaded with the ONNX model)
  instead of ``Tokenizer.from_pretrained`` — no network at inference time, and
  the base ``microsoft/deberta-v3-base`` repo does not ship a ``tokenizer.json``.
* Pads to the longest sequence in the batch instead of always to 512 tokens.
  The ONNX graphs have dynamic axes, so this is numerically identical and
  several times faster on a shared CPU.
* The pad id/token are read from the vocabulary instead of hardcoded to 0.
* Pair inputs use ``only_first`` truncation so the (short) aspect sentence is
  never cut — only the review body is truncated.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from tokenizers import Encoding, Tokenizer

_PAD_CANDIDATES = ("[PAD]", "<pad>", "<PAD>")


class LightTokenizer:
    """Rust-backed tokenizer producing int64 numpy batches for onnxruntime."""

    def __init__(self, tokenizer_path: str | Path, max_length: int = 512) -> None:
        path = Path(tokenizer_path)
        if not path.is_file():
            raise FileNotFoundError(f"tokenizer.json not found: {path}")
        self._tok = Tokenizer.from_file(str(path))
        self.max_length = max_length

        pad_token = next((t for t in _PAD_CANDIDATES if self._tok.token_to_id(t) is not None), None)
        if pad_token is None:
            raise ValueError(f"No padding token {_PAD_CANDIDATES} in vocabulary of {path}")
        self.pad_token = pad_token
        self.pad_id = int(self._tok.token_to_id(pad_token))
        self._tok.enable_padding(pad_id=self.pad_id, pad_token=self.pad_token)

    # ------------------------------------------------------------------
    def __call__(self, text: str, text_pair: str | None = None) -> dict[str, np.ndarray]:
        """Encode one text (or one text pair) into a batch of size 1."""
        if text_pair is None:
            return self.encode_batch([text])
        return self.encode_pairs([(text, text_pair)])

    def encode_batch(self, texts: list[str]) -> dict[str, np.ndarray]:
        """Encode single sequences, padded to the longest in the batch."""
        if not texts:
            raise ValueError("encode_batch() needs at least one text")
        self._tok.enable_truncation(max_length=self.max_length, strategy="longest_first")
        return self._to_arrays(self._tok.encode_batch(texts))

    def encode_pairs(self, pairs: list[tuple[str, str]]) -> dict[str, np.ndarray]:
        """Encode (first, second) pairs; only the first sequence is ever truncated."""
        if not pairs:
            raise ValueError("encode_pairs() needs at least one pair")
        self._tok.enable_truncation(max_length=self.max_length, strategy="only_first")
        return self._to_arrays(self._tok.encode_batch(pairs))

    @staticmethod
    def _to_arrays(encodings: list[Encoding]) -> dict[str, np.ndarray]:
        return {
            "input_ids": np.asarray([e.ids for e in encodings], dtype=np.int64),
            "attention_mask": np.asarray([e.attention_mask for e in encodings], dtype=np.int64),
            "token_type_ids": np.asarray([e.type_ids for e in encodings], dtype=np.int64),
        }
