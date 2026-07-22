"""Pydantic schemas for the Document Management module."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus, ExtractionMethod
from app.models.embedding import IndexStatus


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
    index_status: IndexStatus = IndexStatus.NOT_INDEXED
    indexed_at: datetime | None = None
    indexed_chunk_count: int | None = None
    embedding_model: str | None = None


class DocumentListResponse(BaseModel):
    """Paginated-style list wrapper for documents."""

    items: list[DocumentResponse]
    total: int


class DocumentStatusResponse(BaseModel):
    """Processing lifecycle status for a document."""

    document_id: UUID
    status: DocumentStatus = Field(
        description="uploaded | processing | processed | failed"
    )
    page_count: int | None = None
    extraction_method: ExtractionMethod | None = None
    chunk_count: int = 0


class DocumentUploadResponse(BaseModel):
    """Immediate response after an upload — processing runs in the background."""

    document_id: UUID
    task_id: str | None = Field(
        default=None,
        description="Background task id (null if the task could not be queued)",
    )
    status: DocumentStatus = Field(description="Initial document status")
    filename: str
    message: str = "Upload received. Processing has started."


class ProgressTimelineEntry(BaseModel):
    """A single stage transition in the ingestion timeline."""

    stage: str
    label: str
    at: str


class DocumentProgressResponse(BaseModel):
    """Live, human-friendly progress of a document's ingestion pipeline."""

    document_id: UUID
    task_id: str | None = None
    status: str = Field(
        description="queued | processing | completed | failed | unknown"
    )
    stage: str | None = None
    stage_label: str | None = None
    progress: int = Field(default=0, ge=0, le=100)
    remaining: int = Field(
        default=100, ge=0, le=100, description="Approximate work remaining (%)"
    )
    message: str | None = None
    error: str | None = None
    completed: bool = False
    updated_at: str | None = None
    timeline: list[ProgressTimelineEntry] = Field(default_factory=list)


class ChunkMetadata(BaseModel):
    """Structured metadata stored alongside each chunk."""

    document_id: str
    chunk_index: int
    page_numbers: list[int] = Field(default_factory=list)
    chunk_length: int
    extraction_method: str | None = None
    created_at: str


class DocumentChunkResponse(BaseModel):
    """Public representation of a document chunk."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    chunk_index: int
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def from_chunk(cls, chunk: Any) -> "DocumentChunkResponse":
        """Map ORM ``metadata_`` attribute onto the public ``metadata`` field."""
        return cls(
            id=chunk.id,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            metadata=dict(chunk.metadata_ or {}),
            created_at=chunk.created_at,
        )


class DocumentChunkListResponse(BaseModel):
    """List wrapper for document chunks."""

    document_id: UUID
    items: list[DocumentChunkResponse]
    total: int


class DocumentIndexStatusResponse(BaseModel):
    """Semantic indexing status for a document."""

    document_id: UUID
    index_status: IndexStatus
    chunk_count: int = 0
    indexed_count: int = 0
    embedding_model: str | None = None
    indexed_at: datetime | None = None


class DocumentIndexResponse(BaseModel):
    """Result of an index / delete-index operation."""

    document_id: UUID
    index_status: IndexStatus
    indexed_count: int = 0
    embedding_model: str | None = None
    indexed_at: datetime | None = None
    message: str


class DocumentReindexResponse(BaseModel):
    """Result of re-indexing every processed document."""

    total: int
    succeeded: int
    failed: int
    succeeded_ids: list[UUID] = Field(default_factory=list)
    failed_ids: list[UUID] = Field(default_factory=list)
    message: str
