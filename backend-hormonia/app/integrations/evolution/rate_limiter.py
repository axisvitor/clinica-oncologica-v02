"""
Rate limiting functionality for Evolution API requests.
"""

import time
from typing import List

import structlog

logger = structlog.get_logger(__name__)


class RateLimiter:
    """Rate limiter for API requests."""

    def __init__(self, requests_per_second: int = 10):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Maximum requests allowed per second
        """
        self.requests_per_second = requests_per_second
        self.request_times: List[float] = []
        self.last_reset = time.time()

    def check_rate_limit(self) -> bool:
        """
        Check and enforce rate limiting with improved efficiency.

        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        current_time = time.time()

        # Reset counter every second
        if current_time - self.last_reset > 1:
            self.request_times = []
            self.last_reset = current_time

        # Remove requests older than 1 second (optimization: use list comprehension)
        cutoff_time = current_time - 1
        self.request_times = [t for t in self.request_times if t > cutoff_time]

        # Check if we're under the limit
        current_requests = len(self.request_times)
        if current_requests >= self.requests_per_second:
            logger.warning(
                "Evolution API rate limit exceeded",
                requests_in_last_second=current_requests,
                limit=self.requests_per_second,
                wait_time=1.0 - (current_time - min(self.request_times)),
            )
            return False

        # Record this request
        self.request_times.append(current_time)
        return True

    def get_remaining_quota(self) -> int:
        """
        Get remaining request quota for current second.

        Returns:
            Number of remaining requests allowed
        """
        current_time = time.time()
        cutoff_time = current_time - 1
        recent_requests = [t for t in self.request_times if t > cutoff_time]
        return max(0, self.requests_per_second - len(recent_requests))
