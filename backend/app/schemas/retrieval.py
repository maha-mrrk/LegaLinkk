"""Pydantic schemas for semantic retrieval."""

from uuid import UUID

from pydantic import BaseModel, Field


class RetrieveRequest(BaseModel):
    """Request body for Top-K cosine similarity search."""

    query: str = Field(..., min_length=1, description="Natural-language search query")
    top_k: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Number of chunks to return (default from RETRIEVAL_TOP_K)",
    )


class RetrievedChunk(BaseModel):
    """One retrieved chunk with cosine similarity score."""

    chunk_id: UUID
    document_id: UUID
    filename: str
    text: str
    similarity: float = Field(description="Cosine similarity in [~0, 1] (higher is better)")
    page_numbers: list[int] = Field(default_factory=list)
    extraction_method: str | None = None
    chunk_index: int | None = None
    embedding_model: str | None = None


class RetrieveResponse(BaseModel):
    """Top-K retrieval result wrapper."""

    query: str
    top_k: int
    results: list[RetrievedChunk]


class RerankRequest(BaseModel):
    """Retrieve candidates then CrossEncoder-rerank for RAG."""

    query: str = Field(..., min_length=1, description="Natural-language search query")
    top_k: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Candidate pool from vector search (default RETRIEVAL_CANDIDATE_K)",
    )
    final_k: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Chunks kept after reranking (default RERANKER_FINAL_K)",
    )


class RerankedChunk(BaseModel):
    """Reranked chunk consumable by a future GeneratorService."""

    chunk_id: UUID
    document_id: UUID
    filename: str
    text: str
    retrieval_score: float = Field(description="Original pgvector cosine similarity")
    reranker_score: float = Field(description="CrossEncoder relevance score")
    page_numbers: list[int] = Field(default_factory=list)
    extraction_method: str | None = None
    chunk_index: int | None = None
    embedding_model: str | None = None
    rank: int = Field(description="1-based rank after reranking")


class RerankResponse(BaseModel):
    """Reranked Top-K result wrapper."""

    query: str
    top_k: int
    final_k: int
    reranker_model: str | None = None
    results: list[RerankedChunk]
