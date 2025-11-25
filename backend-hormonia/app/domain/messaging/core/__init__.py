"""Core messaging services."""
# Import from the new message_service package (modularized)
from .message_service import (
    MessageService,
    MessageFactory,
    MessageScheduler,
    MessageTemplate,
    SchedulingWindow,
    MessageSchedulerConfig,
    MessageSchedulingError,
    TimezoneError,
    TaskSchedulingError,
    get_message_service,
    get_message_factory,
    get_message_scheduler,
)

# Legacy import for backward compatibility
from .message_base import MessageService as MessageBaseService

__all__ = [
    "MessageService",
    "MessageBaseService",
    "MessageFactory",
    "MessageScheduler",
    "MessageTemplate",
    "SchedulingWindow",
    "MessageSchedulerConfig",
    "MessageSchedulingError",
    "TimezoneError",
    "TaskSchedulingError",
    "get_message_service",
    "get_message_factory",
    "get_message_scheduler",
]
