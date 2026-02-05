"""LangGraph graph definitions for flow message execution."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

try:
    from langgraph.graph import END, StateGraph
    _LANGGRAPH_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # noqa: BLE001
    END = None  # type: ignore[assignment]
    StateGraph = None  # type: ignore[assignment]
    _LANGGRAPH_IMPORT_ERROR = exc

from .state import FlowMessageState
from .ai_state import AIState
from .nodes import (
    dispatch_response_continuation,
    dispatch_send_mode,
    load_flow_context,
    load_response_context,
    humanize_node,
    sentiment_node,
    generate_node,
    question_variation_node,
    empathetic_follow_up_node,
)


def _route_after_load(state: FlowMessageState) -> str:
    if state.get("result"):
        return "end"
    return "dispatch_send_mode"


def build_flow_message_graph() -> Any:
    """Build and return the flow message graph."""
    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed") from _LANGGRAPH_IMPORT_ERROR
    graph = StateGraph(FlowMessageState)
    graph.add_node("load_flow_context", load_flow_context)
    graph.add_node("dispatch_send_mode", dispatch_send_mode)
    graph.set_entry_point("load_flow_context")
    graph.add_conditional_edges(
        "load_flow_context",
        _route_after_load,
        {"dispatch_send_mode": "dispatch_send_mode", "end": END},
    )
    graph.add_edge("dispatch_send_mode", END)
    return graph.compile()


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
    graph = StateGraph(FlowMessageState)
    graph.add_node("load_response_context", load_response_context)
    graph.add_node("dispatch_response_continuation", dispatch_response_continuation)
    graph.set_entry_point("load_response_context")
    graph.add_conditional_edges(
        "load_response_context",
        _route_after_response_load,
        {"dispatch_response_continuation": "dispatch_response_continuation", "end": END},
    )
    graph.add_edge("dispatch_response_continuation", END)
    return graph.compile()


@lru_cache(maxsize=1)
def get_flow_response_graph() -> Any:
    """Return a cached compiled flow response continuation graph."""
    return build_flow_response_graph()

# --- Unified AI Graphs ---

def build_humanization_graph() -> Any:
    """Build a graph for message humanization."""
    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed") from _LANGGRAPH_IMPORT_ERROR
    builder = StateGraph(AIState)
    builder.add_node("humanize", humanize_node)
    builder.set_entry_point("humanize")
    builder.add_edge("humanize", END)
    return builder.compile()


@lru_cache(maxsize=1)
def get_humanization_graph() -> Any:
    """Cached version of humanization graph."""
    return build_humanization_graph()


def build_sentiment_graph() -> Any:
    """Build a graph for sentiment analysis."""
    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed") from _LANGGRAPH_IMPORT_ERROR
    builder = StateGraph(AIState)
    builder.add_node("sentiment", sentiment_node)
    builder.set_entry_point("sentiment")
    builder.add_edge("sentiment", END)
    return builder.compile()


@lru_cache(maxsize=1)
def get_sentiment_graph() -> Any:
    """Cached version of sentiment graph."""
    return build_sentiment_graph()


def build_generation_graph() -> Any:
    """Build a graph for generic generation."""
    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed") from _LANGGRAPH_IMPORT_ERROR
    builder = StateGraph(AIState)
    builder.add_node("generate", generate_node)
    builder.set_entry_point("generate")
    builder.add_edge("generate", END)
    return builder.compile()


@lru_cache(maxsize=1)
def get_generation_graph() -> Any:
    """Cached version of generation graph."""
    return build_generation_graph()


def build_question_variation_graph() -> Any:
    """Build a graph for question variation."""
    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed") from _LANGGRAPH_IMPORT_ERROR
    builder = StateGraph(AIState)
    builder.add_node("question_variation", question_variation_node)
    builder.set_entry_point("question_variation")
    builder.add_edge("question_variation", END)
    return builder.compile()


@lru_cache(maxsize=1)
def get_question_variation_graph() -> Any:
    """Cached version of question variation graph."""
    return build_question_variation_graph()


def build_empathetic_follow_up_graph() -> Any:
    """Build a graph for empathetic follow-up generation."""
    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed") from _LANGGRAPH_IMPORT_ERROR
    builder = StateGraph(AIState)
    builder.add_node("empathetic_follow_up", empathetic_follow_up_node)
    builder.set_entry_point("empathetic_follow_up")
    builder.add_edge("empathetic_follow_up", END)
    return builder.compile()


@lru_cache(maxsize=1)
def get_empathetic_follow_up_graph() -> Any:
    """Cached version of empathetic follow-up graph."""
    return build_empathetic_follow_up_graph()
