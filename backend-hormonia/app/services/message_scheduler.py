"""
DEPRECATED: This module has been moved to app.domain.messaging.scheduling

This file is kept for backward compatibility only.
Please update your imports to:
    from app.domain.messaging.scheduling import MessageScheduler
"""
import warnings

warnings.warn(
    "message_scheduler has been moved to app.domain.messaging.scheduling. "
    "Please update your imports.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from app.domain.messaging.scheduling import MessageScheduler

__all__ = ["MessageScheduler"]
