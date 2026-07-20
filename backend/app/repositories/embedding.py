"""pgvector persistence layer for document embeddings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.embedding import DocumentEmbedding


@dataclass(frozen=True, slots=True)
class EmbeddingRecord:
    """One embedding row ready for insert / bulk insert into pgvector."""

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


class EmbeddingRepository:
    """All DocumentEmbedding / pgvector interactions go through this repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, record: EmbeddingRecord) -> DocumentEmbedding:
        """Insert a single embedding row."""
        entity = DocumentEmbedding(
            id=uuid4(),
            document_id=record.document_id,
            chunk_id=record.chunk_id,
            filename=record.filename,
            page_numbers=record.page_numbers,
            extraction_method=record.extraction_method,
            upload_date=record.upload_date,
            chunk_index=record.chunk_index,
            chunk_text=record.chunk_text,
            embedding_model=record.embedding_model,
            embedding=record.embedding,
        )
        self._session.add(entity)
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def update(
        self,
        embedding_id: UUID,
        *,
        embedding: list[float],
        embedding_model: str,
        chunk_text: str | None = None,
    ) -> DocumentEmbedding | None:
        """Update an existing embedding by primary key."""
        values: dict = {
            "embedding": embedding,
            "embedding_model": embedding_model,
            "updated_at": func.now(),
        }
        if chunk_text is not None:
            values["chunk_text"] = chunk_text

        await self._session.execute(
            update(DocumentEmbedding)
            .where(DocumentEmbedding.id == embedding_id)
            .values(**values)
        )
        await self._session.flush()
        return await self.get_by_id(embedding_id)

    async def delete(self, embedding_id: UUID) -> int:
        """Delete a single embedding by primary key."""
        result = await self._session.execute(
            delete(DocumentEmbedding).where(DocumentEmbedding.id == embedding_id)
        )
        await self._session.flush()
        return int(result.rowcount or 0)

    async def get_by_id(self, embedding_id: UUID) -> DocumentEmbedding | None:
        """Retrieve one embedding by primary key."""
        result = await self._session.execute(
            select(DocumentEmbedding).where(DocumentEmbedding.id == embedding_id)
        )
        return result.scalar_one_or_none()

    async def get_by_chunk_id(self, chunk_id: UUID) -> DocumentEmbedding | None:
        """Retrieve the embedding linked to a chunk."""
        result = await self._session.execute(
            select(DocumentEmbedding).where(DocumentEmbedding.chunk_id == chunk_id)
        )
        return result.scalar_one_or_none()

    async def list_by_document_id(self, document_id: UUID) -> list[DocumentEmbedding]:
        """Retrieve every embedding for a document."""
        result = await self._session.execute(
            select(DocumentEmbedding)
            .where(DocumentEmbedding.document_id == document_id)
            .order_by(DocumentEmbedding.chunk_index.asc())
        )
        return list(result.scalars().all())

    async def bulk_insert(self, records: list[EmbeddingRecord]) -> int:
        """Insert many embeddings, replacing any existing row for the same chunk_id."""
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

        stmt = insert(DocumentEmbedding).values(rows)
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
        """Delete every embedding associated with a document."""
        result = await self._session.execute(
            delete(DocumentEmbedding).where(
                DocumentEmbedding.document_id == document_id
            )
        )
        await self._session.flush()
        return int(result.rowcount or 0)

    async def count_by_document_id(self, document_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(DocumentEmbedding)
            .where(DocumentEmbedding.document_id == document_id)
        )
        return int(result.scalar_one())

    async def list_chunk_ids(self, document_id: UUID) -> list[UUID]:
        result = await self._session.execute(
            select(DocumentEmbedding.chunk_id).where(
                DocumentEmbedding.document_id == document_id
            )
        )
        return list(result.scalars().all())
