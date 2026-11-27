"""Conversational Audio Buying Advisor Service.

Powered by Google Gemini (gemini-2.5-flash) and integrated with VERA's
curated Indian audio catalog for earbuds and headphones.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from app.config import settings
from app.services.web_search import INDIAN_AUDIO_CATALOG

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are VERA Audio Advisor, an elite acoustic specialist and personal shopping assistant for headphones and earbuds.
Your goal is to guide buyers to their ideal audio device based on budget, use case (gym, commuting, office calls, gaming, audiophile listening), and acoustic preferences.

Key Knowledge & Principles:
1. Headphones vs. Earbuds:
   - Headphones (Over-Ear/On-Ear): Superior soundstage, deeper physical sub-bass (40mm-50mm drivers), better passive isolation and battery life (30h-60h), but heavier.
   - Earbuds (In-Ear TWS): Maximum portability, pocketable cases, sweat/water resistance (IPX4-IPX8), great for workouts, but smaller drivers (10mm-12mm) and smaller batteries (5h-9h per charge).
2. Pricing:
   - Provide prices in Indian Rupees (₹ INR).
   - Acknowledge Indian availability (Amazon.in, Flipkart, Croma, Headphone Zone).
   - Brackets: Budget (< ₹2,500), Mid-range (₹2,500 - ₹8,000), Flagship / Audiophile (> ₹8,000).
3. Sound Profiles:
   - Explain signatures: Bass-heavy / V-shaped (boAt, JBL, Sony XB), Balanced / Harman Neutral (Sony XM5, Sennheiser, Galaxy Buds), Crisp Treble & Vocals (Audio-Technica, AirPods Pro).
4. Honest Trade-offs:
   - Always mention real-world pros and cons (e.g. ear fatigue, mic performance in windy conditions, codec support like LDAC / aptX / AAC).
5. Format:
   - Keep answers structured, enthusiastic, and easy to skim with bold titles, bullet points, and realistic buying advice.
   - Conclude with 2-3 helpful follow-up options or questions."""


def _get_gemini_client():
    """Lazily construct Google GenAI client."""
    api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as exc:
        logger.warning("Failed to initialize Google GenAI client: %s", exc)
        return None


def _find_matching_catalog_products(text: str, max_items: int = 3) -> list[dict[str, Any]]:
    """Find products from INDIAN_AUDIO_CATALOG that appear or closely match text."""
    text_lower = text.lower()
    matches: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for item in INDIAN_AUDIO_CATALOG:
        name = item.get("name", "")
        brand = item.get("brand", "").lower()
        if name in seen_names:
            continue

        # Check if full name or substantial brand+model tokens match
        name_clean = re.sub(r"[^\w\s]", " ", name.lower())
        tokens = [t for t in name_clean.split() if len(t) > 2 and t not in {"wireless", "tws", "earbuds", "headphones", "with", "true"}]
        
        matches_token_count = sum(1 for t in tokens if t in text_lower)
        if matches_token_count >= 2 or (brand in text_lower and any(t in text_lower for t in tokens)):
            matches.append(item)
            seen_names.add(name)
            if len(matches) >= max_items:
                break

    # If no direct match in text, find top products based on category or price mentioned
    if not matches:
        is_headphones = any(w in text_lower for w in ["headphone", "over-ear", "on-ear", "headset"])
        is_earbuds = any(w in text_lower for w in ["earbud", "tws", "airpod", "buds", "in-ear", "earphone", "earphones", "iem", "ciem", "in ear"])
        
        # Extract price if mentioned
        price_match = re.search(r"(?:rs\.?|inr|₹)?\s*(\d{1,2}(?:,\d{3})+|\d{3,6})", text_lower)
        max_budget = None
        if price_match:
            try:
                max_budget = int(price_match.group(1).replace(",", ""))
            except ValueError:
                pass

        candidates = INDIAN_AUDIO_CATALOG
        if is_headphones and not is_earbuds:
            candidates = [p for p in candidates if p.get("category") == "headphones"]
        elif is_earbuds and not is_headphones:
            candidates = [p for p in candidates if p.get("category") == "earbuds"]

        if max_budget:
            budget_candidates = [p for p in candidates if p.get("price_inr", 999999) <= max_budget * 1.15]
            if budget_candidates:
                candidates = budget_candidates

        # Pick top 2-3 highest rated
        sorted_candidates = sorted(candidates, key=lambda x: x.get("rating", 0), reverse=True)
        matches = sorted_candidates[:max_items]

    return matches


def _generate_fallback_response(user_message: str) -> dict[str, Any]:
    """Graceful fallback if Gemini API is unreachable or rate-limited."""
    matches = _find_matching_catalog_products(user_message, max_items=3)
    
    products_summary = "\n".join(
        f"• **{p['name']}** ({p.get('price_str', '')}): {p.get('rating')}★ rating, {p.get('specs', {}).get('driver', '')}. Key strength: {', '.join(p.get('pros', [])[:2])}."
        for p in matches
    )

    reply = (
        f"Here are top-tier recommendations for your request based on our verified acoustic lab data:\n\n"
        f"{products_summary}\n\n"
        "**Buying Advice:** If you prioritize deep sub-bass and long comfort for gaming or desk work, over-ear headphones are unmatched. "
        "For gym workouts and daily commutes, compact TWS earbuds with IPX5 water resistance are the practical choice."
    )

    return {
        "reply": reply,
        "suggested_products": matches,
        "follow_up_questions": [
            "What is your maximum budget in INR (₹)?",
            "Do you prefer compact in-ear earbuds or over-ear headphones?",
            "Will you use these mainly for workouts, office calls, or music listening?",
        ],
    }


def chat_with_advisor(
    message: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Generate intelligent audio buying advice using Gemini."""
    client = _get_gemini_client()
    if not client:
        return _generate_fallback_response(message)

    try:
        from google.genai import types

        model_name = settings.GEMINI_MODEL or "gemini-2.5-flash"
        
        # Build contents from history
        contents: list[types.Content] = []
        if conversation_history:
            for turn in conversation_history[-6:]:  # Keep recent context
                role = "user" if turn.get("role") == "user" else "model"
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=turn.get("content", ""))]
                    )
                )

        # Add current user message
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=message)]
            )
        )

        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7,
                max_output_tokens=1000,
            ),
        )

        reply_text = response.text or ""
        # Use only the user's own message for category matching — the reply
        # text often mentions both categories and would pollute the matcher.
        matched_products = _find_matching_catalog_products(message, max_items=3)

        # Dynamic follow-ups
        follow_ups = [
            "Compare top 2 headphones vs earbuds in this budget",
            "Which one has the best mic for phone & Zoom calls?",
            "Looking for intense bass for gym workouts",
        ]

        return {
            "reply": reply_text,
            "suggested_products": matched_products,
            "follow_up_questions": follow_ups,
        }

    except Exception as exc:
        logger.error("Gemini API error during chat: %s", exc)
        return _generate_fallback_response(message)
