"""Shared boolean flag helpers for flow services."""

from __future__ import annotations

from typing import Any, Optional


def is_awaiting_response(step_data: Optional[dict[str, Any]]) -> bool:
    """Interpret awaiting_response with tolerant truthy string handling."""
    if not step_data:
        return False
    value = step_data.get("awaiting_response")
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def message_expects_response(message: Any) -> bool:
    """Check whether a message metadata payload marks expects_response."""
    metadata = getattr(message, "message_metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
    expects = metadata.get("expects_response")
    if isinstance(expects, str):
        expects = expects.strip().lower() in {"true", "1", "yes", "sim"}
    return bool(expects)
