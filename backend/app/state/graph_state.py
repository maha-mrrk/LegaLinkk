"""Strongly-typed state shared across (future) LangGraph workflow nodes.

This is a pure data contract used to pass information between graph nodes
(document ingestion → cleaning → chunking → indexing → retrieval → rerank →
generation). It intentionally contains **no business logic**; existing services
(ChunkingService, EmbeddingService, RetrievalService, GeneratorService, ...)
remain the single source of truth for behavior.

``total=False`` so nodes can populate the state incrementally: each node reads
the fields it needs and writes back only the fields it produces.
"""

from __future__ import annotations

from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    """Shared state object flowing through the LangGraph pipeline.

    Fields mirror the existing RAG pipeline stages so future graph nodes can be
    mapped 1:1 onto current services without changing any behavior.
    """

    # --- Document ingestion -------------------------------------------------
    document_id: str | None
    filename: str | None
    extracted_text: str | None
    cleaned_text: str | None

    # --- Preprocessing / indexing ------------------------------------------
    chunks: list[dict[str, Any]]
    embeddings: list[list[float]]

    # --- Retrieval / reranking ---------------------------------------------
    retrieved_chunks: list[dict[str, Any]]
    reranked_chunks: list[dict[str, Any]]

    # --- Question answering -------------------------------------------------
    user_question: str | None
    llm_response: str | None

    # --- Cross-cutting ------------------------------------------------------
    metadata: dict[str, Any]
    errors: list[str]
