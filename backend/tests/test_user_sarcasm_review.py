"""Test the exact sarcasm review reported by the user."""

from app.ml.agents.sarcasm import SarcasmDetector


def test_user_reported_sarcastic_review():
    text = (
        "Wow, what a masterpiece. The left ear cup went silent after two days, the microphone makes me "
        "sound like I'm underwater, and the headband squeezes my head like a vice. I especially love the "
        "Bluetooth cutting out in the middle of every match. Absolutely worth the money, and I can't wait "
        "to buy another one so I can be disappointed twice."
    )

    detector = SarcasmDetector()
    result = detector.process(text, star_rating=5.0)

    assert result["has_irony_or_sarcasm"] is True
    assert result["confidence"] >= 0.85
    assert result["calibrated_score"] is not None
    assert result["calibrated_score"] <= 1.5

    # Check affected aspects
    affected = result["affected_aspects"]
    assert "sound_quality" in affected
    assert "comfort" in affected
    assert "fit" in affected
    assert "connectivity" in affected
    assert "microphone" in affected
    assert "value" in affected
