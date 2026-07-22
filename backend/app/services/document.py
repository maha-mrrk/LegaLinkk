"""Business logic for document upload, retrieval, and deletion."""

import asyncio
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, PayloadTooLargeError, ValidationError
from app.core.logging import get_logger
from app.models.document import Document, DocumentStatus
from app.repositories.document import DocumentRepository
from app.services.document_processing import DocumentProcessingService
from app.services.progress import get_ingestion_progress_service
from app.utils.storage import DocumentStorage, is_pdf_content

logger = get_logger(__name__)


class UploadResult:
    """Outcome of an upload: the persisted document + its background task id."""

    __slots__ = ("document", "task_id")

    def __init__(self, document: Document, task_id: str | None) -> None:
        self.document = document
        self.task_id = task_id


class DocumentService:
    """Orchestrates validation, storage, preprocessing, and persistence."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
        storage: DocumentStorage | None = None,
        processing_service: DocumentProcessingService | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._repo = DocumentRepository(session)
        self._session = session
        self._storage = storage or DocumentStorage(self._settings)
        self._processing = processing_service or DocumentProcessingService(
            session, settings=self._settings
        )
        self._progress = get_ingestion_progress_service()

    async def upload(self, file: UploadFile) -> UploadResult:
        """Validate, store, persist as uploaded, then queue background processing.

        The heavy pipeline (extract → OCR → clean → chunk → embed → index) runs
        asynchronously via Celery so this call returns immediately with the
        document id, task id, and initial status. Live progress is exposed via
        ``GET /documents/{id}/progress``.
        """
        original_filename = self._require_filename(file.filename)
        content = await file.read()
        self._validate_upload(original_filename, file.content_type, content)

        stored_filename = self._storage.build_stored_filename(original_filename)
        saved_path = await self._storage.save(stored_filename, content)

        document = Document(
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=str(saved_path),
            mime_type="application/pdf",
            file_size=len(content),
            status=DocumentStatus.UPLOADED,
        )

        try:
            document = await self._repo.create(document)
            await self._session.commit()
            await self._session.refresh(document)
        except Exception:
            await self._session.rollback()
            await self._storage.delete(stored_filename)
            logger.exception(
                "Failed to persist document metadata for %s", original_filename
            )
            raise

        logger.info(
            "Document uploaded id=%s filename=%s status=%s",
            document.id,
            original_filename,
            document.status.value,
        )

        task_id = await self._enqueue_processing(document.id)
        return UploadResult(document=document, task_id=task_id)

    async def _enqueue_processing(self, document_id: UUID) -> str | None:
        """Queue the ingestion task and seed the progress store (best-effort)."""
        # Imported lazily to keep Celery/Redis optional at import time.
        from app.tasks.ingestion import process_document_task

        doc_id = str(document_id)
        try:
            async_result = await asyncio.to_thread(
                process_document_task.delay, doc_id
            )
            task_id = async_result.id
            await self._progress.mark_queued(doc_id, task_id)
            logger.info("Ingestion queued document_id=%s task_id=%s", doc_id, task_id)
            return task_id
        except Exception:
            logger.exception("Failed to enqueue ingestion for document_id=%s", doc_id)
            await self._progress.mark_failed(
                doc_id, "Could not queue processing. Please retry."
            )
            return None

    async def reprocess(self, document_id: UUID) -> UploadResult:
        """Re-queue background processing for an existing document."""
        document = await self.get_document(document_id)
        task_id = await self._enqueue_processing(document.id)
        return UploadResult(document=document, task_id=task_id)

    async def get_progress(self, document_id: UUID) -> dict:
        """Return live ingestion progress, falling back to DB-derived status."""
        live = await self._progress.get(str(document_id))
        if live:
            progress = int(live.get("progress") or 0)
            status = str(live.get("status") or "unknown")
            return {
                "document_id": document_id,
                "task_id": live.get("task_id"),
                "status": status,
                "stage": live.get("stage"),
                "stage_label": live.get("stage_label"),
                "progress": progress,
                "remaining": max(0, 100 - progress),
                "message": live.get("message"),
                "error": live.get("error"),
                "completed": status == "completed",
                "updated_at": live.get("updated_at"),
                "timeline": live.get("timeline") or [],
            }

        document = await self.get_document(document_id)
        return self._progress_from_document(document)

    @staticmethod
    def _progress_from_document(document: Document) -> dict:
        """Best-effort progress when no live Redis entry exists (e.g. expired)."""
        status = document.status
        mapping = {
            DocumentStatus.UPLOADED: ("queued", 5, "Queued", "Queued for processing…"),
            DocumentStatus.PROCESSING: (
                "processing",
                50,
                "Processing",
                "Processing your document…",
            ),
            DocumentStatus.PROCESSED: (
                "completed",
                100,
                "Completed",
                "Document ready for AI analysis.",
            ),
            DocumentStatus.COMPLETED: (
                "completed",
                100,
                "Completed",
                "Document ready for AI analysis.",
            ),
            DocumentStatus.FAILED: (
                "failed",
                100,
                "Failed",
                "Processing failed. Please try again.",
            ),
        }
        state, progress, label, message = mapping.get(
            status, ("unknown", 0, None, None)
        )
        return {
            "document_id": document.id,
            "task_id": None,
            "status": state,
            "stage": state,
            "stage_label": label,
            "progress": progress,
            "remaining": max(0, 100 - progress),
            "message": message,
            "error": None,
            "completed": state == "completed",
            "updated_at": None,
            "timeline": [],
        }

    async def list_documents(
        self, *, skip: int = 0, limit: int = 100
    ) -> tuple[list[Document], int]:
        documents = await self._repo.list_all(skip=skip, limit=limit)
        total = await self._repo.count()
        return documents, total

    async def get_document(self, document_id: UUID) -> Document:
        document = await self._repo.get_by_id(document_id)
        if document is None:
            raise NotFoundError(f"Document {document_id} not found")
        return document

    async def delete_document(self, document_id: UUID) -> None:
        document = await self.get_document(document_id)
        stored_filename = document.stored_filename

        await self._repo.delete(document)
        await self._session.commit()
        await self._storage.delete(stored_filename)
        logger.info("Document deleted id=%s", document_id)

    def _require_filename(self, filename: str | None) -> str:
        if not filename or not filename.strip():
            raise ValidationError("A filename is required")
        return Path(filename).name

    def _validate_upload(
        self,
        original_filename: str,
        content_type: str | None,
        content: bytes,
    ) -> None:
        if not content:
            raise ValidationError("Uploaded file is empty")

        max_bytes = self._settings.max_upload_size_bytes
        if len(content) > max_bytes:
            raise PayloadTooLargeError(
                f"File exceeds the maximum size of {self._settings.max_upload_size_mb} MB"
            )

        extension = Path(original_filename).suffix.lower()
        if extension != ".pdf":
            raise ValidationError("Only PDF files are accepted")

        mime = (content_type or "").split(";")[0].strip().lower()
        allowed = self._settings.allowed_mime_type_set
        if mime and mime not in allowed and mime != "application/octet-stream":
            raise ValidationError("Only PDF files are accepted")

        if not is_pdf_content(content):
            raise ValidationError("File content is not a valid PDF")
