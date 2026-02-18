"""LangGraph state definitions for flow message execution."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, List, Optional, TypedDict
from uuid import UUID


class FlowResponseContext(TypedDict, total=False):
    """Optional correlation payload attached to an inbound patient response."""

    flow_day: int
    flow_kind: str
    message_index: int
    prompt_message_id: UUID
    response_message_id: UUID


class FlowMessageState(TypedDict, total=False):
    """Shared LangGraph state for flow message execution."""

    patient_id: UUID
    response_context: Optional[FlowResponseContext]
    day_number: int
    flow_kind: str
    flow_state_id: UUID
    flow_state_step_data: Dict[str, Any]
    day_config: Optional[Dict[str, Any]]
    messages: List[Dict[str, Any]]
    send_mode: str
    current_index: int
    result: Dict[str, Any]
    error: str


def _ensure_uuid(value: Any, field_name: str) -> UUID:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError(f"Field '{field_name}' must be a valid UUID.") from exc
    raise TypeError(f"Field '{field_name}' must be a UUID or UUID string.")


def _ensure_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Field '{field_name}' must be an integer.")
    return value


def _ensure_str(value: Any, field_name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise TypeError(f"Field '{field_name}' must be a string.")
    if not allow_empty and not value.strip():
        raise ValueError(f"Field '{field_name}' must not be empty.")
    return value


def validate_flow_message_state(
    state: Any,
    *,
    required_keys: tuple[str, ...] = (),
) -> FlowMessageState:
    """
    Lightweight runtime validation for LangGraph flow state.

    Validates only critical keys and core value types used by nodes.
    """
    if not isinstance(state, Mapping):
        raise TypeError("FlowMessageState must be a dict-like object.")

    missing = [key for key in required_keys if key not in state]
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"Missing required FlowMessageState keys: {missing_text}.")

    normalized: FlowMessageState = dict(state)

    if "patient_id" in normalized:
        normalized["patient_id"] = _ensure_uuid(normalized["patient_id"], "patient_id")
    if "flow_state_id" in normalized and normalized["flow_state_id"] is not None:
        normalized["flow_state_id"] = _ensure_uuid(
            normalized["flow_state_id"], "flow_state_id"
        )
    if "day_number" in normalized:
        normalized["day_number"] = _ensure_int(normalized["day_number"], "day_number")
    if "current_index" in normalized:
        normalized["current_index"] = _ensure_int(
            normalized["current_index"], "current_index"
        )
    if "flow_kind" in normalized:
        normalized["flow_kind"] = _ensure_str(normalized["flow_kind"], "flow_kind")
    if "send_mode" in normalized:
        normalized["send_mode"] = _ensure_str(
            normalized["send_mode"], "send_mode"
        )
    response_context = normalized.get("response_context")
    if response_context is not None:
        if not isinstance(response_context, Mapping):
            raise TypeError("Field 'response_context' must be a dict when provided.")
        normalized_context: FlowResponseContext = dict(response_context)
        if "flow_day" in normalized_context:
            normalized_context["flow_day"] = _ensure_int(
                normalized_context["flow_day"], "response_context.flow_day"
            )
        if "flow_kind" in normalized_context:
            normalized_context["flow_kind"] = _ensure_str(
                normalized_context["flow_kind"],
                "response_context.flow_kind",
            )
        if "message_index" in normalized_context:
            normalized_context["message_index"] = _ensure_int(
                normalized_context["message_index"],
                "response_context.message_index",
            )
        if "prompt_message_id" in normalized_context:
            normalized_context["prompt_message_id"] = _ensure_uuid(
                normalized_context["prompt_message_id"],
                "response_context.prompt_message_id",
            )
        if "response_message_id" in normalized_context:
            normalized_context["response_message_id"] = _ensure_uuid(
                normalized_context["response_message_id"],
                "response_context.response_message_id",
            )
        normalized["response_context"] = normalized_context

    for dict_key in ("flow_state_step_data", "day_config", "result"):
        value = normalized.get(dict_key)
        if value is not None and not isinstance(value, dict):
            raise TypeError(f"Field '{dict_key}' must be a dict when provided.")

    messages = normalized.get("messages")
    if messages is not None and not isinstance(messages, list):
        raise TypeError("Field 'messages' must be a list when provided.")

    error = normalized.get("error")
    if error is not None and not isinstance(error, str):
        raise TypeError("Field 'error' must be a string when provided.")

    return normalized
