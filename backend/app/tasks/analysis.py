"""Celery task for contract analysis independent of the browser connection."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from app.agents.legal import LegalAgent
from app.core.celery_app import celery_app
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.db.session import task_session
from app.schemas.agents import LegalAnalysisResponse
from app.services.analysis_job import get_analysis_job_store
from app.services.contract_analysis import ContractAnalysisService
from app.services.conversation import ConversationService
from app.services.generator import GeneratorService

logger = get_logger(__name__)


async def _analyze(
    job_id: str,
    user_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    store = get_analysis_job_store()
    await store.mark_processing(job_id)
    owner_id = UUID(user_id)
    document_id = UUID(str(payload["document_id"]))

    async with task_session() as session:
        history = None
        if payload.get("conversation_id"):
            conversations = ConversationService(session)
            messages = await conversations.load_history(
                UUID(str(payload["conversation_id"])),
                user_id=owner_id,
            )
            history = ConversationService.messages_to_prompt_turns(messages)

        generator = GeneratorService(session)
        service = ContractAnalysisService(session, LegalAgent(generator))
        result = await service.get_or_analyze(
            str(payload["question"]),
            user_id=owner_id,
            document_id=document_id,
            force_refresh=bool(payload.get("force_refresh")),
            top_k=payload.get("top_k"),
            final_k=payload.get("final_k"),
            temperature=payload.get("temperature"),
            max_tokens=payload.get("max_tokens"),
            history=history,
        )
        validated = LegalAnalysisResponse.model_validate(result).model_dump(
            mode="json"
        )
        await store.mark_completed(job_id, validated)
        return {"job_id": job_id, "status": "completed"}


@celery_app.task(
    bind=True,
    name="analysis.generate",
    acks_late=True,
    max_retries=0,
)
def process_analysis_job_task(
    self,
    job_id: str,
    user_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    logger.info(
        "Analysis job started job_id=%s task_id=%s document_id=%s",
        job_id,
        self.request.id,
        payload.get("document_id"),
    )
    try:
        result = asyncio.run(_analyze(job_id, user_id, payload))
    except Exception as exc:
        logger.exception("Analysis job failed job_id=%s", job_id)
        message = (
            exc.message
            if isinstance(exc, AppError)
            else "L’analyse n’a pas pu être terminée. Veuillez réessayer."
        )
        asyncio.run(get_analysis_job_store().mark_failed(job_id, message))
        raise
    logger.info("Analysis job completed job_id=%s", job_id)
    return result


__all__ = ["process_analysis_job_task"]
