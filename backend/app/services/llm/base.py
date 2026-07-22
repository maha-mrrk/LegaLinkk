"""LLM provider abstraction: protocol, result types and a shared base provider.

The provider layer follows a single clean abstraction so every backend
(NVIDIA NIM, OpenRouter, OpenAI, Groq, …) exposes the exact same interface and
shares one battle-tested HTTP + retry implementation. Adding a new provider is
just a small subclass plus a factory registry entry — no duplicated logic.
"""

from __future__ import annotations

import asyncio
import json
import random
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)

# HTTP status codes that are worth retrying (transient / server-side).
_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True, slots=True)
class LLMGenerationResult:
    """Raw completion returned by an LLM provider."""

    content: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class LLMProviderError(AppError):
    """Raised when an LLM HTTP call fails.

    Carries a user-facing (professional, non-technical) ``message`` while the
    technical ``detail`` is kept for logs/observability only. ``retryable``
    marks transient failures the caller may retry.
    """

    def __init__(
        self,
        message: str = "Le service d'analyse IA est momentanément indisponible.",
        *,
        detail: str | None = None,
        retryable: bool = False,
        provider: str | None = None,
    ) -> None:
        super().__init__(message, status_code=502)
        self.detail = detail or message
        self.retryable = retryable
        self.provider = provider


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

    def stream_complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]: ...


class BaseLLMProvider:
    """Shared OpenAI-compatible ``/chat/completions`` provider.

    Concrete providers subclass this and only customise defaults (base URL,
    default model, extra headers) via ``__init__``. All HTTP, retry, timeout,
    error-mapping and SSE-parsing logic lives here exactly once.
    """

    #: Human-readable provider id (overridden by subclasses / factory).
    default_provider_name: str = "openai_compatible"

    def __init__(
        self,
        *,
        provider_name: str | None = None,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        default_temperature: float = 0.1,
        default_max_tokens: int = 1024,
        max_retries: int = 2,
        retry_base_delay: float = 1.0,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        name = provider_name or self.default_provider_name
        if not (api_key or "").strip():
            raise LLMProviderError(
                "La configuration du service IA est incomplète. "
                "Contactez votre administrateur.",
                detail=(
                    f"LLM API key is missing for provider {name!r}. "
                    "Set the provider API key in the environment."
                ),
                retryable=False,
                provider=name,
            )
        self._provider_name = name
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds
        self._default_temperature = default_temperature
        self._default_max_tokens = default_max_tokens
        self._max_retries = max(0, int(max_retries))
        self._retry_base_delay = max(0.0, float(retry_base_delay))
        self._extra_headers = {k: v for k, v in (extra_headers or {}).items() if v}

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model(self) -> str:
        return self._model

    # --- helpers -------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        headers.update(self._extra_headers)
        return headers

    def _payload(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None,
        max_tokens: int | None,
        stream: bool,
    ) -> dict:
        return {
            "model": self._model,
            "messages": messages,
            "temperature": (
                self._default_temperature if temperature is None else temperature
            ),
            "max_tokens": (
                self._default_max_tokens if max_tokens is None else max_tokens
            ),
            "stream": stream,
        }

    def _timeout_config(self) -> httpx.Timeout:
        # Fast to fail on connect, but patient on read: LLM generation (large
        # context + many tokens) can legitimately take a few minutes.
        return httpx.Timeout(
            connect=15.0,
            read=self._timeout,
            write=30.0,
            pool=self._timeout,
        )

    async def _sleep_backoff(self, attempt: int) -> None:
        # Exponential backoff with jitter (attempt is 0-based).
        delay = self._retry_base_delay * (2 ** attempt)
        delay += random.uniform(0, self._retry_base_delay)
        await asyncio.sleep(delay)

    def _raise_for_status(self, status_code: int, body: str) -> None:
        detail = (body or "")[:400]
        retryable = status_code in _RETRYABLE_STATUS
        if status_code == 429:
            message = (
                "Le service d'analyse IA est très sollicité pour le moment. "
                "Veuillez réessayer dans quelques instants."
            )
        elif status_code in {401, 403}:
            message = (
                "La configuration du service IA est invalide. "
                "Contactez votre administrateur."
            )
        elif status_code >= 500:
            message = (
                "Le service d'analyse IA est momentanément indisponible. "
                "Veuillez réessayer dans un instant."
            )
        else:
            message = (
                "Le service d'analyse IA n'a pas pu traiter la demande. "
                "Veuillez réessayer."
            )
        raise LLMProviderError(
            message,
            detail=(
                f"provider={self._provider_name} status={status_code} body={detail}"
            ),
            retryable=retryable,
            provider=self._provider_name,
        )

    # --- public API ----------------------------------------------------------

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMGenerationResult:
        payload = self._payload(
            messages, temperature=temperature, max_tokens=max_tokens, stream=False
        )
        url = f"{self._base_url}/chat/completions"

        last_error: LLMProviderError | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout_config()) as client:
                    response = await client.post(
                        url, headers=self._headers(), json=payload
                    )
                if response.status_code >= 400:
                    self._raise_for_status(response.status_code, response.text)
                return self._parse_completion(response.json())
            except LLMProviderError as exc:
                last_error = exc
                if not exc.retryable or attempt >= self._max_retries:
                    logger.warning(
                        "LLM call failed provider=%s attempt=%s/%s detail=%s",
                        self._provider_name,
                        attempt + 1,
                        self._max_retries + 1,
                        exc.detail,
                    )
                    raise
            except httpx.TimeoutException as exc:
                last_error = LLMProviderError(
                    "Le service d'analyse IA met trop de temps à répondre. "
                    "Veuillez réessayer.",
                    detail=f"timeout provider={self._provider_name}: {exc}",
                    retryable=True,
                    provider=self._provider_name,
                )
                if attempt >= self._max_retries:
                    raise last_error from exc
            except httpx.HTTPError as exc:
                last_error = LLMProviderError(
                    "Le service d'analyse IA est momentanément injoignable. "
                    "Veuillez réessayer.",
                    detail=f"http error provider={self._provider_name}: {exc}",
                    retryable=True,
                    provider=self._provider_name,
                )
                if attempt >= self._max_retries:
                    raise last_error from exc

            logger.info(
                "Retrying LLM call provider=%s attempt=%s/%s",
                self._provider_name,
                attempt + 2,
                self._max_retries + 1,
            )
            await self._sleep_backoff(attempt)

        # Defensive: loop always returns/raises, but keep the type checker happy.
        raise last_error or LLMProviderError(provider=self._provider_name)

    def _parse_completion(self, data: dict) -> LLMGenerationResult:
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(
                "Le service d'analyse IA a renvoyé une réponse inattendue. "
                "Veuillez réessayer.",
                detail=f"unexpected response shape from {self._provider_name}",
                retryable=True,
                provider=self._provider_name,
            ) from exc

        usage = data.get("usage") or {}
        return LLMGenerationResult(
            content=(content or "").strip(),
            model=str(data.get("model") or self._model),
            prompt_tokens=_as_optional_int(usage.get("prompt_tokens")),
            completion_tokens=_as_optional_int(usage.get("completion_tokens")),
            total_tokens=_as_optional_int(usage.get("total_tokens")),
        )

    async def stream_complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Yield incremental answer text as the model generates it (SSE stream).

        Only the *connection / initial-status* phase is retried; once tokens
        start flowing a retry would duplicate output, so mid-stream failures are
        surfaced to the caller (which falls back to a non-streamed completion).
        """
        payload = self._payload(
            messages, temperature=temperature, max_tokens=max_tokens, stream=True
        )
        url = f"{self._base_url}/chat/completions"

        for attempt in range(self._max_retries + 1):
            started_streaming = False
            try:
                async with httpx.AsyncClient(timeout=self._timeout_config()) as client:
                    async with client.stream(
                        "POST", url, headers=self._headers(), json=payload
                    ) as response:
                        if response.status_code >= 400:
                            body = (await response.aread()).decode(errors="replace")
                            self._raise_for_status(response.status_code, body)
                        async for line in response.aiter_lines():
                            delta = _parse_sse_delta(line)
                            if delta:
                                started_streaming = True
                                yield delta
                return
            except LLMProviderError as exc:
                if started_streaming or not exc.retryable or attempt >= self._max_retries:
                    raise
            except httpx.TimeoutException as exc:
                if started_streaming or attempt >= self._max_retries:
                    raise LLMProviderError(
                        "Le service d'analyse IA met trop de temps à répondre. "
                        "Veuillez réessayer.",
                        detail=f"stream timeout provider={self._provider_name}: {exc}",
                        retryable=True,
                        provider=self._provider_name,
                    ) from exc
            except httpx.HTTPError as exc:
                if started_streaming or attempt >= self._max_retries:
                    raise LLMProviderError(
                        "Le service d'analyse IA est momentanément injoignable. "
                        "Veuillez réessayer.",
                        detail=f"stream http error provider={self._provider_name}: {exc}",
                        retryable=True,
                        provider=self._provider_name,
                    ) from exc
            await self._sleep_backoff(attempt)


def _parse_sse_delta(line: str) -> str | None:
    """Extract the incremental content from one OpenAI-style SSE ``data:`` line."""
    if not line or not line.startswith("data:"):
        return None
    data = line[len("data:") :].strip()
    if not data or data == "[DONE]":
        return None
    try:
        obj = json.loads(data)
    except json.JSONDecodeError:
        return None
    try:
        return obj["choices"][0]["delta"].get("content")
    except (KeyError, IndexError, TypeError):
        return None


def _as_optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
