"""
Configuration for message scheduling service.
"""
from datetime import time
from .models import SchedulingWindow


class MessageSchedulerConfig:
    """Configuration constants for MessageScheduler."""

    # Scheduling windows (start_time, end_time)
    SCHEDULING_WINDOWS = {
        SchedulingWindow.MORNING: (time(9, 0), time(12, 0)),
        SchedulingWindow.AFTERNOON: (time(12, 0), time(17, 0)),
        SchedulingWindow.EVENING: (time(17, 0), time(20, 0)),
        SchedulingWindow.BUSINESS_HOURS: (time(9, 0), time(18, 0)),
        SchedulingWindow.EXTENDED_HOURS: (time(8, 0), time(21, 0))
    }

    # Message constraints
    MAX_MESSAGE_LENGTH = 4096  # WhatsApp message limit
    MIN_SCHEDULING_BUFFER_MINUTES = 15  # Minimum time before sending
    FALLBACK_DELAY_MINUTES = 30  # Fallback delay when calculation fails

    # Default timezone
    DEFAULT_TIMEZONE = "America/Sao_Paulo"

    # Retry configuration
    MAX_TASK_RETRIES = 3
    RETRY_DELAY_SECONDS = 60
    MAX_DELIVERY_RETRIES = 3
    RETRY_INITIAL_DELAY_MINUTES = 5
    RETRY_BACKOFF_BASE = 2
