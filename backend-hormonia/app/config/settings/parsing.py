"""
Shared parsing helpers for settings modules.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, MutableMapping

_FALSE_STRINGS = {"false", "0", "no", "off", ""}


def parse_boolean_env_values(
    data: MutableMapping[str, Any],
    field_names: Iterable[str],
) -> None:
    """Normalize boolean env values in-place for known fields."""
    for field in field_names:
        if field not in data:
            continue
        value = data[field]
        if isinstance(value, bool):
            data[field] = value
        elif isinstance(value, str):
            data[field] = value.lower() not in _FALSE_STRINGS
        else:
            data[field] = bool(value)


def strip_wrapping_quotes(value: str) -> str:
    """Strip repeated matching wrapping quotes from environment values."""
    stripped = value.strip()
    while (
        len(stripped) >= 2
        and stripped[0] == stripped[-1]
        and stripped[0] in ('"', "'")
    ):
        stripped = stripped[1:-1].strip()
    return stripped


def parse_list_env_value(
    value: Any,
    *,
    allow_quoted_json: bool = False,
) -> list[Any]:
    """Parse list-like env values from JSON or comma-separated strings."""
    if isinstance(value, list):
        return value
    if value is None or value == "":
        return []
    if not isinstance(value, str):
        return []

    raw = value.strip()
    if not raw:
        return []

    if allow_quoted_json:
        raw = strip_wrapping_quotes(raw)

    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

    normalized = raw.replace("[", "").replace("]", "")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def parse_list_field(
    data: MutableMapping[str, Any],
    field_name: str,
    *,
    allow_quoted_json: bool = False,
) -> None:
    """Parse a list-like field in-place if present."""
    if field_name not in data:
        return
    data[field_name] = parse_list_env_value(
        data[field_name],
        allow_quoted_json=allow_quoted_json,
    )
