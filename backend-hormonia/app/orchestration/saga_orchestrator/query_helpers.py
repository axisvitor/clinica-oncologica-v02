"""
Shared query helpers for saga orchestration modules.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import String, cast, or_


def metadata_key_equals(metadata_column: Any, key: str, value: str):
    """
    Build a dialect-agnostic JSON metadata filter by casting to text.

    This keeps behavior stable across SQLite/PostgreSQL test and runtime paths.
    """
    metadata_text = cast(metadata_column, String)
    escaped_value = value.replace('"', '\\"')
    return or_(
        metadata_text.like(f'%"{key}": "{escaped_value}"%'),
        metadata_text.like(f'%"{key}":"{escaped_value}"%'),
    )


__all__ = ["metadata_key_equals"]
