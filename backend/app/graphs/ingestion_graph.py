"""Document ingestion workflow assembled with LangGraph.

This module wires the existing ingestion **nodes** into a ``StateGraph``::

    Upload PDF
        ↓
    ParserNode ──(scanned?)──► OCRNode
        ↓                         ↓
        └────────► CleaningNode ◄─┘
                        ↓
                   ChunkingNode
                        ↓
                   EmbeddingNode
                        ↓
                   (persist chunks)
                        ↓
                   IndexingNode
                        ↓
                      Ready

The graph is **orchestration only**: every step delegates to an existing
node/service (the single source of truth). No business logic lives here.

Design notes
------------
* **Success path** — parser → (ocr) → cleaning → chunking → embedding →
  persist → indexing → END.
* **Error handling** — a digital-parse failure falls back to OCR; an indexing
  failure is tolerated (the document stays *processed*); any other failure
  propagates so the caller can mark the document *failed*.
* **Retries** — I/O / model heavy steps use a LangGraph ``RetryPolicy``.
* **Logging** — every node logs start/end and failures.

The digital-vs-scanned decision and the chunk persistence both reuse existing
collaborators (``ExtractionPipeline.is_scanned_pdf`` and the
``DocumentProcessingService``), so the graph never re-implements them.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

from langgraph.graph import END, StateGraph

from app.agents.base_agent import BaseGraphAgent
from app.agents.nodes import (
    ChunkingNode,
    CleaningNode,
    EmbeddingNode,
    IndexingNode,
    OCRNode,
    ParserNode,
)
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.graphs.retry import transient_retry_policy
from app.parsers import PdfParseError
from app.parsers.extraction_pipeline import ExtractionPipeline
from app.services.indexing import IndexingError, IndexingService
from app.services.langfuse_service import LangfuseService, get_langfuse_service
from app.state.graph_state import GraphState

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

_WORKFLOW = "ingestion"

# Optional hook fired when a stage starts, used to publish live progress.
# It is pure instrumentation — the workflow (nodes/edges) is unchanged.
StageCallback = Callable[[str], Awaitable[None]]


class ChunkPersister(Protocol):
    """Minimal contract the graph needs to persist chunks (reuses the service)."""

    async def finalize_chunks(
        self,
        document_id: UUID,
        *,
        cleaned_text: str,
        page_count: int,
        extraction_method: str | None,
        chunks: list[dict],
    ) -> object: ...


async def _emit(on_stage: StageCallback | None, stage: str) -> None:
    """Fire the progress hook, swallowing errors so it never breaks ingestion."""
    if on_stage is None:
        return
    try:
        await on_stage(stage)
    except Exception:  # pragma: no cover - progress is best-effort
        logger.debug("[ingestion] progress hook failed for stage=%s", stage, exc_info=True)


async def _run_node(
    node: BaseGraphAgent,
    state: GraphState,
    *,
    langfuse: LangfuseService,
    parent: Any | None = None,
    on_stage: StageCallback | None = None,
) -> GraphState:
    """Execute a node with uniform start/end logging + optional Langfuse trace.

    All observability goes through ``LangfuseService`` (a no-op when disabled),
    so the node itself runs unchanged. When ``parent`` is set, the node span is
    nested under the workflow trace. ``on_stage`` (also optional) publishes live
    progress the moment the stage starts.
    """
    logger.info("[ingestion] node=%s start", node.name)
    await _emit(on_stage, node.name)
    result = await langfuse.trace_node(
        node, state, workflow=_WORKFLOW, parent=parent
    )
    logger.info("[ingestion] node=%s done", node.name)
    return result


def build_ingestion_graph(
    *,
    session: "AsyncSession",
    settings: Settings | None = None,
    persister: ChunkPersister,
    langfuse: LangfuseService | None = None,
    trace: Any | None = None,
    on_stage: StageCallback | None = None,
):
    """Compile the LangGraph ingestion pipeline.

    Dependencies are injected: nodes are built from the given session/settings
    and chunk persistence is delegated to ``persister`` (the existing
    ``DocumentProcessingService``). Tracing is delegated to ``langfuse`` (the
    shared, optional ``LangfuseService``); ``trace`` is an optional parent span
    handle so every node groups under one workflow trace. ``on_stage`` is an
    optional progress hook fired as each stage starts (for live UI feedback).
    """
    settings = settings or get_settings()
    langfuse = langfuse or get_langfuse_service()

    parser_node = ParserNode()
    ocr_node = OCRNode(settings=settings)
    cleaning_node = CleaningNode()
    chunking_node = ChunkingNode(settings=settings)
    embedding_node = EmbeddingNode()
    indexing_node = IndexingNode(IndexingService(session, settings=settings))

    # Reused only for the digital-vs-scanned routing decision.
    router = ExtractionPipeline(settings=settings)

    retry = transient_retry_policy(3)

    async def parser_step(state: GraphState) -> GraphState:
        try:
            return await _run_node(
                parser_node, state, langfuse=langfuse, parent=trace, on_stage=on_stage
            )
        except PdfParseError as exc:
            # Digital parse failed → let the router send this to OCR.
            logger.warning("[ingestion] digital parse failed (%s) → OCR fallback", exc)
            state["extracted_text"] = ""
            metadata = state.get("metadata")
            if metadata is None:
                metadata = {}
                state["metadata"] = metadata
            metadata["page_count"] = 0
            metadata["parse_failed"] = True
            return state

    def route_after_parser(state: GraphState) -> str:
        metadata = state.get("metadata") or {}
        text = state.get("extracted_text") or ""
        page_count = int(metadata.get("page_count") or 0)
        if settings.ocr_enabled and router.is_scanned_pdf(text, page_count):
            logger.info("[ingestion] routing: parser → ocr (scanned/insufficient text)")
            return "ocr"
        logger.info("[ingestion] routing: parser → cleaning (digital text)")
        return "cleaning"

    async def ocr_step(state: GraphState) -> GraphState:
        return await _run_node(
            ocr_node, state, langfuse=langfuse, parent=trace, on_stage=on_stage
        )

    async def cleaning_step(state: GraphState) -> GraphState:
        return await _run_node(
            cleaning_node, state, langfuse=langfuse, parent=trace, on_stage=on_stage
        )

    async def chunking_step(state: GraphState) -> GraphState:
        return await _run_node(
            chunking_node, state, langfuse=langfuse, parent=trace, on_stage=on_stage
        )

    async def embedding_step(state: GraphState) -> GraphState:
        return await _run_node(
            embedding_node, state, langfuse=langfuse, parent=trace, on_stage=on_stage
        )

    async def persist_step(state: GraphState) -> GraphState:
        logger.info("[ingestion] node=persist start")
        await _emit(on_stage, "persist")
        metadata = state.get("metadata") or {}
        await persister.finalize_chunks(
            UUID(str(state["document_id"])),
            cleaned_text=state.get("cleaned_text") or "",
            page_count=int(metadata.get("page_count") or 0),
            extraction_method=metadata.get("extraction_method"),
            chunks=state.get("chunks") or [],
        )
        logger.info("[ingestion] node=persist done")
        return state

    def route_after_persist(state: GraphState) -> str:
        return "indexing" if settings.auto_index_on_process else "ready"

    async def indexing_step(state: GraphState) -> GraphState:
        try:
            return await _run_node(
                indexing_node, state, langfuse=langfuse, parent=trace, on_stage=on_stage
            )
        except IndexingError as exc:
            # Chunking succeeded; keep the document processed even if index fails.
            logger.exception("[ingestion] indexing failed — document stays processed")
            errors = state.get("errors")
            if errors is None:
                errors = []
                state["errors"] = errors
            errors.append(f"indexing_failed: {exc}")
            return state

    builder = StateGraph(GraphState)
    builder.add_node("parser", parser_step, retry=retry)
    builder.add_node("ocr", ocr_step, retry=retry)
    builder.add_node("cleaning", cleaning_step)
    builder.add_node("chunking", chunking_step)
    builder.add_node("embedding", embedding_step, retry=retry)
    builder.add_node("persist", persist_step, retry=retry)
    builder.add_node("indexing", indexing_step, retry=retry)

    builder.set_entry_point("parser")
    builder.add_conditional_edges(
        "parser",
        route_after_parser,
        {"ocr": "ocr", "cleaning": "cleaning"},
    )
    builder.add_edge("ocr", "cleaning")
    builder.add_edge("cleaning", "chunking")
    builder.add_edge("chunking", "embedding")
    builder.add_edge("embedding", "persist")
    builder.add_conditional_edges(
        "persist",
        route_after_persist,
        {"indexing": "indexing", "ready": END},
    )
    builder.add_edge("indexing", END)

    return builder.compile()
