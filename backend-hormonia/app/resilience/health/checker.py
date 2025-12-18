"""
Health Checker Implementation

Comprehensive health monitoring system.
"""

import time
import asyncio
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthResult:
    """Health check result"""

    name: str
    status: HealthStatus
    message: str
    duration: float
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None

    @property
    def is_healthy(self) -> bool:
        """Check if result is healthy"""
        return self.status == HealthStatus.HEALTHY

    @property
    def age(self) -> float:
        """Get result age in seconds"""
        return time.time() - self.timestamp


class HealthCheck(ABC):
    """Abstract base class for health checks"""

    def __init__(self, name: str, timeout: float = 10.0, interval: float = 60.0):
        self.name = name
        self.timeout = timeout
        self.interval = interval

    @abstractmethod
    async def check(self) -> HealthResult:
        """Perform health check"""
        pass

    async def check_with_timeout(self) -> HealthResult:
        """Perform health check with timeout"""
        start_time = time.time()

        try:
            result = await asyncio.wait_for(self.check(), timeout=self.timeout)
            return result

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            return HealthResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check timed out after {self.timeout}s",
                duration=duration,
                error="TimeoutError",
            )

        except Exception as e:
            duration = time.time() - start_time
            return HealthResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                duration=duration,
                error=str(e),
            )


@dataclass
class HealthSummary:
    """Overall health summary"""

    status: HealthStatus
    total_checks: int
    healthy_checks: int
    degraded_checks: int
    unhealthy_checks: int
    unknown_checks: int
    duration: float
    timestamp: float = field(default_factory=time.time)

    @property
    def health_percentage(self) -> float:
        """Get health percentage"""
        if self.total_checks == 0:
            return 0.0
        return (self.healthy_checks / self.total_checks) * 100.0


class HealthChecker:
    """
    Comprehensive health checker

    Features:
    - Multiple health checks
    - Async execution with timeouts
    - Health status aggregation
    - Caching and rate limiting
    - Metrics collection
    """

    def __init__(self, cache_ttl: float = 30.0):
        self.cache_ttl = cache_ttl
        self._checks: Dict[str, HealthCheck] = {}
        self._cache: Dict[str, HealthResult] = {}
        self._metrics = {
            "total_checks": 0,
            "failed_checks": 0,
            "timeout_checks": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        logger.info(f"Health checker initialized with cache TTL: {cache_ttl}s")

    def add_check(self, check: HealthCheck):
        """Add health check"""
        self._checks[check.name] = check
        logger.info(f"Added health check: {check.name}")

    def remove_check(self, name: str) -> bool:
        """Remove health check"""
        if name in self._checks:
            del self._checks[name]
            if name in self._cache:
                del self._cache[name]
            logger.info(f"Removed health check: {name}")
            return True
        return False

    async def check_health(self, check_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform health checks

        Args:
            check_name: Optional specific check name, None for all checks

        Returns:
            Dictionary with health status and results
        """
        start_time = time.time()

        if check_name:
            # Single check
            if check_name not in self._checks:
                return {
                    "error": f'Health check "{check_name}" not found',
                    "available_checks": list(self._checks.keys()),
                }

            result = await self._execute_check(check_name)
            results = {check_name: result}
        else:
            # All checks
            results = await self._execute_all_checks()

        # Calculate summary
        summary = self._calculate_summary(results, time.time() - start_time)

        return {
            "summary": {
                "status": summary.status.value,
                "health_percentage": summary.health_percentage,
                "total_checks": summary.total_checks,
                "healthy": summary.healthy_checks,
                "degraded": summary.degraded_checks,
                "unhealthy": summary.unhealthy_checks,
                "unknown": summary.unknown_checks,
                "duration": summary.duration,
                "timestamp": summary.timestamp,
            },
            "checks": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "duration": result.duration,
                    "details": result.details,
                    "timestamp": result.timestamp,
                    "error": result.error,
                }
                for name, result in results.items()
            },
            "metrics": self._metrics.copy(),
        }

    async def _execute_check(self, check_name: str) -> HealthResult:
        """Execute single health check with caching"""
        # Check cache first
        cached_result = self._get_cached_result(check_name)
        if cached_result:
            self._metrics["cache_hits"] += 1
            return cached_result

        self._metrics["cache_misses"] += 1

        # Execute check
        check = self._checks[check_name]
        result = await check.check_with_timeout()

        # Update metrics
        self._metrics["total_checks"] += 1
        if result.error:
            if "timeout" in result.error.lower():
                self._metrics["timeout_checks"] += 1
            else:
                self._metrics["failed_checks"] += 1

        # Cache result
        self._cache[check_name] = result

        logger.debug(
            f"Health check '{check_name}': {result.status.value} "
            f"({result.duration:.3f}s)"
        )

        return result

    async def _execute_all_checks(self) -> Dict[str, HealthResult]:
        """Execute all health checks concurrently"""
        if not self._checks:
            return {}

        # Create tasks for all checks
        tasks = []
        check_names = []

        for check_name in self._checks.keys():
            tasks.append(self._execute_check(check_name))
            check_names.append(check_name)

        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        health_results = {}
        for check_name, result in zip(check_names, results):
            if isinstance(result, Exception):
                # Handle exception
                health_results[check_name] = HealthResult(
                    name=check_name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check execution failed: {str(result)}",
                    duration=0.0,
                    error=str(result),
                )
            else:
                health_results[check_name] = result

        return health_results

    def _get_cached_result(self, check_name: str) -> Optional[HealthResult]:
        """Get cached result if still valid"""
        cached_result = self._cache.get(check_name)
        if cached_result and cached_result.age < self.cache_ttl:
            return cached_result
        return None

    def _calculate_summary(
        self, results: Dict[str, HealthResult], duration: float
    ) -> HealthSummary:
        """Calculate overall health summary"""
        if not results:
            return HealthSummary(
                status=HealthStatus.UNKNOWN,
                total_checks=0,
                healthy_checks=0,
                degraded_checks=0,
                unhealthy_checks=0,
                unknown_checks=0,
                duration=duration,
            )

        # Count status types
        status_counts = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DEGRADED: 0,
            HealthStatus.UNHEALTHY: 0,
            HealthStatus.UNKNOWN: 0,
        }

        for result in results.values():
            status_counts[result.status] += 1

        # Determine overall status
        if status_counts[HealthStatus.UNHEALTHY] > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif status_counts[HealthStatus.DEGRADED] > 0:
            overall_status = HealthStatus.DEGRADED
        elif status_counts[HealthStatus.HEALTHY] > 0:
            overall_status = HealthStatus.HEALTHY
        else:
            overall_status = HealthStatus.UNKNOWN

        return HealthSummary(
            status=overall_status,
            total_checks=len(results),
            healthy_checks=status_counts[HealthStatus.HEALTHY],
            degraded_checks=status_counts[HealthStatus.DEGRADED],
            unhealthy_checks=status_counts[HealthStatus.UNHEALTHY],
            unknown_checks=status_counts[HealthStatus.UNKNOWN],
            duration=duration,
        )

    def get_check_names(self) -> List[str]:
        """Get list of registered check names"""
        return list(self._checks.keys())

    def clear_cache(self):
        """Clear cached results"""
        self._cache.clear()
        logger.info("Health check cache cleared")

    def get_metrics(self) -> Dict:
        """Get health checker metrics"""
        return {
            "registered_checks": len(self._checks),
            "cached_results": len(self._cache),
            "cache_ttl": self.cache_ttl,
            **self._metrics,
        }

    def reset_metrics(self):
        """Reset metrics"""
        self._metrics = {
            "total_checks": 0,
            "failed_checks": 0,
            "timeout_checks": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }
        logger.info("Health checker metrics reset")


# Global health checker instance
health_checker = HealthChecker()
