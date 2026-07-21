"""ParserNode — graph wrapper around the digital PDF parser service."""

from __future__ import annotations

import asyncio

from app.agents.base_agent import BaseGraphAgent
from app.agents.nodes._state_utils import ensure_metadata, source_path
from app.core.logging import get_logger
from app.parsers import DocumentParser
from app.parsers.pdf_parser import PdfParser
from app.state.graph_state import GraphState

logger = get_logger(__name__)


class ParserNode(BaseGraphAgent):
    """Extract digital text from a PDF by delegating to ``DocumentParser``.

    Orchestration only: the parsing logic lives entirely in the injected
    ``DocumentParser`` service (``PdfParser`` by default).
    """

    def __init__(self, parser: DocumentParser | None = None) -> None:
        self._parser = parser or PdfParser()

    @property
    def name(self) -> str:
        return "parser"

    @property
    def description(self) -> str:
        return "Extract digital text from a PDF via the PdfParser service."

    async def execute(self, state: GraphState) -> GraphState:
        file_path = source_path(state)
        if not file_path:
            raise ValueError("ParserNode requires metadata['file_path'] or filename")

        logger.info("ParserNode: extracting text from %s", file_path)
        result = await asyncio.to_thread(self._parser.extract, file_path)

        state["extracted_text"] = result.text
        metadata = ensure_metadata(state)
        metadata["page_count"] = result.page_count
        metadata["extraction_method"] = result.extraction_method or "pdf_parser"
        metadata["pages"] = [(page.page_number, page.text) for page in result.pages]
        return state
