"""Business logic for document upload, retrieval, and deletion."""

from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, PayloadTooLargeError, ValidationError
from app.core.logging import get_logger
from app.models.document import Document, DocumentStatus
from app.repositories.document import DocumentRepository
from app.services.document_processing import (
    DocumentProcessingError,
    DocumentProcessingService,
)
from app.utils.storage import DocumentStorage, is_pdf_content

logger = get_logger(__name__)


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

    async def upload(self, file: UploadFile) -> Document:
        """Validate, store, persist as uploaded, then run the preprocessing pipeline."""
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

        try:
            document = await self._processing.process_document(document.id)
        except (DocumentProcessingError, Exception):
            # Processing service already marks FAILED and commits.
            logger.exception(
                "Automatic preprocessing failed for document_id=%s", document.id
            )
            failed = await self._repo.get_by_id(document.id)
            if failed is not None:
                return failed
            raise

        return document

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
