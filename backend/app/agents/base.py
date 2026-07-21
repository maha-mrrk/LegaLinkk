"""Abstract agent interface for multi-agent orchestration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.services.generator import GeneratorService


@dataclass
class AgentContext:
    """Shared runtime context injected by the orchestrator into every agent."""

    generator: GeneratorService
    top_k: int | None = None
    final_k: int | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    # Optional precomputed RAG result to avoid duplicate retrieve/rerank/LLM calls
    # when multiple agents are selected for the same question.
    shared_rag: dict[str, Any] | None = None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentResult:
    """Unified agent output collected by the orchestrator."""

    agent: str
    status: str
    message: str
    answer: str | None = None
    sources: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "status": self.status,
            "message": self.message,
            "answer": self.answer,
            "sources": list(self.sources),
            "metadata": dict(self.metadata),
        }


class BaseAgent(ABC):
    """Contract every specialized agent must implement."""

    def __init__(self, generator: GeneratorService) -> None:
        self._generator = generator

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable agent identifier (e.g. ``LegalAgent``)."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Short human-readable description of the agent's domain."""

    @abstractmethod
    def can_handle(self, query: str) -> bool:
        """Return True when this agent is relevant for ``query``."""

    @abstractmethod
    async def execute(self, query: str, context: AgentContext) -> AgentResult:
        """Run the agent. Must reuse ``context.generator`` for RAG — no local retrieval."""

    async def _rag_answer(self, query: str, context: AgentContext) -> dict[str, Any]:
        """Reuse the shared GeneratorService RAG pipeline (no duplicated retrieval)."""
        if context.shared_rag is not None:
            return context.shared_rag

        result = await context.generator.answer_question(
            query,
            top_k=context.top_k,
            final_k=context.final_k,
            temperature=context.temperature,
            max_tokens=context.max_tokens,
        )
        context.shared_rag = result
        return result
