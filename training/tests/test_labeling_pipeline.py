"""Tests for session-4 additions: Groq pacing, balanced pools, honest agreement reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pandas as pd
import pytest

from app.ml.constants import EARBUD_ASPECTS
from vera_training import data, labeling
from vera_training.agreement import agreement_report, get_reference_agreement
from vera_training.data import is_earbud_product


def _label(score: float) -> dict[str, Any]:
    return {
        "experience_score": score,
        "experience_rationale": "r",
        "has_irony_or_sarcasm": False,
        "review_quality": "high",
        "aspects": {a: {"mentioned": False, "sentiment": "not_mentioned"} for a in EARBUD_ASPECTS},
    }


def test_parse_duration_formats() -> None:
    assert labeling.parse_duration("34.605s") == pytest.approx(34.605)
    assert labeling.parse_duration("36m0s") == 2160
    assert labeling.parse_duration("1h2m3s") == 3723
    assert labeling.parse_duration("47") == 47
    assert labeling.parse_duration("250ms") == pytest.approx(0.25)


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _pool(handler: Any, clock: _Clock, keys: int = 2) -> labeling.GroqPool:
    pool = labeling.GroqPool(
        "m", [f"k{i}" for i in range(keys)], clock=clock.time, sleep=clock.sleep
    )
    pool._http = httpx.Client(
        base_url="https://api.groq.com/openai/v1", transport=httpx.MockTransport(handler)
    )
    return pool


def test_groq_pool_waits_on_429_then_succeeds() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers["Authorization"])
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "7"}, text="slow down")
        return httpx.Response(
            200,
            headers={"x-ratelimit-remaining-tokens": "7000", "x-ratelimit-remaining-requests": "5"},
            json={"choices": [{"message": {"content": "{}"}}]},
        )

    clock = _Clock()
    assert _pool(handler, clock, keys=1)("sys", "prompt", 1) == "{}"
    assert len(calls) == 2 and clock.sleeps and clock.sleeps[0] >= 7


def test_groq_pool_retires_keys_on_daily_quota() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Please try again in 2h3m1s.")

    with pytest.raises(labeling.QuotaExhaustedError):
        _pool(handler, _Clock())("sys", "prompt", 1)


def test_run_labels_stops_cleanly_when_quota_exhausted(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {
            "review_id": ["a", "b"],
            "parent_asin": ["p", "q"],
            "text": ["x" * 30] * 2,
            "rating": [1, 5],
        }
    )

    def provider(system: str, prompt: str, seed: int) -> str:
        raise labeling.QuotaExhaustedError("done")

    state = labeling.run_labels(
        frame,
        tmp_path / "c.json",
        provider,
        provider_name="p",
        model="m",
        run_id="r",
        seed=1,
        max_requests=10,
        sleep=lambda _: None,
    )
    assert state["requests"] == 0 and state["labels"] == {}


def test_balanced_order_prefixes_are_star_balanced() -> None:
    rng = np.random.default_rng(0)
    frame = pd.DataFrame(
        {
            "review_id": [f"r{i}" for i in range(1000)],
            "parent_asin": [f"P{i % 300}" for i in range(1000)],
            "text": ["words " * 25] * 1000,
            "rating": rng.integers(1, 6, 1000),
        }
    )
    pool = data.sample_for_labeling(frame, n=200, product_cap=3, balanced_order=True)
    for prefix in (5, 50, 100):
        assert pool.rating.iloc[:prefix].value_counts().nunique() == 1


def test_earbud_filter_uses_category_and_accessory_rules() -> None:
    audio = "Electronics > Headphones, Earbuds & Accessories > Headphones & Earbuds"
    assert is_earbud_product({"parent_asin": "A", "title": "TWS Earbuds", "categories": [audio]})
    assert not is_earbud_product(
        {"parent_asin": "B", "title": "FPV headset", "categories": ["Video Glasses"]}
    )
    assert is_earbud_product({"parent_asin": "C", "title": "Earbuds with Charging Case"})
    assert not is_earbud_product({"parent_asin": "D", "title": "AirPods Case Cover"})


def test_agreement_report_flags_non_human_reference(tmp_path: Path) -> None:
    ids = [f"r{i}" for i in range(40)]
    scores = [1.0 + (i % 9) * 0.5 for i in range(40)]

    def run(run_id: str, seed: int, model: str, shift: float = 0.0) -> Path:
        path = tmp_path / f"{run_id}.json"
        spec = {
            "provider": "groq",
            "model": model,
            "run_id": run_id,
            "seed": seed,
            "prompt_hash": "h",
            "input_hash": run_id,
        }
        labels = {i: _label(min(5.0, s + shift)) for i, s in zip(ids, scores, strict=True)}
        path.write_text(json.dumps({"specification": spec, "labels": labels}))
        return path

    reference = tmp_path / "ref.csv"
    pd.DataFrame({"review_id": ids, "experience_score": scores}).to_csv(reference, index=False)
    report = agreement_report(
        run("a", 1, "big"),
        run("b", 2, "big"),
        reference,
        tmp_path / "out.json",
        minimum_n=40,
        reference_annotator="claude (LLM, not human)",
        cross_model_path=run("c", 3, "other", 0.5),
    )
    assert report["passed"] is True
    assert report["human_validated"] is False
    assert report["reference_annotator"] == "claude (LLM, not human)"
    assert "reference_agreement" in report
    assert "human_agreement" not in report
    assert report["cross_model_agreement"]["model"] == "other"

    unspecified = agreement_report(
        run("a", 1, "big"),
        run("b", 2, "big"),
        reference,
        tmp_path / "unspecified.json",
        minimum_n=40,
    )
    assert unspecified["human_validated"] is False


def test_legacy_non_human_agreement_report_is_read_as_reference() -> None:
    metrics = {"n": 200, "kappa": 0.95, "mae": 0.24}
    legacy = {
        "human_validated": False,
        "reference_annotator": "claude-opus (LLM, not human)",
        "human_agreement": metrics,
    }
    assert get_reference_agreement(legacy) is metrics


def test_ambiguous_legacy_agreement_report_is_rejected() -> None:
    legacy = {"human_validated": False, "human_agreement": {"n": 200}}
    with pytest.raises(ValueError, match="unambiguous reference-agreement"):
        get_reference_agreement(legacy)
