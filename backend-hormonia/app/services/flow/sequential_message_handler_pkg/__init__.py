"""Split sequential message handler package with compatibility re-exports."""

from .service import SequentialMessageHandler, get_sequential_message_handler

__all__ = [
    "SequentialMessageHandler",
    "get_sequential_message_handler",
]
