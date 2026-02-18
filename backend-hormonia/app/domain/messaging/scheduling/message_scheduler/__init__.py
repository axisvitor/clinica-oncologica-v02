"""
MessageScheduler package - modular message scheduling service.

This package provides time-based message delivery with timezone handling,
integrating with Celery for reliable scheduling and delivery tracking.
"""

# Import main classes
from .scheduler import MessageScheduler, get_message_scheduler
from .config import MessageSchedulerConfig
from .models import (
    MessageSchedulingError,
    TimezoneError,
    TaskSchedulingError,
    SchedulingWindow,
)
from .timezone_handler import TimezoneHandler
from .task_scheduler import TaskScheduler
from .retry_handler import RetryHandler
from .metrics import MetricsCollector

# Public API
__all__ = [
    # Main scheduler
    "MessageScheduler",
    "get_message_scheduler",
    # Configuration
    "MessageSchedulerConfig",
    # Exceptions and enums
    "MessageSchedulingError",
    "TimezoneError",
    "TaskSchedulingError",
    "SchedulingWindow",
    # Component handlers (for advanced usage)
    "TimezoneHandler",
    "TaskScheduler",
    "RetryHandler",
    "MetricsCollector",
]
