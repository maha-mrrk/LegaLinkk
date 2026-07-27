"""Data-access layer for persisted contract analyses."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import DocumentAnalysis


class DocumentAnalysisRepository:
    """Persistence operations for one analysis per document."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_document_id(
        self, document_id: UUID
    ) -> DocumentAnalysis | None:
        result = await self._session.execute(
            select(DocumentAnalysis).where(
                DocumentAnalysis.document_id == document_id
            )
        )
        return result.scalar_one_or_none()

    async def create(self, analysis: DocumentAnalysis) -> DocumentAnalysis:
        self._session.add(analysis)
        await self._session.flush()
        return analysis
