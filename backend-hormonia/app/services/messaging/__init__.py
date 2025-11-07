"""
DEPRECATED: This module has been moved to app.domain.messaging

This directory is kept for backward compatibility only.
Please update your imports to:
    from app.domain.messaging import MessageService, WhatsAppService
"""
import warnings

warnings.warn(
    "app.services.messaging has been moved to app.domain.messaging. "
    "Please update your imports.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from app.domain.messaging import (
    MessageService,
    WhatsAppService,
    MessageScheduler,
    MessageSender,
    IdempotentMessageSender,
    MessageFactory
)

__all__ = [
    "MessageService",
    "WhatsAppService",
    "MessageScheduler",
    "MessageSender",
    "IdempotentMessageSender",
    "MessageFactory"
]
