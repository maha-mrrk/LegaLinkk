"""Builder that will assemble LangGraph workflows (architecture preparation).

This is a structural placeholder. It defines *how* future workflows will be
composed — by registering :class:`~app.agents.base_agent.BaseGraphAgent` nodes
and the edges between them — but it does NOT build or run any graph yet, and it
does not import LangGraph. Concrete workflows and the LangGraph binding will be
added in a later step.

Design intent (SOLID):
- Single Responsibility: only assembles a workflow definition; agents keep their
  own logic, services keep the business logic.
- Open/Closed: new nodes/edges are added via registration, without modifying the
  builder.
- Dependency Inversion: works against the ``BaseGraphAgent`` abstraction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.base_agent import BaseGraphAgent

# Sentinel node names for the workflow's implicit start/end.
START: str = "__start__"
END: str = "__end__"


@dataclass
class GraphBuilder:
    """Collects nodes and edges for a future LangGraph workflow.

    Usage (future):
        builder = GraphBuilder()
        builder.add_node(my_agent)
        builder.add_edge(START, my_agent.name)
        builder.add_edge(my_agent.name, END)
        graph = builder.build()  # will return a compiled LangGraph app
    """

    _nodes: dict[str, BaseGraphAgent] = field(default_factory=dict)
    _edges: list[tuple[str, str]] = field(default_factory=list)
    _entry_point: str | None = None

    def add_node(self, agent: BaseGraphAgent) -> "GraphBuilder":
        """Register a graph agent as a node (keyed by its ``name``)."""
        self._nodes[agent.name] = agent
        return self

    def add_edge(self, source: str, target: str) -> "GraphBuilder":
        """Declare a directed edge between two node names."""
        self._edges.append((source, target))
        return self

    def set_entry_point(self, node_name: str) -> "GraphBuilder":
        """Declare the workflow entry node."""
        self._entry_point = node_name
        return self

    def build(self) -> object:
        """Compile the registered definition into a runnable workflow.

        Not implemented yet: the LangGraph binding will be added when workflows
        are introduced. Kept as a clear extension point so no behavior changes.
        """
        raise NotImplementedError(
            "LangGraph workflow assembly is not implemented yet. "
            "GraphBuilder currently only prepares the architecture."
        )
