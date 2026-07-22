"""Concrete LLM providers.

Every provider is a tiny subclass of :class:`BaseLLMProvider` that only sets a
provider name (and, for OpenRouter, optional attribution headers). They share
the exact same interface and HTTP/retry implementation, so adding a new
provider tomorrow is a few lines here plus a factory registry entry.
"""

from __future__ import annotations

from app.services.llm.base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """OpenAI Chat Completions."""

    default_provider_name = "openai"


class GroqProvider(BaseLLMProvider):
    """Groq (OpenAI-compatible)."""

    default_provider_name = "groq"


class NvidiaProvider(BaseLLMProvider):
    """NVIDIA NIM (OpenAI-compatible)."""

    default_provider_name = "nvidia_nim"


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter (OpenAI-compatible).

    OpenRouter recommends sending attribution headers (``HTTP-Referer`` and
    ``X-Title``); they are injected via ``extra_headers`` by the factory when
    configured. Functionally identical to the base provider otherwise.
    """

    default_provider_name = "openrouter"


__all__ = [
    "OpenAIProvider",
    "GroqProvider",
    "NvidiaProvider",
    "OpenRouterProvider",
]
