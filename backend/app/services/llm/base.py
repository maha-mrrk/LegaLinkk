"""LLM provider protocol and result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LLMGenerationResult:
    """Raw completion returned by an LLM provider."""

    content: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class LLMProvider(Protocol):
    """Minimal async chat-completion interface shared by all providers."""

    @property
    def provider_name(self) -> str: ...

    @property
    def model(self) -> str: ...

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMGenerationResult: ...
