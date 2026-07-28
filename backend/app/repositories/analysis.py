"""Data-access layer for persisted contract analyses."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import AnalysisStatus, DocumentAnalysis
from app.models.document import Document


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

    async def list_completed_payloads(
        self,
        document_ids: list[UUID],
        *,
        user_id: UUID,
    ) -> dict[UUID, dict]:
        """Return stored analyses for owned documents without triggering generation."""
        if not document_ids:
            return {}
        result = await self._session.execute(
            select(DocumentAnalysis.document_id, DocumentAnalysis.payload)
            .join(Document, Document.id == DocumentAnalysis.document_id)
            .where(
                Document.user_id == user_id,
                DocumentAnalysis.document_id.in_(document_ids),
                DocumentAnalysis.status == AnalysisStatus.COMPLETED,
            )
        )
        return {
            document_id: dict(payload or {})
            for document_id, payload in result.all()
        }

    async def create(self, analysis: DocumentAnalysis) -> DocumentAnalysis:
        self._session.add(analysis)
        await self._session.flush()
        return analysis
