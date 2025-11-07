"""
DEPRECATED: This module has been moved to app.domain.messaging.core

This file is kept for backward compatibility only.
Please update your imports to:
    from app.domain.messaging.core import MessageBaseService
"""
import warnings

warnings.warn(
    "message service has been moved to app.domain.messaging.core. "
    "Please update your imports.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from app.domain.messaging.core import MessageBaseService as MessageService

__all__ = ["MessageService"]
