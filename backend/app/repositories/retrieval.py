"""pgvector similarity search for document chunk embeddings."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.embedding import DocumentEmbedding, IndexStatus


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    """One cosine-similarity match from PostgreSQL/pgvector."""

    chunk_id: UUID
    document_id: UUID
    filename: str
    text: str
    similarity: float
    page_numbers: list[int]
    extraction_method: str | None
    chunk_index: int
    embedding_model: str


class RetrievalRepository:
    """All vector similarity queries go through this repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search_similar(
        self,
        query_embedding: list[float],
        *,
        user_id: UUID,
        top_k: int = 5,
        document_id: UUID | None = None,
    ) -> list[RetrievalHit]:
        """Return Top-K chunks by cosine similarity (highest first).

        Cosine distance (``<=>``) is converted to similarity as ``1 - distance``.
        Only embeddings belonging to ``INDEXED`` documents are searched.
        """
        if top_k <= 0:
            return []

        distance = DocumentEmbedding.embedding.cosine_distance(query_embedding)
        similarity = (1 - distance).label("similarity")

        stmt: Select = (
            select(DocumentEmbedding, similarity)
            .join(Document, Document.id == DocumentEmbedding.document_id)
            .where(
                Document.user_id == user_id,
                Document.index_status == IndexStatus.INDEXED,
            )
            .order_by(distance)
            .limit(top_k)
        )
        if document_id is not None:
            stmt = stmt.where(DocumentEmbedding.document_id == document_id)

        result = await self._session.execute(stmt)
        hits: list[RetrievalHit] = []
        for row in result.all():
            entity: DocumentEmbedding = row[0]
            score = float(row[1])
            hits.append(self._to_hit(entity, similarity=score))
        return hits

    async def list_all_by_document(
        self, document_id: UUID, *, user_id: UUID
    ) -> list[RetrievalHit]:
        """Return **every** chunk of a document, ordered by ``chunk_index``.

        Unlike :meth:`search_similar`, this performs **no** query embedding and
        **no** cosine ranking: it returns the whole document in reading order so a
        caller can analyse the entire contract without any Top-K slicing. Used by
        the "full-document analysis" mode (see ``GeneratorService``), never by the
        Q&A retrieval path, which must stay similarity-based on the user question.

        Reuses the denormalized ``chunk_embeddings`` row (text, filename, pages)
        so the result is a plain ``list[RetrievalHit]`` that flows through the
        existing prompt/source-building pipeline unchanged. ``similarity`` is set
        to 1.0 because every chunk is included by design, not by relevance score.
        """
        stmt: Select = (
            select(DocumentEmbedding)
            .join(Document, Document.id == DocumentEmbedding.document_id)
            .where(
                DocumentEmbedding.document_id == document_id,
                Document.user_id == user_id,
            )
            .order_by(DocumentEmbedding.chunk_index.asc())
        )
        result = await self._session.execute(stmt)
        return [
            self._to_hit(entity, similarity=1.0)
            for entity in result.scalars().all()
        ]

    @staticmethod
    def _to_hit(entity: DocumentEmbedding, *, similarity: float) -> RetrievalHit:
        pages = entity.page_numbers or []
        return RetrievalHit(
            chunk_id=entity.chunk_id,
            document_id=entity.document_id,
            filename=entity.filename,
            text=entity.chunk_text,
            similarity=similarity,
            page_numbers=[int(p) for p in pages],
            extraction_method=entity.extraction_method,
            chunk_index=entity.chunk_index,
            embedding_model=entity.embedding_model,
        )
