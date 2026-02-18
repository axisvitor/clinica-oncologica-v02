"""
Shared parsers for flow context payload normalization.
"""

from __future__ import annotations

from typing import Any, Optional


def parse_optional_bool(value: Any) -> Optional[bool]:
    """Parse tolerant boolean values from loosely typed context values."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "sim"}:
            return True
        if normalized in {"false", "0", "no", "n", "nao", "não", ""}:
            return False
    return bool(value)


def parse_optional_int(value: Any) -> Optional[int]:
    """Parse numeric flow identifiers (day/index) from loosely typed context values."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None
    return None


def parse_optional_str(value: Any) -> Optional[str]:
    """Normalize optional string values from loosely typed context values."""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
