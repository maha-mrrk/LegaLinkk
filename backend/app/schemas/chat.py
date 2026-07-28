"""Pydantic schemas for grounded RAG chat/query."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.generated_document import GeneratedDocumentKind


class ChatQueryRequest(BaseModel):
    """Full RAG pipeline request: retrieve → rerank → generate."""

    question: str = Field(..., min_length=1, description="User question")
    document_id: UUID | None = Field(
        default=None,
        description=(
            "Scope retrieval to a single document. When omitted, answers are "
            "grounded on the entire document library."
        ),
    )
    top_k: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Vector retrieval candidate pool (default RETRIEVAL_CANDIDATE_K)",
    )
    final_k: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Chunks kept after reranking (default RERANKER_FINAL_K)",
    )
    # Keep low for grounded RAG; high temperature produces gibberish.
    temperature: float | None = Field(default=None, ge=0.0, le=1.0)
    max_tokens: int | None = Field(
        default=None,
        ge=64,
        le=8192,
        description="Completion budget (default LLM_MAX_TOKENS, typically 1024)",
    )


class ChatJobCreateRequest(ChatQueryRequest):
    """Start a reconnectable background chat or specialist-agent generation."""

    mode: Literal["chat", "agent"] = "chat"


class ChatJobCreateResponse(BaseModel):
    """Immediate acknowledgment for a Redis-backed background generation."""

    job_id: UUID
    status: Literal["queued"]


class ChatJobStatusResponse(BaseModel):
    """Current durable status used when restoring the Consultation page."""

    job_id: UUID
    mode: Literal["chat", "agent"]
    status: Literal["queued", "processing", "completed", "failed"]
    event_count: int


class ChatSource(BaseModel):
    """Citation for a grounded answer."""

    document_id: UUID
    filename: str
    page: int | None = None
    chunk_id: UUID
    score: float
    page_numbers: list[int] = Field(default_factory=list)


class ChatMetadata(BaseModel):
    """Generation metadata for observability and future agents."""

    provider: str | None = None
    model: str | None = None
    tokens_used: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    generation_time: float | None = None
    context_chunks: int | None = None
    top_k: int | None = None
    final_k: int | None = None
    history_turns: int | None = None
    conversation_id: str | None = None


class ChatQueryResponse(BaseModel):
    """Grounded answer with sources."""

    answer: str
    sources: list[ChatSource]
    metadata: ChatMetadata


class ChatDocumentResponse(BaseModel):
    """Grounded, self-contained HTML document (printable to PDF) with sources."""

    html: str
    generated_document_id: UUID
    sources: list[ChatSource]
    metadata: ChatMetadata


class ChatDocumentPdfRequest(BaseModel):
    """Convert an already-generated HTML document to a downloadable PDF."""

    html: str = Field(..., min_length=1, description="Self-contained HTML document")
    filename: str | None = Field(
        default=None,
        max_length=200,
        description="Suggested download filename (without path).",
    )
    title: str | None = Field(default=None, max_length=255)
    source_document_id: UUID | None = None
    kind: GeneratedDocumentKind = GeneratedDocumentKind.CHAT_REPORT
    question: str | None = Field(default=None, max_length=10_000)
