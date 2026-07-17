"""Semantic indexing orchestration: chunks → embeddings → pgvector."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.document import Document, DocumentStatus
from app.models.embedding import IndexStatus
from app.repositories.chunk import DocumentChunkRepository
from app.repositories.document import DocumentRepository
from app.repositories.vector import VectorRecord, VectorRepository
from app.services.embedding import EmbeddingService, get_embedding_service

logger = get_logger(__name__)


class IndexingError(AppError):
    """Raised when semantic indexing fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class IndexingService:
    """Build and maintain pgvector indexes for processed documents."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._session = session
        self._documents = DocumentRepository(session)
        self._chunks = DocumentChunkRepository(session)
        self._vectors = VectorRepository(session)
        self._embeddings = embedding_service or get_embedding_service()

    async def index_document(self, document_id: UUID) -> Document:
        """Generate embeddings for all chunks and upsert into pgvector.

        Re-indexing a document replaces its vectors (no duplicates).
        """
        document = await self._documents.get_by_id(document_id)
        if document is None:
            raise NotFoundError(f"Document {document_id} not found")

        if document.status not in {
            DocumentStatus.PROCESSED,
            DocumentStatus.COMPLETED,
        }:
            raise ValidationError(
                "Document must be processed before indexing "
                f"(current status: {document.status.value})"
            )

        chunks = await self._chunks.list_by_document_id(document_id)
        if not chunks:
            raise ValidationError("Document has no chunks to index")

        document.index_status = IndexStatus.INDEXING
        await self._session.commit()
        logger.info(
            "Indexing started for document_id=%s chunks=%s",
            document.id,
            len(chunks),
        )

        try:
            texts = [chunk.text for chunk in chunks]
            vectors = await asyncio.to_thread(self._embeddings.embed_texts, texts)
            if len(vectors) != len(chunks):
                raise IndexingError(
                    f"Embedding count mismatch: got {len(vectors)} for {len(chunks)} chunks"
                )

            model_name = self._embeddings.model_name
            logger.info(
                "Saving vectors... document_id=%s count=%s",
                document.id,
                len(chunks),
            )

            records = [
                VectorRecord(
                    document_id=document.id,
                    chunk_id=chunk.id,
                    filename=document.original_filename,
                    page_numbers=list(
                        (chunk.metadata_ or {}).get("page_numbers") or []
                    ),
                    extraction_method=(
                        document.extraction_method.value
                        if document.extraction_method
                        else (chunk.metadata_ or {}).get("extraction_method")
                    ),
                    upload_date=document.upload_date,
                    chunk_index=chunk.chunk_index,
                    chunk_text=chunk.text,
                    embedding_model=model_name,
                    embedding=vector,
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ]

            # Replace document vectors so re-index never duplicates rows.
            await self._vectors.delete_by_document_id(document.id)
            saved = await self._vectors.upsert_many(records)

            document.index_status = IndexStatus.INDEXED
            document.indexed_at = datetime.now(timezone.utc)
            document.indexed_chunk_count = saved
            document.embedding_model = model_name
            await self._session.commit()
            await self._session.refresh(document)

            logger.info(
                "Index completed document_id=%s vectors=%s model=%s",
                document.id,
                saved,
                model_name,
            )
            logger.info("Document indexed id=%s", document.id)
            return document
        except Exception as exc:
            await self._session.rollback()
            failed = await self._documents.get_by_id(document_id)
            if failed is not None:
                failed.index_status = IndexStatus.FAILED
                await self._session.commit()
            logger.exception("Indexing failed for document_id=%s", document_id)
            raise IndexingError(
                f"Indexing failed for document {document_id}"
            ) from exc

    async def get_index_status(self, document_id: UUID) -> dict:
        document = await self._documents.get_by_id(document_id)
        if document is None:
            raise NotFoundError(f"Document {document_id} not found")

        vector_count = await self._vectors.count_by_document_id(document_id)
        chunk_count = len(await self._chunks.list_by_document_id(document_id))
        return {
            "document_id": document.id,
            "index_status": document.index_status,
            "chunk_count": chunk_count,
            "indexed_count": vector_count,
            "embedding_model": document.embedding_model,
            "indexed_at": document.indexed_at,
        }

    async def delete_index(self, document_id: UUID) -> Document:
        document = await self._documents.get_by_id(document_id)
        if document is None:
            raise NotFoundError(f"Document {document_id} not found")

        deleted = await self._vectors.delete_by_document_id(document_id)
        document.index_status = IndexStatus.NOT_INDEXED
        document.indexed_at = None
        document.indexed_chunk_count = 0
        document.embedding_model = None
        await self._session.commit()
        await self._session.refresh(document)
        logger.info(
            "Index deleted document_id=%s removed_vectors=%s",
            document_id,
            deleted,
        )
        return document
