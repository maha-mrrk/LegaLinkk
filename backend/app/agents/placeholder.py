"""Placeholder specialized agents (no domain business logic yet)."""

from __future__ import annotations

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.intent import DOMAIN_KEYWORDS
from app.services.generator import GeneratorService


class _PlaceholderAgent(BaseAgent):
    """Shared skeleton for Legal / Finance / Compliance placeholders."""

    _agent_name: str
    _description: str
    _domain: str

    def __init__(self, generator: GeneratorService) -> None:
        super().__init__(generator)

    @property
    def name(self) -> str:
        return self._agent_name

    @property
    def description(self) -> str:
        return self._description

    def can_handle(self, query: str) -> bool:
        text = (query or "").strip().lower()
        if not text:
            return False
        keywords = DOMAIN_KEYWORDS.get(self._domain, ())
        return any(kw in text for kw in keywords)

    async def execute(self, query: str, context: AgentContext) -> AgentResult:
        """Reuse GeneratorService RAG; return a clearly labeled placeholder."""
        rag = await self._rag_answer(query, context)
        return AgentResult(
            agent=self.name,
            status="placeholder",
            message=(
                f"{self.name} is a placeholder. Domain-specific analysis is not "
                "implemented yet; the answer below comes from the shared RAG pipeline."
            ),
            answer=rag.get("answer"),
            sources=tuple(rag.get("sources") or ()),
            metadata={
                "placeholder": True,
                "domain": self._domain,
                "rag": rag.get("metadata") or {},
            },
        )


class LegalAgent(_PlaceholderAgent):
    """Placeholder legal specialist."""

    _agent_name = "LegalAgent"
    _description = "Handles clauses, obligations, liabilities, and contractual questions."
    _domain = "legal"


class FinanceAgent(_PlaceholderAgent):
    """Placeholder finance specialist."""

    _agent_name = "FinanceAgent"
    _description = "Handles payments, invoices, penalties, pricing, and financial terms."
    _domain = "finance"


class ComplianceAgent(_PlaceholderAgent):
    """Placeholder compliance specialist."""

    _agent_name = "ComplianceAgent"
    _description = "Handles GDPR, regulations, ISO, and compliance questions."
    _domain = "compliance"
