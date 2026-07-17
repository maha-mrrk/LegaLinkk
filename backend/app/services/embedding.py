"""Embedding generation with multilingual models (bge-m3 / e5-large)."""

from __future__ import annotations

from functools import lru_cache
from threading import Lock

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_model_lock = Lock()


class EmbeddingError(Exception):
    """Raised when embedding model loading or inference fails."""


class EmbeddingService:
    """Generate dense vectors for document chunks via FastEmbed (ONNX).

    Preferred model: ``BAAI/bge-m3``
    Fallback: ``intfloat/multilingual-e5-large``
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._model = None
        self._model_name: str | None = None
        self._is_e5 = False

    @property
    def model_name(self) -> str:
        self._ensure_model()
        assert self._model_name is not None
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._settings.embedding_dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of chunk texts (passage / document style)."""
        if not texts:
            return []
        self._ensure_model()
        assert self._model is not None

        prepared = [self._prepare_passage(text) for text in texts]
        logger.info("Generating embeddings... (%s texts)", len(prepared))

        batch_size = max(1, self._settings.embedding_batch_size)
        vectors: list[list[float]] = []
        total = len(prepared)

        for start in range(0, total, batch_size):
            batch = prepared[start : start + batch_size]
            end = min(start + len(batch), total)
            logger.info("Embedding %s/%s", end, total)
            # FastEmbed yields numpy arrays / lists per text.
            for row in self._model.embed(batch, batch_size=len(batch)):
                vector = [float(x) for x in list(row)]
                if len(vector) != self._settings.embedding_dimension:
                    raise EmbeddingError(
                        f"Unexpected embedding dimension {len(vector)}; "
                        f"expected {self._settings.embedding_dimension}"
                    )
                vectors.append(vector)

        if len(vectors) != len(texts):
            raise EmbeddingError(
                f"Embedding count mismatch: got {len(vectors)} for {len(texts)} texts"
            )
        return vectors

    def _prepare_passage(self, text: str) -> str:
        cleaned = (text or "").strip()
        if not cleaned:
            cleaned = " "
        if self._is_e5:
            return f"passage: {cleaned}"
        return cleaned

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        with _model_lock:
            if self._model is not None:
                return
            self._model, self._model_name, self._is_e5 = _load_embedding_model(
                preferred=self._settings.embedding_model,
                fallback=self._settings.embedding_fallback_model,
                cache_dir=self._settings.embedding_cache_dir,
            )


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Process-wide cached embedding service (heavy model load)."""
    return EmbeddingService()


def _load_embedding_model(
    *,
    preferred: str,
    fallback: str,
    cache_dir: str,
) -> tuple[object, str, bool]:
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise EmbeddingError(
            "fastembed is not installed. Install backend dependencies to enable indexing."
        ) from exc

    candidates = [preferred, fallback]
    # Common FastEmbed aliases if HuggingFace-style ids are rejected.
    aliases = {
        "BAAI/bge-m3": ["BAAI/bge-m3"],
        "intfloat/multilingual-e5-large": [
            "intfloat/multilingual-e5-large",
            "intfloat/multilingual-e5-base",
        ],
    }
    expanded: list[str] = []
    for name in candidates:
        expanded.extend(aliases.get(name, [name]))

    seen: set[str] = set()
    for name in expanded:
        if name in seen:
            continue
        seen.add(name)
        try:
            logger.info("Loading embedding model %s (FastEmbed/ONNX)", name)
            model = TextEmbedding(model_name=name, cache_dir=cache_dir)
            is_e5 = "e5" in name.lower()
            logger.info("Embedding model ready: %s", name)
            return model, name, is_e5
        except Exception:
            logger.exception("Failed to load embedding model %s", name)

    raise EmbeddingError(
        f"Unable to load embedding models ({preferred!r}, {fallback!r})"
    )
