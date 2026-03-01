"""
Version parsing helpers shared across API and repository layers.
"""

from __future__ import annotations

from typing import Any


def parse_version_number(value: Any) -> int:
    """Parse integer major version from raw values (e.g. `2`, `2.0.0`)."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            parts = value.split(".")
            for part in parts:
                if part.isdigit():
                    return int(part)
    raise ValueError(f"Invalid version value: {value}")


def parse_version_number_or_default(value: Any, default: int = 1) -> int:
    """Parse version number and return a safe default when invalid/missing."""
    if value is None:
        return default
    try:
        return parse_version_number(value)
    except (TypeError, ValueError):
        return default
