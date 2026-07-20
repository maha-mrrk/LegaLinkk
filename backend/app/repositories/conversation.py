"""Data-access layer for conversations and messages."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation, Message, MessageRole


class ConversationRepository:
    """All conversation / message persistence goes through this repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, title: str | None = None) -> Conversation:
        conversation = Conversation(title=title)
        self._session.add(conversation)
        await self._session.flush()
        await self._session.refresh(conversation)
        return conversation

    async def get_by_id(
        self,
        conversation_id: UUID,
        *,
        with_messages: bool = False,
    ) -> Conversation | None:
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        if with_messages:
            stmt = stmt.options(selectinload(Conversation.messages))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, *, skip: int = 0, limit: int = 100) -> list[Conversation]:
        result = await self._session.execute(
            select(Conversation)
            .order_by(Conversation.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(Conversation)
        )
        return int(result.scalar_one())

    async def delete(self, conversation: Conversation) -> None:
        await self._session.delete(conversation)
        await self._session.flush()

    async def touch(self, conversation: Conversation) -> Conversation:
        conversation.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        await self._session.refresh(conversation)
        return conversation

    async def append_message(
        self,
        *,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata_=metadata or {},
        )
        self._session.add(message)
        await self._session.flush()
        await self._session.refresh(message)
        return message

    async def list_messages(
        self,
        conversation_id: UUID,
        *,
        limit: int | None = None,
    ) -> list[Message]:
        """Return messages oldest→newest. If ``limit`` is set, keep the last N."""
        if limit is None:
            result = await self._session.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc())
            )
            return list(result.scalars().all())

        if limit < 1:
            return []

        # Fetch newest ``limit`` rows then reverse to chronological order.
        result = await self._session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        newest_first = list(result.scalars().all())
        newest_first.reverse()
        return newest_first
