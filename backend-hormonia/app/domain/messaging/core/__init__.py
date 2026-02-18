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

__all__ = [
    "MessageService",
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
