"""Document preprocessing pipeline: extract → clean → chunk → persist."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentStatus, ExtractionMethod
from app.models.embedding import IndexStatus
from app.parsers.extraction_pipeline import ExtractionError, ExtractionPipeline
from app.repositories.chunk import DocumentChunkRepository
from app.repositories.document import DocumentRepository
from app.services.chunker import SemanticChunker
from app.services.text_cleaner import clean_text

logger = get_logger(__name__)


class DocumentProcessingError(Exception):
    """Raised when the preprocessing pipeline fails."""


class DocumentProcessingService:
    """Orchestrates text extraction, cleaning, chunking, and chunk persistence."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
        extraction_pipeline: ExtractionPipeline | None = None,
        chunker: SemanticChunker | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._session = session
        self._documents = DocumentRepository(session)
        self._chunks = DocumentChunkRepository(session)
        self._extraction = extraction_pipeline or ExtractionPipeline(
            settings=self._settings
        )
        self._chunker = chunker or SemanticChunker(
            chunk_size=self._settings.chunk_size,
            chunk_overlap=self._settings.chunk_overlap,
        )

    async def process_document(self, document_id: UUID) -> Document:
        """Run the full preprocessing pipeline for an existing document."""
        document = await self._documents.get_by_id(document_id)
        if document is None:
            raise NotFoundError(f"Document {document_id} not found")

        document.status = DocumentStatus.PROCESSING
        await self._session.commit()
        logger.info(
            "Processing started for document_id=%s filename=%s",
            document.id,
            document.original_filename,
        )

        try:
            await self._chunks.delete_by_document_id(document.id)
            document.index_status = IndexStatus.NOT_INDEXED
            document.indexed_at = None
            document.indexed_chunk_count = 0
            document.embedding_model = None

            logger.info("Parsing started for document_id=%s", document.id)
            extraction = await asyncio.to_thread(
                self._extraction.extract, document.file_path
            )

            method_value = extraction.extraction_method
            if method_value == ExtractionMethod.PADDLE_OCR.value:
                logger.info("OCR used for document_id=%s", document.id)

            cleaned = clean_text(extraction.text)
            if not cleaned:
                raise DocumentProcessingError(
                    f"No usable text extracted from document {document.id}"
                )

            document.extracted_text = cleaned
            document.page_count = extraction.page_count
            if method_value:
                document.extraction_method = ExtractionMethod(method_value)

            page_tuples = [
                (page.page_number, page.text) for page in extraction.pages
            ] or None

            created_at = datetime.now(timezone.utc)
            drafts = self._chunker.chunk_document(
                document_id=document.id,
                text=cleaned,
                pages=page_tuples,
                extraction_method=method_value,
                created_at=created_at,
            )
            if not drafts:
                raise DocumentProcessingError(
                    f"Chunking produced no chunks for document {document.id}"
                )

            entities = [
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=draft.chunk_index,
                    text=draft.text,
                    metadata_=draft.metadata,
                    created_at=created_at,
                )
                for draft in drafts
            ]
            await self._chunks.create_many(entities)
            logger.info(
                "Chunks stored for document_id=%s count=%s",
                document.id,
                len(entities),
            )

            document.status = DocumentStatus.PROCESSED
            await self._session.commit()
            await self._session.refresh(document)
            logger.info(
                "Processing completed for document_id=%s chunks=%s method=%s",
                document.id,
                len(entities),
                document.extraction_method,
            )

            if self._settings.auto_index_on_process:
                from app.services.indexing import IndexingError, IndexingService

                logger.info(
                    "Auto-indexing enabled — starting semantic index for %s",
                    document.id,
                )
                try:
                    document = await IndexingService(
                        self._session, settings=self._settings
                    ).index_document(document.id)
                except IndexingError:
                    # Chunking succeeded; keep document as processed even if index fails.
                    logger.exception(
                        "Auto-indexing failed for document_id=%s", document.id
                    )
                    document = await self._documents.get_by_id(document.id) or document

            return document
        except Exception:
            await self._session.rollback()
            failed = await self._documents.get_by_id(document_id)
            if failed is not None:
                failed.status = DocumentStatus.FAILED
                await self._session.commit()
            logger.exception(
                "Processing failed for document_id=%s", document_id
            )
            raise

    async def get_chunks(self, document_id: UUID) -> list[DocumentChunk]:
        document = await self._documents.get_by_id(document_id)
        if document is None:
            raise NotFoundError(f"Document {document_id} not found")
        return await self._chunks.list_by_document_id(document_id)

    async def get_status(self, document_id: UUID) -> Document:
        document = await self._documents.get_by_id(document_id)
        if document is None:
            raise NotFoundError(f"Document {document_id} not found")
        return document
