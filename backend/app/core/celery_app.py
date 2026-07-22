"""Celery application used to run long-running work off the request path.

The heavy document ingestion pipeline (parse/OCR → clean → chunk → embed →
index) is executed here as a background task so the upload endpoint can return
immediately. The pipeline itself is unchanged — Celery only *executes* the
existing LangGraph workflow.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "legallink",
    broker=settings.effective_celery_broker_url,
    backend=settings.effective_celery_result_backend,
    include=["app.tasks.ingestion"],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=settings.ingestion_progress_ttl_seconds,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Ingestion can be slow (OCR + embeddings on CPU); give it generous limits.
    task_soft_time_limit=60 * 25,
    task_time_limit=60 * 30,
    timezone="UTC",
    enable_utc=True,
)

__all__ = ["celery_app"]
