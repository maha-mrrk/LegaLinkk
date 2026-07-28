"""Redis-backed durable event store for reconnectable chat jobs."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.core.logging import get_logger
from app.services.progress import get_redis_client

logger = get_logger(__name__)
_PREFIX = "chat:job:"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatJobStore:
    """Persist job ownership, status and every SSE event in Redis."""

    def __init__(self, client: Any | None = None) -> None:
        self._client = client if client is not None else get_redis_client()
        self._ttl = get_settings().chat_job_ttl_seconds

    def _require_client(self) -> Any:
        if self._client is None:
            raise AppError(
                "Le service de reprise des conversations est indisponible.",
                status_code=503,
                code="chat_jobs_unavailable",
                retryable=True,
            )
        return self._client

    @staticmethod
    def _meta_key(job_id: str) -> str:
        return f"{_PREFIX}{job_id}:meta"

    @staticmethod
    def _events_key(job_id: str) -> str:
        return f"{_PREFIX}{job_id}:events"

    async def create(
        self,
        job_id: str,
        *,
        user_id: UUID,
        mode: str,
        task_id: str | None = None,
    ) -> None:
        client = self._require_client()
        meta_key = self._meta_key(job_id)
        events_key = self._events_key(job_id)
        mapping = {
            "job_id": job_id,
            "user_id": str(user_id),
            "mode": mode,
            "status": "queued",
            "task_id": task_id or "",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }

        def write() -> None:
            pipe = client.pipeline()
            pipe.hset(meta_key, mapping=mapping)
            pipe.expire(meta_key, self._ttl)
            pipe.delete(events_key)
            pipe.execute()

        await asyncio.to_thread(write)

    async def set_task_id(self, job_id: str, task_id: str) -> None:
        await self._update_meta(job_id, task_id=task_id)

    async def mark_processing(self, job_id: str) -> None:
        await self._update_meta(job_id, status="processing")

    async def append_event(self, job_id: str, event: dict[str, Any]) -> int:
        client = self._require_client()
        events_key = self._events_key(job_id)
        encoded = json.dumps(event, default=str, ensure_ascii=False)

        def append() -> int:
            pipe = client.pipeline()
            pipe.rpush(events_key, encoded)
            pipe.expire(events_key, self._ttl)
            results = pipe.execute()
            return int(results[0])

        length = await asyncio.to_thread(append)
        if event.get("type") == "done":
            await self._update_meta(job_id, status="completed")
        elif event.get("type") == "error":
            await self._update_meta(job_id, status="failed")
        return length

    async def mark_failed(self, job_id: str, message: str) -> None:
        await self.append_event(
            job_id,
            {
                "type": "error",
                "message": message,
                "code": "background_generation_failed",
                "retryable": True,
            },
        )

    async def get_meta_for_user(
        self,
        job_id: str,
        *,
        user_id: UUID,
    ) -> dict[str, str]:
        client = self._require_client()
        raw = await asyncio.to_thread(client.hgetall, self._meta_key(job_id))
        if not raw or raw.get("user_id") != str(user_id):
            raise NotFoundError("Cette réponse est introuvable.")
        return dict(raw)

    async def get_events(
        self,
        job_id: str,
        *,
        after: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        client = self._require_client()
        start = max(0, after)
        raw_events = await asyncio.to_thread(
            client.lrange,
            self._events_key(job_id),
            start,
            -1,
        )
        events: list[dict[str, Any]] = []
        for raw in raw_events or []:
            try:
                events.append(json.loads(raw))
            except (TypeError, ValueError):
                logger.warning("Malformed chat job event job_id=%s", job_id)
        return events, start + len(raw_events or [])

    async def _update_meta(self, job_id: str, **fields: str) -> None:
        client = self._require_client()
        key = self._meta_key(job_id)
        mapping = {**fields, "updated_at": _now_iso()}

        def update() -> None:
            pipe = client.pipeline()
            pipe.hset(key, mapping=mapping)
            pipe.expire(key, self._ttl)
            pipe.execute()

        await asyncio.to_thread(update)


@lru_cache
def get_chat_job_store() -> ChatJobStore:
    return ChatJobStore()


__all__ = ["ChatJobStore", "get_chat_job_store"]
