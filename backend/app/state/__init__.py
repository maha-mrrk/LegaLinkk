"""Typed graph state package (LangGraph preparation).

Holds the strongly-typed state object shared across future LangGraph nodes.
No business logic lives here — only the data contract.
"""

from app.state.graph_state import GraphState

__all__ = ["GraphState"]
