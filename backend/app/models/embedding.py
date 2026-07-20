"""SQLAlchemy model for document chunk embeddings stored in pgvector."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.chunk import DocumentChunk
    from app.models.document import Document


class IndexStatus(str, enum.Enum):
    """Semantic index lifecycle for a document."""

    NOT_INDEXED = "not_indexed"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"


class DocumentEmbedding(Base):
    """Vector embedding for one document chunk (PostgreSQL + pgvector).

    Core fields required for indexing: id, document_id, chunk_id, embedding,
    embedding_model, created_at. Extra denormalized metadata supports future
    Top-K retrieval / RAG without joining chunks.
    """

    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        UniqueConstraint("chunk_id", name="uq_chunk_embeddings_chunk_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    page_numbers: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    extraction_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    upload_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # Text kept for future RAG context assembly without joining chunks.
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    # Dimension must match Settings.embedding_dimension (bge-m3 / e5-large = 1024).
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    document: Mapped["Document"] = relationship("Document", back_populates="embeddings")
    chunk: Mapped["DocumentChunk"] = relationship("DocumentChunk")

    def __repr__(self) -> str:
        return (
            f"<DocumentEmbedding id={self.id} document_id={self.document_id} "
            f"chunk_id={self.chunk_id} model={self.embedding_model!r}>"
        )


# Backward-compatible alias (previous name).
ChunkEmbedding = DocumentEmbedding
