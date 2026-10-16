"""Stream the corpus, clean reviews and sample with a GLOBAL product cap."""

from __future__ import annotations

import gzip
import json
import re
from collections import Counter, deque
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import IO, Any

import numpy as np
import pandas as pd

from app.ml.agents.preprocessor import TextPreprocessor
from vera_training.io import digest, validate_reviews

#: Product-title filter (PRD §6.2). Same vocabulary as the PRD's EARBUD_KEYWORDS.
EARBUD_PATTERN = re.compile(
    r"earbud|earphone|in-ear|headphone|headset|\btws\b"
    r"|wireless ear|noise cancel|airpod|bluetooth ear",
    re.IGNORECASE,
)


def json_records(path: str | Path) -> Iterator[dict[str, Any]]:
    """Yield JSON objects from a ``.jsonl`` or ``.jsonl.gz`` file, skipping blank lines."""
    path = Path(path)
    stream: IO[str]
    if path.suffix == ".gz":
        stream = gzip.open(path, "rt", encoding="utf-8")
    else:
        stream = path.open(encoding="utf-8")
    with stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


#: Amazon category node that holds actual headphones/earbuds (not cases, pads, adapters).
HEADPHONE_CATEGORY = "Headphones & Earbuds"
#: Accessory / non-audio words; only applied to products WITHOUT a category path.
ACCESSORY_PATTERN = re.compile(
    r"\b(case|cover|skin|sticker|adapter|cable|cord|ear ?pads?|cushions?|tips|stand|holder|"
    r"hanger|splitter|amplifier|dac|receiver|transmitter|webcam|camera|radio|recorder|mp3|mp4|"
    r"charger|organizer|strap|hook|extension|replacement|fpv|goggles|video glasses)\b",
    re.IGNORECASE,
)
_PARENT_ASIN_RE = re.compile(r'"parent_asin":\s*"([^"]+)"')


def is_earbud_product(row: dict[str, Any]) -> bool:
    """Contamination filter for one metadata row (PRD §6.2, tightened — see DECISIONS.md).

    Title keywords alone admit FPV goggles, webcams and radios; the category
    alone admits cases, ear pads and mis-filed products. Require a title
    keyword AND either the "Headphones & Earbuds" category or, for rows with no
    category, a title free of accessory words ("charging case" is allowed).
    """
    title = str(row.get("title") or "")
    if not row.get("parent_asin") or not EARBUD_PATTERN.search(title):
        return False
    categories = row.get("categories") or []
    if categories:
        return any(HEADPHONE_CATEGORY in str(c) for c in categories)
    return not ACCESSORY_PATTERN.search(re.sub(r"charging case", "", title, flags=re.IGNORECASE))


def select_earbud_products(metadata: Iterable[dict[str, Any]]) -> dict[str, str]:
    """``parent_asin -> product title`` for rows passing :func:`is_earbud_product`."""
    return {
        str(r["parent_asin"]): str(r.get("title") or "") for r in metadata if is_earbud_product(r)
    }


#: Product-title filter for Over-Ear and On-Ear Headphones
OVEREAR_HEADPHONE_PATTERN = re.compile(
    r"\b(over[- ]ear|around[- ]ear|on[- ]ear|headband|circumaural|supra[- ]aural|dj headphone|studio headphone|monitor headphone|gaming headset|stereo headphone|wireless headphone)\b",
    re.IGNORECASE,
)

#: Exclude in-ear, earbuds, and accessories
EXCLUDE_IN_EAR_PATTERN = re.compile(
    r"\b(earbud|earbuds|in[- ]ear|in-ear|tws|airpod|airpods|true wireless|ear tip|ear tips|charging case|earphone|earphones)\b",
    re.IGNORECASE,
)


def is_overear_headphone_product(row: dict[str, Any]) -> bool:
    """Contamination filter for Over-Ear and On-Ear headphones (excluding earbuds/TWS)."""
    title = str(row.get("title") or "")
    if not row.get("parent_asin"):
        return False
    if EXCLUDE_IN_EAR_PATTERN.search(title):
        return False
    if not (
        OVEREAR_HEADPHONE_PATTERN.search(title)
        or "headphone" in title.lower()
        or "headset" in title.lower()
    ):
        return False
    categories = row.get("categories") or []
    if categories:
        cat_str = " ".join(str(c) for c in categories).lower()
        if "earbud" in cat_str or "in-ear" in cat_str:
            return False
        if any(h in cat_str for h in ["headphone", "over-ear", "on-ear", "headset"]):
            return not ACCESSORY_PATTERN.search(title)
    return not ACCESSORY_PATTERN.search(title)


def select_headphone_products(metadata: Iterable[dict[str, Any]]) -> dict[str, str]:
    """``parent_asin -> product title`` for rows passing :func:`is_overear_headphone_product`."""
    return {
        str(r["parent_asin"]): str(r.get("title") or "")
        for r in metadata
        if is_overear_headphone_product(r)
    }



def reviews_for_products(path: str | Path, asins: set[str]) -> Iterator[dict[str, Any]]:
    """Stream only reviews of ``asins``; a regex pre-check skips ``json.loads`` for the rest.

    The Electronics file has ~44M lines of which <1% are earbuds, so parsing
    only candidate lines makes corpus preparation roughly 20x faster.
    """
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            match = _PARENT_ASIN_RE.search(line)
            if match and match.group(1) in asins:
                yield json.loads(line)


def prepare_corpus_from_files(
    reviews_path: str | Path, metadata_path: str | Path, min_words: int = 20
) -> pd.DataFrame:
    """Fast path used by notebook 01 on the raw JSONL files."""
    products = select_earbud_products(json_records(metadata_path))
    return prepare_corpus(
        reviews_for_products(reviews_path, set(products)), [], min_words, products=products
    )


def prepare_corpus(
    reviews: Iterable[dict[str, Any]],
    metadata: Iterable[dict[str, Any]],
    min_words: int = 20,
    *,
    products: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Clean, filter and de-duplicate earbud reviews.

    Args:
        reviews: Raw review dicts.
        metadata: Raw metadata dicts (ignored when ``products`` is given).
        min_words: Minimum words after cleaning (PRD: 20).
        products: Pre-selected ``parent_asin -> title`` mapping.
    """
    if products is None:
        products = select_earbud_products(metadata)
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in reviews:
        asin = str(row.get("parent_asin") or "").strip()
        if asin not in products or row.get("rating") not in (1, 2, 3, 4, 5):
            continue
        # Same cleaning as serving (Agent 1). Only clean_text is needed here, so
        # skip process(): running langdetect on ~200K reviews would take ~1 hour.
        # Keep a canonical body only: a title prepended solely offline would
        # create train/serve skew.
        text = TextPreprocessor.clean_text(str(row.get("text") or ""))
        if len(text.split()) < min_words:
            continue
        text_hash = digest(text.casefold())
        if text_hash in seen:
            continue  # remove exact cross-product duplicates before grouped splits
        seen.add(text_hash)
        cleaned.append(
            {
                "review_id": digest([asin, text, row.get("timestamp"), row.get("user_id")]),
                "parent_asin": asin,
                "text": text,
                "rating": row["rating"],
                "product_title": products[asin],
                "helpful_vote": row.get("helpful_vote"),
                "verified_purchase": row.get("verified_purchase"),
                "timestamp": row.get("timestamp"),
            }
        )
    return validate_reviews(pd.DataFrame(cleaned))


def sample_for_labeling(
    frame: pd.DataFrame,
    n: int = 2000,
    seed: int = 42,
    product_cap: int = 5,
    *,
    balanced_order: bool = False,
) -> pd.DataFrame:
    """Star-stratified sample (n/5 per star), helpful-vote weighted, ≤ ``product_cap``
    reviews per product across ALL stars (PRD §6.3)."""
    frame = validate_reviews(frame)
    if n <= 0 or n % 5 or product_cap < 1:
        raise ValueError("n must be a positive multiple of five; product_cap must be positive")
    rng = np.random.default_rng(seed)
    # Weighted random order, followed by round-robin buckets prevents a first
    # star bucket consuming the global product allowance of all other buckets.
    asins = frame["parent_asin"].astype(str).to_dict()
    buckets: dict[int, deque[int]] = {}
    for star in range(1, 6):
        bucket = frame[frame.rating.eq(star)]
        votes = bucket.get("helpful_vote", pd.Series(0, index=bucket.index)).fillna(0)
        weights = np.log1p(votes.clip(lower=0).to_numpy(float)) + 0.1
        keys = -np.log(rng.uniform(np.finfo(float).tiny, 1.0, len(bucket))) / weights
        buckets[star] = deque(bucket.index[np.argsort(keys)].tolist())
    counts: Counter[str] = Counter()
    selected: list[int] = []
    for _ in range(n // 5):
        for star in rng.permutation(np.arange(1, 6)):
            queue = buckets[star]
            while queue and counts[asins[queue[0]]] >= product_cap:
                queue.popleft()
            if not queue:
                raise ValueError(
                    f"Insufficient feasible star-{star} reviews under global product cap; "
                    "reduce n or provide a larger corpus"
                )
            index = queue.popleft()
            selected.append(index)
            counts[asins[index]] += 1
    if balanced_order:
        # Selection order is round-robin over stars: every prefix whose length is a
        # multiple of 5 is exactly star-balanced, so labeling can stop/extend safely.
        return frame.loc[selected].reset_index(drop=True)
    return frame.loc[rng.permutation(selected)].reset_index(drop=True)


def download_corpus(output: str | Path, *, revision: str, max_reviews: int | None = None) -> None:
    """Explicit network operation; pin a Hub commit and stream rather than loading 40M rows."""
    from datasets import load_dataset

    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Pin a 40-character dataset commit after reviewing its loading script")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for config, name in (
        ("raw_meta_Electronics", "metadata.jsonl"),
        ("raw_review_Electronics", "reviews.jsonl"),
    ):
        destination = output / name
        if destination.exists():
            raise FileExistsError(f"Refusing to overwrite {destination}")
        dataset = load_dataset(
            "McAuley-Lab/Amazon-Reviews-2023",
            config,
            split="full",
            streaming=True,
            revision=revision,
            trust_remote_code=True,
        )
        with destination.open("x", encoding="utf-8") as stream:
            for index, row in enumerate(dataset):
                if name == "reviews.jsonl" and max_reviews is not None and index >= max_reviews:
                    break
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
