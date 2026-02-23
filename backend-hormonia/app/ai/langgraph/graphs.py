"""LangGraph graph definitions for flow message execution."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

try:
    from langgraph.graph import END, StateGraph

    _LANGGRAPH_IMPORT_ERROR: Exception | None = None
except ImportError as exc:
    END = None  # type: ignore[assignment]
    StateGraph = None  # type: ignore[assignment]
    _LANGGRAPH_IMPORT_ERROR = exc

from .state import FlowMessageState
from .nodes import (
    dispatch_response_continuation,
    dispatch_send_mode,
    load_flow_context,
    load_response_context,
)
from .runtime import compile_graph, instrument_node


def _add_node(builder: Any, *, graph_name: str, node_name: str, node_fn: Any) -> None:
    builder.add_node(node_name, instrument_node(node_name, node_fn, graph_name=graph_name))


def _compile_graph(builder: Any, *, graph_name: str) -> Any:
    return compile_graph(builder, graph_name=graph_name)


def _route_after_load(state: FlowMessageState) -> str:
    if state.get("result"):
        return "end"
    return "dispatch_send_mode"


def build_flow_message_graph() -> Any:
    """Build and return the flow message graph."""
    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed") from _LANGGRAPH_IMPORT_ERROR
    graph_name = "flow_message_graph"
    graph = StateGraph(FlowMessageState)
    _add_node(
        graph,
        graph_name=graph_name,
        node_name="load_flow_context",
        node_fn=load_flow_context,
    )
    _add_node(
        graph,
        graph_name=graph_name,
        node_name="dispatch_send_mode",
        node_fn=dispatch_send_mode,
    )
    graph.set_entry_point("load_flow_context")
    graph.add_conditional_edges(
        "load_flow_context",
        _route_after_load,
        {"dispatch_send_mode": "dispatch_send_mode", "end": END},
    )
    graph.add_edge("dispatch_send_mode", END)
    return _compile_graph(graph, graph_name=graph_name)


@lru_cache(maxsize=1)
def get_flow_message_graph() -> Any:
    """Return a cached compiled flow message graph."""
    return build_flow_message_graph()


def _route_after_response_load(state: FlowMessageState) -> str:
    if state.get("result"):
        return "end"
    return "dispatch_response_continuation"


def build_flow_response_graph() -> Any:
    """Build and return the flow response continuation graph."""
    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed") from _LANGGRAPH_IMPORT_ERROR
    graph_name = "flow_response_graph"
    graph = StateGraph(FlowMessageState)
    _add_node(
        graph,
        graph_name=graph_name,
        node_name="load_response_context",
        node_fn=load_response_context,
    )
    _add_node(
        graph,
        graph_name=graph_name,
        node_name="dispatch_response_continuation",
        node_fn=dispatch_response_continuation,
    )
    graph.set_entry_point("load_response_context")
    graph.add_conditional_edges(
        "load_response_context",
        _route_after_response_load,
        {"dispatch_response_continuation": "dispatch_response_continuation", "end": END},
    )
    graph.add_edge("dispatch_response_continuation", END)
    return _compile_graph(graph, graph_name=graph_name)


@lru_cache(maxsize=1)
def get_flow_response_graph() -> Any:
    """Return a cached compiled flow response continuation graph."""
    return build_flow_response_graph()
