"""
Data models, enums, and exceptions for message scheduling.
"""
from enum import Enum


class MessageSchedulingError(Exception):
    """Base exception for message scheduling errors."""
    pass


class TimezoneError(MessageSchedulingError):
    """Exception for timezone-related errors."""
    pass


class TaskSchedulingError(MessageSchedulingError):
    """Exception for Celery task scheduling errors."""
    pass


class SchedulingWindow(Enum):
    """Predefined scheduling windows for message delivery."""
    MORNING = "morning"  # 9:00 - 12:00
    AFTERNOON = "afternoon"  # 12:00 - 17:00
    EVENING = "evening"  # 17:00 - 20:00
    BUSINESS_HOURS = "business_hours"  # 9:00 - 18:00
    EXTENDED_HOURS = "extended_hours"  # 8:00 - 21:00
