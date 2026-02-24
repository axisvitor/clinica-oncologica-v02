"""Direct async flow orchestration replacements for LangGraph invocations."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from app.ai.langgraph.nodes import (
    dispatch_response_continuation,
    dispatch_send_mode,
    load_flow_context,
    load_response_context,
)


async def run_flow_message(
    *,
    patient_id: UUID,
    day_number: int,
    flow_kind: str,
    handler: Any,
) -> Dict[str, Any]:
    """Run flow message nodes directly without LangGraph runtime."""
    state: Dict[str, Any] = {
        "patient_id": patient_id,
        "day_number": day_number,
        "flow_kind": flow_kind,
        "result": None,
        "error": None,
    }
    config = {
        "configurable": {
            "thread_id": f"flow_message:{patient_id}:{flow_kind}:{day_number}",
            "handler": handler,
        }
    }

    state.update(await load_flow_context(state, config=config))
    result = state.get("result")
    if isinstance(result, dict) and result:
        return result

    state.update(await dispatch_send_mode(state, config=config))
    result = state.get("result")
    if not isinstance(result, dict):
        raise ValueError("Direct flow function did not return a result payload")
    return result


async def run_flow_response(
    *,
    patient_id: UUID,
    response_context: Optional[Dict[str, Any]],
    handler: Any,
) -> Dict[str, Any]:
    """Run flow response nodes directly without LangGraph runtime."""
    state: Dict[str, Any] = {
        "patient_id": patient_id,
        "result": None,
        "error": None,
    }
    if response_context is not None:
        state["response_context"] = response_context

    config = {
        "configurable": {
            "thread_id": f"flow_response:{patient_id}",
            "handler": handler,
        }
    }

    state.update(await load_response_context(state, config=config))
    result = state.get("result")
    if isinstance(result, dict) and result:
        return result

    state.update(await dispatch_response_continuation(state, config=config))
    result = state.get("result")
    if not isinstance(result, dict):
        raise ValueError("Direct flow function did not return a result payload")
    return result
