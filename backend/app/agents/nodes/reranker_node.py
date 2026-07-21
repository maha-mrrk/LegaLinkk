"""RerankerNode — graph wrapper around the reranker service."""

from __future__ import annotations

import asyncio
from dataclasses import asdict

from app.agents.base_agent import BaseGraphAgent
from app.agents.nodes._state_utils import ensure_metadata
from app.core.logging import get_logger
from app.repositories.retrieval import RetrievalHit
from app.services.reranker import RerankerService
from app.state.graph_state import GraphState

logger = get_logger(__name__)


class RerankerNode(BaseGraphAgent):
    """Rerank retrieved chunks by delegating to ``RerankerService``.

    Orchestration only: CrossEncoder scoring and ordering stay in the
    injected service. The node maps ``retrieved_chunks`` into the service's
    hit type and stores the reranked results back on the state.
    """

    def __init__(self, reranker_service: RerankerService) -> None:
        self._reranker = reranker_service

    @property
    def name(self) -> str:
        return "reranker"

    @property
    def description(self) -> str:
        return "Rerank retrieved chunks with a CrossEncoder via the reranker service."

    async def execute(self, state: GraphState) -> GraphState:
        question = state.get("user_question") or ""
        retrieved = state.get("retrieved_chunks") or []
        metadata = ensure_metadata(state)
        final_k = metadata.get("final_k") or len(retrieved)

        if not retrieved:
            state["reranked_chunks"] = []
            return state

        hits = [
            RetrievalHit(
                chunk_id=item["chunk_id"],
                document_id=item["document_id"],
                filename=item["filename"],
                text=item["text"],
                similarity=item["similarity"],
                page_numbers=list(item.get("page_numbers") or []),
                extraction_method=item.get("extraction_method"),
                chunk_index=item["chunk_index"],
                embedding_model=item["embedding_model"],
            )
            for item in retrieved
        ]

        logger.info("RerankerNode: reranking %s hits", len(hits))
        ranked = await asyncio.to_thread(
            self._reranker.rerank_hits, question, hits, final_k=final_k
        )

        state["reranked_chunks"] = [asdict(hit) for hit in ranked]
        metadata["final_k"] = final_k
        metadata["reranker_model"] = self._reranker.model_name
        return state
