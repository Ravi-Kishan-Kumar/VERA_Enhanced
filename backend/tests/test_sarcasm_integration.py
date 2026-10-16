"""Test Agent 4 (SarcasmDetector) standalone and pipeline integration."""

from app.ml.agents.sarcasm import SarcasmDetector


def test_sarcastic_review_detected():
    """The user's exact example review should be flagged as sarcastic."""
    detector = SarcasmDetector()
    review = (
        "Oh great, another pair of earbuds that disconnect every ten minutes. "
        "Just what I needed. I love how the right one dies after an hour and "
        "the app crashes whenever I try to change the settings. Truly a premium "
        "experience, worth every penny. Can't wait to buy a second pair."
    )
    result = detector.process(review, star_rating=5.0)

    assert result["has_irony_or_sarcasm"] is True
    assert result["confidence"] >= 0.85
    assert result["calibrated_score"] is not None
    assert result["calibrated_score"] <= 1.65  # deeply negative
    assert len(result["sarcastic_markers"]) >= 3
    assert len(result["defect_mentions"]) >= 3
    print(f"✅ Sarcasm detected: confidence={result['confidence']:.2f}, "
          f"calibrated_score={result['calibrated_score']:.2f}")
    print(f"   Markers: {result['sarcastic_markers']}")
    print(f"   Defects: {result['defect_mentions']}")
    print(f"   Explanation: {result['explanation']}")


def test_genuine_positive_not_flagged():
    """A genuinely positive review should NOT be flagged as sarcastic."""
    detector = SarcasmDetector()
    review = (
        "These earbuds are amazing! The sound quality is crystal clear, "
        "the ANC works perfectly, and the battery lasts all day. "
        "Best purchase I've ever made for commuting."
    )
    result = detector.process(review, star_rating=5.0)

    assert result["has_irony_or_sarcasm"] is False
    assert result["calibrated_score"] is None
    print(f"✅ Genuine positive: correctly NOT flagged as sarcastic")


def test_genuine_negative_not_flagged():
    """A straightforward negative review (no sarcasm markers) should not be flagged."""
    detector = SarcasmDetector()
    review = (
        "Terrible product. The earbuds disconnect constantly and the right one "
        "died after two days. Complete waste of money. Returning these immediately."
    )
    result = detector.process(review, star_rating=1.0)

    # Has defect markers but no sarcastic positive markers — should not flag
    assert result["has_irony_or_sarcasm"] is False
    assert result["calibrated_score"] is None
    print(f"✅ Genuine negative: correctly NOT flagged as sarcastic")


if __name__ == "__main__":
    test_sarcastic_review_detected()
    test_genuine_positive_not_flagged()
    test_genuine_negative_not_flagged()
    print("\n🎉 All sarcasm detection tests passed!")
