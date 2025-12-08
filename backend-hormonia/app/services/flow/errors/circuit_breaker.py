from __future__ import annotations
from typing import Any, Optional
"""
Simple circuit breaker implementation for flow integrations.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class CircuitState:
    failures: int = 0
    opened_at: Optional[datetime] = None


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.reset_timeout = timedelta(seconds=reset_timeout_seconds)
        self.state = CircuitState()

    def record_success(self) -> None:
        self.state.failures = 0
        self.state.opened_at = None

    def record_failure(self) -> None:
        self.state.failures += 1
        if self.state.failures >= self.failure_threshold:
            self.state.opened_at = datetime.utcnow()

    def allow_request(self) -> bool:
        if self.state.opened_at is None:
            return True
        if datetime.utcnow() - self.state.opened_at >= self.reset_timeout:
            self.state = CircuitState()
            return True
        return False


__all__ = ["CircuitBreaker"]
