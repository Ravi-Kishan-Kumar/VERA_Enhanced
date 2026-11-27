"""Audio Buyer Assistant Chat Routes.

Provides intelligent conversational buying recommendations for headphones
and earbuds powered by Google Gemini and VERA's acoustic database.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.chat_advisor import chat_with_advisor

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    conversation_history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    suggested_products: list[dict[str, Any]] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)


@router.post("/message", response_model=ChatResponse)
def send_chat_message(request: ChatRequest) -> dict[str, Any]:
    """Send a user message to VERA Audio Advisor and receive intelligent advice.

    Returns natural conversational recommendations along with rich product
    cards and interactive follow-up suggestion chips.
    """
    history_dicts = [
        {"role": m.role, "content": m.content}
        for m in request.conversation_history
    ]
    return chat_with_advisor(
        message=request.message,
        conversation_history=history_dicts,
    )
