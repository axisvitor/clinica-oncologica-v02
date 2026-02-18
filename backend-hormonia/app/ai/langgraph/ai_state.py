"""Unified AI state definitions for LangGraph."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, List, Optional, TypedDict


class AIState(TypedDict, total=False):
    """
    Unified state for AI orchestration.
    Used for humanization, sentiment analysis, classification, etc.
    """

    # Input data
    input_text: str
    template: Optional[str]
    context: Dict[str, Any]
    history: List[str]
    hints: List[str]

    # Processing parameters
    message_type: Optional[str]
    output_kind: str  # e.g., 'message', 'json', 'question'
    
    # Results
    output: Any
    confidence: float
    metadata: Dict[str, Any]
    
    # Error handling
    error: Optional[str]


def _ensure_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"Field '{field_name}' must be a string.")
    return value


def _ensure_optional_str(value: Any, field_name: str) -> Optional[str]:
    if value is None:
        return None
    return _ensure_str(value, field_name)


def _ensure_dict(value: Any, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"Field '{field_name}' must be a dict.")
    return value


def _ensure_list(value: Any, field_name: str) -> List[Any]:
    if not isinstance(value, list):
        raise TypeError(f"Field '{field_name}' must be a list.")
    return value


def validate_ai_state(
    state: Any,
    *,
    required_keys: tuple[str, ...] = (),
) -> AIState:
    """
    Lightweight runtime validation for AI graph state.

    Validates only critical input shape and key field types.
    """
    if not isinstance(state, Mapping):
        raise TypeError("AIState must be a dict-like object.")

    missing = [key for key in required_keys if key not in state]
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"Missing required AIState keys: {missing_text}.")

    normalized: AIState = dict(state)

    for key in required_keys:
        if normalized.get(key) is None:
            raise ValueError(f"Required AIState key '{key}' cannot be None.")

    if "input_text" in normalized:
        normalized["input_text"] = _ensure_str(normalized["input_text"], "input_text")
    if "template" in normalized:
        normalized["template"] = _ensure_optional_str(normalized["template"], "template")
    if "context" in normalized:
        normalized["context"] = _ensure_dict(normalized["context"], "context")
    if "history" in normalized:
        normalized["history"] = _ensure_list(normalized["history"], "history")
    if "hints" in normalized:
        normalized["hints"] = _ensure_list(normalized["hints"], "hints")
    if "message_type" in normalized:
        normalized["message_type"] = _ensure_optional_str(
            normalized["message_type"], "message_type"
        )
    if "output_kind" in normalized:
        normalized["output_kind"] = _ensure_str(
            normalized["output_kind"], "output_kind"
        )
    if "confidence" in normalized:
        confidence = normalized["confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise TypeError("Field 'confidence' must be numeric.")
        normalized["confidence"] = float(confidence)
    if "metadata" in normalized:
        normalized["metadata"] = _ensure_dict(normalized["metadata"], "metadata")
    if "error" in normalized:
        normalized["error"] = _ensure_optional_str(normalized["error"], "error")

    return normalized
