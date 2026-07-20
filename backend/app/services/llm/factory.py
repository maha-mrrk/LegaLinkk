"""Factory that builds the configured LLM provider."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.openai_compatible import (
    LLMProviderError,
    OpenAICompatibleProvider,
)

_PROVIDER_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "nvidia_nim": "https://integrate.api.nvidia.com/v1",
}

_PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "groq": "llama-3.3-70b-versatile",
    "nvidia_nim": "meta/llama-3.1-8b-instruct",
}


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    """Return an LLM provider selected by ``LLM_PROVIDER``."""
    cfg = settings or get_settings()
    provider = (cfg.llm_provider or "openai").strip().lower().replace("-", "_")
    if provider in {"nvidia", "nim"}:
        provider = "nvidia_nim"

    if provider not in _PROVIDER_BASE_URLS:
        raise LLMProviderError(
            f"Unsupported LLM_PROVIDER={cfg.llm_provider!r}. "
            "Use one of: openai, nvidia_nim, groq."
        )

    base_url = (cfg.llm_base_url or _PROVIDER_BASE_URLS[provider]).rstrip("/")
    model = (cfg.llm_model or "").strip() or _PROVIDER_DEFAULT_MODELS[provider]
    api_key = cfg.llm_api_key or ""

    return OpenAICompatibleProvider(
        provider_name=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=cfg.llm_timeout_seconds,
        default_temperature=cfg.llm_temperature,
        default_max_tokens=cfg.llm_max_tokens,
    )
