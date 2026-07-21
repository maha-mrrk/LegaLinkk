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
        logger.info("IndexingNode: indexing document_id=%s", document_id)
        document = await self._indexing.index_document(document_id)

        metadata = ensure_metadata(state)
        metadata["index_status"] = (
            document.index_status.value
            if getattr(document.index_status, "value", None)
            else str(document.index_status)
        )
        metadata["indexed_chunk_count"] = document.indexed_chunk_count
        metadata["embedding_model"] = document.embedding_model
        return state
