"""OpenAI-compatible Chat Completions client (OpenAI / Groq / NVIDIA NIM)."""

from __future__ import annotations

import httpx

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.services.llm.base import LLMGenerationResult

logger = get_logger(__name__)


class LLMProviderError(AppError):
    """Raised when an LLM HTTP call fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class OpenAICompatibleProvider:
    """Call ``/chat/completions`` on any OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        provider_name: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        default_temperature: float = 0.1,
        default_max_tokens: int = 1024,
    ) -> None:
        if not api_key.strip():
            raise LLMProviderError(
                f"LLM API key is missing for provider {provider_name!r}. "
                "Set LLM_API_KEY in the environment."
            )
        self._provider_name = provider_name
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds
        self._default_temperature = default_temperature
        self._default_max_tokens = default_max_tokens

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model(self) -> str:
        return self._model

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMGenerationResult:
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": (
                self._default_temperature if temperature is None else temperature
            ),
            "max_tokens": (
                self._default_max_tokens if max_tokens is None else max_tokens
            ),
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/chat/completions"
        logger.info(
            "Calling LLM provider=%s model=%s",
            self._provider_name,
            self._model,
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise LLMProviderError(
                f"LLM request timed out for provider {self._provider_name}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(
                f"LLM request failed for provider {self._provider_name}: {exc}"
            ) from exc

        if response.status_code >= 400:
            detail = (response.text or "")[:400]
            raise LLMProviderError(
                f"LLM provider {self._provider_name} returned "
                f"{response.status_code}: {detail}"
            )

        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(
                f"Unexpected LLM response shape from {self._provider_name}"
            ) from exc

        usage = data.get("usage") or {}
        return LLMGenerationResult(
            content=(content or "").strip(),
            model=str(data.get("model") or self._model),
            prompt_tokens=_as_optional_int(usage.get("prompt_tokens")),
            completion_tokens=_as_optional_int(usage.get("completion_tokens")),
            total_tokens=_as_optional_int(usage.get("total_tokens")),
        )


def _as_optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
