"""ChunkingNode — graph wrapper around the semantic chunker service."""

from __future__ import annotations

import asyncio

from app.agents.base_agent import BaseGraphAgent
from app.agents.nodes._state_utils import ensure_metadata, require_document_id
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.chunker import SemanticChunker
from app.state.graph_state import GraphState

logger = get_logger(__name__)


class ChunkingNode(BaseGraphAgent):
    """Split cleaned text into chunks by delegating to ``SemanticChunker``.

    Orchestration only: chunking logic lives in the injected chunker service.
    """

    def __init__(
        self,
        chunker: SemanticChunker | None = None,
        settings: Settings | None = None,
    ) -> None:
        settings = settings or get_settings()
        self._chunker = chunker or SemanticChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    @property
    def name(self) -> str:
        return "chunking"

    @property
    def description(self) -> str:
        return "Split cleaned text into semantic chunks via the chunker service."

    async def execute(self, state: GraphState) -> GraphState:
        document_id = require_document_id(state)
        text = state.get("cleaned_text") or state.get("extracted_text") or ""
        metadata = ensure_metadata(state)

        logger.info("ChunkingNode: chunking document_id=%s", document_id)
        drafts = await asyncio.to_thread(
            lambda: self._chunker.chunk_document(
                document_id=document_id,
                text=text,
                pages=metadata.get("pages"),
                extraction_method=metadata.get("extraction_method"),
            )
        )

        state["chunks"] = [
            {
                "chunk_index": draft.chunk_index,
                "text": draft.text,
                "page_numbers": draft.page_numbers,
                "metadata": draft.metadata,
            }
            for draft in drafts
        ]
        return state
