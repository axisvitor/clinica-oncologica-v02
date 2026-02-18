"""Shared text normalization/formatting helpers."""

from __future__ import annotations


def clip_text(text: str, max_len: int = 260, *, ellipsis: str = "...") -> str:
    """Clip text to max_len with configurable ellipsis suffix."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - len(ellipsis)].rstrip() + ellipsis
