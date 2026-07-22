"""IndexingNode — graph wrapper around the indexing service."""

from __future__ import annotations

from app.agents.base_agent import BaseGraphAgent
from app.agents.nodes._state_utils import ensure_metadata, require_document_id
from app.core.logging import get_logger
from app.services.indexing import IndexingService
from app.state.graph_state import GraphState

logger = get_logger(__name__)


class IndexingNode(BaseGraphAgent):
    """Persist chunk embeddings by delegating to ``IndexingService``.

    Orchestration only: indexing logic (embedding + pgvector persistence)
    stays inside the injected service, which remains the source of truth.
    """

    def __init__(self, indexing_service: IndexingService) -> None:
        self._indexing = indexing_service

    @property
    def name(self) -> str:
        return "indexing"

    @property
    def description(self) -> str:
        return "Index a processed document into pgvector via the indexing service."

    async def execute(self, state: GraphState) -> GraphState:
        document_id = require_document_id(state)
        precomputed = self._collect_precomputed(state)
        logger.info(
            "IndexingNode: indexing document_id=%s (reuse_embeddings=%s)",
            document_id,
            bool(precomputed),
        )
        document = await self._indexing.index_document(
            document_id, precomputed_embeddings=precomputed
        )

        metadata = ensure_metadata(state)
        metadata["index_status"] = (
            document.index_status.value
            if getattr(document.index_status, "value", None)
            else str(document.index_status)
        )
        metadata["indexed_chunk_count"] = document.indexed_chunk_count
        metadata["embedding_model"] = document.embedding_model
        return state

    @staticmethod
    def _collect_precomputed(state: GraphState) -> dict[int, list[float]] | None:
        """Map already-computed embeddings (from EmbeddingNode) to chunk indices.

        The vectors reference the exact same chunk texts, so reusing them yields
        identical results while avoiding a duplicate embedding pass. Returns None
        unless every chunk has a matching vector and index.
        """
        chunks = state.get("chunks") or []
        embeddings = state.get("embeddings") or []
        if not embeddings or len(embeddings) != len(chunks):
            return None

        precomputed: dict[int, list[float]] = {}
        for chunk, vector in zip(chunks, embeddings, strict=True):
            index = chunk.get("chunk_index")
            if index is None:
                return None
            precomputed[int(index)] = vector
        return precomputed or None
