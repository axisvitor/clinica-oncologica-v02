"""
Enhanced Circuit Breaker Module - HIGH-006
============================================

Implements circuit breaker pattern for external API calls to prevent cascading failures.

Protects:
- WhatsApp/WuzAPI
- Firebase Authentication
- Gemini AI (LangChain)

Features:
- State management (CLOSED/OPEN/HALF_OPEN)
- Fallback mechanisms
- Prometheus metrics integration
- Redis-based fallback queue
- Per-service configuration
- Automatic recovery testing

Author: Backend API Developer Agent
Date: 2025-11-16
Priority: HIGH (critical for production)
"""

import asyncio
import logging
from typing import Callable, Any, Optional, Dict, TypeVar, Generic
from datetime import datetime, timedelta, timezone
from enum import Enum
from dataclasses import dataclass
import functools
from aiobreaker import CircuitBreaker as AIOCircuitBreaker, CircuitBreakerError
from aiobreaker.listener import CircuitBreakerListener

from app.core.redis_manager import get_sync_redis_client as get_redis_client
from app.core.metrics import (
    circuit_breaker_state_gauge,
    circuit_breaker_failures_total,
    circuit_breaker_successes_total,
    circuit_breaker_fallback_total,
    circuit_breaker_call_duration_seconds,
)
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceType(str, Enum):
    """External service types with circuit breaker protection."""

    WHATSAPP = "wuzapi"
    FIREBASE = "firebase_auth"
    GEMINI_AI = "gemini_ai"


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration per service."""

    fail_max: int  # Number of failures before opening circuit
    timeout_duration: (
        int  # Seconds to wait in OPEN state before transitioning to HALF_OPEN
    )
    expected_exception: tuple = (Exception,)  # Exceptions to count as failures
    name: str = "default"

    # Fallback configuration
    enable_fallback: bool = True
    fallback_queue_enabled: bool = False  # For WhatsApp messages

    # Monitoring
    enable_metrics: bool = True


# Pre-configured circuit breakers for each service
CIRCUIT_CONFIGS: Dict[ServiceType, CircuitBreakerConfig] = {
    ServiceType.WHATSAPP: CircuitBreakerConfig(
        fail_max=5,  # Open after 5 consecutive failures
        timeout_duration=60,  # Try recovery after 60 seconds
        expected_exception=(Exception,),  # Catch all exceptions
        name=ServiceType.WHATSAPP.value,
        enable_fallback=True,
        fallback_queue_enabled=True,  # Queue messages for retry
    ),
    ServiceType.FIREBASE: CircuitBreakerConfig(
        fail_max=3,  # Open after 3 failures (auth is critical)
        timeout_duration=30,  # Quick recovery attempt (30s)
        expected_exception=(Exception,),
        name=ServiceType.FIREBASE.value,
        enable_fallback=True,
        fallback_queue_enabled=False,  # Don't queue auth requests
    ),
    ServiceType.GEMINI_AI: CircuitBreakerConfig(
        fail_max=5,  # Open after 5 failures
        timeout_duration=120,  # Longer recovery window (2 minutes)
        expected_exception=(Exception,),
        name=ServiceType.GEMINI_AI.value,
        enable_fallback=True,
        fallback_queue_enabled=False,  # Use cached/template responses
    ),
}


class EnhancedCircuitBreaker(Generic[T]):
    """
    Enhanced circuit breaker with fallback and metrics.

    Wraps aiobreaker for production-grade async circuit breaking.
    """

    class _StateChangeListener(CircuitBreakerListener):
        """Bridge aiobreaker listener callbacks to instance handler."""

        def __init__(self, callback: Callable[[Any, Any, Any], None]):
            self._callback = callback

        def state_change(self, breaker, old_state, new_state):
            self._callback(breaker, old_state, new_state)

    def __init__(self, config: CircuitBreakerConfig):
        """
        Initialize enhanced circuit breaker.

        Args:
            config: Circuit breaker configuration
        """
        self.config = config
        self.name = config.name

        # Initialize aiobreaker
        breaker_kwargs: Dict[str, Any] = {
            "fail_max": config.fail_max,
            "timeout_duration": timedelta(seconds=config.timeout_duration),
            "name": config.name,
        }
        # aiobreaker>=1.x uses `exclude` instead of `expected_exception`.
        # Keep legacy behavior: by default count all exceptions as failures.
        if config.expected_exception and config.expected_exception != (Exception,):
            breaker_kwargs["exclude"] = [
                lambda exc: not isinstance(exc, config.expected_exception)
            ]

        self._breaker = AIOCircuitBreaker(
            **breaker_kwargs,
        )

        # Register state change listener for metrics
        self._breaker.add_listener(
            self._StateChangeListener(self._on_state_change)
        )

        # Redis client for fallback queue
        self._redis_client = None

        logger.info(
            f"Circuit breaker initialized: {self.name} "
            f"(fail_max={config.fail_max}, timeout={config.timeout_duration}s)"
        )

    async def _ensure_redis(self):
        """Ensure Redis client is initialized."""
        if self._redis_client is None and self.config.fallback_queue_enabled:
            self._redis_client = get_redis_client()

    def _on_state_change(self, breaker, old_state, new_state):
        """Handle circuit breaker state changes for metrics."""
        old_state_name = self._normalize_state_name(old_state)
        new_state_name = self._normalize_state_name(new_state)
        logger.warning(
            f"Circuit breaker {self.name} state changed: "
            f"{old_state_name} -> {new_state_name}"
        )

        # Update Prometheus gauge (0=closed, 1=open, 2=half_open)
        state_value = {"closed": 0, "open": 1, "half_open": 2}.get(new_state_name, 0)
        circuit_breaker_state_gauge.labels(service=self.name).set(state_value)

    @staticmethod
    def _normalize_state_name(state: Any) -> str:
        """
        Normalize aiobreaker state objects/enums to `closed|open|half_open`.

        Supports both current_state enum values and state_change callback objects.
        """
        if state is None:
            return "unknown"

        candidate = getattr(state, "state", state)
        state_name = getattr(candidate, "name", None)
        if isinstance(state_name, str) and state_name:
            return state_name.lower()

        normalized = str(candidate).strip().lower()
        if "." in normalized:
            normalized = normalized.split(".")[-1]
        return normalized

    async def call(
        self,
        func: Callable[..., T],
        *args,
        fallback: Optional[Callable[..., T]] = None,
        **kwargs,
    ) -> T:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Async function to call
            *args: Function arguments
            fallback: Optional fallback function to call if circuit is open
            **kwargs: Function keyword arguments

        Returns:
            Function result or fallback result

        Raises:
            CircuitBreakerError: If circuit is open and no fallback provided
        """
        start_time = now_sao_paulo()

        try:
            # Call through circuit breaker
            result = await self._breaker.call_async(func, *args, **kwargs)

            # Record success metrics
            duration = (now_sao_paulo() - start_time).total_seconds()
            circuit_breaker_successes_total.labels(service=self.name).inc()
            circuit_breaker_call_duration_seconds.labels(
                service=self.name, status="success"
            ).observe(duration)

            return result

        except CircuitBreakerError as e:
            # Circuit is OPEN - use fallback
            logger.error(f"Circuit {self.name} is OPEN: {e}")

            duration = (now_sao_paulo() - start_time).total_seconds()
            circuit_breaker_failures_total.labels(service=self.name).inc()
            circuit_breaker_call_duration_seconds.labels(
                service=self.name, status="circuit_open"
            ).observe(duration)

            if fallback:
                circuit_breaker_fallback_total.labels(service=self.name).inc()
                return await self._execute_fallback(fallback, *args, **kwargs)

            # Queue for retry if enabled
            if self.config.fallback_queue_enabled:
                await self._queue_for_retry(func, args, kwargs)

            raise

        except Exception as e:
            # Service failure - circuit breaker will track this
            logger.error(f"Service {self.name} call failed: {e}")

            duration = (now_sao_paulo() - start_time).total_seconds()
            circuit_breaker_failures_total.labels(service=self.name).inc()
            circuit_breaker_call_duration_seconds.labels(
                service=self.name, status="failure"
            ).observe(duration)

            if fallback:
                circuit_breaker_fallback_total.labels(service=self.name).inc()
                return await self._execute_fallback(fallback, *args, **kwargs)

            raise

    async def _execute_fallback(self, fallback: Callable[..., T], *args, **kwargs) -> T:
        """Execute fallback function."""
        try:
            if asyncio.iscoroutinefunction(fallback):
                return await fallback(*args, **kwargs)
            else:
                return fallback(*args, **kwargs)
        except Exception as e:
            logger.error(f"Fallback failed for {self.name}: {e}")
            raise

    async def _queue_for_retry(self, func: Callable, args: tuple, kwargs: dict):
        """Queue failed request for retry (WhatsApp messages)."""
        try:
            await self._ensure_redis()

            if self._redis_client:
                # Serialize request for retry
                retry_data = {
                    "function": func.__name__,
                    "args": str(args),  # Simplified - production should use pickle/json
                    "kwargs": str(kwargs),
                    "timestamp": now_sao_paulo().isoformat(),
                    "service": self.name,
                }

                # Push to Redis list for retry processing
                queue_key = f"circuit_breaker:retry_queue:{self.name}"
                self._redis_client.rpush(queue_key, str(retry_data))

                logger.info(f"Queued request for retry: {self.name}")

        except Exception as e:
            logger.error(f"Failed to queue request for retry: {e}")

    def get_state(self) -> str:
        """Get current circuit state."""
        return self._normalize_state_name(self._breaker.current_state)

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        last_failure = None
        # aiobreaker API varies by version: some expose `last_failure`,
        # others only `opens_at`/state storage fields.
        for attr_name in ("last_failure", "opens_at"):
            try:
                candidate = getattr(self._breaker, attr_name)
            except Exception:
                continue
            if not candidate:
                continue
            if hasattr(candidate, "isoformat"):
                last_failure = candidate.isoformat()
            else:
                last_failure = str(candidate)
            break

        return {
            "name": self.name,
            "state": self.get_state(),
            "fail_max": self.config.fail_max,
            "timeout_duration": self.config.timeout_duration,
            "failure_count": self._breaker.fail_counter,
            "fallback_enabled": self.config.enable_fallback,
            "last_failure": last_failure,
        }


class CircuitBreakerManager:
    """
    Centralized circuit breaker manager for all external services.

    Provides easy access to circuit breakers and centralized monitoring.
    """

    _instance: Optional["CircuitBreakerManager"] = None
    _initialized = False

    def __init__(self):
        """Initialize circuit breaker manager."""
        if CircuitBreakerManager._initialized:
            return

        self.breakers: Dict[ServiceType, EnhancedCircuitBreaker] = {}

        # Initialize circuit breakers for all services
        for service_type, config in CIRCUIT_CONFIGS.items():
            self.breakers[service_type] = EnhancedCircuitBreaker(config)

        CircuitBreakerManager._initialized = True
        logger.info("Circuit Breaker Manager initialized with all services")

    @classmethod
    def get_instance(cls) -> "CircuitBreakerManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = CircuitBreakerManager()
        return cls._instance

    def get_breaker(self, service: ServiceType) -> EnhancedCircuitBreaker:
        """Get circuit breaker for specific service."""
        return self.breakers.get(service)

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers."""
        return {
            service.value: breaker.get_stats()
            for service, breaker in self.breakers.items()
        }

    async def process_retry_queues(self):
        """
        Process retry queues for all services (background task).

        This should be called periodically (e.g., every 5 minutes) to retry
        queued requests when circuits close.
        """
        for service, breaker in self.breakers.items():
            if (
                breaker.config.fallback_queue_enabled
                and breaker.get_state() == "closed"
            ):
                await self._process_service_retry_queue(service, breaker)

    async def _process_service_retry_queue(
        self, service: ServiceType, breaker: EnhancedCircuitBreaker
    ):
        """Process retry queue for a specific service."""
        try:
            redis_client = get_redis_client()
            queue_key = f"circuit_breaker:retry_queue:{service.value}"

            # Process up to 10 queued items
            for _ in range(10):
                item = redis_client.lpop(queue_key)
                if not item:
                    break

                # Try to retry the request
                # NOTE: In production, properly deserialize and execute
                logger.info(f"Retrying queued request for {service.value}: {item}")

        except Exception as e:
            logger.error(f"Failed to process retry queue for {service.value}: {e}")


# Singleton accessor
def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get circuit breaker manager singleton."""
    return CircuitBreakerManager.get_instance()


# Decorator for easy circuit breaker application
def with_circuit_breaker(service: ServiceType, fallback: Optional[Callable] = None):
    """
    Decorator to apply circuit breaker to async functions.

    Args:
        service: Service type to protect
        fallback: Optional fallback function

    Example:
        @with_circuit_breaker(ServiceType.WHATSAPP)
        async def send_whatsapp_message(phone, message):
            # Implementation
            pass
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            manager = get_circuit_breaker_manager()
            breaker = manager.get_breaker(service)
            return await breaker.call(func, *args, fallback=fallback, **kwargs)

        # Attach breaker for inspection
        wrapper.circuit_breaker_service = service
        return wrapper

    return decorator
