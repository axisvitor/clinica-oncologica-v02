"""
Base types and interfaces for DLQ Service.

This module contains all base types, enums, and protocol definitions
used across the DLQ (Dead Letter Queue) system.
"""

from enum import Enum
from typing import Protocol, Any, Optional, Dict, Tuple
from uuid import UUID
from datetime import datetime


class ErrorCategory(str, Enum):
    """
    Categories for intelligent retry strategy.

    - TRANSIENT: Temporary errors - automatic retry
    - PERMANENT: Permanent errors - requires manual intervention
    - UNKNOWN: Unknown errors - requires analysis
    """
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


class RetryConfig:
    """Configuration for retry behavior."""

    # Maximum retry attempts before giving up
    MAX_RETRY_ATTEMPTS: int = 5

    # Retry delays in seconds (exponential backoff)
    # [1min, 5min, 15min, 1h, 2h]
    RETRY_DELAYS: list[int] = [60, 300, 900, 3600, 7200]

    # Transient errors that should retry automatically
    TRANSIENT_ERRORS: list[str] = [
        "ConnectionError",
        "TimeoutError",
        "ConnectionResetError",
        "TemporaryFailure",
        "ServiceUnavailable",
        "TooManyRequests",
        "RateLimitExceeded",
        "NetworkError",
        "HTTPError: 429",
        "HTTPError: 503",
        "HTTPError: 504",
    ]

    # Permanent errors requiring manual intervention
    PERMANENT_ERRORS: list[str] = [
        "ValidationError",
        "AuthenticationError",
        "AuthorizationError",
        "NotFoundError",
        "InvalidCredentials",
        "HTTPError: 400",
        "HTTPError: 401",
        "HTTPError: 403",
        "HTTPError: 404",
        "HTTPError: 422",
    ]


class MessageProcessor(Protocol):
    """Protocol for message processing handlers."""

    def process(
        self,
        payload: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Process a message payload.

        Args:
            payload: Message payload data
            metadata: Additional metadata

        Returns:
            True if processing succeeded, False otherwise
        """
        ...


class RetryHandler(Protocol):
    """Protocol for retry logic handlers."""

    def should_retry(
        self,
        retry_count: int,
        error_category: ErrorCategory
    ) -> bool:
        """
        Determine if message should be retried.

        Args:
            retry_count: Current retry count
            error_category: Category of the error

        Returns:
            True if should retry, False otherwise
        """
        ...

    def get_retry_delay(self, retry_count: int) -> int:
        """
        Calculate delay before next retry.

        Args:
            retry_count: Current retry count

        Returns:
            Delay in seconds
        """
        ...


class MetricsCollector(Protocol):
    """Protocol for metrics collection."""

    def record_message_added(
        self,
        category: str,
        error_type: str
    ) -> None:
        """Record a message being added to DLQ."""
        ...

    def record_retry_attempt(
        self,
        category: str,
        success: bool,
        duration_seconds: float
    ) -> None:
        """Record a retry attempt."""
        ...

    def update_queue_size(
        self,
        category: str,
        status: str,
        size: int
    ) -> None:
        """Update queue size metric."""
        ...


__all__ = [
    "ErrorCategory",
    "RetryConfig",
    "MessageProcessor",
    "RetryHandler",
    "MetricsCollector",
]
