"""
Message Service Exceptions (QW-022).

This module contains custom exceptions for message service operations.
"""


class MessageSchedulingError(Exception):
    """Base exception for message scheduling errors."""

    pass


class TimezoneError(MessageSchedulingError):
    """Exception for timezone-related errors."""

    pass


class TaskSchedulingError(MessageSchedulingError):
    """Exception for task scheduling errors."""

    pass
