"""Data-access layer for DocumentChunk entities."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import DocumentChunk


class DocumentChunkRepository:
    """CRUD persistence operations for document chunks."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        if not chunks:
            return []
        self._session.add_all(chunks)
        await self._session.flush()
        for chunk in chunks:
            await self._session.refresh(chunk)
        return chunks

    async def list_by_document_id(self, document_id: UUID) -> list[DocumentChunk]:
        result = await self._session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        return list(result.scalars().all())

    async def delete_by_document_id(self, document_id: UUID) -> int:
        result = await self._session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        await self._session.flush()
        return int(result.rowcount or 0)

    async def count_by_document_id(self, document_id: UUID) -> int:
        result = await self._session.execute(
            select(DocumentChunk.id).where(DocumentChunk.document_id == document_id)
        )
        return len(result.all())
