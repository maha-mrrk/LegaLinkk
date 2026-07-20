"""RAG generation: retrieve → rerank → prompt → grounded LLM answer."""

from __future__ import annotations

import asyncio
import time
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
from app.services.prompt_builder import PromptBuilder
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
    ) -> dict[str, Any]:
        """Full RAG pipeline: embed → retrieve → rerank → LLM."""
        cleaned = (question or "").strip()
        if not cleaned:
            raise ValidationError("Question must not be empty")

        candidate_k = (
            top_k if top_k is not None else self._settings.retrieval_candidate_k
        )
        keep_k = final_k if final_k is not None else self._settings.reranker_final_k
        if candidate_k < 1 or keep_k < 1:
            raise ValidationError("top_k and final_k must be >= 1")
        if candidate_k < keep_k:
            candidate_k = keep_k

        started = time.perf_counter()

        # retrieve_hits logs: Generating query embedding... / Retrieving chunks...
        _, hits, _ = await self._retrieval.retrieve_hits(
            cleaned,
            top_k=candidate_k,
            document_id=document_id,
            log_search_as="Retrieving chunks...",
        )
        logger.info("Retrieved %s candidate chunks.", len(hits))

        logger.info("Reranking...")
        if hits:
            ranked = await asyncio.to_thread(
                self._reranker.rerank_hits,
                cleaned,
                hits,
                final_k=keep_k,
            )
        else:
            ranked = []
        logger.info("Reranked to %s chunks.", len(ranked))

        result = await self.generate_from_chunks(
            cleaned,
            ranked,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        result["metadata"]["top_k"] = candidate_k
        result["metadata"]["final_k"] = keep_k
        result["metadata"]["generation_time"] = round(
            time.perf_counter() - started, 3
        )
        return result

    async def generate_from_chunks(
        self,
        question: str,
        chunks: Sequence[Any],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Generate a grounded answer from already selected chunks.

        Intended for reuse by future agents that bring their own context.
        """
        cleaned = (question or "").strip()
        if not cleaned:
            raise ValidationError("Question must not be empty")

        started = time.perf_counter()
        context_chunks = chunks_from_reranked(chunks)
        no_answer = self._prompt_builder.no_answer_message

        if not context_chunks:
            logger.info("No context chunks — returning grounded no-answer.")
            return self._empty_response(
                answer=no_answer,
                generation_time=round(time.perf_counter() - started, 3),
            )

        logger.info("Building prompt...")
        context_text, used_chunks = merge_chunks(
            context_chunks,
            max_chars=self._settings.rag_max_context_chars,
        )
        prompt = self._prompt_builder.build(question=cleaned, context=context_text)
        sources = build_sources(used_chunks)

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
            "metadata": {
                "provider": llm.provider_name,
                "model": completion.model,
                "tokens_used": completion.total_tokens,
                "prompt_tokens": completion.prompt_tokens,
                "completion_tokens": completion.completion_tokens,
                "generation_time": elapsed,
                "context_chunks": len(used_chunks),
            },
        }

    def _empty_response(
        self,
        *,
        answer: str,
        generation_time: float,
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
            },
        }


# Re-export for agents that want the typed context object.
__all__ = ["GeneratorService", "GenerationError", "ContextChunk"]
