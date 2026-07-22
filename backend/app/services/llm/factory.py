"""Factory that builds the configured LLM provider (entirely env-driven).

Provider selection is controlled by ``LLM_PROVIDER``. Each provider resolves its
API key from a provider-specific env var first (e.g. ``OPENROUTER_API_KEY``),
falling back to the generic ``LLM_API_KEY``. Onboarding a new provider is
config-only — no code changes are required after adding the key.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.llm.base import BaseLLMProvider, LLMProvider, LLMProviderError
from app.services.llm.providers import (
    GroqProvider,
    NvidiaProvider,
    OpenAIProvider,
    OpenRouterProvider,
)

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """Static configuration for one supported provider."""

    cls: type[BaseLLMProvider]
    base_url: str
    default_model: str
    #: Resolve the provider-specific API key from settings (may be empty).
    key_getter: Callable[[Settings], str]
    #: Optional extra HTTP headers (provider attribution, etc.).
    headers_getter: Callable[[Settings], dict[str, str]] | None = None


def _no_headers(_: Settings) -> dict[str, str]:
    return {}


def _openrouter_headers(cfg: Settings) -> dict[str, str]:
    headers: dict[str, str] = {}
    if cfg.openrouter_referer:
        headers["HTTP-Referer"] = cfg.openrouter_referer
    if cfg.openrouter_title:
        headers["X-Title"] = cfg.openrouter_title
    return headers


# Single source of truth for supported providers. Add a new provider here.
_REGISTRY: dict[str, ProviderSpec] = {
    "openai": ProviderSpec(
        cls=OpenAIProvider,
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        key_getter=lambda c: c.openai_api_key,
    ),
    "groq": ProviderSpec(
        cls=GroqProvider,
        base_url="https://api.groq.com/openai/v1",
        default_model="llama-3.3-70b-versatile",
        key_getter=lambda c: c.groq_api_key,
    ),
    "nvidia_nim": ProviderSpec(
        cls=NvidiaProvider,
        base_url="https://integrate.api.nvidia.com/v1",
        default_model="meta/llama-3.1-8b-instruct",
        key_getter=lambda c: c.nvidia_api_key,
    ),
    "openrouter": ProviderSpec(
        cls=OpenRouterProvider,
        base_url="https://openrouter.ai/api/v1",
        default_model="meta-llama/llama-3.1-8b-instruct",
        key_getter=lambda c: c.openrouter_api_key,
        headers_getter=_openrouter_headers,
    ),
}

# Convenience aliases accepted for LLM_PROVIDER.
_ALIASES = {
    "nvidia": "nvidia_nim",
    "nim": "nvidia_nim",
    "open_router": "openrouter",
    "open-router": "openrouter",
}


def _normalize_provider(raw: str) -> str:
    provider = (raw or "openai").strip().lower().replace("-", "_")
    return _ALIASES.get(provider, provider)


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    """Return an LLM provider selected by ``LLM_PROVIDER`` (env-driven)."""
    cfg = settings or get_settings()
    provider = _normalize_provider(cfg.llm_provider)

    spec = _REGISTRY.get(provider)
    if spec is None:
        supported = ", ".join(sorted(_REGISTRY))
        raise LLMProviderError(
            "La configuration du service IA est invalide. "
            "Contactez votre administrateur.",
            detail=(
                f"Unsupported LLM_PROVIDER={cfg.llm_provider!r}. "
                f"Use one of: {supported}."
            ),
            retryable=False,
            provider=provider,
        )

    # Provider-specific key takes precedence over the generic LLM_API_KEY.
    api_key = (spec.key_getter(cfg) or cfg.llm_api_key or "").strip()
    base_url = (cfg.llm_base_url or spec.base_url).rstrip("/")
    model = (cfg.llm_model or "").strip() or spec.default_model
    headers = (spec.headers_getter or _no_headers)(cfg)

    logger.info(
        "LLM provider selected provider=%s model=%s base_url=%s",
        provider,
        model,
        base_url,
    )

    return spec.cls(
        provider_name=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=cfg.llm_timeout_seconds,
        default_temperature=cfg.llm_temperature,
        default_max_tokens=cfg.llm_max_tokens,
        max_retries=cfg.llm_max_retries,
        retry_base_delay=cfg.llm_retry_base_delay_seconds,
        extra_headers=headers,
    )
