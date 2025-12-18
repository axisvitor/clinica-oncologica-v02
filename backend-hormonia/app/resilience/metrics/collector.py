"""
Metrics Collector for Resilience Patterns

Comprehensive metrics collection and aggregation.
"""

import time
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import deque
import statistics
import logging

logger = logging.getLogger(__name__)


@dataclass
class ResilienceMetrics:
    """Comprehensive resilience metrics"""

    # Circuit Breaker Metrics
    circuit_breaker_trips: int = 0
    circuit_breaker_failures: int = 0
    circuit_breaker_successes: int = 0
    circuit_breaker_state_changes: int = 0

    # Retry Metrics
    retry_attempts: int = 0
    retry_successes: int = 0
    retry_failures: int = 0
    retry_dead_letters: int = 0

    # Rate Limit Metrics
    rate_limit_requests: int = 0
    rate_limit_allowed: int = 0
    rate_limit_denied: int = 0
    rate_limit_whitelisted: int = 0

    # Health Check Metrics
    health_check_total: int = 0
    health_check_healthy: int = 0
    health_check_degraded: int = 0
    health_check_unhealthy: int = 0

    # Performance Metrics
    average_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    error_rate: float = 0.0

    # System Metrics
    uptime_seconds: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0

    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "circuit_breaker": {
                "trips": self.circuit_breaker_trips,
                "failures": self.circuit_breaker_failures,
                "successes": self.circuit_breaker_successes,
                "state_changes": self.circuit_breaker_state_changes,
            },
            "retry": {
                "attempts": self.retry_attempts,
                "successes": self.retry_successes,
                "failures": self.retry_failures,
                "dead_letters": self.retry_dead_letters,
            },
            "rate_limit": {
                "requests": self.rate_limit_requests,
                "allowed": self.rate_limit_allowed,
                "denied": self.rate_limit_denied,
                "whitelisted": self.rate_limit_whitelisted,
            },
            "health_check": {
                "total": self.health_check_total,
                "healthy": self.health_check_healthy,
                "degraded": self.health_check_degraded,
                "unhealthy": self.health_check_unhealthy,
            },
            "performance": {
                "average_response_time": self.average_response_time,
                "p95_response_time": self.p95_response_time,
                "p99_response_time": self.p99_response_time,
                "error_rate": self.error_rate,
            },
            "system": {
                "uptime_seconds": self.uptime_seconds,
                "memory_usage_mb": self.memory_usage_mb,
                "cpu_usage_percent": self.cpu_usage_percent,
            },
            "timestamp": self.timestamp,
        }


class MetricsCollector:
    """
    Comprehensive metrics collector for resilience patterns

    Features:
    - Real-time metrics collection
    - Historical data retention
    - Statistical calculations
    - Thread-safe operations
    - Multiple data sources
    """

    def __init__(
        self,
        retention_period: int = 3600,  # 1 hour
        collection_interval: int = 60,
    ):  # 1 minute
        self.retention_period = retention_period
        self.collection_interval = collection_interval
        self.start_time = time.time()

        # Metrics storage
        self._metrics_history: deque = deque(
            maxlen=retention_period // collection_interval
        )
        self._current_metrics = ResilienceMetrics()
        self._lock = threading.Lock()

        # Response time tracking
        self._response_times: deque = deque(maxlen=1000)

        # Component references (set by registration)
        self._circuit_breakers = {}
        self._retry_managers = {}
        self._rate_limiters = {}
        self._health_checkers = {}

        # Collection thread
        self._collection_thread: Optional[threading.Thread] = None
        self._stop_collection = threading.Event()

        logger.info(
            f"Metrics collector initialized "
            f"(retention={retention_period}s, interval={collection_interval}s)"
        )

    def register_circuit_breaker(self, name: str, circuit_breaker):
        """Register circuit breaker for metrics collection"""
        self._circuit_breakers[name] = circuit_breaker
        logger.info(f"Registered circuit breaker: {name}")

    def register_retry_manager(self, name: str, retry_manager):
        """Register retry manager for metrics collection"""
        self._retry_managers[name] = retry_manager
        logger.info(f"Registered retry manager: {name}")

    def register_rate_limiter(self, name: str, rate_limiter):
        """Register rate limiter for metrics collection"""
        self._rate_limiters[name] = rate_limiter
        logger.info(f"Registered rate limiter: {name}")

    def register_health_checker(self, name: str, health_checker):
        """Register health checker for metrics collection"""
        self._health_checkers[name] = health_checker
        logger.info(f"Registered health checker: {name}")

    def record_response_time(self, duration: float):
        """Record response time for performance metrics"""
        with self._lock:
            self._response_times.append(duration)

    def collect_metrics(self) -> ResilienceMetrics:
        """Collect current metrics from all components"""
        metrics = ResilienceMetrics()

        # Collect circuit breaker metrics
        for name, cb in self._circuit_breakers.items():
            try:
                cb_metrics = cb.get_metrics()
                metrics.circuit_breaker_trips += cb_metrics.get(
                    "circuit_breaker_trips", 0
                )
                metrics.circuit_breaker_failures += cb_metrics.get("failed_requests", 0)
                metrics.circuit_breaker_successes += cb_metrics.get(
                    "successful_requests", 0
                )
            except Exception as e:
                logger.warning(
                    f"Error collecting circuit breaker metrics for {name}: {e}"
                )

        # Collect retry metrics
        for name, rm in self._retry_managers.items():
            try:
                rm_metrics = rm.get_metrics()
                metrics.retry_attempts += rm_metrics.get("total_attempts", 0)
                metrics.retry_successes += rm_metrics.get("successful_executions", 0)
                metrics.retry_failures += rm_metrics.get("failed_executions", 0)
                metrics.retry_dead_letters += rm_metrics.get("dead_letter_count", 0)
            except Exception as e:
                logger.warning(f"Error collecting retry metrics for {name}: {e}")

        # Collect rate limiter metrics
        for name, rl in self._rate_limiters.items():
            try:
                rl_metrics = rl.get_metrics()
                metrics.rate_limit_requests += rl_metrics.get("total_requests", 0)
                metrics.rate_limit_allowed += rl_metrics.get("allowed_requests", 0)
                metrics.rate_limit_denied += rl_metrics.get("denied_requests", 0)
                metrics.rate_limit_whitelisted += rl_metrics.get(
                    "whitelisted_requests", 0
                )
            except Exception as e:
                logger.warning(f"Error collecting rate limiter metrics for {name}: {e}")

        # Collect health check metrics
        for name, hc in self._health_checkers.items():
            try:
                hc_metrics = hc.get_metrics()
                metrics.health_check_total += hc_metrics.get("total_checks", 0)
                # We'd need to modify health checkers to track status counts
            except Exception as e:
                logger.warning(f"Error collecting health check metrics for {name}: {e}")

        # Calculate performance metrics
        with self._lock:
            if self._response_times:
                response_times = list(self._response_times)
                metrics.average_response_time = statistics.mean(response_times)

                if len(response_times) >= 20:  # Need enough samples for percentiles
                    metrics.p95_response_time = statistics.quantiles(
                        response_times, n=20
                    )[18]  # 95th percentile
                    metrics.p99_response_time = statistics.quantiles(
                        response_times, n=100
                    )[98]  # 99th percentile

        # Calculate error rate
        total_requests = (
            metrics.circuit_breaker_successes
            + metrics.circuit_breaker_failures
            + metrics.retry_successes
            + metrics.retry_failures
        )

        if total_requests > 0:
            total_failures = metrics.circuit_breaker_failures + metrics.retry_failures
            metrics.error_rate = total_failures / total_requests

        # System metrics
        metrics.uptime_seconds = time.time() - self.start_time

        try:
            import psutil

            metrics.memory_usage_mb = psutil.Process().memory_info().rss / (1024 * 1024)
            metrics.cpu_usage_percent = psutil.Process().cpu_percent()
        except ImportError:
            logger.debug("psutil not available for system metrics")

        return metrics

    def start_collection(self):
        """Start background metrics collection"""
        if self._collection_thread and self._collection_thread.is_alive():
            logger.warning("Metrics collection already started")
            return

        self._stop_collection.clear()
        self._collection_thread = threading.Thread(
            target=self._collection_loop, daemon=True
        )
        self._collection_thread.start()

        logger.info("Started background metrics collection")

    def stop_collection(self):
        """Stop background metrics collection"""
        self._stop_collection.set()

        if self._collection_thread:
            self._collection_thread.join(timeout=5.0)

        logger.info("Stopped background metrics collection")

    def _collection_loop(self):
        """Background collection loop"""
        while not self._stop_collection.is_set():
            try:
                # Collect current metrics
                current_metrics = self.collect_metrics()

                # Store in history
                with self._lock:
                    self._current_metrics = current_metrics
                    self._metrics_history.append(current_metrics)

                logger.debug("Collected metrics snapshot")

                # Wait for next collection interval
                self._stop_collection.wait(self.collection_interval)

            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")
                time.sleep(5)

    def get_current_metrics(self) -> ResilienceMetrics:
        """Get current metrics"""
        with self._lock:
            return self._current_metrics

    def get_metrics_history(
        self, last_n_minutes: Optional[int] = None
    ) -> List[ResilienceMetrics]:
        """Get historical metrics"""
        with self._lock:
            history = list(self._metrics_history)

        if last_n_minutes:
            # Filter by time
            cutoff_time = time.time() - (last_n_minutes * 60)
            history = [m for m in history if m.timestamp >= cutoff_time]

        return history

    def get_aggregated_metrics(
        self, last_n_minutes: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get aggregated metrics over time period"""
        history = self.get_metrics_history(last_n_minutes)

        if not history:
            return {}

        # Calculate aggregations
        response_times = [
            m.average_response_time for m in history if m.average_response_time > 0
        ]
        error_rates = [m.error_rate for m in history if m.error_rate >= 0]

        aggregated = {
            "time_period_minutes": last_n_minutes
            or (len(history) * self.collection_interval / 60),
            "data_points": len(history),
            "circuit_breaker": {
                "total_trips": sum(m.circuit_breaker_trips for m in history),
                "total_failures": sum(m.circuit_breaker_failures for m in history),
                "total_successes": sum(m.circuit_breaker_successes for m in history),
            },
            "retry": {
                "total_attempts": sum(m.retry_attempts for m in history),
                "total_successes": sum(m.retry_successes for m in history),
                "total_failures": sum(m.retry_failures for m in history),
                "total_dead_letters": sum(m.retry_dead_letters for m in history),
            },
            "rate_limit": {
                "total_requests": sum(m.rate_limit_requests for m in history),
                "total_allowed": sum(m.rate_limit_allowed for m in history),
                "total_denied": sum(m.rate_limit_denied for m in history),
            },
            "performance": {
                "avg_response_time": statistics.mean(response_times)
                if response_times
                else 0,
                "max_response_time": max(response_times) if response_times else 0,
                "min_response_time": min(response_times) if response_times else 0,
                "avg_error_rate": statistics.mean(error_rates) if error_rates else 0,
                "max_error_rate": max(error_rates) if error_rates else 0,
            },
            "latest": history[-1].to_dict() if history else {},
        }

        return aggregated

    def export_metrics(self, format: str = "json") -> str:
        """Export metrics in specified format"""
        current = self.get_current_metrics()

        if format == "json":
            import json

            return json.dumps(current.to_dict(), indent=2)
        elif format == "prometheus":
            return self._export_prometheus_format(current)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def _export_prometheus_format(self, metrics: ResilienceMetrics) -> str:
        """Export metrics in Prometheus format"""
        lines = []

        # Circuit breaker metrics
        lines.append(f"circuit_breaker_trips_total {metrics.circuit_breaker_trips}")
        lines.append(
            f"circuit_breaker_failures_total {metrics.circuit_breaker_failures}"
        )
        lines.append(
            f"circuit_breaker_successes_total {metrics.circuit_breaker_successes}"
        )

        # Retry metrics
        lines.append(f"retry_attempts_total {metrics.retry_attempts}")
        lines.append(f"retry_successes_total {metrics.retry_successes}")
        lines.append(f"retry_failures_total {metrics.retry_failures}")
        lines.append(f"retry_dead_letters_total {metrics.retry_dead_letters}")

        # Rate limit metrics
        lines.append(f"rate_limit_requests_total {metrics.rate_limit_requests}")
        lines.append(f"rate_limit_allowed_total {metrics.rate_limit_allowed}")
        lines.append(f"rate_limit_denied_total {metrics.rate_limit_denied}")

        # Performance metrics
        lines.append(f"response_time_seconds {metrics.average_response_time}")
        lines.append(f"response_time_p95_seconds {metrics.p95_response_time}")
        lines.append(f"response_time_p99_seconds {metrics.p99_response_time}")
        lines.append(f"error_rate {metrics.error_rate}")

        # System metrics
        lines.append(f"uptime_seconds {metrics.uptime_seconds}")
        lines.append(f"memory_usage_bytes {metrics.memory_usage_mb * 1024 * 1024}")
        lines.append(f"cpu_usage_percent {metrics.cpu_usage_percent}")

        return "\n".join(lines)

    def clear_history(self):
        """Clear metrics history"""
        with self._lock:
            self._metrics_history.clear()
            self._response_times.clear()

        logger.info("Cleared metrics history")


# Global metrics collector
metrics_collector = MetricsCollector()
