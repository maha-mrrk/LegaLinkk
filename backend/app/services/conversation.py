"""Conversation lifecycle: create, load history, append messages, delete."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.conversation import Conversation, Message, MessageRole
from app.repositories.conversation import ConversationRepository

logger = get_logger(__name__)


class ConversationService:
    """Manage multi-turn chat sessions persisted in PostgreSQL."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._repo = ConversationRepository(session)

    async def create_conversation(self, *, title: str | None = None) -> Conversation:
        conversation = await self._repo.create(title=title)
        await self._session.commit()
        await self._session.refresh(conversation)
        logger.info("Conversation created id=%s", conversation.id)
        return conversation

    async def get_conversation(
        self,
        conversation_id: UUID,
        *,
        with_messages: bool = True,
    ) -> Conversation:
        conversation = await self._repo.get_by_id(
            conversation_id, with_messages=with_messages
        )
        if conversation is None:
            raise NotFoundError(f"Conversation {conversation_id} not found")
        return conversation

    async def list_conversations(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Conversation], int]:
        items = await self._repo.list_all(skip=skip, limit=limit)
        total = await self._repo.count()
        return items, total

    async def delete_conversation(self, conversation_id: UUID) -> None:
        conversation = await self._repo.get_by_id(conversation_id)
        if conversation is None:
            raise NotFoundError(f"Conversation {conversation_id} not found")
        await self._repo.delete(conversation)
        await self._session.commit()
        logger.info("Conversation deleted id=%s", conversation_id)

    async def append_message(
        self,
        conversation_id: UUID,
        *,
        role: MessageRole | str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        cleaned = (content or "").strip()
        if not cleaned:
            raise ValidationError("Message content must not be empty")

        conversation = await self._repo.get_by_id(conversation_id)
        if conversation is None:
            raise NotFoundError(f"Conversation {conversation_id} not found")

        role_enum = role if isinstance(role, MessageRole) else MessageRole(role)
        message = await self._repo.append_message(
            conversation_id=conversation_id,
            role=role_enum,
            content=cleaned,
            metadata=metadata,
        )
        await self._repo.touch(conversation)
        await self._session.commit()
        await self._session.refresh(message)
        logger.info(
            "Message stored conversation_id=%s role=%s message_id=%s",
            conversation_id,
            role_enum.value,
            message.id,
        )
        return message

    async def load_history(
        self,
        conversation_id: UUID,
        *,
        limit: int | None = None,
    ) -> list[Message]:
        conversation = await self._repo.get_by_id(conversation_id)
        if conversation is None:
            raise NotFoundError(f"Conversation {conversation_id} not found")

        history_limit = (
            limit
            if limit is not None
            else self._settings.conversation_history_limit
        )
        messages = await self._repo.list_messages(
            conversation_id, limit=history_limit
        )
        logger.info(
            "History loaded conversation_id=%s messages=%s limit=%s",
            conversation_id,
            len(messages),
            history_limit,
        )
        return messages

    @staticmethod
    def messages_to_prompt_turns(messages: list[Message]) -> list[dict[str, str]]:
        """Serialize ORM messages into PromptBuilder history turns."""
        turns: list[dict[str, str]] = []
        for message in messages:
            turns.append(
                {
                    "role": message.role.value,
                    "content": message.content,
                }
            )
        return turns

    async def send_user_message(
        self,
        conversation_id: UUID,
        *,
        content: str,
        generator: Any,
        top_k: int | None = None,
        final_k: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Append user message, run grounded RAG with history, store assistant reply."""
        from app.services.generator import GeneratorService

        if not isinstance(generator, GeneratorService):
            raise ValidationError("A GeneratorService is required")

        history_messages = await self.load_history(conversation_id)
        history = self.messages_to_prompt_turns(history_messages)

        user_message = await self.append_message(
            conversation_id,
            role=MessageRole.USER,
            content=content,
        )

        result = await generator.answer_question(
            content,
            top_k=top_k,
            final_k=final_k,
            temperature=temperature,
            max_tokens=max_tokens,
            history=history,
        )

        assistant_meta = {
            "sources": [
                {
                    "document_id": str(src["document_id"]),
                    "filename": src.get("filename"),
                    "page": src.get("page"),
                    "chunk_id": str(src["chunk_id"]),
                    "score": src.get("score"),
                }
                for src in result.get("sources") or []
            ],
            "generation": result.get("metadata") or {},
        }
        assistant_message = await self.append_message(
            conversation_id,
            role=MessageRole.ASSISTANT,
            content=result["answer"],
            metadata=assistant_meta,
        )

        meta = dict(result.get("metadata") or {})
        meta["conversation_id"] = str(conversation_id)

        return {
            "conversation_id": conversation_id,
            "user_message": user_message,
            "assistant_message": assistant_message,
            "answer": result["answer"],
            "sources": result.get("sources") or [],
            "metadata": meta,
        }