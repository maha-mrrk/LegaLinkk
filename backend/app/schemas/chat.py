"""Pydantic schemas for grounded RAG chat/query."""

from uuid import UUID

from pydantic import BaseModel, Field


class ChatQueryRequest(BaseModel):
    """Full RAG pipeline request: retrieve → rerank → generate."""

    question: str = Field(..., min_length=1, description="User question")
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


class ChatQueryResponse(BaseModel):
    """Grounded answer with sources."""

    answer: str
    sources: list[ChatSource]
    metadata: ChatMetadata
