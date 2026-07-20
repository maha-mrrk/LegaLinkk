"""Utilities to format retrieved/reranked chunks into LLM context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ContextChunk:
    """Normalized chunk used for prompt context and source citations."""

    chunk_id: UUID
    document_id: UUID
    filename: str
    text: str
    score: float
    page_numbers: list[int]
    extraction_method: str | None = None
    rank: int | None = None


def chunks_from_reranked(results: Sequence[Any]) -> list[ContextChunk]:
    """Normalize ``RerankedHit`` objects or dicts into ``ContextChunk``."""
    chunks: list[ContextChunk] = []
    for item in results:
        if hasattr(item, "chunk_id"):
            pages = list(getattr(item, "page_numbers", []) or [])
            chunks.append(
                ContextChunk(
                    chunk_id=item.chunk_id,
                    document_id=item.document_id,
                    filename=item.filename,
                    text=item.text,
                    score=float(
                        getattr(item, "reranker_score", None)
                        or getattr(item, "retrieval_score", 0.0)
                    ),
                    page_numbers=[int(p) for p in pages],
                    extraction_method=getattr(item, "extraction_method", None),
                    rank=getattr(item, "rank", None),
                )
            )
            continue

        data = dict(item)
        pages = list(data.get("page_numbers") or [])
        chunks.append(
            ContextChunk(
                chunk_id=UUID(str(data["chunk_id"])),
                document_id=UUID(str(data["document_id"])),
                filename=str(data.get("filename") or ""),
                text=str(data.get("text") or ""),
                score=float(
                    data.get("reranker_score")
                    if data.get("reranker_score") is not None
                    else data.get("retrieval_score")
                    if data.get("retrieval_score") is not None
                    else data.get("similarity")
                    or 0.0
                ),
                page_numbers=[int(p) for p in pages],
                extraction_method=data.get("extraction_method"),
                rank=data.get("rank"),
            )
        )
    return chunks


def dedupe_chunks(chunks: Sequence[ContextChunk]) -> list[ContextChunk]:
    """Remove duplicate chunks by ``chunk_id`` (keep first / highest rank)."""
    seen: set[UUID] = set()
    unique: list[ContextChunk] = []
    for chunk in chunks:
        if chunk.chunk_id in seen:
            continue
        if not (chunk.text or "").strip():
            continue
        seen.add(chunk.chunk_id)
        unique.append(chunk)
    return unique


def merge_chunks(
    chunks: Sequence[ContextChunk],
    *,
    max_chars: int = 12000,
) -> tuple[str, list[ContextChunk]]:
    """Merge chunks into a single context string within ``max_chars``.

    Preserves document names and page references. Returns the formatted
    context and the list of chunks that actually fit in the window.
    """
    unique = dedupe_chunks(chunks)
    if max_chars < 1:
        return "", []

    parts: list[str] = []
    used: list[ContextChunk] = []
    used_chars = 0

    for index, chunk in enumerate(unique, start=1):
        pages = ", ".join(str(p) for p in chunk.page_numbers) or "n/a"
        header = (
            f"[Source {index}] Document: {chunk.filename} "
            f"| Pages: {pages} | chunk_id: {chunk.chunk_id}"
        )
        block = f"{header}\n{chunk.text.strip()}\n"
        # Leave room for separators between blocks.
        separator = "\n---\n" if parts else ""
        addition = len(separator) + len(block)
        if used_chars + addition > max_chars:
            remaining = max_chars - used_chars - len(separator)
            if remaining < 80:
                break
            truncated = block[: max(0, remaining - 20)].rstrip() + "\n...[truncated]\n"
            parts.append(separator + truncated)
            used.append(chunk)
            break
        parts.append(separator + block)
        used.append(chunk)
        used_chars += addition

    return "".join(parts).strip(), used


def build_sources(chunks: Sequence[ContextChunk]) -> list[dict[str, Any]]:
    """Build citation payloads for the API response."""
    sources: list[dict[str, Any]] = []
    for chunk in chunks:
        page = chunk.page_numbers[0] if chunk.page_numbers else None
        sources.append(
            {
                "document_id": chunk.document_id,
                "filename": chunk.filename,
                "page": page,
                "chunk_id": chunk.chunk_id,
                "score": chunk.score,
                "page_numbers": list(chunk.page_numbers),
            }
        )
    return sources
