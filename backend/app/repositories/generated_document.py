"""Data access for owner-scoped generated PDF reports."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.generated_document import GeneratedDocument


class GeneratedDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, item: GeneratedDocument) -> GeneratedDocument:
        self._session.add(item)
        await self._session.flush()
        return item

    async def get_by_id(
        self,
        item_id: UUID,
        *,
        user_id: UUID,
    ) -> GeneratedDocument | None:
        result = await self._session.execute(
            select(GeneratedDocument).where(
                GeneratedDocument.id == item_id,
                GeneratedDocument.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        *,
        user_id: UUID,
        source_document_id: UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[tuple[GeneratedDocument, str | None]], int]:
        filters = [GeneratedDocument.user_id == user_id]
        if source_document_id is not None:
            filters.append(
                GeneratedDocument.source_document_id == source_document_id
            )
        stmt = (
            select(GeneratedDocument, Document.original_filename)
            .outerjoin(
                Document,
                Document.id == GeneratedDocument.source_document_id,
            )
            .where(*filters)
            .order_by(GeneratedDocument.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = select(func.count(GeneratedDocument.id)).where(*filters)
        result = await self._session.execute(stmt)
        total = int((await self._session.execute(count_stmt)).scalar_one())
        return list(result.all()), total

    async def delete(self, item: GeneratedDocument) -> None:
        await self._session.delete(item)
        await self._session.flush()


__all__ = ["GeneratedDocumentRepository"]
