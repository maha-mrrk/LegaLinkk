"""RAG question-answering workflow assembled with LangGraph.

Wires the existing query-time **nodes** into a sequential ``StateGraph``::

    User question
        ↓
    EmbeddingNode
        ↓
    RetrievalNode
        ↓
    RerankerNode
        ↓
    GeneratorNode
        ↓
      Answer

Orchestration only — every step delegates to an existing node/service (the
single source of truth). No business logic and no duplicated logic live here,
and ``GeneratorService`` is used unchanged.

Notes
-----
* ``RetrievalNode`` embeds the *query* internally (via ``RetrievalService``),
  which is the single source of truth for query embedding. ``EmbeddingNode`` is
  kept in the chain per the workflow spec; in a pure Q&A run (no chunks on the
  state) it is a harmless pass-through, so no embedding work is duplicated.
* The graph is deliberately built as a plain ``StateGraph`` so future work can
  add **branching** (``add_conditional_edges``) and **multi-agent
  orchestration** (extra nodes / sub-graphs) without touching the nodes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langgraph.graph import END, StateGraph

from app.agents.base_agent import BaseGraphAgent
from app.agents.nodes import (
    EmbeddingNode,
    GeneratorNode,
    RerankerNode,
    RetrievalNode,
)
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.graphs.retry import transient_retry_policy
from app.services.generator import GeneratorService
from app.services.langfuse_service import LangfuseService, get_langfuse_service
from app.services.reranker import RerankerService
from app.services.retrieval import RetrievalService
from app.state.graph_state import GraphState

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

_WORKFLOW = "rag"


async def _run_node(
    node: BaseGraphAgent,
    state: GraphState,
    *,
    langfuse: LangfuseService,
    parent: Any | None = None,
) -> GraphState:
    """Execute a node with uniform start/end logging + optional Langfuse trace.

    All observability goes through ``LangfuseService`` (a no-op when disabled),
    so the node itself runs unchanged. When ``parent`` is set, the node span is
    nested under the workflow trace.
    """
    logger.info("[rag] node=%s start", node.name)
    result = await langfuse.trace_node(
        node, state, workflow=_WORKFLOW, parent=parent
    )
    logger.info("[rag] node=%s done", node.name)
    return result


def build_rag_graph(
    *,
    session: "AsyncSession",
    settings: Settings | None = None,
    langfuse: LangfuseService | None = None,
    trace: Any | None = None,
):
    """Compile the LangGraph RAG pipeline.

    Dependencies are injected: each node wraps an existing service built from
    the given session/settings. Nodes execute sequentially and the shared
    ``GraphState`` is propagated from one to the next. Tracing is delegated to
    ``langfuse`` (the shared, optional ``LangfuseService``); ``trace`` is an
    optional parent span handle so every node groups under one workflow trace.
    """
    settings = settings or get_settings()
    langfuse = langfuse or get_langfuse_service()

    embedding_node = EmbeddingNode()
    retrieval_node = RetrievalNode(RetrievalService(session, settings=settings))
    reranker_node = RerankerNode(RerankerService(session, settings=settings))
    generator_node = GeneratorNode(GeneratorService(session, settings=settings))

    retry = transient_retry_policy(3)

    async def embedding_step(state: GraphState) -> GraphState:
        return await _run_node(embedding_node, state, langfuse=langfuse, parent=trace)

    async def retrieval_step(state: GraphState) -> GraphState:
        return await _run_node(retrieval_node, state, langfuse=langfuse, parent=trace)

    async def reranker_step(state: GraphState) -> GraphState:
        return await _run_node(reranker_node, state, langfuse=langfuse, parent=trace)

    async def generator_step(state: GraphState) -> GraphState:
        return await _run_node(generator_node, state, langfuse=langfuse, parent=trace)

    builder = StateGraph(GraphState)
    builder.add_node("embedding", embedding_step, retry=retry)
    builder.add_node("retrieval", retrieval_step, retry=retry)
    builder.add_node("reranker", reranker_step, retry=retry)
    builder.add_node("generator", generator_step, retry=retry)

    builder.set_entry_point("embedding")
    builder.add_edge("embedding", "retrieval")
    builder.add_edge("retrieval", "reranker")
    builder.add_edge("reranker", "generator")
    builder.add_edge("generator", END)

    return builder.compile()
