"""
Circuit Breaker Service
Implements circuit breaker pattern for AI service resilience.
"""

import asyncio
import logging
from typing import Callable, Any, Optional, Dict, List
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field
import functools

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitStats:
    """Circuit breaker statistics"""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    last_failure_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    state_changes: List[tuple[CircuitState, datetime]] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        return 100.0 - self.success_rate


class CircuitBreaker:
    """
    Circuit breaker for protecting AI service calls.
    Prevents cascading failures and provides fallback mechanisms.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        success_threshold: int = 2,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Circuit breaker name
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before half-opening
            expected_exception: Exception type to catch
            success_threshold: Successes needed to close from half-open
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold

        self.state = CircuitState.CLOSED
        self.stats = CircuitStats()
        self._lock = asyncio.Lock()
        self._last_attempt_time: Optional[datetime] = None

    def can_execute(self) -> bool:
        """
        Check if circuit allows execution (non-async version for sync contexts).

        Returns:
            True if circuit is closed or half-open and ready for retry
        """
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if we should attempt reset
            if self._should_attempt_reset():
                return True  # Allow attempt in half-open state
            return False

        # HALF_OPEN state
        return True

    def record_success(self):
        """Record successful execution (sync version)."""
        self.stats.total_requests += 1
        self.stats.successful_requests += 1
        self.stats.consecutive_failures = 0
        self.stats.consecutive_successes += 1

        if self.state == CircuitState.HALF_OPEN:
            if self.stats.consecutive_successes >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.stats.state_changes.append(
                    (CircuitState.CLOSED, datetime.now(timezone.utc))
                )
                logger.info(f"Circuit {self.name} closed after recovery")

    def record_failure(self):
        """Record failed execution (sync version)."""
        self.stats.total_requests += 1
        self.stats.failed_requests += 1
        self.stats.last_failure_time = datetime.now(timezone.utc)
        self.stats.consecutive_failures += 1
        self.stats.consecutive_successes = 0

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.stats.state_changes.append((CircuitState.OPEN, datetime.now(timezone.utc)))
            logger.warning(f"Circuit {self.name} reopened after test failure")
        elif self.state == CircuitState.CLOSED:
            if self.stats.consecutive_failures >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.stats.state_changes.append((CircuitState.OPEN, datetime.now(timezone.utc)))
                logger.error(
                    f"Circuit {self.name} opened after {self.failure_threshold} failures"
                )

    async def call(
        self, func: Callable, *args, fallback: Optional[Callable] = None, **kwargs
    ) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Async function to call
            *args: Function arguments
            fallback: Optional fallback function
            **kwargs: Function keyword arguments

        Returns:
            Function result or fallback result

        Raises:
            Exception if circuit is open and no fallback
        """
        async with self._lock:
            # Check circuit state
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.stats.state_changes.append(
                        (CircuitState.HALF_OPEN, datetime.now(timezone.utc))
                    )
                    logger.info(f"Circuit {self.name} half-opened for testing")
                else:
                    # Circuit is open, use fallback or raise
                    if fallback:
                        logger.warning(f"Circuit {self.name} is open, using fallback")
                        return await self._execute_fallback(fallback, *args, **kwargs)
                    raise CircuitOpenError(f"Circuit {self.name} is open")

        # Try to execute the function
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result

        except self.expected_exception as e:
            await self._on_failure()

            # Use fallback if available
            if fallback:
                logger.warning(f"Circuit {self.name} call failed, using fallback: {e}")
                return await self._execute_fallback(fallback, *args, **kwargs)
            raise

    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            self.stats.total_requests += 1
            self.stats.successful_requests += 1
            self.stats.consecutive_failures = 0
            self.stats.consecutive_successes += 1

            if self.state == CircuitState.HALF_OPEN:
                if self.stats.consecutive_successes >= self.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.stats.state_changes.append(
                        (CircuitState.CLOSED, datetime.now(timezone.utc))
                    )
                    logger.info(f"Circuit {self.name} closed after recovery")

    async def _on_failure(self):
        """Handle failed call."""
        async with self._lock:
            self.stats.total_requests += 1
            self.stats.failed_requests += 1
            self.stats.last_failure_time = datetime.now(timezone.utc)
            self.stats.consecutive_failures += 1
            self.stats.consecutive_successes = 0

            if self.state == CircuitState.HALF_OPEN:
                # Failed during recovery test, reopen
                self.state = CircuitState.OPEN
                self.stats.state_changes.append((CircuitState.OPEN, datetime.now(timezone.utc)))
                logger.warning(f"Circuit {self.name} reopened after test failure")

            elif self.state == CircuitState.CLOSED:
                if self.stats.consecutive_failures >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    self.stats.state_changes.append(
                        (CircuitState.OPEN, datetime.now(timezone.utc))
                    )
                    logger.error(
                        f"Circuit {self.name} opened after {self.failure_threshold} failures"
                    )

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self.stats.last_failure_time:
            return True

        time_since_failure = datetime.now(timezone.utc) - self.stats.last_failure_time
        return time_since_failure.total_seconds() >= self.recovery_timeout

    async def _execute_fallback(self, fallback: Callable, *args, **kwargs) -> Any:
        """Execute fallback function."""
        try:
            if asyncio.iscoroutinefunction(fallback):
                return await fallback(*args, **kwargs)
            else:
                return fallback(*args, **kwargs)
        except Exception as e:
            logger.error(f"Fallback failed for {self.name}: {e}")
            raise

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self.state

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit statistics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "total_requests": self.stats.total_requests,
            "successful_requests": self.stats.successful_requests,
            "failed_requests": self.stats.failed_requests,
            "success_rate": f"{self.stats.success_rate:.2f}%",
            "consecutive_failures": self.stats.consecutive_failures,
            "consecutive_successes": self.stats.consecutive_successes,
            "last_failure": self.stats.last_failure_time.isoformat()
            if self.stats.last_failure_time
            else None,
        }

    def reset(self):
        """Reset circuit to closed state."""
        self.state = CircuitState.CLOSED
        self.stats = CircuitStats()
        logger.info(f"Circuit {self.name} manually reset")


class CircuitOpenError(Exception):
    """Exception raised when circuit is open."""

    pass


# Alias for backward compatibility
CircuitBreakerOpenError = CircuitOpenError


class AIServiceCircuitBreaker:
    """
    Specialized circuit breaker for AI services with intelligent fallbacks.
    """

    def __init__(self):
        """Initialize AI service circuit breaker."""
        self.breakers = {
            "gemini": CircuitBreaker(
                name="gemini",
                failure_threshold=3,
                recovery_timeout=30,
                success_threshold=2,
            ),
            "sentiment": CircuitBreaker(
                name="sentiment_analysis", failure_threshold=5, recovery_timeout=60
            ),
            "quiz": CircuitBreaker(
                name="quiz_interpretation", failure_threshold=5, recovery_timeout=45
            ),
        }

    async def call_gemini(
        self, func: Callable, prompt: str, fallback_response: Optional[str] = None
    ) -> str:
        """
        Call Gemini with circuit breaker protection.

        Args:
            func: Gemini call function
            prompt: Prompt for Gemini
            fallback_response: Fallback response if circuit is open

        Returns:
            Gemini response or fallback
        """

        async def fallback():
            if fallback_response:
                return fallback_response
            # Generate simple fallback based on prompt content
            if "sentiment" in prompt.lower():
                return '{"sentiment": "neutral", "confidence": 0.5}'
            elif "quiz" in prompt.lower():
                return '{"interpreted": true, "value": "unknown"}'
            else:
                return "Desculpe, estou temporariamente indisponível. Por favor, tente novamente."

        return await self.breakers["gemini"].call(func, prompt, fallback=fallback)

    async def call_sentiment_analysis(
        self, func: Callable, message: str, context: Any
    ) -> Dict[str, Any]:
        """
        Call sentiment analysis with circuit breaker.

        Args:
            func: Sentiment analysis function
            message: Message to analyze
            context: Patient context

        Returns:
            Sentiment analysis result or fallback
        """

        async def fallback():
            # Simple rule-based sentiment fallback
            positive_words = ["bem", "melhor", "ótimo", "bom", "feliz"]
            negative_words = ["mal", "pior", "ruim", "triste", "dor"]

            message_lower = message.lower()

            sentiment = "neutral"
            if any(word in message_lower for word in positive_words):
                sentiment = "positive"
            elif any(word in message_lower for word in negative_words):
                sentiment = "negative"

            return {"sentiment": sentiment, "confidence": 0.6, "fallback": True}

        return await self.breakers["sentiment"].call(
            func, message, context, fallback=fallback
        )

    async def call_quiz_interpretation(
        self, func: Callable, question: Dict[str, Any], response: str
    ) -> Dict[str, Any]:
        """
        Call quiz interpretation with circuit breaker.

        Args:
            func: Quiz interpretation function
            question: Quiz question
            response: Patient response

        Returns:
            Interpretation result or fallback
        """

        async def fallback():
            # Try simple matching fallback
            if question.get("options"):
                response_lower = response.lower()
                for option in question["options"]:
                    if (
                        option["text"].lower() in response_lower
                        or response_lower in option["text"].lower()
                    ):
                        return {
                            "matched_option": option["value"],
                            "confidence": 0.7,
                            "fallback": True,
                        }

            return {
                "matched_option": "unknown",
                "confidence": 0.0,
                "fallback": True,
                "error": "Could not interpret response",
            }

        return await self.breakers["quiz"].call(
            func, question, response, fallback=fallback
        )

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all circuit breakers."""
        return {name: breaker.get_stats() for name, breaker in self.breakers.items()}

    def reset_all(self):
        """Reset all circuit breakers."""
        for breaker in self.breakers.values():
            breaker.reset()


# Global circuit breaker instance
_ai_circuit_breaker: Optional[AIServiceCircuitBreaker] = None


def get_ai_circuit_breaker() -> AIServiceCircuitBreaker:
    """
    Get or create AI circuit breaker instance.

    Returns:
        AIServiceCircuitBreaker instance
    """
    global _ai_circuit_breaker

    if _ai_circuit_breaker is None:
        _ai_circuit_breaker = AIServiceCircuitBreaker()

    return _ai_circuit_breaker


def circuit_breaker(
    name: str = "default", failure_threshold: int = 5, recovery_timeout: int = 60
):
    """
    Decorator for adding circuit breaker to functions.

    Args:
        name: Circuit breaker name
        failure_threshold: Failures before opening
        recovery_timeout: Recovery timeout in seconds
    """
    breaker = CircuitBreaker(
        name=name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
    )

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)

        # Attach breaker for inspection
        wrapper.circuit_breaker = breaker
        return wrapper

    return decorator
