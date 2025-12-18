"""
Retry helpers used by FlowManager and FlowEngine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Awaitable, Type, Tuple
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class RetryPolicy:
    attempts: int = 3
    backoff_seconds: float = 2.0
    multiplier: float = 2.0
    retry_exceptions: Tuple[Type[Exception], ...] = (Exception,)

    async def run(self, fn: Callable[[], Awaitable]):
        delay = self.backoff_seconds
        last_error: Exception | None = None

        for attempt in range(1, self.attempts + 1):
            try:
                return await fn()
            except self.retry_exceptions as exc:  # type: ignore
                last_error = exc
                logger.warning(
                    "Retryable error on attempt %s/%s: %s", attempt, self.attempts, exc
                )
                await asyncio.sleep(delay)
                delay *= self.multiplier

        if last_error:
            raise last_error


__all__ = ["RetryPolicy"]
