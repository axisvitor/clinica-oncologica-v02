"""Shim - canonical code lives in sequential_message_handler_pkg/. See Phase 18."""

from app.services.flow.sequential_message_handler_pkg import (
    SequentialMessageHandler,
    get_sequential_message_handler,
)

__all__ = [
    "SequentialMessageHandler",
    "get_sequential_message_handler",
]
