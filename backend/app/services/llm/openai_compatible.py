"""Generic OpenAI-compatible Chat Completions client.

Thin wrapper kept for backward compatibility. All shared HTTP, retry, timeout
and SSE logic now lives in :class:`app.services.llm.base.BaseLLMProvider`; this
module re-exports :class:`LLMProviderError` so existing imports keep working.
"""

from __future__ import annotations

from app.services.llm.base import BaseLLMProvider, LLMProviderError

__all__ = ["OpenAICompatibleProvider", "LLMProviderError"]


class OpenAICompatibleProvider(BaseLLMProvider):
    """Call ``/chat/completions`` on any OpenAI-compatible endpoint."""

    default_provider_name = "openai_compatible"
