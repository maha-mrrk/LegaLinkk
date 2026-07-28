"""API contracts for the generated PDF library."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.generated_document import GeneratedDocumentKind


class GeneratedDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_document_id: UUID | None
    source_document_filename: str | None = None
    title: str
    original_filename: str
    file_size: int
    mime_type: str
    kind: GeneratedDocumentKind
    question: str | None
    created_at: datetime


class GeneratedDocumentListResponse(BaseModel):
    items: list[GeneratedDocumentResponse]
    total: int


__all__ = ["GeneratedDocumentListResponse", "GeneratedDocumentResponse"]
