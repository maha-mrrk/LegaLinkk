"""LangGraph workflow assembly package (architecture preparation).

Will host the builders that wire graph agents/nodes and edges into executable
LangGraph workflows over :class:`~app.state.graph_state.GraphState`.
No workflow is defined yet — only the structure.
"""

from app.graphs.graph_builder import GraphBuilder

__all__ = ["GraphBuilder"]
