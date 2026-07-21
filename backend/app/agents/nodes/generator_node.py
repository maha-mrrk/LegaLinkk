"""GeneratorNode — graph wrapper around the RAG generator service."""

from __future__ import annotations

from typing import Any, Sequence

from app.agents.base_agent import BaseGraphAgent
from app.agents.nodes._state_utils import ensure_metadata
from app.core.logging import get_logger
from app.services.generator import GeneratorService
from app.state.graph_state import GraphState

logger = get_logger(__name__)


class GeneratorNode(BaseGraphAgent):
    """Produce the final answer by delegating to ``GeneratorService``.

    Orchestration only: prompt building, LLM call and source shaping stay in
    the injected service. When ``reranked_chunks`` are already present on the
    state they are reused; otherwise the service runs its full RAG pipeline.
    """

    def __init__(self, generator_service: GeneratorService) -> None:
        self._generator = generator_service

    @property
    def name(self) -> str:
        return "generator"

    @property
    def description(self) -> str:
        return "Generate a grounded answer from context via the generator service."

    async def execute(self, state: GraphState) -> GraphState:
        question = state.get("user_question") or ""
        metadata = ensure_metadata(state)
        history: Sequence[dict[str, str]] | None = metadata.get("history")
        reranked = state.get("reranked_chunks")

        if reranked:
            logger.info("GeneratorNode: generating from %s reranked chunks", len(reranked))
            result: dict[str, Any] = await self._generator.generate_from_chunks(
                question,
                reranked,
                history=history,
            )
        else:
            logger.info("GeneratorNode: running full RAG pipeline")
            result = await self._generator.answer_question(
                question,
                top_k=metadata.get("top_k"),
                final_k=metadata.get("final_k"),
                history=history,
            )

        state["llm_response"] = result.get("answer")
        metadata["sources"] = result.get("sources", [])
        metadata["generation"] = result.get("metadata", {})
        return state
