"""Shared skeleton for the specialized domain-agent graph nodes.

Legal / Finance / Compliance nodes are thin wrappers: each one runs the shared
``GeneratorService`` RAG pipeline with its own specialized system prompt and
stores a structured result on the state. No business logic lives here — the
retrieval / rerank / generation logic stays in the injected service (the single
source of truth).
"""

from __future__ import annotations

from typing import Any, Sequence

from app.agents.base_agent import BaseGraphAgent
from app.agents.nodes._state_utils import ensure_metadata
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.services.generator import GeneratorService
from app.state.graph_state import GraphState

logger = get_logger(__name__)


class DomainAgentNode(BaseGraphAgent):
    """Base node running one specialized RAG analysis via ``GeneratorService``.

    Subclasses only declare identity (agent/node names, domain), the state field
    to write, and the specialized system prompt. Behaviour is identical across
    the three agents, which keeps them true "thin wrappers".
    """

    #: Public agent id surfaced in the API (e.g. ``"LegalAgent"``).
    _agent_name: str
    #: Stable graph-node id (e.g. ``"legal"``).
    _node_name: str
    #: Intent domain (``"legal"`` | ``"finance"`` | ``"compliance"``).
    _domain: str
    #: GraphState key this node writes (e.g. ``"legal_result"``).
    _result_key: str
    #: Specialized system prompt injected into the shared RAG pipeline.
    _system_prompt: str

    def __init__(self, generator_service: GeneratorService) -> None:
        self._generator = generator_service

    @property
    def name(self) -> str:
        return self._node_name

    @property
    def description(self) -> str:
        return f"{self._agent_name}: specialized {self._domain} analysis over RAG."

    async def execute(self, state: GraphState) -> GraphState:
        question = (state.get("user_query") or state.get("user_question") or "").strip()
        metadata = ensure_metadata(state)
        history: Sequence[dict[str, str]] | None = metadata.get("history")

        logger.info("[multi_agent] node=%s analysing", self._node_name)
        try:
            rag: dict[str, Any] = await self._generator.answer_question(
                question,
                top_k=metadata.get("top_k"),
                final_k=metadata.get("final_k"),
                temperature=metadata.get("temperature"),
                max_tokens=metadata.get("max_tokens"),
                history=history,
                document_id=metadata.get("document_id"),
                system_prompt=self._system_prompt,
            )
            state[self._result_key] = {
                "agent": self._agent_name,
                "domain": self._domain,
                "status": "ok",
                "answer": rag.get("answer"),
                "sources": list(rag.get("sources") or []),
                "metadata": dict(rag.get("metadata") or {}),
            }
            logger.info("[multi_agent] node=%s ok", self._node_name)
        except Exception as exc:  # graceful degradation: never break the graph
            logger.exception("[multi_agent] node=%s failed", self._node_name)
            message = (
                exc.message
                if isinstance(exc, AppError)
                else "L'analyse spécialisée a échoué. Veuillez réessayer."
            )
            state[self._result_key] = {
                "agent": self._agent_name,
                "domain": self._domain,
                "status": "error",
                "answer": None,
                "sources": [],
                "metadata": {"error_type": type(exc).__name__},
                "message": message,
            }
        return state
