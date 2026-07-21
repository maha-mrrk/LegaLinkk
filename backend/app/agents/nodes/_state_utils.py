"""Tiny state-access helpers shared by graph nodes.

Pure glue (no business logic): centralizes reading/writing common GraphState
fields so nodes stay small and free of duplicated boilerplate.
"""

from __future__ import annotations

from uuid import UUID

from app.state.graph_state import GraphState


def ensure_metadata(state: GraphState) -> dict:
    """Return the mutable ``metadata`` dict, creating it if missing."""
    meta = state.get("metadata")
    if meta is None:
        meta = {}
        state["metadata"] = meta
    return meta


def source_path(state: GraphState) -> str | None:
    """Resolve the source file path for parsing/OCR (metadata first)."""
    meta = state.get("metadata") or {}
    return meta.get("file_path") or state.get("filename")


def require_document_id(state: GraphState) -> UUID:
    """Return ``document_id`` as a UUID, raising if it is absent."""
    raw = state.get("document_id")
    if raw is None:
        raise ValueError("GraphState.document_id is required")
    return UUID(str(raw))
