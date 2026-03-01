"""
Utilities for deterministic thread/checkpoint identifiers.
"""

from __future__ import annotations


def sanitize_thread_component(value) -> str:
    """Normalize thread component values to safe deterministic text."""
    text = str(value).strip() if value is not None else ""
    if not text:
        return "unknown"
    return "".join(
        ch if ch.isalnum() or ch in {"-", "_", "."} else "_"
        for ch in text
    )
