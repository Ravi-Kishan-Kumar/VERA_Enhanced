"""Stream and prepare the Over-Ear / On-Ear Headphones corpus directly on Colab or locally.

Streams from Hugging Face (McAuley-Lab/Amazon-Reviews-2023) directly via HTTP without downloading 25 GB of raw files.
Bypasses deprecated dataset scripts.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd
from huggingface_hub import hf_hub_url

from app.ml.agents.preprocessor import TextPreprocessor
from vera_training.data import (
    ACCESSORY_PATTERN,
    EXCLUDE_IN_EAR_PATTERN,
    OVEREAR_HEADPHONE_PATTERN,
    is_overear_headphone_product,
    sample_for_labeling,
)
from vera_training.io import digest, validate_reviews

_PARENT_ASIN_RE = re.compile(r'"parent_asin":\s*"([^"]+)"')


def stream_headphone_metadata(max_products: int = 15000) -> dict[str, str]:
    """Stream raw/meta_categories/meta_Electronics.jsonl over HTTP."""
    url = hf_hub_url(
        repo_id="McAuley-Lab/Amazon-Reviews-2023",
        filename="raw/meta_categories/meta_Electronics.jsonl",
        repo_type="dataset",
    )
    print(f"Connecting to metadata stream: {url[:60]}...", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    
    products: dict[str, str] = {}
    scanned = 0
    start = time.time()
    
    with urllib.request.urlopen(req) as resp:
        for line in resp:
            scanned += 1
            try:
                row = json.loads(line.decode("utf-8"))
            except Exception:
                continue
                
            if is_overear_headphone_product(row):
                asin = str(row.get("parent_asin") or "").strip()
                title = str(row.get("title") or "").strip()
                if asin and title:
                    products[asin] = title
                    if len(products) >= max_products:
                        break
            if scanned % 100000 == 0:
                elapsed = time.time() - start
                print(f"Scanned {scanned:,} metadata rows -> found {len(products):,} headphone ASINs ({scanned/elapsed:.0f} rows/s)", flush=True)
                
    print(f"Finished metadata stream: found {len(products):,} headphone products from {scanned:,} rows in {time.time()-start:.1f}s.")
    return products


def stream_headphone_reviews(
    products: dict[str, str],
    target_reviews: int = 50000,
    min_words: int = 20,
) -> pd.DataFrame:
    """Stream raw/review_categories/Electronics.jsonl and filter for headphone ASINs."""
    url = hf_hub_url(
        repo_id="McAuley-Lab/Amazon-Reviews-2023",
        filename="raw/review_categories/Electronics.jsonl",
        repo_type="dataset",
    )
    print(f"Connecting to reviews stream: {url[:60]}...", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    
    asins = set(products.keys())
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    scanned = 0
    start = time.time()
    
    with urllib.request.urlopen(req) as resp:
        for raw_line in resp:
            scanned += 1
            line = raw_line.decode("utf-8", errors="replace")
            
            # Fast regex pre-check on parent_asin before parsing full JSON
            match = _PARENT_ASIN_RE.search(line)
            if not match or match.group(1) not in asins:
                continue
                
            try:
                row = json.loads(line)
            except Exception:
                continue
                
            asin = match.group(1)
            if row.get("rating") not in (1, 2, 3, 4, 5, 1.0, 2.0, 3.0, 4.0, 5.0):
                continue
                
            text = TextPreprocessor.clean_text(str(row.get("text") or ""))
            if len(text.split()) < min_words:
                continue
                
            text_hash = digest(text.casefold())
            if text_hash in seen:
                continue
            seen.add(text_hash)
            
            cleaned.append(
                {
                    "review_id": digest([asin, text, row.get("timestamp"), row.get("user_id")]),
                    "parent_asin": asin,
                    "text": text,
                    "rating": float(row["rating"]),
                    "product_title": products[asin],
                    "helpful_vote": row.get("helpful_vote"),
                    "verified_purchase": row.get("verified_purchase"),
                    "timestamp": row.get("timestamp"),
                }
            )
            
            if len(cleaned) % 5000 == 0:
                elapsed = time.time() - start
                rate = len(cleaned) / max(elapsed, 1)
                print(f"Collected {len(cleaned):,}/{target_reviews:,} reviews (scanned {scanned:,} lines, {rate:.1f} rev/s)...", flush=True)
                
            if len(cleaned) >= target_reviews:
                break
                
    df = pd.DataFrame(cleaned)
    validated = validate_reviews(df)
    print(f"Successfully collected total {len(validated):,} valid headphone reviews across {validated.parent_asin.nunique():,} products in {time.time()-start:.1f}s.")
    return validated
