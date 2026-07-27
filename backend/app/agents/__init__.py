"""Multi-agent orchestration package.

Orchestration now lives in the LangGraph ``multi_agent_graph`` (see
``app.graphs.multi_agent_graph``): the Legal / Finance / Compliance / Synthesis
agents are graph **nodes** (``app.agents.nodes``). The former hand-rolled
``AgentOrchestrator`` + ``IntentRouter`` dispatch has been removed. ``LegalAgent``
remains for the dedicated ``/agents/legal/analyze`` endpoint, and ``intent`` is
kept only for its ``DOMAIN_KEYWORDS`` (reused by ``LegalAgent.can_handle``).
"""

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.legal import LegalAgent
from app.agents.risk import (
    RiskAssessment,
    RiskClassifier,
    RiskFinding,
    RuleBasedRiskClassifier,
)

__all__ = [
    "AgentContext",
    "AgentResult",
    "BaseAgent",
    "LegalAgent",
    "RiskAssessment",
    "RiskClassifier",
    "RiskFinding",
    "RuleBasedRiskClassifier",
]
