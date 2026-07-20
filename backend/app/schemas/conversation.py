"""Pydantic schemas for conversation persistence and messaging."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.conversation import MessageRole
from app.schemas.chat import ChatMetadata, ChatSource


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_orm_message(cls, message: Any) -> "MessageResponse":
        return cls(
            id=message.id,
            conversation_id=message.conversation_id,
            role=message.role,
            content=message.content,
            timestamp=message.created_at,
            metadata=dict(message.metadata_ or {}),
        )


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse] = Field(default_factory=list)

    @classmethod
    def from_orm(
        cls,
        conversation: Any,
        *,
        include_messages: bool = True,
    ) -> "ConversationResponse":
        messages: list[MessageResponse] = []
        if include_messages:
            for message in getattr(conversation, "messages", []) or []:
                messages.append(MessageResponse.from_orm_message(message))
        return cls(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=messages,
        )


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    total: int


class ConversationMessageRequest(BaseModel):
    """Send a user message inside an existing conversation (full RAG turn)."""

    content: str = Field(..., min_length=1, description="User message")
    top_k: int | None = Field(default=None, ge=1, le=50)
    final_k: int | None = Field(default=None, ge=1, le=50)
    temperature: float | None = Field(default=None, ge=0.0, le=1.0)
    max_tokens: int | None = Field(default=None, ge=64, le=8192)


class ConversationMessageResponse(BaseModel):
    """Assistant reply after a conversational RAG turn."""

    conversation_id: UUID
    user_message: MessageResponse
    assistant_message: MessageResponse
    answer: str
    sources: list[ChatSource] = Field(default_factory=list)
    metadata: ChatMetadata
