"""Validation helpers for template day_config payloads."""

from __future__ import annotations

from typing import Any

from app.services.flow._flow_orchestration_utils import _CANONICAL_SEND_MODES


def _coerce_bool(value: Any) -> bool:
    """Normalize loose boolean-like values stored in template metadata."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on", "sim"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", "", "nao", "não"}:
            return False
    return bool(value)


class DayConfigValidationError(ValueError):
    """Raised when template day_config is structurally invalid."""

    def __init__(self, message: str, *, errors: list[str] | None = None) -> None:
        self.errors = errors or [message]
        super().__init__(message)


def validate_day_config(
    day_config: Any,
    *,
    flow_kind: str = "",
    day_number: int = 0,
) -> dict[str, Any]:
    """Validate and lightly normalize a day_config payload before dispatch."""
    if day_config is None:
        raise DayConfigValidationError(
            f"day_config is None for flow_kind={flow_kind} day={day_number}",
            errors=["day_config is None"],
        )

    if not isinstance(day_config, dict):
        raise DayConfigValidationError(
            f"day_config must be a dict, got {type(day_config).__name__}",
            errors=["day_config must be a dict"],
        )

    errors: list[str] = []

    send_mode = day_config.get("send_mode", "single")
    if send_mode is None or (isinstance(send_mode, str) and not send_mode.strip()):
        day_config["send_mode"] = "single"
    elif not isinstance(send_mode, str):
        errors.append(f"send_mode must be a string, got {type(send_mode).__name__}")
    else:
        normalized_send_mode = send_mode.strip().lower()
        if normalized_send_mode not in _CANONICAL_SEND_MODES:
            allowed_values = ", ".join(sorted(_CANONICAL_SEND_MODES))
            errors.append(
                f"Invalid send_mode '{send_mode}'. Allowed values: {allowed_values}"
            )
        else:
            day_config["send_mode"] = normalized_send_mode

    if "messages" not in day_config:
        errors.append("'messages' key is missing from day_config")
    else:
        messages = day_config.get("messages")
        if not isinstance(messages, list):
            errors.append(f"'messages' must be a list, got {type(messages).__name__}")
        elif not messages:
            errors.append("'messages' list is empty - no messages to send")
        else:
            for index, message in enumerate(messages):
                if not isinstance(message, dict):
                    errors.append(
                        f"messages[{index}] must be a dict, got {type(message).__name__}"
                    )
                    continue

                content = message.get("content")
                if content is None:
                    errors.append(f"messages[{index}] missing required 'content' key")
                elif not isinstance(content, str):
                    errors.append(
                        f"messages[{index}].content must be a string, got {type(content).__name__}"
                    )
                elif not content.strip():
                    errors.append(f"messages[{index}].content is empty")

                if "expects_response" in message:
                    message["expects_response"] = _coerce_bool(
                        message.get("expects_response")
                    )

                delay_seconds = message.get("delay_seconds")
                if delay_seconds is not None:
                    if isinstance(delay_seconds, bool) or not isinstance(
                        delay_seconds, (int, float)
                    ):
                        errors.append(
                            f"messages[{index}].delay_seconds must be a number, got {type(delay_seconds).__name__}"
                        )
                    elif delay_seconds < 0:
                        errors.append(
                            f"messages[{index}].delay_seconds must be >= 0"
                        )

    if errors:
        detail = "; ".join(errors).replace(
            "'messages' list is empty",
            "messages list is empty",
        )
        raise DayConfigValidationError(
            f"day_config validation failed for flow_kind={flow_kind} day={day_number}: {detail}",
            errors=errors,
        )

    return day_config
