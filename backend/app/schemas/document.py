"""Pydantic schemas for the Document Management module."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus, ExtractionMethod


class DocumentResponse(BaseModel):
    """Public representation of a stored document."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    stored_filename: str
    file_path: str
    mime_type: str
    file_size: int = Field(description="File size in bytes")
    upload_date: datetime
    status: DocumentStatus
    page_count: int | None = Field(
        default=None,
        description="Number of pages detected during text extraction",
    )
    extraction_method: ExtractionMethod | None = Field(
        default=None,
        description="Engine used to extract text (pdf_parser or paddle_ocr)",
    )


class DocumentListResponse(BaseModel):
    """Paginated-style list wrapper for documents."""

    items: list[DocumentResponse]
    total: int
