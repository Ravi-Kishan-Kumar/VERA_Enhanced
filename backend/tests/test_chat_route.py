"""Unit tests for Chat Advisor API route."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from pydantic import ValidationError

from app.api.routes.chat import ChatRequest, send_chat_message


def test_chat_message_schema():
    """Verify chat route accepts messages and returns valid schema using mocked client."""
    mock_response = MagicMock()
    mock_response.text = "I recommend the boAt Rockerz 450 and Sony WH-1000XM5 for excellent sound."

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.chat_advisor._get_gemini_client", return_value=mock_client):
        request = ChatRequest(message="Suggest budget headphones under 2500 for bass")
        data = send_chat_message(request)
        assert "reply" in data
        assert isinstance(data["reply"], str)
        assert "boAt Rockerz 450" in data["reply"]
        assert "suggested_products" in data
        assert isinstance(data["suggested_products"], list)
        assert len(data["suggested_products"]) > 0
        assert "follow_up_questions" in data
        assert isinstance(data["follow_up_questions"], list)


def test_chat_fallback_when_no_client():
    """Verify chat falls back to acoustic catalog when client is unavailable."""
    with patch("app.services.chat_advisor._get_gemini_client", return_value=None):
        request = ChatRequest(message="Suggest top earbuds under 3000")
        data = send_chat_message(request)
        assert "reply" in data
        assert len(data["suggested_products"]) > 0


def test_chat_empty_message_rejected():
    """Verify empty message raises validation error."""
    with pytest.raises(ValidationError):
        ChatRequest(message="")
