"""Seed real web review data from labels_v1.jsonl and headphone_labels_v1.jsonl into the database."""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models.product import Product
from app.models.review import Review, ReviewStatus

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "labels"
EARBUDS_FILE = DATA_DIR / "labels_v1.jsonl"
HEADPHONES_FILE = DATA_DIR / "headphone_labels_v1.jsonl"


def seed_web_reviews():
    print("Loading web reviews from data/labels/...")
    earbuds_reviews = []
    if EARBUDS_FILE.exists():
        with open(EARBUDS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    earbuds_reviews.append(json.loads(line))

    headphones_reviews = []
    if HEADPHONES_FILE.exists():
        with open(HEADPHONES_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    headphones_reviews.append(json.loads(line))

    print(f"Loaded {len(earbuds_reviews)} earbuds web reviews and {len(headphones_reviews)} headphones web reviews.")

    with SessionLocal() as db:
        products = db.query(Product).all()
        print(f"Attaching web reviews to {len(products)} products in database...")

        # Distribute real web reviews across products
        eb_products = [p for p in products if p.product_category == "earbuds"]
        hp_products = [p for p in products if p.product_category == "headphones"]

        # Helper to convert review dict to model
        def create_review_obj(raw: dict, product: Product, category: str) -> Review:
            aspects_dict = {}
            for asp, asp_data in raw.get("aspects", {}).items():
                if isinstance(asp_data, dict):
                    sentiment = asp_data.get("sentiment", "not_mentioned")
                    detected = asp_data.get("detected", sentiment in ("positive", "negative", "neutral"))
                    confidence = asp_data.get("confidence", 0.85)
                    aspects_dict[asp] = {
                        "detected": detected,
                        "sentiment": sentiment,
                        "confidence": confidence,
                        "prob_neg": 0.9 if sentiment == "negative" else 0.05,
                        "prob_neu": 0.9 if sentiment == "neutral" else 0.05,
                        "prob_pos": 0.9 if sentiment == "positive" else 0.05,
                    }

            is_sarcastic = raw.get("has_irony_or_sarcasm", False)
            exp_score = raw.get("experience_score", raw.get("rating", 4.0))

            raw_qual = raw.get("review_quality", 0.75)
            if isinstance(raw_qual, str):
                qual_score = 0.85 if raw_qual == "high" else (0.65 if raw_qual == "medium" else 0.45)
            else:
                qual_score = float(raw_qual or 0.75)

            return Review(
                text=raw["text"][:10000],
                star_rating=float(raw.get("rating", 4.0)),
                product_category=category,
                helpful_votes=raw.get("helpful_vote", 0),
                verified_purchase=raw.get("verified_purchase", True),
                product_title=product.title,
                product_asin=product.asin,
                status=ReviewStatus.DONE.value,
                corrected_score=exp_score,
                interval_lower=max(1.0, exp_score - 0.4),
                interval_upper=min(5.0, exp_score + 0.4),
                confidence_value=0.88,
                star_text_gap=round(raw.get("rating", 4.0) - exp_score, 3),
                review_quality=qual_score,
                aspects=aspects_dict,
                flags={
                    "is_english": True,
                    "is_earbud": True,
                    "sarcasm_detected": is_sarcastic,
                    "sarcasm_confidence": 0.92 if is_sarcastic else 0.0,
                    "sarcasm_override": is_sarcastic,
                    "sarcasm_markers": ["rhetorical praise"] if is_sarcastic else [],
                    "defect_mentions": ["hardware failure"] if is_sarcastic else [],
                },
                explanation=(
                    f"Text implies about {exp_score:.1f} stars based on web review analysis."
                    if not is_sarcastic
                    else f"⚠️ Sarcasm detected: praise contradicted by defects. Score overridden to {exp_score:.1f}."
                ),
            )

        new_reviews_count = 0

        # Assign 15-20 web reviews to each earbuds product
        eb_idx = 0
        for p in eb_products:
            # Check how many reviews it already has
            existing_count = db.query(Review).filter(Review.product_asin == p.asin).count()
            needed = max(0, 15 - existing_count)
            for _ in range(needed):
                if eb_idx >= len(earbuds_reviews):
                    eb_idx = 0
                raw = earbuds_reviews[eb_idx]
                eb_idx += 1
                r = create_review_obj(raw, p, "earbuds")
                db.add(r)
                new_reviews_count += 1

        # Assign 15-20 web reviews to each headphones product
        hp_idx = 0
        for p in hp_products:
            existing_count = db.query(Review).filter(Review.product_asin == p.asin).count()
            needed = max(0, 15 - existing_count)
            for _ in range(needed):
                if hp_idx >= len(headphones_reviews):
                    hp_idx = 0
                raw = headphones_reviews[hp_idx]
                hp_idx += 1
                r = create_review_obj(raw, p, "headphones")
                db.add(r)
                new_reviews_count += 1

        db.commit()
        print(f"Successfully added {new_reviews_count} real web reviews to database products!")


if __name__ == "__main__":
    seed_web_reviews()
