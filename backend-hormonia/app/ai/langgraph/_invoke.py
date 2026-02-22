"""Centralized LangGraph graph invocation with explicit failure handling.

AI-02: Replaces per-call-site None checks with a single wrapper that raises
FeatureNotAvailableError when a graph returns no usable output.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def invoke_langgraph_graph(
    graph: Any,
    state: dict,
    config: dict,
    graph_name: str,
    output_key: str = "output",
    operation: Optional[str] = None,
    expect_dict: bool = False,
) -> Any:
    """Invoke a LangGraph graph and raise FeatureNotAvailableError on empty output.

    Args:
        graph: Compiled LangGraph graph (result of StateGraph.compile())
        state: Input state dict for the graph
        config: LangGraph run config (must include configurable.thread_id)
        graph_name: Human-readable graph name for error messages (PII-safe)
        output_key: Key to extract from result dict (default: "output")
        operation: Optional operation label for error context (PII-safe)
        expect_dict: If True, validates output is a non-empty dict (for sentiment).
                     If False, validates output is truthy (for string outputs).

    Returns:
        The graph output value (guaranteed non-None and non-empty)

    Raises:
        FeatureNotAvailableError: If graph returns None, empty, or invalid type
    """
    from app.core.exceptions import FeatureNotAvailableError

    result = await graph.ainvoke(state, config=config)
    output = result.get(output_key) if isinstance(result, dict) else None

    if expect_dict:
        if not isinstance(output, dict) or not output:
            raise FeatureNotAvailableError(
                f"{graph_name} returned no usable dict output",
                graph_name=graph_name,
                operation=operation,
            )
    else:
        if not output:
            raise FeatureNotAvailableError(
                f"{graph_name} returned no usable output",
                graph_name=graph_name,
                operation=operation,
            )

    return output
