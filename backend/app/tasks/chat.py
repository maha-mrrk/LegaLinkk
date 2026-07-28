"""Background chat/agent generation that survives browser disconnection."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from app.core.celery_app import celery_app
from app.core.logging import get_logger
from app.db.session import task_session
from app.services.agent_stream import AgentStreamService
from app.services.chat_job import get_chat_job_store
from app.services.generator import GeneratorService

logger = get_logger(__name__)


async def _generate(
    job_id: str,
    user_id: str,
    mode: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    store = get_chat_job_store()
    await store.mark_processing(job_id)
    owner_id = UUID(user_id)
    document_id = (
        UUID(str(payload["document_id"]))
        if payload.get("document_id")
        else None
    )

    async with task_session() as session:
        generator = GeneratorService(session)
        if mode == "agent":
            events = AgentStreamService(generator).stream(
                str(payload["question"]),
                user_id=owner_id,
                document_id=document_id,
                top_k=payload.get("top_k"),
                final_k=payload.get("final_k"),
                temperature=payload.get("temperature"),
                max_tokens=payload.get("max_tokens"),
            )
        else:
            events = generator.stream_answer(
                str(payload["question"]),
                user_id=owner_id,
                document_id=document_id,
                top_k=payload.get("top_k"),
                final_k=payload.get("final_k"),
                temperature=payload.get("temperature"),
                max_tokens=payload.get("max_tokens"),
            )

        event_count = 0
        async for event in events:
            await store.append_event(job_id, event)
            event_count += 1

    return {"job_id": job_id, "status": "completed", "events": event_count}


@celery_app.task(
    bind=True,
    name="chat.generate",
    acks_late=True,
    max_retries=0,
)
def process_chat_job_task(
    self,
    job_id: str,
    user_id: str,
    mode: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Run generation independently from the originating HTTP connection."""
    logger.info(
        "Chat job started job_id=%s task_id=%s mode=%s",
        job_id,
        self.request.id,
        mode,
    )
    try:
        result = asyncio.run(_generate(job_id, user_id, mode, payload))
    except Exception:
        logger.exception("Chat job failed job_id=%s", job_id)
        asyncio.run(
            get_chat_job_store().mark_failed(
                job_id,
                "La génération a été interrompue. Vous pouvez relancer la question.",
            )
        )
        raise
    logger.info("Chat job completed job_id=%s", job_id)
    return result


__all__ = ["process_chat_job_task"]
