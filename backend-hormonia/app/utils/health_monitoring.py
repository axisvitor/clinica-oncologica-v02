"""
System health monitoring utilities.
"""

import time
import psutil
from datetime import datetime
from typing import Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import text

from app.database import get_db
from app.config import settings
from app.utils.logging import get_logger
from app.utils.error_tracking import get_error_summary


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


@dataclass
class HealthMetric:
    """Represents a health metric."""

    name: str
    value: float
    unit: str
    status: HealthStatus
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComponentHealth:
    """Represents the health of a system component."""

    name: str
    status: HealthStatus
    metrics: List[HealthMetric] = field(default_factory=list)
    error_message: Optional[str] = None
    last_check: datetime = field(default_factory=datetime.utcnow)
    response_time_ms: Optional[float] = None


class HealthMonitor:
    """System health monitoring service."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.components: dict[str, ComponentHealth] = {}
        self.system_metrics: List[HealthMetric] = []
        self.last_full_check: Optional[datetime] = None

        # Health check thresholds
        self.thresholds = {
            "cpu_percent": {"warning": 80.0, "critical": 95.0},
            "memory_percent": {"warning": 85.0, "critical": 95.0},
            "disk_percent": {"warning": 85.0, "critical": 95.0},
            "response_time_ms": {"warning": 1000.0, "critical": 5000.0},
            "error_rate": {"warning": 10.0, "critical": 50.0},
        }

    async def check_system_health(self) -> dict[str, Any]:
        """Perform comprehensive system health check."""
        start_time = time.time()

        try:
            # Check all components
            await self._check_system_resources()
            await self._check_database_health()
            await self._check_redis_health()
            await self._check_external_services()
            await self._check_application_health()

            # Calculate overall health
            overall_status = self._calculate_overall_status()

            # Update last check time
            self.last_full_check = datetime.utcnow()

            # Calculate check duration
            check_duration = (time.time() - start_time) * 1000

            # Log health check
            self.logger.info(
                f"Health check completed in {check_duration:.2f}ms",
                extra={
                    "event_type": "health_check_complete",
                    "overall_status": overall_status.value,
                    "check_duration_ms": check_duration,
                    "components_checked": len(self.components),
                },
            )

            return self._build_health_response(overall_status, check_duration)

        except Exception as e:
            self.logger.error(
                f"Health check failed: {str(e)}",
                extra={"event_type": "health_check_error"},
                exc_info=True,
            )

            return {
                "status": HealthStatus.CRITICAL.value,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "check_duration_ms": (time.time() - start_time) * 1000,
            }

    async def _check_system_resources(self) -> None:
        """Check system resource utilization."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_status = self._determine_status(cpu_percent, "cpu_percent")

            # Memory usage
            memory = psutil.virtual_memory()
            memory_status = self._determine_status(memory.percent, "memory_percent")

            # Disk usage
            disk = psutil.disk_usage("/")
            disk_percent = (disk.used / disk.total) * 100
            disk_status = self._determine_status(disk_percent, "disk_percent")

            # Network I/O
            network = psutil.net_io_counters()

            # Create system component health
            system_health = ComponentHealth(
                name="system_resources",
                status=max(
                    cpu_status, memory_status, disk_status, key=lambda x: x.value
                ),
                metrics=[
                    HealthMetric(
                        name="cpu_percent",
                        value=cpu_percent,
                        unit="%",
                        status=cpu_status,
                        threshold_warning=self.thresholds["cpu_percent"]["warning"],
                        threshold_critical=self.thresholds["cpu_percent"]["critical"],
                    ),
                    HealthMetric(
                        name="memory_percent",
                        value=memory.percent,
                        unit="%",
                        status=memory_status,
                        threshold_warning=self.thresholds["memory_percent"]["warning"],
                        threshold_critical=self.thresholds["memory_percent"][
                            "critical"
                        ],
                        metadata={
                            "total_gb": round(memory.total / (1024**3), 2),
                            "available_gb": round(memory.available / (1024**3), 2),
                            "used_gb": round(memory.used / (1024**3), 2),
                        },
                    ),
                    HealthMetric(
                        name="disk_percent",
                        value=disk_percent,
                        unit="%",
                        status=disk_status,
                        threshold_warning=self.thresholds["disk_percent"]["warning"],
                        threshold_critical=self.thresholds["disk_percent"]["critical"],
                        metadata={
                            "total_gb": round(disk.total / (1024**3), 2),
                            "free_gb": round(disk.free / (1024**3), 2),
                            "used_gb": round(disk.used / (1024**3), 2),
                        },
                    ),
                    HealthMetric(
                        name="network_bytes_sent",
                        value=network.bytes_sent,
                        unit="bytes",
                        status=HealthStatus.HEALTHY,
                    ),
                    HealthMetric(
                        name="network_bytes_recv",
                        value=network.bytes_recv,
                        unit="bytes",
                        status=HealthStatus.HEALTHY,
                    ),
                ],
            )

            self.components["system_resources"] = system_health

        except Exception as e:
            self.logger.error(f"System resource check failed: {str(e)}", exc_info=True)
            self.components["system_resources"] = ComponentHealth(
                name="system_resources",
                status=HealthStatus.CRITICAL,
                error_message=str(e),
            )

    async def _check_database_health(self) -> None:
        """Check database connectivity and performance."""
        start_time = time.time()

        try:
            # Test database connection
            db = next(get_db())
            try:
                # Simple query to test connectivity
                result = db.execute(text("SELECT 1 as health_check"))
                row = result.fetchone()

                if row and row[0] == 1:
                    response_time = (time.time() - start_time) * 1000
                    status = self._determine_status(response_time, "response_time_ms")

                    # Get database statistics
                    stats_result = db.execute(
                        text("""
                        SELECT
                            count(*) as total_connections,
                            sum(case when state = 'active' then 1 else 0 end) as active_connections
                        FROM pg_stat_activity
                        WHERE datname = current_database()
                    """)
                    )
                    stats = stats_result.fetchone()

                    # Get connection pool statistics
                    from app.database import get_pool_status

                    pool_stats = get_pool_status(use_service_role=True)

                    # Calculate pool utilization
                    pool_size = pool_stats.get("pool_size", 0)
                    checked_out = pool_stats.get("checked_out", 0)
                    utilization = (
                        (checked_out / pool_size * 100) if pool_size > 0 else 0
                    )

                    # Determine pool health status
                    pool_status = HealthStatus.HEALTHY
                    if utilization >= 92:  # Critical threshold (was the issue)
                        pool_status = HealthStatus.CRITICAL
                    elif utilization >= 85:  # Warning threshold
                        pool_status = HealthStatus.DEGRADED

                    self.components["database"] = ComponentHealth(
                        name="database",
                        status=max(status, pool_status, key=lambda x: x.value),
                        response_time_ms=response_time,
                        metrics=[
                            HealthMetric(
                                name="response_time_ms",
                                value=response_time,
                                unit="ms",
                                status=status,
                                threshold_warning=self.thresholds["response_time_ms"][
                                    "warning"
                                ],
                                threshold_critical=self.thresholds["response_time_ms"][
                                    "critical"
                                ],
                            ),
                            HealthMetric(
                                name="total_connections",
                                value=stats[0] if stats else 0,
                                unit="count",
                                status=HealthStatus.HEALTHY,
                            ),
                            HealthMetric(
                                name="active_connections",
                                value=stats[1] if stats else 0,
                                unit="count",
                                status=HealthStatus.HEALTHY,
                            ),
                            HealthMetric(
                                name="pool_size",
                                value=pool_size,
                                unit="count",
                                status=HealthStatus.HEALTHY,
                                metadata=pool_stats,
                            ),
                            HealthMetric(
                                name="pool_checked_out",
                                value=checked_out,
                                unit="count",
                                status=pool_status,
                                threshold_warning=pool_size * 0.85,
                                threshold_critical=pool_size * 0.92,
                            ),
                            HealthMetric(
                                name="pool_utilization",
                                value=utilization,
                                unit="%",
                                status=pool_status,
                                threshold_warning=85.0,
                                threshold_critical=92.0,
                            ),
                        ],
                    )
                else:
                    raise Exception("Database health check query failed")
            finally:
                db.close()

        except Exception as e:
            self.logger.error(f"Database health check failed: {str(e)}", exc_info=True)
            self.components["database"] = ComponentHealth(
                name="database",
                status=HealthStatus.CRITICAL,
                error_message=str(e),
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def _check_redis_health(self) -> None:
        """Check Redis connectivity and performance."""
        start_time = time.time()

        try:
            import redis.asyncio as redis

            # Create Redis client
            redis_client = redis.from_url(settings.REDIS_URL)

            # Test Redis connection
            await redis_client.ping()

            # Get Redis info
            info = await redis_client.info()

            response_time = (time.time() - start_time) * 1000
            status = self._determine_status(response_time, "response_time_ms")

            # Get Redis pool statistics
            try:
                from app.core.redis_manager import get_redis_manager

                redis_manager = get_redis_manager()
                pool_stats = await redis_manager.get_pool_stats_async()
            except Exception as pool_err:
                self.logger.warning(f"Could not get Redis pool stats: {pool_err}")
                pool_stats = {"status": "unavailable"}

            # Calculate cache hit ratio
            hits = info.get("keyspace_hits", 0)
            misses = info.get("keyspace_misses", 0)
            total_ops = hits + misses
            hit_ratio = (hits / total_ops * 100) if total_ops > 0 else 0

            self.components["redis"] = ComponentHealth(
                name="redis",
                status=status,
                response_time_ms=response_time,
                metrics=[
                    HealthMetric(
                        name="response_time_ms",
                        value=response_time,
                        unit="ms",
                        status=status,
                        threshold_warning=self.thresholds["response_time_ms"][
                            "warning"
                        ],
                        threshold_critical=self.thresholds["response_time_ms"][
                            "critical"
                        ],
                    ),
                    HealthMetric(
                        name="connected_clients",
                        value=info.get("connected_clients", 0),
                        unit="count",
                        status=HealthStatus.HEALTHY,
                        metadata={
                            "max_connections": pool_stats.get("max_connections", "N/A")
                        },
                    ),
                    HealthMetric(
                        name="used_memory_mb",
                        value=info.get("used_memory", 0) / (1024 * 1024),
                        unit="MB",
                        status=HealthStatus.HEALTHY,
                    ),
                    HealthMetric(
                        name="keyspace_hits",
                        value=hits,
                        unit="count",
                        status=HealthStatus.HEALTHY,
                    ),
                    HealthMetric(
                        name="keyspace_misses",
                        value=misses,
                        unit="count",
                        status=HealthStatus.HEALTHY,
                    ),
                    HealthMetric(
                        name="cache_hit_ratio",
                        value=hit_ratio,
                        unit="%",
                        status=HealthStatus.HEALTHY
                        if hit_ratio >= 80
                        else HealthStatus.DEGRADED,
                        threshold_warning=80.0,
                        threshold_critical=50.0,
                    ),
                    HealthMetric(
                        name="pool_status",
                        value=1 if pool_stats.get("status") == "healthy" else 0,
                        unit="status",
                        status=HealthStatus.HEALTHY
                        if pool_stats.get("status") == "healthy"
                        else HealthStatus.DEGRADED,
                        metadata=pool_stats,
                    ),
                ],
            )

            await redis_client.aclose()  # Redis 5.x uses aclose() for async

        except Exception as e:
            self.logger.error(f"Redis health check failed: {str(e)}", exc_info=True)
            self.components["redis"] = ComponentHealth(
                name="redis",
                status=HealthStatus.CRITICAL,
                error_message=str(e),
                response_time_ms=(time.time() - start_time) * 1000,
            )

    async def _check_external_services(self) -> None:
        """Check external service connectivity."""
        import httpx

        services = [
            {
                "name": "evolution_api",
                "url": f"{settings.WHATSAPP_EVOLUTION_API_URL}/instance/connectionState/{settings.WHATSAPP_EVOLUTION_INSTANCE_NAME}",
                "headers": {"apikey": settings.WHATSAPP_EVOLUTION_API_KEY},
            }
        ]

        for service_config in services:
            start_time = time.time()

            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(
                        service_config["url"], headers=service_config.get("headers", {})
                    )

                    response_time = (time.time() - start_time) * 1000

                    if response.status_code == 200:
                        status = self._determine_status(
                            response_time, "response_time_ms"
                        )
                    else:
                        status = HealthStatus.DEGRADED

                    self.components[service_config["name"]] = ComponentHealth(
                        name=service_config["name"],
                        status=status,
                        response_time_ms=response_time,
                        metrics=[
                            HealthMetric(
                                name="response_time_ms",
                                value=response_time,
                                unit="ms",
                                status=status,
                                threshold_warning=self.thresholds["response_time_ms"][
                                    "warning"
                                ],
                                threshold_critical=self.thresholds["response_time_ms"][
                                    "critical"
                                ],
                            ),
                            HealthMetric(
                                name="status_code",
                                value=response.status_code,
                                unit="code",
                                status=HealthStatus.HEALTHY
                                if response.status_code == 200
                                else HealthStatus.DEGRADED,
                            ),
                        ],
                    )

            except Exception as e:
                self.logger.error(
                    f"{service_config['name']} health check failed: {str(e)}",
                    exc_info=True,
                )
                self.components[service_config["name"]] = ComponentHealth(
                    name=service_config["name"],
                    status=HealthStatus.CRITICAL,
                    error_message=str(e),
                    response_time_ms=(time.time() - start_time) * 1000,
                )

    async def _check_application_health(self) -> None:
        """Check application-specific health metrics."""
        try:
            # Get error summary
            error_summary = get_error_summary(hours=1)
            error_count = error_summary.get("total_errors", 0)
            error_rate = min(error_count, 100)  # Cap at 100 for percentage calculation

            error_status = self._determine_status(error_rate, "error_rate")

            # Check if we have recent errors
            recent_critical_errors = sum(
                1
                for error_type, details in error_summary.get(
                    "errors_by_type", {}
                ).items()
                if details.get("severity") == "critical"
            )

            self.components["application"] = ComponentHealth(
                name="application",
                status=error_status,
                metrics=[
                    HealthMetric(
                        name="error_rate_1h",
                        value=error_rate,
                        unit="count",
                        status=error_status,
                        threshold_warning=self.thresholds["error_rate"]["warning"],
                        threshold_critical=self.thresholds["error_rate"]["critical"],
                    ),
                    HealthMetric(
                        name="critical_errors_1h",
                        value=recent_critical_errors,
                        unit="count",
                        status=HealthStatus.CRITICAL
                        if recent_critical_errors > 0
                        else HealthStatus.HEALTHY,
                    ),
                    HealthMetric(
                        name="unique_error_types_1h",
                        value=error_summary.get("unique_error_types", 0),
                        unit="count",
                        status=HealthStatus.HEALTHY,
                    ),
                ],
            )

        except Exception as e:
            self.logger.error(
                f"Application health check failed: {str(e)}", exc_info=True
            )
            self.components["application"] = ComponentHealth(
                name="application", status=HealthStatus.CRITICAL, error_message=str(e)
            )

    def _determine_status(self, value: float, metric_type: str) -> HealthStatus:
        """Determine health status based on value and thresholds."""
        thresholds = self.thresholds.get(metric_type, {})

        critical_threshold = thresholds.get("critical")
        warning_threshold = thresholds.get("warning")

        if critical_threshold and value >= critical_threshold:
            return HealthStatus.CRITICAL
        elif warning_threshold and value >= warning_threshold:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def _calculate_overall_status(self) -> HealthStatus:
        """Calculate overall system health status."""
        if not self.components:
            return HealthStatus.UNHEALTHY

        statuses = [component.status for component in self.components.values()]

        # If any component is critical, overall is critical
        if HealthStatus.CRITICAL in statuses:
            return HealthStatus.CRITICAL

        # If any component is unhealthy, overall is unhealthy
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY

        # If any component is degraded, overall is degraded
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED

        # All components are healthy
        return HealthStatus.HEALTHY

    def _build_health_response(
        self, overall_status: HealthStatus, check_duration: float
    ) -> dict[str, Any]:
        """Build comprehensive health response."""
        return {
            "status": overall_status.value,
            "service": "hormonia-backend",
            "version": "1.0.0",
            "environment": settings.APP_ENVIRONMENT,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "check_duration_ms": round(check_duration, 2),
            "components": {
                name: {
                    "status": component.status.value,
                    "last_check": component.last_check.isoformat() + "Z",
                    "response_time_ms": component.response_time_ms,
                    "error_message": component.error_message,
                    "metrics": [
                        {
                            "name": metric.name,
                            "value": metric.value,
                            "unit": metric.unit,
                            "status": metric.status.value,
                            "threshold_warning": metric.threshold_warning,
                            "threshold_critical": metric.threshold_critical,
                            "timestamp": metric.timestamp.isoformat() + "Z",
                            "metadata": metric.metadata,
                        }
                        for metric in component.metrics
                    ],
                }
                for name, component in self.components.items()
            },
            "summary": {
                "total_components": len(self.components),
                "healthy_components": len(
                    [
                        c
                        for c in self.components.values()
                        if c.status == HealthStatus.HEALTHY
                    ]
                ),
                "degraded_components": len(
                    [
                        c
                        for c in self.components.values()
                        if c.status == HealthStatus.DEGRADED
                    ]
                ),
                "unhealthy_components": len(
                    [
                        c
                        for c in self.components.values()
                        if c.status == HealthStatus.UNHEALTHY
                    ]
                ),
                "critical_components": len(
                    [
                        c
                        for c in self.components.values()
                        if c.status == HealthStatus.CRITICAL
                    ]
                ),
            },
        }

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get summary of all collected metrics."""
        all_metrics = []

        for component in self.components.values():
            for metric in component.metrics:
                all_metrics.append(
                    {
                        "component": component.name,
                        "name": metric.name,
                        "value": metric.value,
                        "unit": metric.unit,
                        "status": metric.status.value,
                        "timestamp": metric.timestamp.isoformat() + "Z",
                    }
                )

        return {
            "total_metrics": len(all_metrics),
            "metrics": all_metrics,
            "last_collection": self.last_full_check.isoformat() + "Z"
            if self.last_full_check
            else None,
        }


# Global health monitor instance
health_monitor = HealthMonitor()


async def check_system_health() -> dict[str, Any]:
    """Convenience function to check system health."""
    return await health_monitor.check_system_health()


def get_health_metrics() -> dict[str, Any]:
    """Get health metrics summary."""
    return health_monitor.get_metrics_summary()
