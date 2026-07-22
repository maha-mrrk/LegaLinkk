"""RAG generation: retrieve → rerank → prompt → grounded LLM answer."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, ValidationError
from app.core.logging import get_logger
from app.services.context_formatter import (
    ContextChunk,
    build_sources,
    chunks_from_reranked,
    merge_chunks,
)
from app.services.llm import LLMProvider, get_llm_provider
from app.services.llm.openai_compatible import LLMProviderError
from app.services.prompt_builder import DOCUMENT_SYSTEM_INSTRUCTIONS, PromptBuilder
from app.services.reranker import RerankerService
from app.services.retrieval import RetrievalService

logger = get_logger(__name__)


class GenerationError(AppError):
    """Raised when grounded answer generation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class GeneratorService:
    """Reusable grounded generation engine for future multi-agent orchestration.

    Agents (Legal / Finance / Compliance / Report) can call:
    - ``answer_question`` for the full RAG pipeline
    - ``generate_from_chunks`` when chunks are already selected
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
        retrieval_service: RetrievalService | None = None,
        reranker_service: RerankerService | None = None,
        llm_provider: LLMProvider | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._retrieval = retrieval_service or RetrievalService(
            session, settings=self._settings
        )
        self._reranker = reranker_service or RerankerService(
            session,
            settings=self._settings,
            retrieval_service=self._retrieval,
        )
        self._llm = llm_provider
        self._prompt_builder = prompt_builder or PromptBuilder(
            no_answer_message=self._settings.rag_no_answer_message
        )

    def _get_llm(self) -> LLMProvider:
        if self._llm is None:
            self._llm = get_llm_provider(self._settings)
        return self._llm

    async def answer_question(
        self,
        question: str,
        *,
        top_k: int | None = None,
        final_k: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        document_id: UUID | None = None,
        history: Sequence[dict[str, str]] | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Full RAG pipeline: embed → retrieve → rerank → LLM."""
        cleaned = (question or "").strip()
        if not cleaned:
            raise ValidationError("Question must not be empty")

        logger.info(
            "Question received chars=%s document_id=%s history_turns=%s",
            len(cleaned),
            document_id,
            len(history or []),
        )
        started = time.perf_counter()
        ranked, candidate_k, keep_k = await self._retrieve_and_rerank(
            cleaned, top_k=top_k, final_k=final_k, document_id=document_id
        )

        result = await self.generate_from_chunks(
            cleaned,
            ranked,
            temperature=temperature,
            max_tokens=max_tokens,
            history=history,
            system_prompt=system_prompt,
        )
        result["metadata"]["top_k"] = candidate_k
        result["metadata"]["final_k"] = keep_k
        result["metadata"]["history_turns"] = len(history or [])
        result["metadata"]["generation_time"] = round(
            time.perf_counter() - started, 3
        )
        return result

    async def _retrieve_and_rerank(
        self,
        question: str,
        *,
        top_k: int | None,
        final_k: int | None,
        document_id: UUID | None,
    ) -> tuple[list[Any], int, int]:
        """Embed → retrieve → rerank. Shared by full-answer and streaming paths.

        In **all-documents** mode (``document_id is None``) plain Top-K tends to
        concentrate on whichever document has the most matching chunks. To span
        the whole library we widen the candidate pool and diversify the final
        selection so no single document dominates the context.
        """
        candidate_k = (
            top_k if top_k is not None else self._settings.retrieval_candidate_k
        )
        keep_k = final_k if final_k is not None else self._settings.reranker_final_k
        if candidate_k < 1 or keep_k < 1:
            raise ValidationError("top_k and final_k must be >= 1")

        all_docs = document_id is None
        if all_docs:
            # Broaden coverage across the library (bounded by the SQL limit of 50).
            candidate_k = max(candidate_k, self._settings.multi_doc_candidate_k)
            keep_k = max(keep_k, self._settings.multi_doc_final_k)
        candidate_k = min(candidate_k, 50)
        keep_k = min(keep_k, 50)
        if candidate_k < keep_k:
            candidate_k = keep_k

        # retrieve_hits logs: Generating query embedding... / Retrieving chunks...
        _, hits, _ = await self._retrieval.retrieve_hits(
            question,
            top_k=candidate_k,
            document_id=document_id,
            log_search_as="Retrieving chunks...",
        )
        logger.info("Retrieved %s candidate chunks.", len(hits))

        logger.info("Reranking...")
        if not hits:
            ranked: list[Any] = []
        elif all_docs:
            # Rerank the whole candidate pool, then cap per-document contribution
            # so the final context spans several documents.
            reranked_all = await asyncio.to_thread(
                self._reranker.rerank_hits,
                question,
                hits,
                final_k=len(hits),
            )
            ranked = _diversify_by_document(
                reranked_all,
                keep_k=keep_k,
                per_doc_cap=self._settings.multi_doc_per_document_cap,
            )
            distinct_docs = len({getattr(h, "document_id", None) for h in ranked})
            logger.info(
                "All-documents mode: kept %s chunks across %s documents.",
                len(ranked),
                distinct_docs,
            )
        else:
            ranked = await asyncio.to_thread(
                self._reranker.rerank_hits,
                question,
                hits,
                final_k=keep_k,
            )
        logger.info("Reranked to %s chunks.", len(ranked))
        return ranked, candidate_k, keep_k

    def _prepare_prompt(
        self,
        question: str,
        chunks: Sequence[Any],
        *,
        history: Sequence[dict[str, str]] | None,
        system_prompt: str | None,
    ) -> tuple[Any | None, list[dict[str, Any]], str, list[Any]]:
        """Build the grounded prompt + sources from chunks (single source of truth).

        Returns ``(prompt, sources, context_text, used_chunks)``; ``prompt`` is
        None when there is no usable context.
        """
        context_chunks = chunks_from_reranked(chunks)
        if not context_chunks:
            return None, [], "", []

        logger.info("Building prompt...")
        context_text, used_chunks = merge_chunks(
            context_chunks,
            max_chars=self._settings.rag_max_context_chars,
        )
        prompt = self._prompt_builder.build(
            question=question,
            context=context_text,
            history=history,
            system_prompt=system_prompt,
        )
        sources = build_sources(used_chunks)
        return prompt, sources, context_text, used_chunks

    async def stream_answer(
        self,
        question: str,
        *,
        top_k: int | None = None,
        final_k: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        document_id: UUID | None = None,
        history: Sequence[dict[str, str]] | None = None,
        system_prompt: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream a grounded answer as it is generated.

        Reuses the same retrieval/rerank/prompt logic as ``answer_question`` and
        yields events: ``{"type": "sources", ...}``, then incremental
        ``{"type": "delta", "text": ...}``, and finally
        ``{"type": "done", "metadata": ...}``.
        """
        cleaned = (question or "").strip()
        if not cleaned:
            raise ValidationError("Question must not be empty")

        logger.info(
            "Question received (stream) chars=%s document_id=%s history_turns=%s",
            len(cleaned),
            document_id,
            len(history or []),
        )
        started = time.perf_counter()
        no_answer = self._prompt_builder.no_answer_message
        ranked, candidate_k, keep_k = await self._retrieve_and_rerank(
            cleaned, top_k=top_k, final_k=final_k, document_id=document_id
        )
        prompt, sources, _context_text, used_chunks = self._prepare_prompt(
            cleaned, ranked, history=history, system_prompt=system_prompt
        )

        yield {"type": "sources", "sources": sources}

        if prompt is None:
            logger.info("No context chunks — streaming grounded no-answer.")
            yield {"type": "delta", "text": no_answer}
            yield {
                "type": "done",
                "metadata": self._empty_response(
                    answer=no_answer,
                    generation_time=round(time.perf_counter() - started, 3),
                    history_turns=len(history or []),
                )["metadata"],
            }
            return

        llm = self._get_llm()
        logger.info("Streaming answer...")
        messages = prompt.as_messages()
        parts: list[str] = []
        try:
            async for delta in llm.stream_complete(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                parts.append(delta)
                yield {"type": "delta", "text": delta}
        except LLMProviderError:
            raise
        except Exception as exc:
            logger.exception("LLM streaming failed")
            raise GenerationError("Failed to stream grounded answer") from exc

        answer = "".join(parts).strip()
        if not answer:
            # Some providers/models can finish a stream without emitting any
            # content deltas. Never leave the user with a blank answer: fall
            # back to a single blocking completion and emit it as one fragment.
            logger.warning(
                "Stream produced no content — falling back to a blocking completion."
            )
            try:
                completion = await llm.complete(
                    messages, temperature=temperature, max_tokens=max_tokens
                )
                answer = (completion.content or "").strip()
            except LLMProviderError:
                raise
            except Exception as exc:
                logger.exception("LLM fallback generation failed")
                raise GenerationError("Failed to generate grounded answer") from exc
            if answer:
                yield {"type": "delta", "text": answer}

        if not answer:
            answer = no_answer
            yield {"type": "delta", "text": answer}

        elapsed = round(time.perf_counter() - started, 3)
        logger.info(
            "Streaming completed provider=%s model=%s chars=%s elapsed=%ss",
            llm.provider_name,
            llm.model,
            len(answer),
            elapsed,
        )
        yield {
            # ``answer`` lets the client render the full reply even if it missed
            # or could not accumulate the incremental fragments.
            "type": "done",
            "answer": answer,
            "metadata": {
                "provider": llm.provider_name,
                "model": llm.model,
                "generation_time": elapsed,
                "context_chunks": len(used_chunks),
                "history_turns": len(history or []),
                "top_k": candidate_k,
                "final_k": keep_k,
                "answer_chars": len(answer),
            },
        }

    async def generate_from_chunks(
        self,
        question: str,
        chunks: Sequence[Any],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        history: Sequence[dict[str, str]] | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Generate a grounded answer from already selected chunks.

        Intended for reuse by future agents that bring their own context.
        """
        cleaned = (question or "").strip()
        if not cleaned:
            raise ValidationError("Question must not be empty")

        started = time.perf_counter()
        no_answer = self._prompt_builder.no_answer_message
        prompt, sources, context_text, used_chunks = self._prepare_prompt(
            cleaned, chunks, history=history, system_prompt=system_prompt
        )

        if prompt is None:
            logger.info("No context chunks — returning grounded no-answer.")
            result = self._empty_response(
                answer=no_answer,
                generation_time=round(time.perf_counter() - started, 3),
                history_turns=len(history or []),
            )
            result["context_text"] = ""
            return result

        logger.info("Calling LLM...")
        logger.info("Generating answer...")
        try:
            llm = self._get_llm()
            completion = await llm.complete(
                prompt.as_messages(),
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except LLMProviderError:
            raise
        except Exception as exc:
            logger.exception("LLM generation failed")
            raise GenerationError("Failed to generate grounded answer") from exc

        answer = (completion.content or "").strip() or no_answer
        elapsed = round(time.perf_counter() - started, 3)
        logger.info("Generation completed.")

        return {
            "answer": answer,
            "sources": sources,
            # Internal reuse (e.g. LegalAgent risk rules); not exposed by chat API.
            "context_text": context_text,
            "metadata": {
                "provider": llm.provider_name,
                "model": completion.model,
                "tokens_used": completion.total_tokens,
                "prompt_tokens": completion.prompt_tokens,
                "completion_tokens": completion.completion_tokens,
                "generation_time": elapsed,
                "context_chunks": len(used_chunks),
                "history_turns": len(history or []),
            },
        }

    async def generate_document(
        self,
        question: str,
        *,
        top_k: int | None = None,
        final_k: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        document_id: UUID | None = None,
        history: Sequence[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Generate a grounded, self-contained HTML document (printable to PDF).

        Reuses the same retrieval/rerank pipeline as ``answer_question`` but asks
        the LLM (via a dedicated system prompt) for a full HTML document instead
        of a plain-text answer. Returns ``{html, sources, metadata}``.
        """
        cleaned = (question or "").strip()
        if not cleaned:
            raise ValidationError("Question must not be empty")

        logger.info("Document generation requested chars=%s", len(cleaned))
        started = time.perf_counter()
        ranked, candidate_k, keep_k = await self._retrieve_and_rerank(
            cleaned, top_k=top_k, final_k=final_k, document_id=document_id
        )
        prompt, sources, _context_text, used_chunks = self._prepare_prompt(
            cleaned,
            ranked,
            history=history,
            system_prompt=DOCUMENT_SYSTEM_INSTRUCTIONS,
        )

        if prompt is None:
            logger.info("No context chunks — returning grounded no-answer document.")
            return {
                "html": _wrap_html(
                    "Document indisponible",
                    f"<p>{self._prompt_builder.no_answer_message}</p>",
                ),
                "sources": [],
                "metadata": self._empty_response(
                    answer="",
                    generation_time=round(time.perf_counter() - started, 3),
                    history_turns=len(history or []),
                )["metadata"],
            }

        # Documents need a larger completion budget than a chat reply.
        budget = max_tokens or max(self._settings.llm_max_tokens, 6000)
        logger.info("Generating document (max_tokens=%s)...", budget)
        try:
            llm = self._get_llm()
            completion = await llm.complete(
                prompt.as_messages(),
                temperature=temperature,
                max_tokens=budget,
            )
        except LLMProviderError:
            raise
        except Exception as exc:
            logger.exception("Document generation failed")
            raise GenerationError("Failed to generate document") from exc

        html = _extract_html(completion.content or "")
        elapsed = round(time.perf_counter() - started, 3)
        logger.info("Document generated chars=%s elapsed=%ss", len(html), elapsed)

        return {
            "html": html,
            "sources": sources,
            "metadata": {
                "provider": llm.provider_name,
                "model": completion.model,
                "tokens_used": completion.total_tokens,
                "prompt_tokens": completion.prompt_tokens,
                "completion_tokens": completion.completion_tokens,
                "generation_time": elapsed,
                "context_chunks": len(used_chunks),
                "history_turns": len(history or []),
                "top_k": candidate_k,
                "final_k": keep_k,
            },
        }

    def _empty_response(
        self,
        *,
        answer: str,
        generation_time: float,
        history_turns: int = 0,
    ) -> dict[str, Any]:
        provider_name = (self._settings.llm_provider or "openai").strip().lower()
        model = (self._settings.llm_model or "").strip() or None
        return {
            "answer": answer,
            "sources": [],
            "metadata": {
                "provider": provider_name,
                "model": model,
                "tokens_used": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "generation_time": generation_time,
                "context_chunks": 0,
                "history_turns": history_turns,
            },
        }


def _diversify_by_document(
    ranked: list[Any], *, keep_k: int, per_doc_cap: int
) -> list[Any]:
    """Select up to ``keep_k`` chunks in score order while capping how many come
    from any single document (``per_doc_cap``), then back-fill remaining slots
    with the best leftover chunks.

    ``ranked`` must already be sorted best-first. This spreads the final context
    across multiple documents for library-wide ("all documents") questions,
    without discarding relevance ordering.
    """
    if keep_k <= 0:
        return []
    cap = max(1, per_doc_cap)
    selected: list[Any] = []
    overflow: list[Any] = []
    per_doc: dict[Any, int] = {}
    for hit in ranked:
        doc_id = getattr(hit, "document_id", None)
        if per_doc.get(doc_id, 0) < cap:
            selected.append(hit)
            per_doc[doc_id] = per_doc.get(doc_id, 0) + 1
            if len(selected) >= keep_k:
                return selected
        else:
            overflow.append(hit)
    for hit in overflow:
        if len(selected) >= keep_k:
            break
        selected.append(hit)
    return selected[:keep_k]


def _wrap_html(title: str, body_html: str) -> str:
    """Wrap plain content in a minimal, print-friendly HTML document."""
    safe_title = (title or "Document").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!DOCTYPE html>\n"
        '<html lang="fr">\n<head>\n<meta charset="utf-8"/>\n'
        f"<title>{safe_title}</title>\n"
        "<style>body{font-family:Georgia,'Times New Roman',serif;color:#1f2937;"
        "max-width:800px;margin:2rem auto;padding:0 1.5rem;line-height:1.6}"
        "h1{font-size:1.6rem}h2{font-size:1.2rem;margin-top:1.5rem}"
        "@media print{body{margin:0}}</style>\n</head>\n"
        f"<body>\n<h1>{safe_title}</h1>\n{body_html}\n</body>\n</html>"
    )


def _extract_html(text: str) -> str:
    """Normalise the model output into a full, standalone HTML document.

    Handles the common cases where the model wraps HTML in a ```html code fence
    or returns plain text instead of markup.
    """
    content = (text or "").strip()
    if not content:
        return _wrap_html("Document", "<p>Document vide.</p>")

    # Strip a leading/trailing markdown code fence (```html ... ``` or ``` ... ```).
    if content.startswith("```"):
        first_newline = content.find("\n")
        if first_newline != -1:
            content = content[first_newline + 1 :]
        if content.rstrip().endswith("```"):
            content = content.rstrip()[: -3]
        content = content.strip()

    lowered = content.lower()
    if "<!doctype html" in lowered or "<html" in lowered:
        return content

    # The model returned prose/partial markup — wrap it so it still renders.
    return _wrap_html("Document", content)


# Re-export for agents that want the typed context object.
__all__ = ["GeneratorService", "GenerationError", "ContextChunk"]
