"""Abstract base class for LangGraph agent tools (architecture preparation).

Defines the *contract only*. Concrete tools will wrap existing services
(ChunkingService, EmbeddingService, RetrievalService, GeneratorService, ...)
without changing their behavior or duplicating logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Contract for a reusable, single-responsibility tool used by agents."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable, unique identifier for this tool."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Short human-readable description of what the tool does."""

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool. Concrete tools delegate to existing services."""
