"""Message-flow context loading and send-mode dispatch."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from app.models.patient import Patient
from app.services.flow.config_validation import (
    DayConfigValidationError,
    validate_day_config,
)

from app.services.flow._flow_orchestration_utils import (
    FlowMessageState,
    _coerce_awaiting_response,
    _load_flow_state,
    _parse_send_mode,
    _require_handler,
    validate_flow_message_state,
)
from app.utils.structured_logger import correlation_id as correlation_id_var

logger = logging.getLogger(__name__)


def _correlation_extra(**extra: Any) -> Dict[str, Any]:
    return {
        "correlation_id": correlation_id_var.get(),
        **extra,
    }


async def load_flow_context(
    state: FlowMessageState, config: Optional[dict] = None
) -> FlowMessageState:
    """Load patient, flow template, and current flow state."""
    try:
        state = validate_flow_message_state(
            state,
            required_keys=("patient_id", "day_number", "flow_kind"),
        )
    except (TypeError, ValueError) as exc:
        logger.exception("Flow state validation failed in load_flow_context")
        return {"result": {"status": "error", "message": str(exc)}}

    try:
        handler = _require_handler(config)
        patient_id = state["patient_id"]
        day_number = state["day_number"]
        flow_kind = state["flow_kind"]

        patient = await asyncio.to_thread(
            lambda: handler.db.query(Patient).filter(Patient.id == patient_id).first()
        )
        if not patient:
            return {"result": {"status": "error", "message": "Patient not found"}}

        flow_state = await handler._get_or_create_flow_state(patient_id, flow_kind)
        if not flow_state:
            return {
                "result": {
                    "status": "error",
                    "message": f"No active flow template for flow_kind={flow_kind}",
                },
            }

        day_config = await handler._get_day_config(flow_kind, day_number, patient_flow_state_id=flow_state.id)
        if not day_config:
            logger.info(
                "No config for day %s in %s - skipping",
                day_number,
                flow_kind,
                extra=_correlation_extra(
                    patient_id=str(patient_id),
                    day_number=day_number,
                    flow_kind=flow_kind,
                ),
            )
            return {
                "result": {
                    "status": "skip",
                    "message": f"No messages configured for day {day_number}",
                },
            }

        try:
            day_config = validate_day_config(
                day_config,
                flow_kind=flow_kind,
                day_number=day_number,
            )
        except DayConfigValidationError as exc:
            logger.warning(
                "day_config validation failed - failing fast",
                extra=_correlation_extra(
                    patient_id=str(patient_id),
                    flow_kind=flow_kind,
                    day_number=day_number,
                    validation_errors=exc.errors,
                ),
            )
            return {
                "result": {
                    "status": "error",
                    "message": str(exc),
                    "validation_errors": exc.errors,
                }
            }

        messages = day_config.get("messages", [])
        send_mode = _parse_send_mode(day_config.get("send_mode", "single"))

        if not messages:
            logger.info(
                "No messages for day %s in %s - skipping",
                day_number,
                flow_kind,
                extra=_correlation_extra(
                    patient_id=str(patient_id),
                    day_number=day_number,
                    flow_kind=flow_kind,
                ),
            )
            return {
                "result": {
                    "status": "skip",
                    "message": f"No messages configured for day {day_number}",
                },
            }

        step_data_raw = flow_state.step_data or {}
        if not isinstance(step_data_raw, dict):
            raise TypeError("Flow state step_data must be a dict.")
        step_data = dict(step_data_raw)

        previous_day = step_data.get("current_flow_day")
        if previous_day == day_number:
            if step_data.get("day_complete"):
                return {
                    "result": {"status": "day_complete", "day": day_number},
                }
            if _coerce_awaiting_response(step_data.get("awaiting_response")):
                return {
                    "result": {
                        "status": "waiting",
                        "day": day_number,
                        "message_index": step_data.get("current_day_message_index", 0),
                    },
                }
        if (
            previous_day is not None
            and previous_day != day_number
            and _coerce_awaiting_response(step_data.get("awaiting_response"))
        ):
            pending_index = step_data.get("current_day_message_index", 0)
            if isinstance(pending_index, bool) or not isinstance(pending_index, int):
                pending_index = 0
            logger.info(
                "Day changed from %s to %s while awaiting response; preserving pending message index %s",
                previous_day,
                day_number,
                pending_index,
                extra=_correlation_extra(
                    patient_id=str(patient_id),
                    previous_day=previous_day,
                    day_number=day_number,
                    pending_index=pending_index,
                ),
            )
            return {
                "result": {
                    "status": "waiting",
                    "day": previous_day,
                    "message_index": pending_index,
                },
            }
        if previous_day is not None and previous_day != day_number:
            logger.debug(
                "Day changed from %s to %s - resetting message index",
                previous_day,
                day_number,
            )
            step_data["current_day_message_index"] = 0
            step_data["day_complete"] = False
            step_data["awaiting_response"] = False
            step_data.pop("pending_response_context", None)

        current_index = step_data.get("current_day_message_index", 0)
        if isinstance(current_index, bool) or not isinstance(current_index, int):
            raise TypeError("Flow step index must be an integer.")
        if current_index < 0 or current_index >= len(messages):
            logger.warning(
                "current_day_message_index out of range (%s) for day %s in %s; resetting to 0",
                current_index,
                day_number,
                flow_kind,
                extra=_correlation_extra(
                    patient_id=str(patient_id),
                    current_index=current_index,
                    day_number=day_number,
                    flow_kind=flow_kind,
                ),
            )
            if step_data.get("day_complete"):
                return {
                    "result": {"status": "day_complete", "day": day_number},
                }
            current_index = 0
            step_data["current_day_message_index"] = current_index

        step_data["current_flow_day"] = day_number
        step_data["flow_kind"] = flow_kind
        step_data["current_day_message_index"] = current_index
        flow_state.step_data = step_data

        logger.info(
            "Loaded flow context for dispatch",
            extra=_correlation_extra(
                patient_id=str(patient_id),
                day_number=day_number,
                flow_kind=flow_kind,
                send_mode=send_mode,
                current_index=current_index,
            ),
        )
        return {
            "result": {},
            "flow_state_id": getattr(flow_state, "id", None),
            "flow_state_step_data": step_data,
            "day_config": day_config,
            "messages": messages,
            "send_mode": send_mode,
            "current_index": current_index,
        }
    except (RuntimeError, TypeError, ValueError) as exc:
        logger.exception("Failed to load flow context")
        return {"result": {"status": "error", "message": str(exc)}}
    except Exception as exc:
        logger.exception("Unexpected failure in load_flow_context")
        return {"result": {"status": "error", "message": str(exc)}}


async def dispatch_send_mode(
    state: FlowMessageState, config: Optional[dict] = None
) -> FlowMessageState:
    """Dispatch to the correct sending behavior based on send_mode."""
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

    result: Dict[str, Any]
    if not messages:
        return {
            "result": {
                "status": "skip",
                "message": f"No messages configured for day {day_number}",
            },
        }

    if send_mode == "sequential_auto":
        result = await handler._send_all_sequential(
            patient,
            messages,
            flow_state,
            day_number,
            flow_kind,
            day_config,
        )
    elif send_mode == "wait_response":
        if current_index == 0:
            first_expects_response = messages[0].get("expects_response", True)
            if not first_expects_response:
                result = await handler._send_wait_each_with_auto_advance(
                    patient,
                    messages,
                    0,
                    flow_state,
                    day_number,
                    flow_kind,
                    day_config,
                )
            else:
                result = await handler._send_message_and_wait(
                    patient,
                    messages,
                    0,
                    flow_state,
                    day_number,
                    flow_kind,
                    day_config,
                )
        else:
            result = await handler._send_remaining_after_response(
                patient,
                messages,
                current_index,
                flow_state,
                day_number,
                flow_kind,
                day_config,
            )
    elif send_mode == "wait_each":
        result = await handler._send_wait_each_with_auto_advance(
            patient,
            messages,
            current_index,
            flow_state,
            day_number,
            flow_kind,
            day_config,
        )
    elif send_mode == "single":
        if len(messages) > 1:
            logger.warning(
                "send_mode=single but %s messages configured for day %s in %s; sending first only",
                len(messages),
                day_number,
                flow_kind,
                extra=_correlation_extra(
                    patient_id=str(getattr(patient, "id", state["patient_id"])),
                    day_number=day_number,
                    flow_kind=flow_kind,
                    send_mode=send_mode,
                ),
            )
        result = await handler._send_all_sequential(
            patient,
            messages[:1],
            flow_state,
            day_number,
            flow_kind,
            day_config,
        )
    else:
        return {
            "result": {
                "status": "error",
                "message": f"Invalid send_mode '{send_mode}'.",
            },
        }

    logger.info(
        "Dispatched flow send mode",
        extra=_correlation_extra(
            patient_id=str(getattr(patient, "id", state["patient_id"])),
            day_number=day_number,
            flow_kind=flow_kind,
            send_mode=send_mode,
            current_index=current_index,
        ),
    )
    return {"result": result}


async def _prepare_dispatch_execution_context(
    *,
    state: FlowMessageState,
    config: Optional[dict],
) -> tuple[dict[str, Any], Optional[FlowMessageState]]:
    """Load shared state required by dispatch nodes and return early errors."""
    existing_result = state.get("result")
    if isinstance(existing_result, dict) and existing_result:
        return {}, {"result": existing_result}
    if existing_result and not isinstance(existing_result, dict):
        return {}, {
            "result": {
                "status": "error",
                "message": "Invalid LangGraph result payload in flow state.",
            }
        }

    handler = _require_handler(config)
    patient_id = state["patient_id"]
    patient = await asyncio.to_thread(
        lambda: handler.db.query(Patient).filter(Patient.id == patient_id).first()
    )
    if not patient:
        return {}, {"result": {"status": "error", "message": "Patient not found"}}

    flow_state = await _load_flow_state(handler, state.get("flow_state_id"), patient_id)
    if not flow_state:
        return {}, {"result": {"status": "error", "message": "Flow state not found"}}

    flow_state_step_data = state.get("flow_state_step_data")
    if isinstance(flow_state_step_data, dict):
        flow_state.step_data = flow_state_step_data

    try:
        send_mode = _parse_send_mode(state.get("send_mode") or "single")
    except (TypeError, ValueError) as exc:
        return {}, {"result": {"status": "error", "message": str(exc)}}

    return {
        "handler": handler,
        "patient": patient,
        "flow_state": flow_state,
        "day_number": state["day_number"],
        "flow_kind": state["flow_kind"],
        "day_config": state.get("day_config") or {},
        "messages": state.get("messages") or [],
        "send_mode": send_mode,
        "current_index": state.get("current_index", 0),
    }, None


async def run_flow_message(
    *,
    patient_id: UUID,
    day_number: int,
    flow_kind: str,
    handler: Any,
) -> Dict[str, Any]:
    """Run flow message nodes directly without LangGraph runtime."""
    state: FlowMessageState = {
        "patient_id": patient_id,
        "day_number": day_number,
        "flow_kind": flow_kind,
        "result": None,
        "error": None,
    }
    config: dict[str, dict[str, Any]] = {
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
