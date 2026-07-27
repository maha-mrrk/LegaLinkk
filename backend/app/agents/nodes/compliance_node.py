"""ComplianceNode — specialized regulatory/GDPR compliance analysis node."""

from __future__ import annotations

from app.agents.nodes._agent_node import DomainAgentNode
from app.agents.nodes.agent_prompts import COMPLIANCE_SYSTEM_PROMPT


class ComplianceNode(DomainAgentNode):
    """Run the compliance analysis (GDPR/RGPD, regulations, audit) via RAG."""

    _agent_name = "ComplianceAgent"
    _node_name = "compliance"
    _domain = "compliance"
    _result_key = "compliance_result"
    _system_prompt = COMPLIANCE_SYSTEM_PROMPT
