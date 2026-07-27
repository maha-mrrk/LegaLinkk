"""FinanceNode — specialized financial-impact analysis as a graph node."""

from __future__ import annotations

from app.agents.nodes._agent_node import DomainAgentNode
from app.agents.nodes.agent_prompts import FINANCE_SYSTEM_PROMPT


class FinanceNode(DomainAgentNode):
    """Run the financial analysis (payments, pricing, penalties, budget) via RAG."""

    _agent_name = "FinanceAgent"
    _node_name = "finance"
    _domain = "finance"
    _result_key = "finance_result"
    _system_prompt = FINANCE_SYSTEM_PROMPT
