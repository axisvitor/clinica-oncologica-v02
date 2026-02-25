"""Response-flow context loading and continuation dispatch."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from app.utils.timezone import now_sao_paulo

from app.services.flow._flow_message_flow import _prepare_dispatch_execution_context
from app.services.flow._flow_orchestration_utils import (
    FlowMessageState,
    _build_expected_response_context,
    _collect_response_context_mismatches,
    _coerce_awaiting_response,
    _parse_send_mode,
    _require_handler,
    validate_flow_message_state,
)

logger = logging.getLogger(__name__)


async def load_response_context(
    state: FlowMessageState, config: Optional[dict] = None
) -> FlowMessageState:
    """Load flow state and prepare continuation after a patient response."""
    try:
        state = validate_flow_message_state(
            state,
            required_keys=("patient_id",),
        )
    except (TypeError, ValueError) as exc:
        logger.exception("Flow state validation failed in load_response_context")
        return {"result": {"status": "error", "message": str(exc)}}

    try:
        handler = _require_handler(config)
        patient_id = state["patient_id"]

        flow_state = await asyncio.to_thread(
            handler.flow_state_repo.get_active_flow, patient_id
        )
        if not flow_state:
            return {"result": {"status": "no_active_flow"}}

        step_data_raw = flow_state.step_data or {}
        if not isinstance(step_data_raw, dict):
            raise TypeError("Flow state step_data must be a dict.")
        step_data = dict(step_data_raw)

        current_day = step_data.get("current_flow_day")
        flow_kind = step_data.get("flow_kind")
        if not current_day or not flow_kind:
            return {"result": {"status": "not_awaiting", "message": "Missing flow context"}}
        if step_data.get("day_complete") and not _coerce_awaiting_response(
            step_data.get("awaiting_response")
        ):
            return {"result": {"status": "day_complete", "day": current_day}}

        day_config = await handler._get_day_config(flow_kind, current_day)
        if not day_config:
            return {"result": {"status": "no_config"}}
        if not isinstance(day_config, dict):
            raise TypeError("Day config must be a dict.")

        messages = day_config.get("messages", [])
        if not isinstance(messages, list):
            raise TypeError("Day config messages must be a list.")
        send_mode = _parse_send_mode(day_config.get("send_mode", "single"))
        current_index = step_data.get("current_day_message_index", 0)
        if isinstance(current_index, bool) or not isinstance(current_index, int):
            raise TypeError("Flow step index must be an integer.")

        if current_index < 0 or (messages and current_index >= len(messages)):
            logger.warning(
                "current_day_message_index out of range (%s) for response continuation; clamping",
                current_index,
            )
            max_index = max(len(messages) - 1, 0)
            current_index = min(max(current_index, 0), max_index)
            step_data["current_day_message_index"] = current_index

        awaiting_response = _coerce_awaiting_response(
            step_data.get("awaiting_response", False)
        )
        if not awaiting_response:
            return {
                "result": {"status": "not_awaiting", "message": "Not waiting for response"},
            }

        expected_context = _build_expected_response_context(
            step_data,
            flow_day=current_day,
            flow_kind=flow_kind,
            message_index=current_index,
        )
        response_context = state.get("response_context")
        if not isinstance(response_context, dict) or not response_context:
            response_context = {
                key: value for key, value in expected_context.items() if value is not None
            }
        mismatches = _collect_response_context_mismatches(
            expected_context=expected_context,
            received_context=response_context,
        )
        if mismatches:
            logger.info(
                "Response context mismatch; keeping flow waiting",
                extra={
                    "patient_id": str(patient_id),
                    "expected_context": expected_context,
                    "received_context": response_context,
                    "mismatch_fields": sorted(mismatches.keys()),
                },
            )
            return {
                "result": {
                    "status": "waiting",
                    "day": current_day,
                    "message_index": current_index,
                    "reason": "context_mismatch",
                    "mismatches": mismatches,
                }
            }

        next_index = current_index + 1
        if next_index >= len(messages):
            step_data["day_complete"] = True
            step_data["awaiting_response"] = False
            step_data["last_response_at"] = now_sao_paulo().isoformat()
            step_data.pop("pending_response_context", None)
            flow_state.step_data = step_data
            await asyncio.to_thread(handler.db.commit)
            return {"result": {"status": "day_complete", "day": current_day}}

        return {
            "flow_state_id": getattr(flow_state, "id", None),
            "flow_state_step_data": dict(flow_state.step_data or {}),
            "day_config": day_config,
            "messages": messages,
            "send_mode": send_mode,
            "current_index": next_index,
            "day_number": current_day,
            "flow_kind": flow_kind,
        }
    except (RuntimeError, TypeError, ValueError) as exc:
        logger.exception("Failed to load response context")
        return {"result": {"status": "error", "message": str(exc)}}
    except Exception as exc:
        logger.exception("Unexpected failure in load_response_context")
        return {"result": {"status": "error", "message": str(exc)}}


async def dispatch_response_continuation(
    state: FlowMessageState, config: Optional[dict] = None
) -> FlowMessageState:
    """Send the next message(s) after a patient response."""
    dispatch_context, early_result = await _prepare_dispatch_execution_context(
        state=state,
        config=config,
    )
    if early_result is not None:
        return early_result

    handler = dispatch_context["handler"]
    patient = dispatch_context["patient"]
    flow_state = dispatch_context["flow_state"]
    day_number = dispatch_context["day_number"]
    flow_kind = dispatch_context["flow_kind"]
    day_config = dispatch_context["day_config"]
    messages = dispatch_context["messages"]
    send_mode = dispatch_context["send_mode"]
    current_index = dispatch_context["current_index"]

    step_data = flow_state.step_data or {}
    if not step_data.get("last_response_at"):
        step_data["last_response_at"] = now_sao_paulo().isoformat()
        flow_state.step_data = step_data
        await asyncio.to_thread(handler.db.commit)

    if send_mode == "wait_response":
        result = await handler._send_remaining_after_response(
            patient,
            messages,
            current_index,
            flow_state,
            day_number,
            flow_kind,
            day_config,
        )
        return {"result": result}

    if send_mode == "wait_each":
        result = await handler._send_wait_each_with_auto_advance(
            patient,
            messages,
            current_index,
            flow_state,
            day_number,
            flow_kind,
            day_config,
        )
        return {"result": result}

    return {"result": {"status": "ok"}}


async def run_flow_response(
    *,
    patient_id: UUID,
    response_context: Optional[Dict[str, Any]],
    handler: Any,
) -> Dict[str, Any]:
    """Run flow response nodes directly without LangGraph runtime."""
    state: FlowMessageState = {
        "patient_id": patient_id,
        "result": None,
        "error": None,
    }
    if response_context is not None:
        state["response_context"] = response_context

    config: dict[str, dict[str, Any]] = {
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
