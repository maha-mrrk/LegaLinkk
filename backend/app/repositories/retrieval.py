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
            .where(Document.index_status == IndexStatus.INDEXED)
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
            pages = entity.page_numbers or []
            hits.append(
                RetrievalHit(
                    chunk_id=entity.chunk_id,
                    document_id=entity.document_id,
                    filename=entity.filename,
                    text=entity.chunk_text,
                    similarity=score,
                    page_numbers=[int(p) for p in pages],
                    extraction_method=entity.extraction_method,
                    chunk_index=entity.chunk_index,
                    embedding_model=entity.embedding_model,
                )
            )
        return hits
