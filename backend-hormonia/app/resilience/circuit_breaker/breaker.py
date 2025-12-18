"""
Circuit Breaker Implementation

Production-ready circuit breaker pattern with comprehensive monitoring.
"""

import asyncio
import time
from enum import Enum
from typing import Any, Callable, Optional, Dict, List
from dataclasses import dataclass, field
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class CircuitBreakerStates(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""

    failure_threshold: int = 5  # Failures to trip breaker
    recovery_timeout: float = 60.0  # Seconds before retry
    success_threshold: int = 3  # Successes to close breaker
    timeout: float = 30.0  # Request timeout
    expected_exception: tuple = (Exception,)  # Exceptions that count as failures

    # Monitoring
    monitor_window: int = 60  # Monitoring window in seconds
    min_requests: int = 10  # Min requests before evaluation


@dataclass
class CircuitBreakerMetrics:
    """Circuit breaker metrics"""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    circuit_breaker_trips: int = 0
    current_state: CircuitBreakerStates = CircuitBreakerStates.CLOSED
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    failure_rate: float = 0.0

    # Time series data
    state_changes: List[Dict] = field(default_factory=list)
    request_history: List[Dict] = field(default_factory=list)


class CircuitBreakerError(Exception):
    """Circuit breaker specific exception"""

    pass


class CircuitBreakerOpenError(CircuitBreakerError):
    """Raised when circuit breaker is open"""

    pass


class CircuitBreaker:
    """
    Production-ready circuit breaker implementation

    Features:
    - Three states: CLOSED, OPEN, HALF_OPEN
    - Configurable failure thresholds
    - Automatic recovery testing
    - Comprehensive metrics
    - Thread-safe operation
    """

    def __init__(self, config: CircuitBreakerConfig, name: str = "default"):
        self.config = config
        self.name = name
        self.state = CircuitBreakerStates.CLOSED
        self.metrics = CircuitBreakerMetrics()

        # State management
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._lock = Lock()

        # Monitoring
        self._request_times = []

        logger.info(f"Circuit breaker '{name}' initialized with config: {config}")

    def __call__(self, func: Callable) -> Callable:
        """Decorator interface"""
        if asyncio.iscoroutinefunction(func):
            return self._async_wrapper(func)
        else:
            return self._sync_wrapper(func)

    def _sync_wrapper(self, func: Callable) -> Callable:
        """Synchronous wrapper"""

        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)

        return wrapper

    def _async_wrapper(self, func: Callable) -> Callable:
        """Asynchronous wrapper"""

        async def wrapper(*args, **kwargs):
            return await self.acall(func, *args, **kwargs)

        return wrapper

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        with self._lock:
            self._record_request()

            if self.state == CircuitBreakerStates.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    self._record_rejection()
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN"
                    )

        # Execute the function
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            self._record_success(execution_time)
            return result

        except self.config.expected_exception as e:
            execution_time = time.time() - start_time
            self._record_failure(execution_time, str(e))
            raise

    async def acall(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with circuit breaker protection"""
        with self._lock:
            self._record_request()

            if self.state == CircuitBreakerStates.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    self._record_rejection()
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN"
                    )

        # Execute the async function
        start_time = time.time()
        try:
            result = await asyncio.wait_for(
                func(*args, **kwargs), timeout=self.config.timeout
            )
            execution_time = time.time() - start_time
            self._record_success(execution_time)
            return result

        except (asyncio.TimeoutError, *self.config.expected_exception) as e:
            execution_time = time.time() - start_time
            self._record_failure(execution_time, str(e))
            raise

    def _record_request(self):
        """Record a request attempt"""
        self.metrics.total_requests += 1
        current_time = time.time()

        # Clean old request times
        cutoff_time = current_time - self.config.monitor_window
        self._request_times = [t for t in self._request_times if t > cutoff_time]
        self._request_times.append(current_time)

        # Record in history
        self.metrics.request_history.append(
            {"timestamp": current_time, "state": self.state.value, "type": "request"}
        )

    def _record_success(self, execution_time: float):
        """Record a successful execution"""
        with self._lock:
            self.metrics.successful_requests += 1
            self.metrics.last_success_time = time.time()

            if self.state == CircuitBreakerStates.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._transition_to_closed()

            self._update_failure_rate()

            logger.debug(
                f"Circuit breaker '{self.name}' recorded success "
                f"(execution_time={execution_time:.3f}s)"
            )

    def _record_failure(self, execution_time: float, error: str):
        """Record a failed execution"""
        with self._lock:
            self.metrics.failed_requests += 1
            self.metrics.last_failure_time = time.time()
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self.state == CircuitBreakerStates.CLOSED:
                if self._should_trip():
                    self._transition_to_open()
            elif self.state == CircuitBreakerStates.HALF_OPEN:
                self._transition_to_open()

            self._update_failure_rate()

            logger.warning(
                f"Circuit breaker '{self.name}' recorded failure: {error} "
                f"(execution_time={execution_time:.3f}s, failures={self._failure_count})"
            )

    def _record_rejection(self):
        """Record a rejected request"""
        logger.debug(f"Circuit breaker '{self.name}' rejected request (state=OPEN)")

    def _should_trip(self) -> bool:
        """Check if circuit breaker should trip to OPEN"""
        if len(self._request_times) < self.config.min_requests:
            return False

        return self._failure_count >= self.config.failure_threshold

    def _should_attempt_reset(self) -> bool:
        """Check if should attempt reset from OPEN to HALF_OPEN"""
        if not self._last_failure_time:
            return False

        time_since_failure = time.time() - self._last_failure_time
        return time_since_failure >= self.config.recovery_timeout

    def _transition_to_open(self):
        """Transition to OPEN state"""
        if self.state != CircuitBreakerStates.OPEN:
            self.state = CircuitBreakerStates.OPEN
            self.metrics.circuit_breaker_trips += 1
            self.metrics.current_state = self.state

            self._record_state_change("OPEN", "Failure threshold exceeded")
            logger.warning(f"Circuit breaker '{self.name}' transitioned to OPEN")

    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state"""
        self.state = CircuitBreakerStates.HALF_OPEN
        self.metrics.current_state = self.state
        self._success_count = 0

        self._record_state_change("HALF_OPEN", "Recovery timeout elapsed")
        logger.info(f"Circuit breaker '{self.name}' transitioned to HALF_OPEN")

    def _transition_to_closed(self):
        """Transition to CLOSED state"""
        self.state = CircuitBreakerStates.CLOSED
        self.metrics.current_state = self.state
        self._failure_count = 0
        self._success_count = 0

        self._record_state_change("CLOSED", "Success threshold met")
        logger.info(f"Circuit breaker '{self.name}' transitioned to CLOSED")

    def _record_state_change(self, new_state: str, reason: str):
        """Record state change for monitoring"""
        self.metrics.state_changes.append(
            {
                "timestamp": time.time(),
                "from_state": self.state.value,
                "to_state": new_state,
                "reason": reason,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
            }
        )

    def _update_failure_rate(self):
        """Update failure rate metric"""
        if self.metrics.total_requests > 0:
            self.metrics.failure_rate = (
                self.metrics.failed_requests / self.metrics.total_requests
            )

    def get_metrics(self) -> Dict:
        """Get comprehensive metrics"""
        current_time = time.time()
        recent_requests = len(
            [
                t
                for t in self._request_times
                if t > current_time - self.config.monitor_window
            ]
        )

        return {
            "name": self.name,
            "state": self.state.value,
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "failure_rate": self.metrics.failure_rate,
            "circuit_breaker_trips": self.metrics.circuit_breaker_trips,
            "recent_requests": recent_requests,
            "last_failure_time": self.metrics.last_failure_time,
            "last_success_time": self.metrics.last_success_time,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
            },
        }

    def force_open(self):
        """Manually force circuit breaker to OPEN state"""
        with self._lock:
            self._transition_to_open()
            logger.warning(f"Circuit breaker '{self.name}' manually forced to OPEN")

    def force_closed(self):
        """Manually force circuit breaker to CLOSED state"""
        with self._lock:
            self._transition_to_closed()
            logger.info(f"Circuit breaker '{self.name}' manually forced to CLOSED")

    def reset(self):
        """Reset circuit breaker to initial state"""
        with self._lock:
            self.state = CircuitBreakerStates.CLOSED
            self.metrics = CircuitBreakerMetrics()
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._request_times = []

            logger.info(f"Circuit breaker '{self.name}' reset to initial state")
