"""Persisted contract-analysis ORM model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# Increment this value when the analysis prompt, output schema, or risk rules
# change. Older rows are then recomputed automatically on their next access.
ANALYSIS_VERSION = "1"


class AnalysisStatus(str, enum.Enum):
    """Lifecycle of a persisted contract analysis."""

    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentAnalysis(Base):
    """Latest structured legal analysis for one document."""

    __tablename__ = "document_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(
            AnalysisStatus,
            name="analysis_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=AnalysisStatus.PROCESSING,
        server_default=AnalysisStatus.PROCESSING.value,
    )
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    analysis_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ANALYSIS_VERSION,
        server_default=ANALYSIS_VERSION,
    )
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
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


__all__ = ["ANALYSIS_VERSION", "AnalysisStatus", "DocumentAnalysis"]
