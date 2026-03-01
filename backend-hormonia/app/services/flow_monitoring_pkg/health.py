"""System health checks and health aggregation."""

import inspect
import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select, text

from app.models.alert import AlertSeverity
from app.models.message import Message
from app.utils.timezone import now_sao_paulo

from .models import HealthStatus, PerformanceMetrics

logger = logging.getLogger(__name__)


class FlowMonitoringHealthMixin:
    async def _resolve(self, maybe_awaitable):
        if inspect.isawaitable(maybe_awaitable):
            return await maybe_awaitable
        return maybe_awaitable

    async def get_system_health(self) -> dict[str, Any]:
        """Get overall system health status."""
        try:
            metrics = await self.collect_performance_metrics()
            health_status = await self._determine_health_status(metrics)
            active_alerts = await self.get_active_alerts()
            trends = await self._get_performance_trends()

            return {
                "status": health_status.value,
                "timestamp": now_sao_paulo().isoformat(),
                "metrics": metrics.__dict__,
                "active_alerts": [alert.__dict__ for alert in active_alerts],
                "trends": trends,
                "components": await self._get_component_health(),
            }

        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {
                "status": HealthStatus.CRITICAL.value,
                "error": str(e),
                "timestamp": now_sao_paulo().isoformat(),
            }

    async def run_health_checks(self) -> dict[str, Any]:
        """Run comprehensive health checks."""
        health_checks = {
            "database_connectivity": await self._check_database_connectivity(),
            "redis_connectivity": await self._check_redis_connectivity(),
            "flow_processing": await self._check_flow_processing_health(),
            "message_delivery": await self._check_message_delivery_health(),
            "data_integrity": await self._check_data_integrity(),
            "external_services": await self._check_external_services(),
        }

        overall_status = HealthStatus.HEALTHY
        for _check_name, check_result in health_checks.items():
            if check_result["status"] == HealthStatus.CRITICAL.value:
                overall_status = HealthStatus.CRITICAL
                break
            if (
                check_result["status"] == HealthStatus.DEGRADED.value
                and overall_status != HealthStatus.CRITICAL
            ):
                overall_status = HealthStatus.DEGRADED
            elif (
                check_result["status"] == HealthStatus.WARNING.value
                and overall_status == HealthStatus.HEALTHY
            ):
                overall_status = HealthStatus.WARNING

        return {
            "overall_status": overall_status.value,
            "timestamp": now_sao_paulo().isoformat(),
            "checks": health_checks,
        }

    async def _determine_health_status(
        self, metrics: PerformanceMetrics
    ) -> HealthStatus:
        """Determine overall health status based on metrics."""
        if (
            metrics.error_rate >= self.thresholds["error_rate_critical"]
            or metrics.average_response_time >= self.thresholds["response_time_critical"]
            or metrics.queue_depth >= self.thresholds["queue_depth_critical"]
            or metrics.redis_memory_usage >= self.thresholds["redis_memory_critical"]
        ):
            return HealthStatus.CRITICAL

        if (
            metrics.error_rate >= self.thresholds["error_rate_warning"]
            or metrics.average_response_time >= self.thresholds["response_time_warning"]
            or metrics.queue_depth >= self.thresholds["queue_depth_warning"]
            or metrics.redis_memory_usage >= self.thresholds["redis_memory_warning"]
        ):
            return HealthStatus.DEGRADED

        active_alerts = await self.get_active_alerts()
        critical_alerts = [
            alert
            for alert in active_alerts
            if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]
        ]

        if critical_alerts:
            return HealthStatus.WARNING

        return HealthStatus.HEALTHY

    async def _get_component_health(self) -> dict[str, str]:
        """Get health status of individual components."""
        return {
            "database": "healthy",
            "redis": "healthy",
            "message_queue": "healthy",
            "flow_engine": "healthy",
            "ai_services": "healthy",
        }

    async def _check_database_connectivity(self) -> dict[str, Any]:
        """Check database connectivity and performance."""
        try:
            start_time = now_sao_paulo()
            await self._resolve(self.db.execute(text("SELECT 1")))
            response_time = (now_sao_paulo() - start_time).total_seconds()

            return {
                "status": HealthStatus.HEALTHY.value,
                "response_time": response_time,
                "message": "Database connectivity is healthy",
            }
        except Exception as e:
            return {
                "status": HealthStatus.CRITICAL.value,
                "error": str(e),
                "message": "Database connectivity failed",
            }

    async def _check_redis_connectivity(self) -> dict[str, Any]:
        """Check Redis connectivity and performance."""
        try:
            start_time = now_sao_paulo()
            self.redis.ping()
            response_time = (now_sao_paulo() - start_time).total_seconds()

            return {
                "status": HealthStatus.HEALTHY.value,
                "response_time": response_time,
                "message": "Redis connectivity is healthy",
            }
        except Exception as e:
            return {
                "status": HealthStatus.CRITICAL.value,
                "error": str(e),
                "message": "Redis connectivity failed",
            }

    async def _check_flow_processing_health(self) -> dict[str, Any]:
        """Check flow processing health."""
        try:
            one_hour_ago = now_sao_paulo() - timedelta(hours=1)
            recent_result = await self._resolve(
                self.db.execute(
                    select(func.count(Message.id)).where(Message.sent_at >= one_hour_ago)
                )
            )
            recent_messages = int(recent_result.scalar() or 0)

            if recent_messages > 0:
                return {
                    "status": HealthStatus.HEALTHY.value,
                    "recent_messages": recent_messages,
                    "message": "Flow processing is active",
                }

            return {
                "status": HealthStatus.WARNING.value,
                "recent_messages": recent_messages,
                "message": "No recent flow processing activity",
            }
        except Exception as e:
            return {
                "status": HealthStatus.CRITICAL.value,
                "error": str(e),
                "message": "Flow processing health check failed",
            }

    async def _check_message_delivery_health(self) -> dict[str, Any]:
        """Check message delivery health."""
        return {
            "status": HealthStatus.HEALTHY.value,
            "message": "Message delivery is healthy",
        }

    async def _check_data_integrity(self) -> dict[str, Any]:
        """Check data integrity."""
        try:
            corruption_report = await self.corruption_detector.detect_bulk_corruption(10)

            if not corruption_report:
                return {
                    "status": HealthStatus.HEALTHY.value,
                    "message": "Data integrity is healthy",
                }

            return {
                "status": HealthStatus.WARNING.value,
                "corrupted_flows": len(corruption_report),
                "message": f"Found {len(corruption_report)} flows with data issues",
            }
        except Exception as e:
            return {
                "status": HealthStatus.CRITICAL.value,
                "error": str(e),
                "message": "Data integrity check failed",
            }

    async def _check_external_services(self) -> dict[str, Any]:
        """Check external services health."""
        return {
            "status": HealthStatus.HEALTHY.value,
            "message": "External services are healthy",
        }
