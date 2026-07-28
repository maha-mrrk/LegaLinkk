"""CommandParserNode — routes a message by its leading ``/command`` prefix.

Thin orchestration node (no business logic): it inspects the raw user message,
detects an optional ``/legal`` | ``/finance`` | ``/compliance`` prefix
(case-insensitive), and writes ``target_agent`` + the command-stripped
``user_query`` back onto the shared state. ``target_agent`` is ``None`` when no
command is present, which the graph uses to fan out to all three agents.
"""

from __future__ import annotations

import re

from app.agents.base_agent import BaseGraphAgent
from app.core.logging import get_logger
from app.state.graph_state import GraphState

logger = get_logger(__name__)

# Leading "/legal", "/finance" or "/compliance" (case-insensitive), with or
# without text after it. The captured group is the domain.
_COMMAND_RE = re.compile(
    r"^\s*/(legal|finance|compliance)\b[ \t]*(.*)$",
    re.IGNORECASE | re.DOTALL,
)

# Domain-specific fallbacks keep a bare command inside the selected mandate.
_DEFAULT_QUESTIONS = {
    "legal": "Analyse les clauses et risques juridiques de ce contrat.",
    "finance": "Analyse les montants, paiements et risques financiers de ce contrat.",
    "compliance": "Analyse la conformité réglementaire et RGPD de ce contrat.",
}


class CommandParserNode(BaseGraphAgent):
    """Parse the ``/command`` prefix and set ``target_agent`` / ``user_query``."""

    @property
    def name(self) -> str:
        return "command_parser"

    @property
    def description(self) -> str:
        return (
            "Detect a leading /legal, /finance or /compliance command and route "
            "to the matching agent (or all three when absent)."
        )

    async def execute(self, state: GraphState) -> GraphState:
        raw = (state.get("user_query") or state.get("user_question") or "").strip()
        match = _COMMAND_RE.match(raw)

        if match:
            domain = match.group(1).lower()
            remainder = (match.group(2) or "").strip()
            state["target_agent"] = domain  # "legal" | "finance" | "compliance"
            state["user_query"] = remainder or _DEFAULT_QUESTIONS[domain]
            logger.info(
                "[multi_agent] command detected target=%s has_text=%s",
                domain,
                bool(remainder),
            )
        else:
            state["target_agent"] = None
            state["user_query"] = raw
            logger.info("[multi_agent] no command → running all agents")

        return state
