"""Data-access layer for Document entities."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document


class DocumentRepository:
    """CRUD persistence operations for documents."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, document: Document) -> Document:
        self._session.add(document)
        await self._session.flush()
        await self._session.refresh(document)
        return document

    async def get_by_id(self, document_id: UUID) -> Document | None:
        result = await self._session.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, *, skip: int = 0, limit: int = 100) -> list[Document]:
        result = await self._session.execute(
            select(Document)
            .order_by(Document.upload_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(Document))
        return int(result.scalar_one())

    async def delete(self, document: Document) -> None:
        await self._session.delete(document)
        await self._session.flush()
