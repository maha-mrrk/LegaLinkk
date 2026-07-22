"""Reusable, optional Langfuse tracing for LangGraph nodes.

This module centralizes **all** observability so the graphs never talk to the
Langfuse SDK directly. It is intentionally defensive:

* Tracing is **optional**. It is only active when ``LANGFUSE_ENABLED`` is true
  *and* both API keys are configured *and* the ``langfuse`` package is
  importable. In every other case the service is a no-op and the application
  keeps working exactly as before.
* No business logic lives here. The service only wraps a node's ``execute`` call
  to record its execution time, input, output, metadata and errors — the node
  itself is run unchanged and its result is returned untouched.

Two levels of tracing are supported:

* **Node spans** — one span per LangGraph node (execution time, I/O, metadata,
  errors).
* **Workflow trace (parent)** — an optional parent span that groups every node
  of a single graph run (one ingestion, one chat answer) into a readable tree.
  Node spans are attached as children of the parent when one is provided.

Payloads are summarized by default (sizes/previews) to keep traces small and
avoid leaking whole documents. Set ``LANGFUSE_CAPTURE_FULL_IO=true`` to capture
full text content instead (raw embedding vectors are always kept as counts).

Usage (from a graph / caller)::

    langfuse = get_langfuse_service()
    parent = langfuse.start_trace("ingestion", input={...})
    try:
        result = await langfuse.trace_node(node, state, workflow="ingestion",
                                           parent=parent)
    finally:
        langfuse.end_trace(parent, output={...})

If Langfuse is disabled every call above is a no-op and ``trace_node`` is just
``await node.execute(state)``.
"""

from __future__ import annotations

import json
import time
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.agents.base_agent import BaseGraphAgent
    from app.state.graph_state import GraphState

logger = get_logger(__name__)

# GraphState keys that can hold very large / noisy payloads (full page text,
# raw embedding vectors, prior conversation turns). They are summarized rather
# than dumped verbatim to keep traces small, safe and serializable.
_HEAVY_METADATA_KEYS = ("pages", "history")
_MAX_TEXT_PREVIEW = 2000
_MAX_TEXT_FULL = 200_000


class LangfuseService:
    """Single entry point for tracing. Safe to use whether enabled or not."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: Any | None = None
        self._enabled = False
        self._full_io = bool(self._settings.langfuse_capture_full_io)
        self._init_client()

    # --- lifecycle -----------------------------------------------------------

    def _init_client(self) -> None:
        cfg = self._settings
        if not cfg.langfuse_enabled:
            logger.info("Langfuse tracing disabled (LANGFUSE_ENABLED is false).")
            return
        if not (cfg.langfuse_public_key and cfg.langfuse_secret_key):
            logger.warning(
                "Langfuse enabled but keys are missing — tracing stays disabled."
            )
            return

        try:
            from langfuse import Langfuse  # imported lazily: optional dependency

            self._client = Langfuse(
                public_key=cfg.langfuse_public_key,
                secret_key=cfg.langfuse_secret_key,
                host=cfg.langfuse_host or None,
                release=cfg.langfuse_release or None,
                environment=cfg.langfuse_environment or None,
            )
            self._enabled = True
            logger.info(
                "Langfuse tracing enabled (host=%s, full_io=%s).",
                cfg.langfuse_host,
                self._full_io,
            )
        except Exception:  # missing package, bad config, network client, etc.
            self._client = None
            self._enabled = False
            logger.warning(
                "Langfuse client could not be initialized — tracing disabled. "
                "The application will continue normally.",
                exc_info=True,
            )

    @property
    def is_enabled(self) -> bool:
        return self._enabled and self._client is not None

    def flush(self) -> None:
        """Best-effort flush of buffered traces (safe to call when disabled)."""
        if not self.is_enabled:
            return
        try:
            self._client.flush()
        except Exception:
            logger.debug("Langfuse flush failed", exc_info=True)

    # --- workflow (parent) trace --------------------------------------------

    def start_trace(
        self,
        name: str,
        *,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any | None:
        """Open a parent span grouping a whole graph run. Returns a handle/None."""
        if not self.is_enabled:
            return None
        try:
            return self._client.start_span(
                name=name,
                input=self._safe(input),
                metadata=metadata,
            )
        except Exception:
            logger.debug("Langfuse start_trace failed for %s", name, exc_info=True)
            return None

    def end_trace(
        self,
        handle: Any | None,
        *,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
        error: BaseException | None = None,
    ) -> None:
        """Close a parent span opened by :meth:`start_trace` (safe if handle is None)."""
        if handle is None:
            return
        try:
            if error is not None:
                handle.update(
                    level="ERROR",
                    status_message=f"{type(error).__name__}: {error}",
                    metadata=metadata,
                )
            else:
                handle.update(output=self._safe(output), metadata=metadata)
            handle.end()
        except Exception:
            logger.debug("Langfuse end_trace failed", exc_info=True)
        finally:
            # Ensure the completed run is delivered even for short-lived flows.
            self.flush()

    # --- node span -----------------------------------------------------------

    async def trace_node(
        self,
        node: "BaseGraphAgent",
        state: "GraphState",
        *,
        workflow: str,
        parent: Any | None = None,
    ) -> "GraphState":
        """Run ``node.execute(state)`` and record one span for it.

        Captures execution time, input, output, metadata and errors. When a
        ``parent`` handle is given the span is nested under it. When tracing is
        disabled this simply awaits and returns ``node.execute``.
        """
        if not self.is_enabled:
            return await node.execute(state)

        span = self._start_span(node, state, workflow, parent)
        started = time.perf_counter()
        try:
            result = await node.execute(state)
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            self._finish_error(span, node, workflow, exc, elapsed_ms)
            raise  # never swallow: preserve the graph's retry/error handling
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        self._finish_success(span, node, workflow, result, elapsed_ms)
        return result

    # --- internals (all guarded so tracing never breaks the request) ---------

    def _start_span(
        self,
        node: "BaseGraphAgent",
        state: "GraphState",
        workflow: str,
        parent: Any | None,
    ) -> Any | None:
        kwargs = {
            "name": f"{workflow}.{node.name}",
            "input": self._summarize_state(state),
            "metadata": {
                "workflow": workflow,
                "node": node.name,
                "description": node.description,
            },
        }
        try:
            # Nest under the parent when available so all nodes of one run group
            # into a single trace; otherwise create a standalone span.
            if parent is not None:
                return parent.start_span(**kwargs)
            return self._client.start_span(**kwargs)
        except Exception:
            logger.debug("Langfuse start_span failed for %s", node.name, exc_info=True)
            return None

    def _finish_success(
        self,
        span: Any | None,
        node: "BaseGraphAgent",
        workflow: str,
        result: "GraphState",
        elapsed_ms: float,
    ) -> None:
        if span is None:
            return
        try:
            span.update(
                output=self._summarize_state(result),
                metadata={
                    "workflow": workflow,
                    "node": node.name,
                    "status": "ok",
                    "execution_time_ms": elapsed_ms,
                },
            )
            span.end()
        except Exception:
            logger.debug("Langfuse span finalize failed for %s", node.name, exc_info=True)

    def _finish_error(
        self,
        span: Any | None,
        node: "BaseGraphAgent",
        workflow: str,
        exc: Exception,
        elapsed_ms: float,
    ) -> None:
        if span is None:
            return
        try:
            span.update(
                level="ERROR",
                status_message=f"{type(exc).__name__}: {exc}",
                metadata={
                    "workflow": workflow,
                    "node": node.name,
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "execution_time_ms": elapsed_ms,
                },
            )
            span.end()
        except Exception:
            logger.debug("Langfuse error finalize failed for %s", node.name, exc_info=True)

    # --- payload shaping -----------------------------------------------------

    def _summarize_state(self, state: "GraphState") -> dict[str, Any]:
        """Build a JSON-safe snapshot of the state for a trace.

        By default large fields (text, embeddings, chunks, pages) are reduced to
        sizes/previews so traces stay lightweight and never leak whole documents.
        When ``LANGFUSE_CAPTURE_FULL_IO`` is true, full text content is captured
        (raw embedding vectors are still summarized as counts — they are huge and
        not human-readable).
        """
        full = self._full_io
        limit = _MAX_TEXT_FULL if full else _MAX_TEXT_PREVIEW

        def _count(value: Any) -> int:
            try:
                return len(value) if value else 0
            except TypeError:
                return 0

        def _text(value: Any) -> str | None:
            if not value:
                return None
            text = str(value)
            if len(text) <= limit:
                return text
            return f"{text[:limit]}… (+{len(text) - limit})"

        raw_meta = state.get("metadata") or {}
        safe_meta = {k: v for k, v in raw_meta.items() if k not in _HEAVY_METADATA_KEYS}
        embeddings = state.get("embeddings") or []

        # Surface generation info (provider / model / token usage) at the top
        # level so a single glance at a span shows what the LLM did.
        generation = raw_meta.get("generation") or {}

        summary: dict[str, Any] = {
            "document_id": state.get("document_id"),
            "filename": state.get("filename"),
            "user_question": _text(state.get("user_question")),
            "extracted_text_chars": _count(state.get("extracted_text")),
            "cleaned_text_chars": _count(state.get("cleaned_text")),
            "chunks": _count(state.get("chunks")),
            "embeddings": _count(embeddings),
            "embedding_dim": _count(embeddings[0]) if embeddings else 0,
            "retrieved_chunks": _count(state.get("retrieved_chunks")),
            "reranked_chunks": _count(state.get("reranked_chunks")),
            "llm_response": _text(state.get("llm_response")),
            "provider": generation.get("provider"),
            "model": generation.get("model"),
            "tokens_used": generation.get("tokens_used"),
            "generation_time": generation.get("generation_time"),
            "errors": list(state.get("errors") or []),
            "metadata": safe_meta,
        }

        if full:
            # Add verbatim text content for deep debugging (no raw vectors).
            summary["extracted_text"] = _text(state.get("extracted_text"))
            summary["cleaned_text"] = _text(state.get("cleaned_text"))
            summary["chunks_text"] = [
                _text(c.get("text")) for c in (state.get("chunks") or [])
            ]
            summary["retrieved_chunks_text"] = [
                _text(c.get("text")) for c in (state.get("retrieved_chunks") or [])
            ]
            summary["reranked_chunks_text"] = [
                _text(c.get("text")) for c in (state.get("reranked_chunks") or [])
            ]

        # Drop empty/zero entries to keep the payload compact.
        compact = {k: v for k, v in summary.items() if v not in (None, 0, [], {}, "")}
        return self._safe(compact)

    @staticmethod
    def _safe(value: Any) -> Any:
        """Guarantee JSON-serializability (UUIDs, datetimes, etc.)."""
        if value is None:
            return None
        try:
            return json.loads(json.dumps(value, default=str))
        except (TypeError, ValueError):
            return {"note": "payload not serializable"}


@lru_cache
def get_langfuse_service() -> LangfuseService:
    """Return a cached, process-wide LangfuseService (one client per process)."""
    return LangfuseService()


__all__ = ["LangfuseService", "get_langfuse_service"]
