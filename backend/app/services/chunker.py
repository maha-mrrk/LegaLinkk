"""Semantic text chunking with overlap for future embedding / RAG."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.core.logging import get_logger
from app.services.text_cleaner import clean_pages, clean_text

logger = get_logger(__name__)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    """In-memory chunk before persistence."""

    chunk_index: int
    text: str
    page_numbers: list[int]
    metadata: dict


@dataclass(frozen=True, slots=True)
class _Span:
    start: int
    end: int
    page_number: int


class SemanticChunker:
    """Split cleaned text into overlapping chunks that prefer paragraph breaks."""

    def __init__(
        self,
        *,
        chunk_size: int = 900,
        chunk_overlap: int = 175,
    ) -> None:
        if chunk_size < 200:
            raise ValueError("chunk_size must be >= 200")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be >= 0 and < chunk_size")
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def chunk_document(
        self,
        *,
        document_id: UUID,
        text: str,
        pages: list[tuple[int, str]] | None,
        extraction_method: str | None,
        created_at: datetime | None = None,
    ) -> list[ChunkDraft]:
        """Build non-empty semantic chunks with metadata."""
        logger.info(
            "Chunking started for document_id=%s (target_size=%s overlap=%s)",
            document_id,
            self._chunk_size,
            self._chunk_overlap,
        )

        stamp = created_at or datetime.now(timezone.utc)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)

        merged, spans = self._build_merged_text(text=text, pages=pages)
        if not merged:
            logger.warning(
                "Chunking skipped — empty text for document_id=%s", document_id
            )
            return []

        raw_chunks = self._split_text(merged)
        drafts: list[ChunkDraft] = []
        search_from = 0
        for index, chunk_text in enumerate(raw_chunks):
            start = merged.find(chunk_text, search_from)
            if start < 0:
                start = merged.find(chunk_text)
            if start < 0:
                start = search_from
            end = start + len(chunk_text)
            search_from = max(start + 1, end - self._chunk_overlap)

            page_numbers = self._pages_for_span(spans, start, end)
            metadata = {
                "document_id": str(document_id),
                "chunk_index": index,
                "page_numbers": page_numbers,
                "chunk_length": len(chunk_text),
                "extraction_method": extraction_method,
                "created_at": stamp.isoformat(),
            }
            drafts.append(
                ChunkDraft(
                    chunk_index=index,
                    text=chunk_text,
                    page_numbers=page_numbers,
                    metadata=metadata,
                )
            )

        logger.info(
            "Chunking completed for document_id=%s — %s chunks",
            document_id,
            len(drafts),
        )
        return drafts

    def _build_merged_text(
        self,
        *,
        text: str,
        pages: list[tuple[int, str]] | None,
    ) -> tuple[str, list[_Span]]:
        if pages:
            cleaned_pages = clean_pages(pages)
            if cleaned_pages:
                parts: list[str] = []
                spans: list[_Span] = []
                cursor = 0
                for page_number, page_text in cleaned_pages:
                    if parts:
                        parts.append("\n\n")
                        cursor += 2
                    start = cursor
                    parts.append(page_text)
                    cursor += len(page_text)
                    spans.append(
                        _Span(start=start, end=cursor, page_number=page_number)
                    )
                return "".join(parts), spans

        cleaned = clean_text(text)
        if not cleaned:
            return "", []
        return cleaned, [_Span(start=0, end=len(cleaned), page_number=1)]

    def _split_text(self, text: str) -> list[str]:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if not paragraphs:
            return []

        chunks: list[str] = []
        current_parts: list[str] = []

        def current_len() -> int:
            if not current_parts:
                return 0
            return sum(len(p) for p in current_parts) + 2 * (len(current_parts) - 1)

        def emit() -> None:
            nonlocal current_parts
            chunk = "\n\n".join(current_parts).strip()
            if chunk:
                chunks.append(chunk)
            if chunk and self._chunk_overlap > 0:
                overlap = chunk[-self._chunk_overlap :].strip()
                overlap = self._align_overlap(overlap)
                current_parts = [overlap] if overlap else []
            else:
                current_parts = []

        for paragraph in paragraphs:
            if len(paragraph) > self._chunk_size:
                if current_parts:
                    emit()
                for piece in self._split_long_unit(paragraph):
                    if piece:
                        chunks.append(piece)
                # Seed overlap from last hard-split piece
                if chunks and self._chunk_overlap > 0:
                    overlap = self._align_overlap(chunks[-1][-self._chunk_overlap :])
                    current_parts = [overlap] if overlap else []
                continue

            projected = current_len() + (2 if current_parts else 0) + len(paragraph)
            if current_parts and projected > self._chunk_size:
                emit()
            current_parts.append(paragraph)

        if current_parts:
            chunk = "\n\n".join(current_parts).strip()
            if chunk:
                # Avoid emitting a tiny leftover that is only overlap residue
                if chunks and chunk == self._align_overlap(chunks[-1][-self._chunk_overlap :]):
                    pass
                else:
                    chunks.append(chunk)

        return [c for c in chunks if c.strip()]

    def _split_long_unit(self, text: str) -> list[str]:
        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
        units = sentences if len(sentences) > 1 else None
        if units is None:
            step = max(1, self._chunk_size - self._chunk_overlap)
            return [
                text[i : i + self._chunk_size].strip()
                for i in range(0, len(text), step)
                if text[i : i + self._chunk_size].strip()
            ]

        pieces: list[str] = []
        current = ""
        for sentence in units:
            candidate = f"{current} {sentence}".strip() if current else sentence
            if current and len(candidate) > self._chunk_size:
                pieces.append(current)
                if self._chunk_overlap > 0:
                    overlap = self._align_overlap(current[-self._chunk_overlap :])
                    current = f"{overlap} {sentence}".strip() if overlap else sentence
                else:
                    current = sentence
            else:
                current = candidate
        if current.strip():
            pieces.append(current.strip())
        return pieces

    @staticmethod
    def _align_overlap(overlap: str) -> str:
        overlap = overlap.strip()
        if not overlap:
            return ""
        for sep in ("\n\n", "\n", ". ", "! ", "? ", "… "):
            idx = overlap.find(sep)
            if 0 <= idx < len(overlap) - len(sep):
                trimmed = overlap[idx + len(sep) :].strip()
                if trimmed:
                    return trimmed
        return overlap

    @staticmethod
    def _pages_for_span(spans: list[_Span], start: int, end: int) -> list[int]:
        if not spans:
            return []
        return sorted(
            {
                span.page_number
                for span in spans
                if span.page_number > 0 and span.start < end and span.end > start
            }
        )
