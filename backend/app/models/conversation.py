"""SQLAlchemy models for chat conversations and messages."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MessageRole(str, enum.Enum):
    """Speaker role inside a conversation turn."""

    USER = "user"
    ASSISTANT = "assistant"


class Conversation(Base):
    """A multi-turn chat session grounded on uploaded documents."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} title={self.title!r}>"


class Message(Base):
    """One user or assistant message inside a conversation."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(
            MessageRole,
            name="message_role",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Spec alias: ``timestamp`` exposed as created_at for consistency.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        return (
            f"<Message id={self.id} conversation_id={self.conversation_id} "
            f"role={self.role.value}>"
        )
