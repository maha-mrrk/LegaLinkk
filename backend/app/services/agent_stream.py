"""Streaming multi-agent orchestration for the chat composer.

Mirrors the non-streaming ``multi_agent_graph`` behavior but yields Server-Sent
Event dicts so the UI can render agent answers progressively (token-by-token),
exactly like the plain RAG chat stream.

Routing is driven by the leading ``/command`` in the question:

* ``/legal`` | ``/finance`` | ``/compliance`` → stream ONE specialized agent's
  grounded answer (reuses ``GeneratorService.stream_answer`` with that agent's
  system prompt).
* no command → run the three agents (blocking, with progress events), then
  STREAM the synthesis recommendation built from their three analyses.

Business logic stays in the shared services (retrieval / rerank / generation and
the LLM provider); the specialized prompts remain the single source of truth
(imported from the agent modules). This service only orchestrates them for the
streaming transport — it introduces no new business logic.
"""

from __future__ import annotations

import re
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from app.agents.legal import LEGAL_SYSTEM_PROMPT
from app.agents.nodes.agent_prompts import (
    COMPLIANCE_SYSTEM_PROMPT,
    FINANCE_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
)
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.services.generator import GeneratorService
from app.services.llm import LLMProvider, get_llm_provider

logger = get_logger(__name__)

# Same leading-command detection as CommandParserNode (single source of routing).
_COMMAND_RE = re.compile(
    r"^\s*/(legal|finance|compliance)\b[ \t]*(.*)$",
    re.IGNORECASE | re.DOTALL,
)
_DEFAULT_QUESTION = "Analyse ce contrat en détail."

# domain -> (public agent name, specialized system prompt, human label)
_DOMAINS: dict[str, tuple[str, str, str]] = {
    "legal": ("LegalAgent", LEGAL_SYSTEM_PROMPT, "Analyse juridique (Legal)"),
    "finance": (
        "FinanceAgent",
        FINANCE_SYSTEM_PROMPT,
        "Analyse financière (Finance)",
    ),
    "compliance": (
        "ComplianceAgent",
        COMPLIANCE_SYSTEM_PROMPT,
        "Analyse conformité (Compliance)",
    ),
}
_MULTI_ORDER: tuple[str, ...] = ("legal", "finance", "compliance")


class AgentStreamService:
    """Stream a single agent's answer, or a multi-agent synthesis, over SSE."""

    def __init__(
        self,
        generator: GeneratorService,
        *,
        settings: Settings | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self._generator = generator
        self._settings = settings or get_settings()
        self._llm = llm_provider

    def _get_llm(self) -> LLMProvider:
        if self._llm is None:
            self._llm = get_llm_provider(self._settings)
        return self._llm

    async def stream(
        self,
        question: str,
        *,
        user_id: UUID,
        document_id: UUID | None = None,
        top_k: int | None = None,
        final_k: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Route by leading ``/command`` and yield SSE event dicts."""
        raw = (question or "").strip()
        match = _COMMAND_RE.match(raw)
        if match:
            domain = match.group(1).lower()
            remainder = (match.group(2) or "").strip() or _DEFAULT_QUESTION
            async for event in self._stream_single(
                domain,
                remainder,
                user_id=user_id,
                document_id=document_id,
                top_k=top_k,
                final_k=final_k,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                yield event
            return

        async for event in self._stream_multi(
            raw,
            user_id=user_id,
            document_id=document_id,
            top_k=top_k,
            final_k=final_k,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield event

    async def _stream_single(
        self,
        domain: str,
        question: str,
        *,
        user_id: UUID,
        document_id: UUID | None,
        top_k: int | None,
        final_k: int | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> AsyncIterator[dict[str, Any]]:
        agent_name, system_prompt, _label = _DOMAINS[domain]
        logger.info("[agent_stream] single domain=%s document_id=%s", domain, document_id)
        # Tell the UI which agent is answering before any content flows.
        yield {"type": "agent", "mode": "single", "domain": domain, "label": agent_name}
        async for event in self._generator.stream_answer(
            question,
            user_id=user_id,
            top_k=top_k,
            final_k=final_k,
            temperature=temperature,
            max_tokens=max_tokens,
            document_id=document_id,
            system_prompt=system_prompt,
        ):
            yield event

    async def _stream_multi(
        self,
        question: str,
        *,
        user_id: UUID,
        document_id: UUID | None,
        top_k: int | None,
        final_k: int | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> AsyncIterator[dict[str, Any]]:
        logger.info("[agent_stream] multi (synthesis) document_id=%s", document_id)
        yield {"type": "agent", "mode": "multi"}
        started = time.perf_counter()

        analyses_public: list[dict[str, Any]] = []
        analyses_for_synth: list[tuple[str, str]] = []
        for domain in _MULTI_ORDER:
            agent_name, system_prompt, label = _DOMAINS[domain]
            yield {"type": "status", "domain": domain, "message": f"{label}…"}
            try:
                rag = await self._generator.answer_question(
                    question,
                    user_id=user_id,
                    top_k=top_k,
                    final_k=final_k,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    document_id=document_id,
                    system_prompt=system_prompt,
                )
                answer = (rag.get("answer") or "").strip()
                analyses_public.append(
                    {
                        "domain": domain,
                        "label": agent_name,
                        "status": "ok",
                        "answer": answer,
                        "sources": list(rag.get("sources") or []),
                    }
                )
                if answer:
                    analyses_for_synth.append((label, answer))
            except Exception as exc:  # graceful degradation: keep the other agents
                logger.exception("[agent_stream] domain=%s failed", domain)
                message = (
                    exc.message
                    if isinstance(exc, AppError)
                    else "L'analyse spécialisée a échoué."
                )
                analyses_public.append(
                    {
                        "domain": domain,
                        "label": agent_name,
                        "status": "error",
                        "answer": "",
                        "sources": [],
                        "message": message,
                    }
                )

        # Hand the three analyses to the UI so it can render the collapsible
        # detail behind the synthesis before the recommendation streams in.
        yield {"type": "analyses", "analyses": analyses_public}

        if not analyses_for_synth:
            fallback = (
                "Aucune analyse spécialisée n'a pu être produite pour ce contrat. "
                "Veuillez réessayer."
            )
            yield {"type": "delta", "text": fallback}
            yield {
                "type": "done",
                "answer": fallback,
                "metadata": {
                    "generation_time": round(time.perf_counter() - started, 3)
                },
            }
            return

        sections = [f"### {label}\n{answer}" for label, answer in analyses_for_synth]
        user_prompt = (
            "Voici les analyses spécialisées d'un même contrat. Produis une "
            "recommandation globale qui les croise et les pondère explicitement.\n\n"
            + "\n\n".join(sections)
        )
        messages = [
            {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        llm = self._get_llm()
        parts: list[str] = []
        try:
            async for delta in llm.stream_complete(
                messages, temperature=self._settings.llm_temperature
            ):
                parts.append(delta)
                yield {"type": "delta", "text": delta}
        except Exception:
            logger.exception("[agent_stream] synthesis streaming failed")
            # Some providers can fail mid-stream: fall back to one blocking call.
            if not parts:
                try:
                    completion = await llm.complete(
                        messages, temperature=self._settings.llm_temperature
                    )
                    text = (completion.content or "").strip()
                    if text:
                        parts.append(text)
                        yield {"type": "delta", "text": text}
                except Exception:
                    logger.exception("[agent_stream] synthesis fallback failed")

        answer = "".join(parts).strip() or "La synthèse n'a pas pu être générée."
        elapsed = round(time.perf_counter() - started, 3)
        logger.info("[agent_stream] synthesis done chars=%s elapsed=%ss", len(answer), elapsed)
        yield {
            "type": "done",
            "answer": answer,
            "metadata": {
                "provider": llm.provider_name,
                "model": llm.model,
                "generation_time": elapsed,
            },
        }


__all__ = ["AgentStreamService"]
