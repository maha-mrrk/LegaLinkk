"""Document preprocessing pipeline: extract → clean → chunk → persist."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentStatus, ExtractionMethod
from app.models.embedding import IndexStatus
from app.parsers.extraction_pipeline import ExtractionPipeline
from app.repositories.chunk import DocumentChunkRepository
from app.repositories.document import DocumentRepository
from app.services.chunker import SemanticChunker

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
        """Run the full ingestion pipeline (LangGraph) for an existing document.

        The node orchestration (parse → ocr → clean → chunk → embed → persist →
        index) is driven by :func:`app.graphs.ingestion_graph.build_ingestion_graph`.
        This method only owns the surrounding transactional shell: flipping the
        document status and resetting any previous processing/index state.
        """
        # Imported lazily to avoid a circular import (the graph persists via us).
        from app.graphs.ingestion_graph import build_ingestion_graph

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
            await self._session.commit()

            graph = build_ingestion_graph(
                session=self._session,
                settings=self._settings,
                persister=self,
            )
            initial_state = {
                "document_id": str(document.id),
                "filename": document.original_filename,
                "metadata": {"file_path": document.file_path},
                "errors": [],
            }
            final_state = await graph.ainvoke(initial_state)

            errors = final_state.get("errors") or []
            if errors:
                logger.warning(
                    "Ingestion finished with non-fatal errors for document_id=%s: %s",
                    document.id,
                    errors,
                )

            refreshed = await self._documents.get_by_id(document.id)
            document = refreshed or document
            logger.info(
                "Processing completed for document_id=%s method=%s",
                document.id,
                document.extraction_method,
            )
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

    async def finalize_chunks(
        self,
        document_id: UUID,
        *,
        cleaned_text: str,
        page_count: int,
        extraction_method: str | None,
        chunks: list[dict],
        created_at: datetime | None = None,
    ) -> Document:
        """Persist chunks produced by the ingestion graph and mark the document processed.

        This is the single source of truth for chunk persistence: the graph's
        persistence step delegates here so the logic is never duplicated.
        """
        document = await self._documents.get_by_id(document_id)
        if document is None:
            raise NotFoundError(f"Document {document_id} not found")

        if not (cleaned_text or "").strip():
            raise DocumentProcessingError(
                f"No usable text extracted from document {document_id}"
            )
        if not chunks:
            raise DocumentProcessingError(
                f"Chunking produced no chunks for document {document_id}"
            )

        document.extracted_text = cleaned_text
        document.page_count = page_count
        if extraction_method:
            document.extraction_method = ExtractionMethod(extraction_method)

        stamp = created_at or datetime.now(timezone.utc)
        entities = [
            DocumentChunk(
                document_id=document.id,
                chunk_index=chunk["chunk_index"],
                text=chunk["text"],
                metadata_=chunk.get("metadata") or {},
                created_at=stamp,
            )
            for chunk in chunks
        ]
        await self._chunks.create_many(entities)

        document.status = DocumentStatus.PROCESSED
        await self._session.commit()
        await self._session.refresh(document)
        logger.info(
            "Chunks stored for document_id=%s count=%s",
            document.id,
            len(entities),
        )
        return document

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
