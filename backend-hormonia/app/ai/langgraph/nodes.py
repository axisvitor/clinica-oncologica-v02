"""LangGraph nodes for flow message execution."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from langchain_core.runnables import RunnableConfig

from app.models.patient import Patient
from app.utils.timezone import now_sao_paulo

from .state import FlowMessageState, validate_flow_message_state
from .runtime import require_configurable_thread_id

logger = logging.getLogger(__name__)
_CANONICAL_SEND_MODES = frozenset(
    {"single", "sequential_auto", "wait_response", "wait_each"}
)


def _coerce_awaiting_response(value: Any) -> bool:
    """Normalize persisted awaiting_response values to a strict boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", ""}:
            return False
    return bool(value)


def _require_handler(config: Optional[RunnableConfig]) -> Any:
    require_configurable_thread_id(config)
    configurable = (config or {}).get("configurable") or {}
    handler = configurable.get("handler")
    if handler is None:
        raise RuntimeError(
            "Flow handler missing. Pass it via config['configurable']['handler']."
        )
    return handler


def _looks_like_flow_state(candidate: Any) -> bool:
    """Guard against mocked DB queries returning non-flow entities."""
    return candidate is not None and hasattr(candidate, "step_data")


async def _load_flow_state(handler: Any, flow_state_id: Any, patient_id: Any) -> Any:
    flow_state = None
    if hasattr(handler, "flow_state_repo"):
        repo_state = await asyncio.to_thread(
            handler.flow_state_repo.get_active_flow, patient_id
        )
        if _looks_like_flow_state(repo_state):
            flow_state = repo_state
    if flow_state is None and flow_state_id:
        from app.models.flow import PatientFlowState

        queried_state = await asyncio.to_thread(
            lambda: handler.db.query(PatientFlowState)
            .filter(PatientFlowState.id == flow_state_id)
            .first()
        )
        if _looks_like_flow_state(queried_state):
            flow_state = queried_state
        elif queried_state is not None:
            logger.warning(
                "Ignoring invalid flow state loaded by id lookup",
                extra={
                    "flow_state_id": str(flow_state_id),
                    "loaded_type": type(queried_state).__name__,
                },
            )
    return flow_state


def _parse_send_mode(send_mode: str | None) -> str:
    if send_mode is None:
        return "single"
    if not isinstance(send_mode, str):
        raise TypeError("Day config send_mode must be a string.")
    normalized = send_mode.strip().lower()
    if not normalized:
        return "single"
    if normalized not in _CANONICAL_SEND_MODES:
        allowed_modes = ", ".join(sorted(_CANONICAL_SEND_MODES))
        raise ValueError(
            f"Invalid send_mode '{normalized}'. Allowed values: {allowed_modes}."
        )
    return normalized


def _build_expected_response_context(
    step_data: Dict[str, Any],
    *,
    flow_day: Any,
    flow_kind: Any,
    message_index: Any,
) -> Dict[str, Any]:
    """Build expected correlation context from current pending flow state."""
    expected: Dict[str, Any] = {
        "flow_day": flow_day,
        "flow_kind": flow_kind,
        "message_index": message_index,
        "prompt_message_id": None,
    }
    pending_context = step_data.get("pending_response_context")
    if isinstance(pending_context, dict):
        if pending_context.get("flow_day") is not None:
            expected["flow_day"] = pending_context.get("flow_day")
        if pending_context.get("flow_kind") is not None:
            expected["flow_kind"] = pending_context.get("flow_kind")
        if pending_context.get("message_index") is not None:
            expected["message_index"] = pending_context.get("message_index")
        prompt_message_id = pending_context.get("prompt_message_id")
        if prompt_message_id:
            expected["prompt_message_id"] = str(prompt_message_id)
    return expected


def _collect_response_context_mismatches(
    expected_context: Dict[str, Any],
    received_context: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Compare received response context against expected pending context."""
    mismatches: Dict[str, Dict[str, Any]] = {}
    for field in ("flow_day", "flow_kind", "message_index"):
        received_value = received_context.get(field)
        if received_value is None:
            continue
        expected_value = expected_context.get(field)
        if expected_value is None:
            continue

        if field == "flow_kind":
            matches = (
                str(received_value).strip().lower()
                == str(expected_value).strip().lower()
            )
        else:
            try:
                matches = int(received_value) == int(expected_value)
            except (TypeError, ValueError):
                matches = received_value == expected_value

        if not matches:
            mismatches[field] = {
                "expected": expected_value,
                "received": received_value,
            }

    expected_prompt_id = expected_context.get("prompt_message_id")
    received_prompt_id = received_context.get("prompt_message_id")
    if received_prompt_id is not None:
        if expected_prompt_id is None:
            mismatches["prompt_message_id"] = {
                "expected": expected_prompt_id,
                "received": received_prompt_id,
            }
        elif str(expected_prompt_id) != str(received_prompt_id):
            mismatches["prompt_message_id"] = {
                "expected": expected_prompt_id,
                "received": received_prompt_id,
            }

    return mismatches


async def load_flow_context(
    state: FlowMessageState, config: Optional[RunnableConfig] = None
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

        day_config = await handler._get_day_config(flow_kind, day_number)
        if not day_config:
            logger.info("No config for day %s in %s - skipping", day_number, flow_kind)
            return {
                "result": {
                    "status": "skip",
                    "message": f"No messages configured for day {day_number}",
                },
            }
        if not isinstance(day_config, dict):
            raise TypeError("Day config must be a dict.")

        messages = day_config.get("messages", [])
        if not isinstance(messages, list):
            raise TypeError("Day config messages must be a list.")
        send_mode = _parse_send_mode(day_config.get("send_mode", "single"))

        if not messages:
            logger.info("No messages for day %s in %s - skipping", day_number, flow_kind)
            return {
                "result": {
                    "status": "skip",
                    "message": f"No messages configured for day {day_number}",
                },
            }

        flow_state = await handler._get_or_create_flow_state(patient_id, flow_kind)
        if not flow_state:
            return {
                "result": {
                    "status": "error",
                    "message": f"No active flow template for flow_kind={flow_kind}",
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
    state: FlowMessageState, config: Optional[RunnableConfig] = None
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
            "result": {"status": "skip", "message": f"No messages configured for day {day_number}"},
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
            }
        }

    return {"result": result}


async def load_response_context(
    state: FlowMessageState, config: Optional[RunnableConfig] = None
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
            # Backward compatibility: some callers still trigger continuation
            # without explicit response_context (e.g., validation harnesses).
            # In this case, trust the currently pending flow state.
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
    state: FlowMessageState, config: Optional[RunnableConfig] = None
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

    # Record response timestamp before continuing
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


async def _prepare_dispatch_execution_context(
    *,
    state: FlowMessageState,
    config: Optional[RunnableConfig],
) -> tuple[dict[str, Any], Optional[FlowMessageState]]:
    """Load shared state required by dispatch nodes and return early errors when needed."""
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


# AI generation and tone-adjustment nodes are defined in nodes_ai.
from .nodes_ai import (  # noqa: F401, E402
    generate_node,
    humanize_node,
    sentiment_node,
    question_variation_node,
    empathetic_follow_up_node,
)
