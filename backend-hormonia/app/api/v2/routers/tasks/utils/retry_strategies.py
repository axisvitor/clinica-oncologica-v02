"""
Retry Strategy Utilities

Functions for calculating retry delays based on different strategies:
- IMMEDIATE: No delay
- LINEAR: Proportional delay increase
- EXPONENTIAL: Exponential backoff
- FIBONACCI: Fibonacci sequence delays
"""

from app.schemas.v2.tasks import RetryStrategy


def _calculate_retry_delay(
    retry_count: int, strategy: RetryStrategy, base_delay: int, max_delay: int
) -> int:
    """
    Calculate retry delay based on strategy.

    Implements different retry delay strategies with configurable
    base delay and maximum delay cap.

    Args:
        retry_count: Number of retry attempts so far (0-indexed)
        strategy: Retry strategy to use
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds

    Returns:
        Calculated delay in seconds (capped at max_delay)
    """
    if strategy == RetryStrategy.IMMEDIATE:
        return 0
    elif strategy == RetryStrategy.LINEAR:
        return min(base_delay * (retry_count + 1), max_delay)
    elif strategy == RetryStrategy.EXPONENTIAL:
        return min(base_delay * (2**retry_count), max_delay)
    elif strategy == RetryStrategy.FIBONACCI:
        fib = [1, 1]
        for i in range(retry_count):
            fib.append(fib[-1] + fib[-2])
        return min(base_delay * fib[retry_count], max_delay)
    return base_delay
