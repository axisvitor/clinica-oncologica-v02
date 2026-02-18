"""
Data models, enums, and exceptions for message scheduling.
"""

from app.domain.messaging.core.message_service.config import SchedulingWindow


class MessageSchedulingError(Exception):
    """Base exception for message scheduling errors."""

    pass


class TimezoneError(MessageSchedulingError):
    """Exception for timezone-related errors."""

    pass


class TaskSchedulingError(MessageSchedulingError):
    """Exception for Celery task scheduling errors."""

    pass

