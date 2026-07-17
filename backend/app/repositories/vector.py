"""pgvector persistence layer for chunk embeddings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.embedding import ChunkEmbedding


@dataclass(frozen=True, slots=True)
class VectorRecord:
    """One embedding row ready for upsert into pgvector."""

    document_id: UUID
    chunk_id: UUID
    filename: str
    page_numbers: list[int]
    extraction_method: str | None
    upload_date: datetime
    chunk_index: int
    chunk_text: str
    embedding_model: str
    embedding: list[float]


class VectorRepository:
    """All pgvector / chunk_embeddings interactions go through this repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, records: list[VectorRecord]) -> int:
        """Insert or update embeddings by ``chunk_id`` (no duplicates)."""
        if not records:
            return 0

        rows = [
            {
                "id": uuid4(),
                "document_id": record.document_id,
                "chunk_id": record.chunk_id,
                "filename": record.filename,
                "page_numbers": record.page_numbers,
                "extraction_method": record.extraction_method,
                "upload_date": record.upload_date,
                "chunk_index": record.chunk_index,
                "chunk_text": record.chunk_text,
                "embedding_model": record.embedding_model,
                "embedding": record.embedding,
            }
            for record in records
        ]

        stmt = insert(ChunkEmbedding).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_chunk_embeddings_chunk_id",
            set_={
                "document_id": stmt.excluded.document_id,
                "filename": stmt.excluded.filename,
                "page_numbers": stmt.excluded.page_numbers,
                "extraction_method": stmt.excluded.extraction_method,
                "upload_date": stmt.excluded.upload_date,
                "chunk_index": stmt.excluded.chunk_index,
                "chunk_text": stmt.excluded.chunk_text,
                "embedding_model": stmt.excluded.embedding_model,
                "embedding": stmt.excluded.embedding,
                "updated_at": func.now(),
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return len(rows)

    async def delete_by_document_id(self, document_id: UUID) -> int:
        result = await self._session.execute(
            delete(ChunkEmbedding).where(ChunkEmbedding.document_id == document_id)
        )
        await self._session.flush()
        return int(result.rowcount or 0)

    async def count_by_document_id(self, document_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(ChunkEmbedding)
            .where(ChunkEmbedding.document_id == document_id)
        )
        return int(result.scalar_one())

    async def list_chunk_ids(self, document_id: UUID) -> list[UUID]:
        result = await self._session.execute(
            select(ChunkEmbedding.chunk_id).where(
                ChunkEmbedding.document_id == document_id
            )
        )
        return list(result.scalars().all())
