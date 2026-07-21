"""Abstract base class for LangGraph-style agents (architecture preparation).

Every future graph agent/node will subclass :class:`BaseGraphAgent` and operate
on the shared :class:`~app.state.graph_state.GraphState`. This class defines the
*contract only* — it contains no business logic. Concrete agents will delegate
to the existing services (ChunkingService, EmbeddingService, RetrievalService,
GeneratorService, ...) which remain unchanged.

Note: this is intentionally separate from ``app.agents.base.BaseAgent`` (the
current orchestration interface), which stays in place and unmodified.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.state.graph_state import GraphState


class BaseGraphAgent(ABC):
    """Contract for a single node/agent in a LangGraph workflow.

    A graph agent is a pure transformation over the shared state: it reads the
    fields it needs from ``state`` and returns the (updated) state. Subclasses
    must expose a stable ``name`` and human-readable ``description`` and
    implement ``execute``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable, unique identifier for this agent/node."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Short human-readable description of the agent's responsibility."""

    @abstractmethod
    async def execute(self, state: GraphState) -> GraphState:
        """Run the agent against the shared state and return the updated state.

        Implementations must not embed retrieval/generation logic directly; they
        should delegate to the existing services and only orchestrate.
        """
