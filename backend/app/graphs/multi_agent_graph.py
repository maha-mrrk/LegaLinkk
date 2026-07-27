"""Multi-agent orchestration workflow assembled with LangGraph.

Replaces the old hand-rolled ``AgentOrchestrator`` + ``IntentRouter`` with a
real ``StateGraph`` where every agent is a **node**::

                         CommandParserNode
                                │
              ┌─────────────────┼──────────────────┐
        target=legal      target=finance      target=compliance      target=None
              │                 │                   │                     │
          LegalNode         FinanceNode       ComplianceNode         LegalNode
              │                 │                   │                     │
             END               END                 END              FinanceNode
                                                                          │
                                                                    ComplianceNode
                                                                          │
                                                                    SynthesisNode
                                                                          │
                                                                         END

Routing is data-driven (conditional edges on ``target_agent``), never a Python
``if`` dispatch outside the graph:

* A leading ``/legal`` | ``/finance`` | ``/compliance`` command runs ONLY that
  agent node and returns its answer.
* No command → the three agents run **sequentially as chained nodes** and the
  ``SynthesisNode`` fans in from their three result fields to build one final
  recommendation.

Why sequential (not a parallel fan-out)? A request carries a single
``AsyncSession`` and SQLAlchemy sessions are not safe for concurrent use; the
three agents each hit the DB (retrieval), so running them one after another in
the graph is the correct, safe design. They remain **true graph nodes** with
real conditional edges — no external Python loop.

Orchestration only: each node delegates to the existing services (the single
source of truth). Retries reuse the shared ``transient_retry_policy`` and every
node is traced via the shared, optional ``LangfuseService``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langgraph.graph import END, StateGraph

from app.agents.base_agent import BaseGraphAgent
from app.agents.nodes import (
    CommandParserNode,
    ComplianceNode,
    FinanceNode,
    LegalNode,
    SynthesisNode,
)
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.graphs.retry import transient_retry_policy
from app.services.generator import GeneratorService
from app.services.langfuse_service import LangfuseService, get_langfuse_service
from app.state.graph_state import GraphState

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

_WORKFLOW = "multi_agent"


# --- routing predicates (module-level & pure so they are unit-testable) ------


def route_after_command(state: GraphState) -> str:
    """Enter the targeted agent, or the head of the default chain (legal)."""
    target = state.get("target_agent")
    if target == "finance":
        return "finance"
    if target == "compliance":
        return "compliance"
    # "legal" (single) or None (default chain starts at legal).
    return "legal"


def _next_or_end(state: GraphState, following: str) -> str:
    """Single-agent mode stops at the current node; default mode continues."""
    return "end" if state.get("target_agent") else following


def route_after_legal(state: GraphState) -> str:
    return _next_or_end(state, "finance")


def route_after_finance(state: GraphState) -> str:
    return _next_or_end(state, "compliance")


def route_after_compliance(state: GraphState) -> str:
    return _next_or_end(state, "synthesis")


async def _run_node(
    node: BaseGraphAgent,
    state: GraphState,
    *,
    langfuse: LangfuseService,
    parent: Any | None = None,
) -> GraphState:
    """Execute a node with uniform start/end logging + optional Langfuse trace."""
    logger.info("[multi_agent] node=%s start", node.name)
    result = await langfuse.trace_node(
        node, state, workflow=_WORKFLOW, parent=parent
    )
    logger.info("[multi_agent] node=%s done", node.name)
    return result


def build_multi_agent_graph(
    *,
    session: "AsyncSession",
    settings: Settings | None = None,
    langfuse: LangfuseService | None = None,
    trace: Any | None = None,
):
    """Compile the multi-agent LangGraph workflow.

    Dependencies are injected: the three agent nodes share one
    ``GeneratorService`` (reusing the RAG pipeline with a specialized system
    prompt each) and the synthesis node reuses the existing LLM provider.
    """
    settings = settings or get_settings()
    langfuse = langfuse or get_langfuse_service()

    generator = GeneratorService(session, settings=settings)
    command_parser = CommandParserNode()
    legal_node = LegalNode(generator)
    finance_node = FinanceNode(generator)
    compliance_node = ComplianceNode(generator)
    synthesis_node = SynthesisNode(settings=settings)

    retry = transient_retry_policy(3)

    async def command_parser_step(state: GraphState) -> GraphState:
        return await _run_node(command_parser, state, langfuse=langfuse, parent=trace)

    async def legal_step(state: GraphState) -> GraphState:
        return await _run_node(legal_node, state, langfuse=langfuse, parent=trace)

    async def finance_step(state: GraphState) -> GraphState:
        return await _run_node(finance_node, state, langfuse=langfuse, parent=trace)

    async def compliance_step(state: GraphState) -> GraphState:
        return await _run_node(compliance_node, state, langfuse=langfuse, parent=trace)

    async def synthesis_step(state: GraphState) -> GraphState:
        return await _run_node(synthesis_node, state, langfuse=langfuse, parent=trace)

    builder = StateGraph(GraphState)
    builder.add_node("command_parser", command_parser_step)
    builder.add_node("legal", legal_step, retry=retry)
    builder.add_node("finance", finance_step, retry=retry)
    builder.add_node("compliance", compliance_step, retry=retry)
    builder.add_node("synthesis", synthesis_step, retry=retry)

    builder.set_entry_point("command_parser")
    builder.add_conditional_edges(
        "command_parser",
        route_after_command,
        {"legal": "legal", "finance": "finance", "compliance": "compliance"},
    )
    builder.add_conditional_edges(
        "legal",
        route_after_legal,
        {"finance": "finance", "end": END},
    )
    builder.add_conditional_edges(
        "finance",
        route_after_finance,
        {"compliance": "compliance", "end": END},
    )
    builder.add_conditional_edges(
        "compliance",
        route_after_compliance,
        {"synthesis": "synthesis", "end": END},
    )
    builder.add_edge("synthesis", END)

    return builder.compile()
