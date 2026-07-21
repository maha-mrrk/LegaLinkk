"""Reusable tools for (future) LangGraph agents.

A "tool" is a thin, single-responsibility wrapper that a graph agent can call
(e.g. a retrieval tool, a reranking tool, a generation tool). Tools here will
delegate to the existing services and MUST NOT duplicate business logic.

Empty for now — populated when LangGraph workflows are introduced.
"""

from app.tools.base_tool import BaseTool

__all__ = ["BaseTool"]
