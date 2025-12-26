"""
Initialization Helper Utilities for FastAPI Startup.

Provides timeout protection, parallel initialization, and graceful degradation
for application startup services.

Usage:
    from app.core.initialization_helpers import (
        initialize_with_timeout,
        parallel_initialize,
        StartupTimer
    )

    # Single service with timeout
    redis_client = await initialize_with_timeout(
        func=lambda: get_redis_manager().get_async_client(),
        timeout=2.0,
        service_name="Redis",
        logger=logger,
        fallback=None
    )

    # Parallel initialization
    results = await parallel_initialize([
        ("Redis", lambda: initialize_redis(), 5.0),
        ("Firebase", lambda: initialize_firebase(), 10.0),
        ("WebSocket", lambda: initialize_websocket(), 3.0),
    ], logger)
"""

import asyncio
import time
from typing import Callable, TypeVar, Optional, List, Tuple, Any, Dict
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


async def initialize_with_timeout(
    func: Callable[[], T],
    timeout: float,
    service_name: str,
    logger: logging.Logger,
    fallback: Optional[T] = None,
    critical: bool = False
) -> T:
    """
    Initialize service with timeout and graceful degradation.

    Args:
        func: Async initialization function
        timeout: Timeout in seconds
        service_name: Name for logging
        logger: Logger instance
        fallback: Value to return on timeout/error
        critical: If True, raise exception on failure; if False, return fallback

    Returns:
        Initialized service or fallback value

    Raises:
        Exception: If critical=True and initialization fails

    Example:
        redis_client = await initialize_with_timeout(
            func=lambda: get_redis_manager().get_async_client(),
            timeout=2.0,
            service_name="Redis",
            logger=logger,
            fallback=None,
            critical=False  # Continue without Redis
        )
    """
    start_time = time.perf_counter()

    try:
        logger.info(f"Initializing {service_name} (timeout: {timeout}s)...")

        result = await asyncio.wait_for(func(), timeout=timeout)

        duration = time.perf_counter() - start_time
        logger.info(f"✓ {service_name} initialized successfully in {duration:.2f}s")

        return result

    except asyncio.TimeoutError:
        duration = time.perf_counter() - start_time
        logger.warning(
            f"⚠ {service_name} initialization timeout after {duration:.2f}s "
            f"(limit: {timeout}s)"
        )

        if critical:
            raise TimeoutError(
                f"{service_name} initialization failed: timeout after {timeout}s"
            )

        logger.info(f"Continuing without {service_name} (fallback mode)")
        return fallback

    except Exception as e:
        duration = time.perf_counter() - start_time
        logger.error(
            f"✗ {service_name} initialization failed after {duration:.2f}s: {e}",
            exc_info=not critical  # Log traceback only for non-critical
        )

        if critical:
            raise

        logger.info(f"Continuing without {service_name} (fallback mode)")
        return fallback


async def parallel_initialize(
    services: List[Tuple[str, Callable, float]],
    logger: logging.Logger,
    raise_on_failure: bool = False
) -> Dict[str, Any]:
    """
    Initialize multiple independent services in parallel.

    Args:
        services: List of (name, init_func, timeout) tuples
        logger: Logger instance
        raise_on_failure: If True, raise exception if any service fails

    Returns:
        Dict mapping service names to initialized instances or None

    Example:
        results = await parallel_initialize([
            ("Redis", lambda: initialize_redis(), 5.0),
            ("Firebase", lambda: initialize_firebase(), 10.0),
            ("WebSocket", lambda: initialize_websocket(), 3.0),
        ], logger)

        redis_client = results["Redis"]
        firebase_client = results["Firebase"]
    """
    logger.info(f"Initializing {len(services)} services in parallel...")

    # Create tasks for all services
    tasks = []
    service_names = []

    for service_name, init_func, timeout in services:
        service_names.append(service_name)
        tasks.append(
            initialize_with_timeout(
                func=init_func,
                timeout=timeout,
                service_name=service_name,
                logger=logger,
                fallback=None,
                critical=raise_on_failure
            )
        )

    # Execute all tasks concurrently
    start_time = time.perf_counter()
    results_list = await asyncio.gather(*tasks, return_exceptions=not raise_on_failure)
    total_duration = time.perf_counter() - start_time

    # Build results dictionary
    results = {}
    failed_services = []

    for service_name, result in zip(service_names, results_list):
        if isinstance(result, Exception):
            logger.error(f"Service {service_name} failed: {result}")
            results[service_name] = None
            failed_services.append(service_name)
        else:
            results[service_name] = result

    # Summary
    successful = len(services) - len(failed_services)
    logger.info(
        f"Parallel initialization completed in {total_duration:.2f}s: "
        f"{successful}/{len(services)} services initialized successfully"
    )

    if failed_services:
        logger.warning(f"Failed services: {', '.join(failed_services)}")

    return results


class StartupTimer:
    """
    Track initialization timing for each component.

    Usage:
        timer = StartupTimer()

        async with timer.track("Firebase"):
            await initialize_firebase()

        async with timer.track("Redis"):
            await initialize_redis()

        report = timer.get_report()
        logger.info(f"Startup report: {report}")
    """

    def __init__(self):
        self.timings: Dict[str, float] = {}
        self._start_time = time.perf_counter()

    @asynccontextmanager
    async def track(self, component: str):
        """
        Context manager to track component initialization time.

        Args:
            component: Component name

        Yields:
            None

        Example:
            async with timer.track("Database"):
                await initialize_database()
        """
        start = time.perf_counter()
        logger.info(f"[TIMER] Starting {component}...")

        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.timings[component] = duration
            logger.info(f"[TIMER] {component} completed in {duration:.2f}s")

    def get_report(self) -> Dict[str, Any]:
        """
        Get initialization timing report.

        Returns:
            dict: Report with total time, component timings, and slowest component

        Example:
            {
                "total_seconds": 12.5,
                "components": {
                    "Firebase": 3.2,
                    "Redis": 2.1,
                    "Database": 1.8
                },
                "slowest": ("Firebase", 3.2),
                "fastest": ("Database", 1.8)
            }
        """
        if not self.timings:
            return {
                "total_seconds": 0.0,
                "components": {},
                "slowest": None,
                "fastest": None
            }

        total = sum(self.timings.values())
        sorted_timings = sorted(self.timings.items(), key=lambda x: x[1], reverse=True)

        return {
            "total_seconds": round(total, 2),
            "elapsed_since_start": round(time.perf_counter() - self._start_time, 2),
            "components": {k: round(v, 2) for k, v in self.timings.items()},
            "slowest": sorted_timings[0] if sorted_timings else None,
            "fastest": sorted_timings[-1] if sorted_timings else None,
            "component_count": len(self.timings)
        }

    def log_report(self, logger: logging.Logger):
        """Log detailed startup timing report."""
        report = self.get_report()

        logger.info("=" * 60)
        logger.info("STARTUP TIMING REPORT")
        logger.info("=" * 60)
        logger.info(f"Total initialization time: {report['total_seconds']}s")
        logger.info(f"Components initialized: {report['component_count']}")

        if report['slowest']:
            logger.info(f"Slowest component: {report['slowest'][0]} ({report['slowest'][1]:.2f}s)")

        if report['fastest']:
            logger.info(f"Fastest component: {report['fastest'][0]} ({report['fastest'][1]:.2f}s)")

        logger.info("\nComponent breakdown:")
        for component, duration in sorted(
            report['components'].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            percentage = (duration / report['total_seconds'] * 100) if report['total_seconds'] > 0 else 0
            logger.info(f"  {component:.<30} {duration:>6.2f}s ({percentage:>5.1f}%)")

        logger.info("=" * 60)


async def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 10.0,
    logger: Optional[logging.Logger] = None
) -> T:
    """
    Retry function with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries (seconds)
        backoff_factor: Delay multiplier for each retry
        max_delay: Maximum delay between retries (seconds)
        logger: Optional logger instance

    Returns:
        Result from successful function call

    Raises:
        Exception: Last exception if all retries fail

    Example:
        result = await retry_with_backoff(
            func=lambda: some_flaky_network_call(),
            max_retries=3,
            initial_delay=1.0,
            backoff_factor=2.0
        )
    """
    _logger = logger or logging.getLogger(__name__)
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_exception = e

            if attempt == max_retries:
                _logger.error(f"All {max_retries + 1} attempts failed: {e}")
                raise

            _logger.warning(
                f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                f"Retrying in {delay:.1f}s..."
            )

            await asyncio.sleep(delay)
            delay = min(delay * backoff_factor, max_delay)

    # Should never reach here, but for type safety
    if last_exception:
        raise last_exception


__all__ = [
    "initialize_with_timeout",
    "parallel_initialize",
    "StartupTimer",
    "retry_with_backoff",
]
