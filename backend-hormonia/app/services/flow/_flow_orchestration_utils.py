"""Shared helpers for direct flow orchestration modules."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections.abc import Mapping
from typing import Any, Dict, List, Optional, TypedDict
from uuid import UUID

logger = logging.getLogger(__name__)

_CANONICAL_SEND_MODES = frozenset(
    {"single", "sequential_auto", "wait_response", "wait_each"}
)
_THREAD_ID_REQUIRED_MESSAGE = (
    "LangGraph thread_id missing. Pass it via config['configurable']['thread_id']."
)
_THREAD_ID_MAX_LENGTH = 96
_THREAD_ID_SANITIZE_PATTERN = re.compile(r"[\s\0\r\n\t]+")


class FlowResponseContext(TypedDict, total=False):
    """Optional correlation payload attached to an inbound patient response."""

    flow_day: int
    flow_kind: str
    message_index: int
    prompt_message_id: UUID
    response_message_id: UUID


class FlowMessageState(TypedDict, total=False):
    """Shared flow state for flow message execution."""

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
    """Lightweight runtime validation for flow state."""
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
        normalized["send_mode"] = _ensure_str(normalized["send_mode"], "send_mode")

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
                normalized_context["flow_kind"], "response_context.flow_kind"
            )
        if "message_index" in normalized_context:
            normalized_context["message_index"] = _ensure_int(
                normalized_context["message_index"], "response_context.message_index"
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


def validate_thread_id(thread_id: Any) -> str:
    """Validate and normalize thread ids."""
    if thread_id is None:
        raise ValueError(_THREAD_ID_REQUIRED_MESSAGE)
    normalized = _THREAD_ID_SANITIZE_PATTERN.sub("-", str(thread_id).strip())
    if not normalized:
        raise ValueError(_THREAD_ID_REQUIRED_MESSAGE)
    if len(normalized) > _THREAD_ID_MAX_LENGTH:
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
        normalized = f"{normalized[:48]}:{digest}"
    return normalized


def require_configurable_thread_id(config: Optional[dict]) -> str:
    """Extract and validate thread_id from run config."""
    configurable = (config or {}).get("configurable")
    if not isinstance(configurable, Mapping):
        raise ValueError(_THREAD_ID_REQUIRED_MESSAGE)
    return validate_thread_id(configurable.get("thread_id"))


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


def _require_handler(config: Optional[dict]) -> Any:
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
