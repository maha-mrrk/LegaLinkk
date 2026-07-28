"""Redis state store for durable, reconnectable contract-analysis jobs."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.services.progress import get_redis_client

_PREFIX = "analysis:job:"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnalysisJobStore:
    def __init__(self, client: Any | None = None) -> None:
        self._client = client if client is not None else get_redis_client()
        self._ttl = get_settings().chat_job_ttl_seconds

    def _require_client(self) -> Any:
        if self._client is None:
            raise AppError(
                "Le service de reprise des analyses est momentanément indisponible.",
                status_code=503,
                code="analysis_jobs_unavailable",
                retryable=True,
            )
        return self._client

    @staticmethod
    def _key(job_id: str) -> str:
        return f"{_PREFIX}{job_id}"

    async def create(
        self,
        job_id: str,
        *,
        user_id: UUID,
        document_id: UUID,
    ) -> None:
        client = self._require_client()
        key = self._key(job_id)
        await asyncio.to_thread(
            client.hset,
            key,
            mapping={
                "job_id": job_id,
                "user_id": str(user_id),
                "document_id": str(document_id),
                "status": "queued",
                "progress": "5",
                "message": "Analyse en attente…",
                "task_id": "",
                "result": "",
                "error": "",
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
            },
        )
        await asyncio.to_thread(client.expire, key, self._ttl)

    async def set_task_id(self, job_id: str, task_id: str) -> None:
        await self._update(job_id, task_id=task_id)

    async def mark_processing(self, job_id: str) -> None:
        await self._update(
            job_id,
            status="processing",
            progress="20",
            message="Analyse juridique en cours…",
        )

    async def mark_completed(
        self,
        job_id: str,
        result: dict[str, Any],
    ) -> None:
        await self._update(
            job_id,
            status="completed",
            progress="100",
            message="Analyse terminée.",
            result=json.dumps(result, default=str, ensure_ascii=False),
            error="",
        )

    async def mark_failed(self, job_id: str, message: str) -> None:
        await self._update(
            job_id,
            status="failed",
            progress="100",
            message="L’analyse a échoué.",
            error=message,
        )

    async def get_for_user(
        self,
        job_id: str,
        *,
        user_id: UUID,
    ) -> dict[str, Any]:
        client = self._require_client()
        raw = await asyncio.to_thread(client.hgetall, self._key(job_id))
        if not raw or raw.get("user_id") != str(user_id):
            raise NotFoundError("Cette analyse est introuvable.")
        result = None
        if raw.get("result"):
            try:
                result = json.loads(raw["result"])
            except (TypeError, ValueError):
                result = None
        return {
            **raw,
            "progress": int(raw.get("progress") or 0),
            "result": result,
            "error": raw.get("error") or None,
        }

    async def _update(self, job_id: str, **fields: str) -> None:
        client = self._require_client()
        key = self._key(job_id)
        await asyncio.to_thread(
            client.hset,
            key,
            mapping={**fields, "updated_at": _now_iso()},
        )
        await asyncio.to_thread(client.expire, key, self._ttl)


@lru_cache
def get_analysis_job_store() -> AnalysisJobStore:
    return AnalysisJobStore()


__all__ = ["AnalysisJobStore", "get_analysis_job_store"]
