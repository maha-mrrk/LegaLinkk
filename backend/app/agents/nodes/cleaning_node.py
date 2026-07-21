"""CleaningNode — graph wrapper around the text-cleaning service."""

from __future__ import annotations

import asyncio
from typing import Callable

from app.agents.base_agent import BaseGraphAgent
from app.agents.nodes._state_utils import ensure_metadata
from app.core.logging import get_logger
from app.services.text_cleaner import clean_pages, clean_text
from app.state.graph_state import GraphState

logger = get_logger(__name__)

CleanTextFn = Callable[[str], str]
CleanPagesFn = Callable[[list[tuple[int, str]]], list[tuple[int, str]]]


class CleaningNode(BaseGraphAgent):
    """Normalize extracted text by delegating to ``text_cleaner``.

    Orchestration only: cleaning logic stays in the injected callables
    (``clean_text`` / ``clean_pages`` by default).
    """

    def __init__(
        self,
        clean_text_fn: CleanTextFn = clean_text,
        clean_pages_fn: CleanPagesFn = clean_pages,
    ) -> None:
        self._clean_text = clean_text_fn
        self._clean_pages = clean_pages_fn

    @property
    def name(self) -> str:
        return "cleaning"

    @property
    def description(self) -> str:
        return "Normalize extracted document text via the text_cleaner service."

    async def execute(self, state: GraphState) -> GraphState:
        text = state.get("extracted_text") or ""
        logger.info("CleaningNode: cleaning %s characters", len(text))
        state["cleaned_text"] = await asyncio.to_thread(self._clean_text, text)

        metadata = ensure_metadata(state)
        pages = metadata.get("pages")
        if pages:
            metadata["pages"] = await asyncio.to_thread(self._clean_pages, pages)
        return state
