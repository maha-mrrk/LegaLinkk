"""RetrievalNode — graph wrapper around the retrieval service."""

from __future__ import annotations

from uuid import UUID

from app.agents.base_agent import BaseGraphAgent
from app.agents.nodes._state_utils import ensure_metadata
from app.core.logging import get_logger
from app.services.retrieval import RetrievalService
from app.state.graph_state import GraphState

logger = get_logger(__name__)


class RetrievalNode(BaseGraphAgent):
    """Retrieve Top-K chunks by delegating to ``RetrievalService``.

    Orchestration only: query embedding and vector search stay in the
    injected service.
    """

    def __init__(self, retrieval_service: RetrievalService) -> None:
        self._retrieval = retrieval_service

    @property
    def name(self) -> str:
        return "retrieval"

    @property
    def description(self) -> str:
        return "Retrieve relevant chunks for a question via the retrieval service."

    async def execute(self, state: GraphState) -> GraphState:
        question = state.get("user_question") or ""
        metadata = ensure_metadata(state)
        top_k = metadata.get("top_k")
        raw_document_id = state.get("document_id")
        document_id = UUID(str(raw_document_id)) if raw_document_id else None

        logger.info("RetrievalNode: retrieving for question_len=%s", len(question))
        result = await self._retrieval.retrieve(
            question,
            top_k=top_k,
            document_id=document_id,
        )

        state["retrieved_chunks"] = result["results"]
        metadata["top_k"] = result["top_k"]
        return state
