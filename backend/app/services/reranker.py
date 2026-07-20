"""CrossEncoder reranking of retrieved chunks (ONNX via FastEmbed)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from threading import Lock
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, ValidationError
from app.core.logging import get_logger
from app.repositories.retrieval import RetrievalHit
from app.services.retrieval import RetrievalService

logger = get_logger(__name__)

_model_lock = Lock()


class RerankerError(AppError):
    """Raised when CrossEncoder reranking fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


@dataclass(frozen=True, slots=True)
class RerankedHit:
    """Chunk ready for a future GeneratorService / RAG pipeline."""

    chunk_id: UUID
    document_id: UUID
    filename: str
    text: str
    retrieval_score: float
    reranker_score: float
    page_numbers: list[int]
    extraction_method: str | None
    chunk_index: int
    embedding_model: str
    rank: int


class RerankerService:
    """Rerank vector-retrieved chunks with a multilingual CrossEncoder.

    Preferred: ``BAAI/bge-reranker-v2-m3`` (ONNX when available)
    Fallback: ``cross-encoder/ms-marco-MiniLM-L-6-v2`` → Xenova ONNX
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
        retrieval_service: RetrievalService | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._retrieval = retrieval_service or RetrievalService(
            session, settings=self._settings
        )
        self._model = None
        self._model_name: str | None = None

    @property
    def model_name(self) -> str:
        self._ensure_model()
        assert self._model_name is not None
        return self._model_name

    def score_pairs(self, query: str, texts: list[str]) -> list[float]:
        """Score (query, text) pairs; higher is more relevant."""
        if not texts:
            return []
        self._ensure_model()
        assert self._model is not None
        scores = list(self._model.rerank(query, texts))
        if len(scores) != len(texts):
            raise RerankerError(
                f"Reranker score count mismatch: got {len(scores)} for {len(texts)} texts"
            )
        return [float(s) for s in scores]

    def rerank_hits(
        self,
        query: str,
        hits: list[RetrievalHit],
        *,
        final_k: int,
    ) -> list[RerankedHit]:
        """Order ``hits`` by CrossEncoder score and keep Top ``final_k``."""
        if not hits:
            return []
        if final_k < 1:
            raise ValidationError("final_k must be >= 1")

        texts = [hit.text for hit in hits]
        scores = self.score_pairs(query, texts)
        ranked = sorted(
            zip(hits, scores, strict=True),
            key=lambda item: item[1],
            reverse=True,
        )[:final_k]

        return [
            RerankedHit(
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                filename=hit.filename,
                text=hit.text,
                retrieval_score=hit.similarity,
                reranker_score=score,
                page_numbers=list(hit.page_numbers),
                extraction_method=hit.extraction_method,
                chunk_index=hit.chunk_index,
                embedding_model=hit.embedding_model,
                rank=index + 1,
            )
            for index, (hit, score) in enumerate(ranked)
        ]

    async def retrieve_and_rerank(
        self,
        query: str,
        *,
        top_k: int | None = None,
        final_k: int | None = None,
        document_id: UUID | None = None,
    ) -> dict:
        """Retrieve candidates then rerank for a future RAG generator."""
        candidate_k = (
            top_k
            if top_k is not None
            else self._settings.retrieval_candidate_k
        )
        keep_k = (
            final_k if final_k is not None else self._settings.reranker_final_k
        )
        if keep_k < 1:
            raise ValidationError("final_k must be >= 1")
        if keep_k > 50:
            raise ValidationError("final_k must be <= 50")
        if candidate_k < keep_k:
            # Ensure we retrieve at least as many as we plan to keep.
            candidate_k = keep_k

        cleaned, hits, _ = await self._retrieval.retrieve_hits(
            query,
            top_k=candidate_k,
            document_id=document_id,
            log_search_as="Retrieving vectors...",
        )
        logger.info("Retrieved %s chunks.", len(hits))

        if not hits:
            logger.info("Top 0 chunks selected.")
            logger.info("Reranking completed.")
            return {
                "query": cleaned,
                "top_k": candidate_k,
                "final_k": keep_k,
                "reranker_model": None,
                "results": [],
            }

        logger.info("Running CrossEncoder...")
        try:
            ranked = await asyncio.to_thread(
                self.rerank_hits, cleaned, hits, final_k=keep_k
            )
        except ValidationError:
            raise
        except Exception as exc:
            logger.exception("CrossEncoder reranking failed")
            raise RerankerError("Reranking failed") from exc

        model_name = self.model_name
        logger.info("Top %s chunks selected.", len(ranked))
        logger.info("Reranking completed.")

        return {
            "query": cleaned,
            "top_k": candidate_k,
            "final_k": keep_k,
            "reranker_model": model_name,
            "results": [self._hit_to_dict(item) for item in ranked],
        }

    @staticmethod
    def _hit_to_dict(hit: RerankedHit) -> dict:
        return {
            "chunk_id": hit.chunk_id,
            "document_id": hit.document_id,
            "filename": hit.filename,
            "text": hit.text,
            "retrieval_score": hit.retrieval_score,
            "reranker_score": hit.reranker_score,
            "page_numbers": hit.page_numbers,
            "extraction_method": hit.extraction_method,
            "chunk_index": hit.chunk_index,
            "embedding_model": hit.embedding_model,
            "rank": hit.rank,
        }

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        with _model_lock:
            if self._model is not None:
                return
            self._model, self._model_name = _load_reranker_model(
                preferred=self._settings.reranker_model,
                fallback=self._settings.reranker_fallback_model,
                cache_dir=self._settings.reranker_cache_dir,
            )


def _load_reranker_model(
    *,
    preferred: str,
    fallback: str,
    cache_dir: str,
) -> tuple[object, str]:
    try:
        from fastembed.common.model_description import ModelSource
        from fastembed.rerank.cross_encoder import TextCrossEncoder
    except ImportError as exc:
        raise RerankerError(
            "fastembed CrossEncoder is not available. Upgrade fastembed to enable reranking."
        ) from exc

    _register_custom_onnx_aliases(TextCrossEncoder, ModelSource)

    aliases = {
        "BAAI/bge-reranker-v2-m3": [
            "BAAI/bge-reranker-v2-m3",
            "BAAI/bge-reranker-base",
            "jinaai/jina-reranker-v2-base-multilingual",
        ],
        "cross-encoder/ms-marco-MiniLM-L-6-v2": [
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
            "Xenova/ms-marco-MiniLM-L-6-v2",
        ],
    }

    candidates: list[str] = []
    for name in (preferred, fallback):
        candidates.extend(aliases.get(name, [name]))
    # Always keep a tiny ONNX fallback last.
    candidates.append("Xenova/ms-marco-MiniLM-L-6-v2")

    seen: set[str] = set()
    for name in candidates:
        if name in seen:
            continue
        seen.add(name)
        try:
            logger.info("Loading CrossEncoder reranker %s (FastEmbed/ONNX)", name)
            model = TextCrossEncoder(model_name=name, cache_dir=cache_dir)
            logger.info("CrossEncoder ready: %s", name)
            return model, name
        except Exception:
            logger.exception("Failed to load CrossEncoder model %s", name)

    raise RerankerError(
        f"Unable to load CrossEncoder models ({preferred!r}, {fallback!r})"
    )


def _register_custom_onnx_aliases(text_cross_encoder: type, model_source: type) -> None:
    """Register HuggingFace-style ids that map to ONNX Community / custom repos."""
    customs = [
        {
            "model": "BAAI/bge-reranker-v2-m3",
            "model_file": "model.onnx",
            "sources": model_source(hf="viplao5/bge-reranker-v2-m3-onnx"),
            "size_in_gb": 2.5,
            "additional_files": ["model.onnx_data"],
        },
        {
            "model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
            "model_file": "onnx/model.onnx",
            "sources": model_source(hf="Xenova/ms-marco-MiniLM-L-6-v2"),
            "size_in_gb": 0.08,
        },
    ]
    for spec in customs:
        try:
            text_cross_encoder.add_custom_model(**spec)
        except (ValueError, TypeError, AttributeError):
            # Already registered or older fastembed without add_custom_model.
            continue
