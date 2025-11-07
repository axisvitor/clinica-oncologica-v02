"""
DEPRECATED: This module has been moved to app.domain.messaging.delivery

This file is kept for backward compatibility only.
Please update your imports to:
    from app.domain.messaging.delivery import MessageSender
"""
import warnings

warnings.warn(
    "message_sender has been moved to app.domain.messaging.delivery. "
    "Please update your imports.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from app.domain.messaging.delivery import MessageSender

__all__ = ["MessageSender"]
