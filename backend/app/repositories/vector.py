"""Backward-compatible re-exports for the embedding repository."""

from app.repositories.embedding import (
    EmbeddingRecord as VectorRecord,
    EmbeddingRepository as VectorRepository,
)

__all__ = ["VectorRecord", "VectorRepository"]
