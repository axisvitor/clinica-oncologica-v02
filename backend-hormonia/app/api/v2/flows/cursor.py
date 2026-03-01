"""Shared cursor helpers for flow pagination."""

from datetime import datetime

from app.utils.cursor import encode_cursor

def _create_cursor(item_id: str, created_at: datetime) -> str:
    """Create cursor for pagination."""
    return encode_cursor(item_id, created_at)
