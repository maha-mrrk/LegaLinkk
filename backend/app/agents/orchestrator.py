"""Multi-agent orchestrator: intent → select agents → execute → aggregate."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.agents.intent import IntentRouter
from app.agents.legal import LegalAgent
from app.agents.placeholder import ComplianceAgent, FinanceAgent
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, ValidationError
from app.core.logging import get_logger
from app.services.generator import GeneratorService

logger = get_logger(__name__)


class OrchestrationError(AppError):
    """Raised when multi-agent orchestration fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class AgentOrchestrator:
    """Route a user question to one or more specialized agents.

    The orchestrator stays independent of each agent's future business logic.
    Agents receive a shared ``GeneratorService`` and must reuse the RAG pipeline.
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
        generator: GeneratorService | None = None,
        agents: Sequence[BaseAgent] | None = None,
        intent_router: IntentRouter | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._generator = generator or GeneratorService(
            session, settings=self._settings
        )
        self._intent = intent_router or IntentRouter()
        self._agents: list[BaseAgent] = list(
            agents
            if agents is not None
            else self._default_agents(self._generator)
        )

    @staticmethod
    def _default_agents(generator: GeneratorService) -> list[BaseAgent]:
        return [
            LegalAgent(generator),
            FinanceAgent(generator),
            ComplianceAgent(generator),
        ]

    @property
    def agents(self) -> list[BaseAgent]:
        return list(self._agents)

    def register_agent(self, agent: BaseAgent) -> None:
        """Register an additional agent (for future extensions)."""
        self._agents.append(agent)

    async def query(
        self,
        question: str,
        *,
        top_k: int | None = None,
        final_k: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """Analyze intent, run selected agents, return a unified result."""
        cleaned = (question or "").strip()
        if not cleaned:
            raise ValidationError("Question must not be empty")

        logger.info("Question received.")
        intent = self._intent.detect(cleaned)
        logger.info(
            "Intent detected. domains=%s keywords=%s",
            list(intent.domains),
            list(intent.keywords_hit),
        )

        selected = self._select_agents(cleaned)
        selected_names = [agent.name for agent in selected]
        logger.info("Selected agents: %s", selected_names)

        if not selected:
            logger.info("Executing agents.")
            logger.info("Aggregation completed.")
            return {
                "question": cleaned,
                "selected_agents": [],
                "intent": {
                    "domains": list(intent.domains),
                    "keywords_hit": list(intent.keywords_hit),
                },
                "responses": [],
                "message": (
                    "No specialized agent matched this question. "
                    "Try mentioning legal, finance, or compliance terms."
                ),
            }

        context = AgentContext(
            generator=self._generator,
            top_k=top_k,
            final_k=final_k,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        logger.info("Executing agents.")
        responses: list[AgentResult] = []
        for agent in selected:
            try:
                result = await agent.execute(cleaned, context)
                responses.append(result)
            except Exception as exc:
                logger.exception("Agent %s failed", agent.name)
                responses.append(
                    AgentResult(
                        agent=agent.name,
                        status="error",
                        message=f"Agent execution failed: {exc}",
                        answer=None,
                        sources=(),
                        metadata={"error": type(exc).__name__},
                    )
                )

        logger.info("Aggregation completed.")
        return {
            "question": cleaned,
            "selected_agents": selected_names,
            "intent": {
                "domains": list(intent.domains),
                "keywords_hit": list(intent.keywords_hit),
            },
            "responses": [item.to_dict() for item in responses],
        }

    def _select_agents(self, query: str) -> list[BaseAgent]:
        """Select agents from intent domains and ``can_handle`` checks."""
        by_name = {agent.name: agent for agent in self._agents}
        selected: list[BaseAgent] = []
        seen: set[str] = set()

        # Prefer explicit intent routing.
        for domain_agent in self._intent.agent_names_for(query):
            agent = by_name.get(domain_agent)
            if agent is not None and agent.name not in seen:
                selected.append(agent)
                seen.add(agent.name)

        # Also include any registered agent that claims the query (extensibility).
        for agent in self._agents:
            if agent.name in seen:
                continue
            if agent.can_handle(query):
                selected.append(agent)
                seen.add(agent.name)

        return selected
