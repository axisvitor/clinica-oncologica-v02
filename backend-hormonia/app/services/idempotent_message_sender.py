"""
DEPRECATED: This module has been moved to app.domain.messaging.delivery

This file is kept for backward compatibility only.
Please update your imports to:
    from app.domain.messaging.delivery import IdempotentMessageSender
"""
import warnings

warnings.warn(
    "idempotent_message_sender has been moved to app.domain.messaging.delivery. "
    "Please update your imports.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from app.domain.messaging.delivery import IdempotentMessageSender

__all__ = ["IdempotentMessageSender"]
