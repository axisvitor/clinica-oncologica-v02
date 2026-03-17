"""
Shared helpers for message scheduler modules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.models.message import Message


def ensure_message_metadata(message: Message, logger: logging.Logger) -> Dict[str, Any]:
    """Guarantee message.message_metadata is a mutable dictionary."""
    metadata = getattr(message, "message_metadata", None)
    if isinstance(metadata, dict):
        return metadata

    if metadata is None:
        normalized = {}
    else:
        try:
            normalized = dict(metadata)
        except Exception:
            logger.warning(
                "Invalid message_metadata type for message %s: %s",
                getattr(message, "id", "<unknown>"),
                type(metadata).__name__,
            )
            normalized = {}

    message.message_metadata = normalized
    return normalized


async def get_task_status(task_id: str, logger: logging.Logger) -> Dict[str, Any]:
    """Fetch task status — returns a stub since Celery AsyncResult is removed."""
    return {
        "task_id": task_id,
        "status": "UNKNOWN",
        "result": None,
        "traceback": None,
        "date_done": None,
        "note": "Task status polling removed with Celery migration",
    }
