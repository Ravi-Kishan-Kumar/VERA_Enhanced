"""Star-blinded labeling with schema validation, bounded calls and durable resume."""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ml.constants import EARBUD_ASPECTS
from vera_training.io import atomic_json, digest, validate_reviews

# Verbatim PRD §7.2. Do not insert rating, metadata, examples or prior labels.
SYSTEM_PROMPT = """You are an expert product experience analyst. 
Your job is to read product reviews and estimate the actual customer experience — 
completely ignoring the star rating they gave.

Stars are unreliable. Focus ONLY on what the text says about the experience.
Return ONLY valid JSON. No markdown, no explanation, no preamble."""

USER_PROMPT_TEMPLATE = '''Product: {product_title}

Review text:
"""
{review_text}
"""

Return a JSON object with this exact schema:
{{
  "experience_score": <float, one of [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]>,
  "experience_rationale": "<one sentence: what specific evidence led to this score>",
  "has_irony_or_sarcasm": <true or false>,
  "review_quality": "<one of: low, medium, high>",
  "aspects": {{
    "sound_quality":      {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}},
    "bass":               {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}},
    "battery_life":       {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}},
    "comfort":            {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}},
    "fit":                {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}},
    "build_quality":      {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}},
    "connectivity":       {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}},
    "microphone":         {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}},
    "noise_cancellation": {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}},
    "value":              {{"mentioned": <bool>, "sentiment": "<positive|negative|neutral|not_mentioned>"}}
  }}
}}'''


class AspectLabel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    mentioned: bool
    sentiment: Literal["positive", "negative", "neutral", "not_mentioned"]

    @model_validator(mode="after")
    def consistent(self) -> AspectLabel:
        if self.mentioned == (self.sentiment == "not_mentioned"):
            raise ValueError("mentioned must agree with sentiment")
        return self


class ExperienceLabel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    experience_score: float = Field(ge=1, le=5, allow_inf_nan=False)
    experience_rationale: str = Field(min_length=1)
    has_irony_or_sarcasm: bool
    review_quality: Literal["low", "medium", "high"]
    aspects: dict[str, AspectLabel]

    @model_validator(mode="after")
    def valid_score_and_aspects(self) -> ExperienceLabel:
        if self.experience_score * 2 != round(self.experience_score * 2):
            raise ValueError("experience_score must be a half-step")
        if set(self.aspects) != set(EARBUD_ASPECTS):
            raise ValueError("Exactly all ten canonical earbud aspects are required")
        if not self.experience_rationale.strip():
            raise ValueError("Empty rationale")
        return self


class Provider:
    """No network call until explicitly invoked. SDK automatic retries are disabled."""

    def __init__(self, name: Literal["gemini", "groq"], model: str) -> None:
        self.name, self.model = name, model
        if not model.strip():
            raise ValueError("Choose an available provider model explicitly")
        if name == "gemini":
            from google import genai

            self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        elif name == "groq":
            from groq import Groq

            self.client = Groq(api_key=os.environ["GROQ_API_KEY"], max_retries=0, timeout=60)
        else:
            raise ValueError("Provider must be gemini or groq")

    def __call__(self, system: str, prompt: str, seed: int) -> str:
        if self.name == "gemini":
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "system_instruction": system,
                    "response_mime_type": "application/json",
                    "temperature": 0.1,
                    "max_output_tokens": 2048,
                    "seed": seed,
                },
            )
            if not response.text:
                raise ValueError("Gemini returned no text")
            return response.text
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=2048,
            seed=seed,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Groq returned no text")
        return content


class QuotaExhaustedError(RuntimeError):
    """Every key hit its daily quota. ``run_labels`` saves and stops instead of burning rows."""


class GroqPool:
    """Groq chat provider pacing requests from Groq's own rate-limit headers.

    Groq enforces per-ORGANIZATION limits per model (requests/day, tokens/min and
    output-tokens/min). Several keys only add capacity when they belong to
    different Groq accounts; keys from one account share a quota.

    * After each response, a key whose ``x-ratelimit-remaining-tokens`` cannot
      cover the next request waits ``x-ratelimit-reset-tokens``.
    * HTTP 429 waits for ``retry-after`` (or the "try again in Ns" hint); waits
      longer than ``max_short_wait`` mean the daily quota is gone, so the key is
      retired. With every key retired, :class:`QuotaExhaustedError` is raised.
    * ``max_tokens`` is kept small because Groq reserves it against the
      output-tokens-per-minute budget; reasoning models use ``reasoning_effort=low``.
    """

    def __init__(
        self,
        model: str,
        api_keys: list[str],
        max_tokens: int = 900,
        max_short_wait: float = 1800.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        import httpx

        if not api_keys:
            raise ValueError("At least one Groq API key is required")
        self.model = model
        self.max_tokens = max_tokens
        self._http = httpx.Client(base_url="https://api.groq.com/openai/v1", timeout=120)
        self._keys = list(api_keys)
        self._ready_at = [0.0] * len(api_keys)
        self._retired: set[int] = set()
        self._org: dict[int, str] = {}  # learned from 429 messages
        self._max_short_wait = max_short_wait
        self._clock, self._sleep = clock, sleep
        self._next = 0

    def _pick_key(self) -> int:
        active = [i for i in range(len(self._keys)) if i not in self._retired]
        if not active:
            raise QuotaExhaustedError("All Groq keys exhausted their daily quota")
        index = min(active, key=lambda i: (self._ready_at[i], (i - self._next) % len(self._keys)))
        wait = self._ready_at[index] - self._clock()
        if wait > 0:
            self._sleep(wait)
        self._next = (index + 1) % len(self._keys)
        return index

    def _defer(self, index: int, seconds: float) -> None:
        # Groq's per-day token/request limits are rolling windows: a key comes back after
        # the wait, so cool it down rather than retiring it permanently. Keys of the same
        # organization share one quota, so they all cool down together.
        until = self._clock() + seconds + 0.5
        org = self._org.get(index)
        for other in range(len(self._keys)):
            if other == index or (org is not None and self._org.get(other) == org):
                self._ready_at[other] = max(self._ready_at[other], until)
        if min(self._ready_at) - self._clock() > self._max_short_wait:
            raise QuotaExhaustedError(
                f"All keys cooling down for > {self._max_short_wait:.0f}s; re-run later"
            )

    def __call__(self, system: str, prompt: str, seed: int) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": self.max_tokens,
            "seed": seed,
        }
        if "gpt-oss" in self.model:
            body["reasoning_effort"] = "low"
        needed = (len(system) + len(prompt)) // 3 + self.max_tokens
        while True:
            index = self._pick_key()
            response = self._http.post(
                "/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {self._keys[index]}"},
            )
            headers = response.headers
            if response.status_code == 429:
                org = re.search(r"organization .(org_[A-Za-z0-9]+)", response.text)
                if org:
                    self._org[index] = org.group(1)
                hint = re.search(r"try again in ([0-9hms.]+)", response.text)
                wait = parse_duration(
                    headers.get("retry-after") or (hint.group(1) if hint else "30")
                )
                self._defer(index, wait)
                continue
            if response.status_code >= 500:
                self._defer(index, 5.0)
                continue
            response.raise_for_status()  # other 4xx: propagate (message contains no key)
            if headers.get("x-ratelimit-remaining-requests") == "0":
                self._defer(index, parse_duration(headers.get("x-ratelimit-reset-requests", "1h")))
            remaining = int(float(headers.get("x-ratelimit-remaining-tokens", needed)))
            if remaining < needed:
                self._defer(index, parse_duration(headers.get("x-ratelimit-reset-tokens", "10s")))
            content = response.json()["choices"][0]["message"].get("content")
            if not content:
                raise ValueError("Groq returned no content")
            return str(content)


def parse_duration(value: str) -> float:
    """Parse Groq durations such as ``"34.6s"``, ``"36m0s"``, ``"1h2m3s"``, ``"47"``."""
    value = value.strip()
    try:
        return float(value)
    except ValueError:
        pass
    total = 0.0
    for amount, unit in re.findall(r"([0-9.]+)(ms|h|m|s)", value):
        total += float(amount) * {"h": 3600, "m": 60, "s": 1, "ms": 0.001}[unit]
    return total


def groq_keys_from_env() -> list[str]:
    """``GROQ_API_KEY``, ``GROQ_API_KEY_2``, … in order."""
    names = sorted(
        (k for k in os.environ if k == "GROQ_API_KEY" or k.startswith("GROQ_API_KEY_")),
        key=lambda k: (k != "GROQ_API_KEY", k),
    )
    return [os.environ[k] for k in names if os.environ[k].strip()]


#: PRD §7.3 input caps (bound prompt tokens; long reviews rarely add evidence).
MAX_REVIEW_CHARS = 1500
MAX_TITLE_CHARS = 200


def run_labels(
    frame: pd.DataFrame,
    checkpoint: str | Path,
    provider: Callable[[str, str, int], str],
    *,
    provider_name: str,
    model: str,
    run_id: str,
    seed: int,
    max_requests: int,
    requests_per_minute: float = 20,
    retries: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """max_requests is a hard lifetime budget for this checkpoint, including retries.

    Count each attempt BEFORE the call, so a crash never silently repeats a paid
    attempt outside the budget. An interrupted call can still need re-labeling.
    Separate run IDs/checkpoint files and seeds produce independent agreement runs.
    """
    frame = validate_reviews(frame)
    if max_requests < 1 or requests_per_minute <= 0 or retries < 1 or not run_id.strip():
        raise ValueError("Positive request budget, rate, retries and nonempty run_id required")
    checkpoint = Path(checkpoint)
    # Fingerprint the full blinded input and stable ID, not just mutable row positions.
    blinded = [
        {
            "review_id": row.review_id,
            "text": row.text,
            "product_title": str(getattr(row, "product_title", "") or ""),
        }
        for row in frame.itertuples()
    ]
    specification = {
        "provider": provider_name,
        "model": model,
        "run_id": run_id,
        "seed": seed,
        "prompt_hash": digest([SYSTEM_PROMPT, USER_PROMPT_TEMPLATE]),
        "input_hash": digest(blinded),
    }
    state: dict[str, Any] = {
        "specification": specification,
        "requests": 0,
        "labels": {},
        "errors": {},
    }
    if checkpoint.exists():
        state = json.loads(checkpoint.read_text(encoding="utf-8"))
        if state["specification"] != specification:
            raise ValueError("Checkpoint inputs/model/prompt/run changed; use a new checkpoint")
        for value in state["labels"].values():
            ExperienceLabel.model_validate(value)
    for row in blinded:
        review_id = row["review_id"]
        if review_id in state["labels"]:
            continue
        prompt = USER_PROMPT_TEMPLATE.format(
            product_title=str(row["product_title"])[:MAX_TITLE_CHARS],
            review_text=str(row["text"])[:MAX_REVIEW_CHARS],
        )
        for attempt in range(retries):
            if state["requests"] >= max_requests:
                atomic_json(checkpoint, state)
                return state
            state["requests"] += 1
            atomic_json(checkpoint, state)
            try:
                label = ExperienceLabel.model_validate_json(provider(SYSTEM_PROMPT, prompt, seed))
                state["labels"][review_id] = label.model_dump()
                state["errors"].pop(review_id, None)
                atomic_json(checkpoint, state)
                sleep(60 / requests_per_minute)
                break
            except QuotaExhaustedError:
                state["requests"] -= 1  # the attempt never reached a model
                atomic_json(checkpoint, state)
                return state
            except Exception as error:
                # Avoid persisting provider errors that might include request headers / keys.
                state["errors"][review_id] = type(error).__name__
                atomic_json(checkpoint, state)
                sleep(max(60 / requests_per_minute, 2**attempt))
    return state


def merge_labels(frame: pd.DataFrame, checkpoint: str | Path) -> pd.DataFrame:
    state = json.loads(Path(checkpoint).read_text(encoding="utf-8"))
    rows = [
        {"review_id": review_id, **ExperienceLabel.model_validate(label).model_dump()}
        for review_id, label in state["labels"].items()
    ]
    merged = validate_reviews(frame).merge(
        pd.DataFrame(rows), on="review_id", validate="one_to_one"
    )
    if len(merged) != len(frame):
        raise ValueError("Label run is incomplete; finish it before training")
    return validate_reviews(merged, labels=True)
