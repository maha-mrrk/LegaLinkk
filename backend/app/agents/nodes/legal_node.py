"""LegalNode — specialized legal/contract-risk analysis as a graph node."""

from __future__ import annotations

from app.agents.legal import LEGAL_SYSTEM_PROMPT
from app.agents.nodes._agent_node import DomainAgentNode


class LegalNode(DomainAgentNode):
    """Run the legal analysis (clauses, obligations, contractual risks) via RAG."""

    _agent_name = "LegalAgent"
    _node_name = "legal"
    _domain = "legal"
    _result_key = "legal_result"
    _system_prompt = LEGAL_SYSTEM_PROMPT
