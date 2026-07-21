"""LegalAgent: specialized legal contract analysis over the RAG pipeline.

The agent owns *no* retrieval / reranking / generation logic. It delegates all
of that to the shared :class:`GeneratorService` (dependency-injected), and only
adds a legal system prompt, a rule-based risk classifier, and structured output.
"""

from __future__ import annotations

from typing import Any, Sequence

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.intent import DOMAIN_KEYWORDS
from app.agents.risk import RiskAssessment, RiskClassifier, RuleBasedRiskClassifier
from app.core.logging import get_logger
from app.services.generator import GeneratorService

logger = get_logger(__name__)


LEGAL_SYSTEM_PROMPT = """You are LegalLink Counsel, a meticulous legal contract analyst.

Your job is to analyze contractual documents and answer legal questions.

Strict rules:
1. Behave as a legal contract analyst reviewing the provided contract excerpts.
2. Answer ONLY using the retrieved document context provided by the user.
3. Never invent, assume, or infer clauses, parties, dates, amounts, or obligations
   that are not present in the retrieved context.
4. When information needed to answer is not in the context, explicitly state that
   the information is unavailable in the provided documents.
5. If PART of the question is supported, answer that part and clearly state what
   is missing. Do not fabricate the missing parts.
6. Only if NOTHING in the context is relevant, reply exactly with:
   {no_answer}
7. Preserve precise legal terminology; do not simplify legal terms into
   approximations that change their meaning.
8. Whenever possible, cite the source document filename and page number(s) that
   support each statement.
9. Cover, when the context allows: clause explanations, obligations of each party,
   rights of each party, and summaries of contractual provisions.
10. The context may be in French or English; answer in the language of the
    question while using only facts from the context.
"""


class LegalAgent(BaseAgent):
    """Specialized agent for legal contract analysis.

    Responsibilities: explain clauses, identify obligations and rights, summarize
    provisions, answer legal questions grounded in documents, flag missing or
    ambiguous clauses, and assess legal risk.
    """

    _agent_name = "LegalAgent"
    _description = (
        "Legal contract analyst: clauses, obligations, rights, provisions, "
        "missing/ambiguous clause detection, and legal risk assessment."
    )
    _domain = "legal"

    def __init__(
        self,
        generator: GeneratorService,
        risk_classifier: RiskClassifier | None = None,
    ) -> None:
        super().__init__(generator)
        # Injected + modular: swap for an ML/LLM classifier later.
        self._risk: RiskClassifier = risk_classifier or RuleBasedRiskClassifier()

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
        return any(kw in text for kw in DOMAIN_KEYWORDS.get(self._domain, ()))

    async def analyze(
        self,
        question: str,
        *,
        top_k: int | None = None,
        final_k: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        history: Sequence[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Run the full legal analysis and return the structured payload."""
        logger.info("Legal analysis started.")

        logger.info("Calling GeneratorService.")
        rag = await self._generator.answer_question(
            question,
            top_k=top_k,
            final_k=final_k,
            temperature=temperature,
            max_tokens=max_tokens,
            history=history,
            system_prompt=LEGAL_SYSTEM_PROMPT,
        )

        answer: str = rag.get("answer") or ""
        sources: list[dict[str, Any]] = list(rag.get("sources") or [])
        context_text: str = rag.get("context_text") or ""
        rag_metadata: dict[str, Any] = dict(rag.get("metadata") or {})

        assessment: RiskAssessment = self._risk.classify(
            context_text=context_text,
            answer=answer,
            question=question,
        )
        logger.info("Risk assessment completed. level=%s", assessment.risk_level)

        payload: dict[str, Any] = {
            "analysis": answer,
            "risk_level": assessment.risk_level,
            "missing_information": list(assessment.missing_information),
            "sources": sources,
            "recommendations": list(assessment.recommendations),
            "metadata": {
                **rag_metadata,
                "agent": self.name,
                "risk_findings": [
                    {
                        "level": f.level,
                        "category": f.category,
                        "detail": f.detail,
                    }
                    for f in assessment.findings
                ],
            },
        }

        logger.info("Legal analysis completed.")
        return payload

    async def execute(self, query: str, context: AgentContext) -> AgentResult:
        """Orchestrator entry point: wrap the structured analysis in AgentResult."""
        history = None
        if context.extras:
            history = context.extras.get("history")

        payload = await self.analyze(
            query,
            top_k=context.top_k,
            final_k=context.final_k,
            temperature=context.temperature,
            max_tokens=context.max_tokens,
            history=history,
        )

        return AgentResult(
            agent=self.name,
            status="ok",
            message="Legal analysis completed.",
            answer=payload["analysis"],
            sources=tuple(payload["sources"]),
            metadata={
                "risk_level": payload["risk_level"],
                "missing_information": payload["missing_information"],
                "recommendations": payload["recommendations"],
                **payload["metadata"],
            },
        )


__all__ = ["LegalAgent", "LEGAL_SYSTEM_PROMPT"]
