"""Redis-backed ingestion progress tracking.

Exposes the live state of the background ingestion pipeline so the frontend can
show continuous, meaningful progress. The store is keyed by ``document_id`` and
updated as each LangGraph node runs (via an ``on_stage`` callback) so the UI can
poll ``GET /documents/{id}/progress`` and reflect each stage the moment it
starts.

This module holds **no business logic** — it only records/reads progress.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_KEY_PREFIX = "ingestion:progress:"

# Ordered pipeline stages → (friendly label, cumulative progress %).
# OCR is conditional; it only appears when a scanned PDF triggers the fallback.
STAGE_INFO: dict[str, tuple[str, int]] = {
    "queued": ("Queued", 5),
    "extracting": ("Extracting text", 20),
    "ocr": ("Running OCR", 35),
    "cleaning": ("Cleaning document", 50),
    "chunking": ("Creating chunks", 65),
    "embedding": ("Generating embeddings", 80),
    "persisting": ("Saving chunks", 88),
    "indexing": ("Building semantic index", 95),
    "completed": ("Completed", 100),
    "failed": ("Failed", 100),
}

# Map LangGraph node names (and the persist step) to progress stages.
NODE_TO_STAGE: dict[str, str] = {
    "parser": "extracting",
    "ocr": "ocr",
    "cleaning": "cleaning",
    "chunking": "chunking",
    "embedding": "embedding",
    "persist": "persisting",
    "indexing": "indexing",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@lru_cache
def get_redis_client() -> Any | None:
    """Return a shared, thread-safe sync Redis client (or None if unavailable)."""
    settings = get_settings()
    try:
        import redis  # imported lazily so the app still boots without the package

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        return client
    except Exception:
        logger.warning(
            "Redis client unavailable — ingestion progress will not be tracked.",
            exc_info=True,
        )
        return None


class IngestionProgressService:
    """Read/write the live progress of a document's ingestion pipeline."""

    def __init__(self, client: Any | None = None) -> None:
        self._client = client if client is not None else get_redis_client()
        self._ttl = get_settings().ingestion_progress_ttl_seconds

    @property
    def is_available(self) -> bool:
        return self._client is not None

    # --- writes --------------------------------------------------------------

    async def mark_queued(self, document_id: str, task_id: str | None) -> None:
        label, progress = STAGE_INFO["queued"]
        await self._write(
            document_id,
            {
                "document_id": document_id,
                "task_id": task_id,
                "status": "queued",
                "stage": "queued",
                "stage_label": label,
                "progress": progress,
                "message": "Your document is queued for processing…",
                "error": None,
                "updated_at": _now_iso(),
                "timeline": [{"stage": "queued", "label": label, "at": _now_iso()}],
            },
        )
        logger.info("Task queued document_id=%s task_id=%s", document_id, task_id)

    async def report_stage(self, document_id: str, node_or_stage: str) -> None:
        """Record that a pipeline stage has started (called per LangGraph node)."""
        stage = NODE_TO_STAGE.get(node_or_stage, node_or_stage)
        info = STAGE_INFO.get(stage)
        if info is None:
            return
        label, progress = info

        current = await self._read(document_id) or {}
        timeline = list(current.get("timeline") or [])
        timeline.append({"stage": stage, "label": label, "at": _now_iso()})

        await self._write(
            document_id,
            {
                **current,
                "document_id": document_id,
                "status": "processing",
                "stage": stage,
                "stage_label": label,
                "progress": progress,
                "message": f"{label}…",
                "error": None,
                "updated_at": _now_iso(),
                "timeline": timeline,
            },
        )
        logger.info("Stage %s (%s) document_id=%s", stage, label, document_id)

    async def mark_completed(
        self, document_id: str, *, extra: dict[str, Any] | None = None
    ) -> None:
        label, progress = STAGE_INFO["completed"]
        current = await self._read(document_id) or {}
        payload = {
            **current,
            "document_id": document_id,
            "status": "completed",
            "stage": "completed",
            "stage_label": label,
            "progress": progress,
            "message": "Document ready for AI analysis.",
            "error": None,
            "updated_at": _now_iso(),
        }
        if extra:
            payload.update(extra)
        await self._write(document_id, payload)
        logger.info("Document ready document_id=%s", document_id)

    async def mark_failed(
        self, document_id: str, error: str, *, stage: str | None = None
    ) -> None:
        label, _ = STAGE_INFO["failed"]
        current = await self._read(document_id) or {}
        await self._write(
            document_id,
            {
                **current,
                "document_id": document_id,
                "status": "failed",
                "stage": stage or current.get("stage") or "failed",
                "stage_label": label,
                "progress": current.get("progress", 100),
                "message": "Processing failed. Please try again.",
                "error": error,
                "updated_at": _now_iso(),
            },
        )
        logger.error("Ingestion failed document_id=%s error=%s", document_id, error)

    # --- reads ---------------------------------------------------------------

    async def get(self, document_id: str) -> dict[str, Any] | None:
        return await self._read(document_id)

    # --- internals -----------------------------------------------------------

    async def _write(self, document_id: str, payload: dict[str, Any]) -> None:
        if self._client is None:
            return
        key = f"{_KEY_PREFIX}{document_id}"
        data = json.dumps(payload, default=str)
        try:
            await asyncio.to_thread(self._client.set, key, data, self._ttl)
        except Exception:
            logger.debug("Failed to write progress for %s", document_id, exc_info=True)

    async def _read(self, document_id: str) -> dict[str, Any] | None:
        if self._client is None:
            return None
        key = f"{_KEY_PREFIX}{document_id}"
        try:
            raw = await asyncio.to_thread(self._client.get, key)
        except Exception:
            logger.debug("Failed to read progress for %s", document_id, exc_info=True)
            return None
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None


@lru_cache
def get_ingestion_progress_service() -> IngestionProgressService:
    """Return a cached, process-wide progress service."""
    return IngestionProgressService()


__all__ = [
    "IngestionProgressService",
    "get_ingestion_progress_service",
    "get_redis_client",
    "STAGE_INFO",
    "NODE_TO_STAGE",
]
