"""EmbeddingNode — graph wrapper around the embedding service."""

from __future__ import annotations

import asyncio

from app.agents.base_agent import BaseGraphAgent
from app.agents.nodes._state_utils import ensure_metadata
from app.core.logging import get_logger
from app.services.embedding import EmbeddingService, get_embedding_service
from app.state.graph_state import GraphState

logger = get_logger(__name__)


class EmbeddingNode(BaseGraphAgent):
    """Generate dense vectors by delegating to ``EmbeddingService``.

    Orchestration only: embedding logic lives in the injected service.
    """

    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self._embeddings = embedding_service or get_embedding_service()

    @property
    def name(self) -> str:
        return "embedding"

    @property
    def description(self) -> str:
        return "Generate dense embeddings for chunks via the embedding service."

    async def execute(self, state: GraphState) -> GraphState:
        chunks = state.get("chunks") or []
        texts = [chunk.get("text", "") for chunk in chunks]

        logger.info("EmbeddingNode: embedding %s chunks", len(texts))
        vectors = await asyncio.to_thread(self._embeddings.embed_batch, texts)

        state["embeddings"] = vectors
        metadata = ensure_metadata(state)
        if texts:
            metadata["embedding_model"] = self._embeddings.model_name
        return state
