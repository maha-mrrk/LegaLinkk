"""Semantic retrieval: query embedding → pgvector Top-K cosine search."""

from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, ValidationError
from app.core.logging import get_logger
from app.repositories.retrieval import RetrievalHit, RetrievalRepository
from app.services.embedding import EmbeddingService, get_embedding_service

logger = get_logger(__name__)


class RetrievalError(AppError):
    """Raised when semantic retrieval fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class RetrievalService:
    """Retrieve the most relevant indexed chunks for a natural-language query."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._session = session
        self._repo = RetrievalRepository(session)
        self._embeddings = embedding_service or get_embedding_service()

    async def retrieve_hits(
        self,
        query: str,
        *,
        top_k: int | None = None,
        document_id: UUID | None = None,
        log_search_as: str = "Searching vectors...",
    ) -> tuple[str, list[RetrievalHit], int]:
        """Embed ``query`` and return ranked hits (no response shaping)."""
        cleaned = (query or "").strip()
        if not cleaned:
            raise ValidationError("Query must not be empty")

        k = top_k if top_k is not None else self._settings.retrieval_top_k
        if k < 1:
            raise ValidationError("top_k must be >= 1")
        if k > 50:
            raise ValidationError("top_k must be <= 50")

        logger.info("Generating query embedding...")
        try:
            vector = await asyncio.to_thread(self._embeddings.embed_query, cleaned)
        except Exception as exc:
            logger.exception("Query embedding failed")
            raise RetrievalError("Failed to generate query embedding") from exc

        logger.info("%s top_k=%s", log_search_as, k)
        try:
            hits = await self._repo.search_similar(
                vector,
                top_k=k,
                document_id=document_id,
            )
        except Exception as exc:
            logger.exception("Vector similarity search failed")
            raise RetrievalError("Similarity search failed") from exc

        return cleaned, hits, k

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        document_id: UUID | None = None,
    ) -> dict:
        """Embed ``query`` and return Top-K cosine-similar chunks."""
        cleaned, hits, k = await self.retrieve_hits(
            query,
            top_k=top_k,
            document_id=document_id,
        )
        logger.info("Top %s chunks retrieved.", len(hits))
        logger.info("Retrieval completed.")

        return {
            "query": cleaned,
            "top_k": k,
            "results": [self._hit_to_dict(hit) for hit in hits],
        }

    @staticmethod
    def _hit_to_dict(hit: RetrievalHit) -> dict:
        return {
            "chunk_id": hit.chunk_id,
            "document_id": hit.document_id,
            "filename": hit.filename,
            "text": hit.text,
            "similarity": hit.similarity,
            "page_numbers": hit.page_numbers,
            "extraction_method": hit.extraction_method,
            "chunk_index": hit.chunk_index,
            "embedding_model": hit.embedding_model,
        }
