"""Background ingestion task.

Runs the **existing** LangGraph ingestion pipeline off the request path so the
upload endpoint returns immediately. The pipeline itself is untouched: the task
only executes ``DocumentProcessingService.process_document`` inside a worker,
wiring a progress hook so each stage is streamed to Redis for the UI.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from app.core.celery_app import celery_app
from app.core.logging import get_logger
from app.db.session import task_session
from app.models.embedding import IndexStatus
from app.services.document_processing import DocumentProcessingService
from app.services.progress import get_ingestion_progress_service

logger = get_logger(__name__)


async def _process(document_id: str) -> dict:
    progress = get_ingestion_progress_service()
    doc_uuid = UUID(document_id)

    async def on_stage(node_name: str) -> None:
        await progress.report_stage(document_id, node_name)

    async with task_session() as session:
        service = DocumentProcessingService(session)
        try:
            document = await service.process_document(doc_uuid, on_stage=on_stage)
        except Exception as exc:
            await progress.mark_failed(document_id, str(exc))
            raise

        ready = document.index_status == IndexStatus.INDEXED
        await progress.mark_completed(
            document_id,
            extra={
                "document_status": _enum_value(document.status),
                "index_status": _enum_value(document.index_status),
                "indexed_chunk_count": document.indexed_chunk_count or 0,
                "page_count": document.page_count,
                "ready_for_analysis": ready,
            },
        )
        return {
            "document_id": document_id,
            "status": _enum_value(document.status),
            "index_status": _enum_value(document.index_status),
            "indexed_chunk_count": document.indexed_chunk_count or 0,
        }


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


@celery_app.task(
    bind=True,
    name="ingestion.process_document",
    acks_late=True,
    max_retries=0,
)
def process_document_task(self, document_id: str) -> dict:
    """Celery entrypoint: execute the async ingestion pipeline for one document."""
    logger.info(
        "Ingestion task started document_id=%s task_id=%s",
        document_id,
        self.request.id,
    )
    result = asyncio.run(_process(document_id))
    logger.info(
        "Ingestion task finished document_id=%s status=%s",
        document_id,
        result.get("status"),
    )
    return result


__all__ = ["process_document_task"]
