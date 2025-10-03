"""
Database performance monitoring service.

Collects and exposes database metrics for monitoring systems
like Prometheus, Grafana, and custom dashboards.
"""
import logging
from typing import Dict, Any
from datetime import datetime, timezone
from app.core.database import get_pool_status, is_pool_healthy, test_connection, connection_manager
import time

logger = logging.getLogger(__name__)


class DatabasePerformanceMonitor:
    """
    Monitor and collect database performance metrics.

    Provides:
    - Connection pool statistics
    - Query performance metrics
    - Health indicators
    - Resource utilization
    """

    def __init__(self):
        """Initialize performance monitor."""
        self.start_time = time.time()
        self.query_stats = {
            "total_queries": 0,
            "slow_queries": 0,
            "failed_queries": 0,
            "total_duration": 0.0
        }
        logger.info("Database performance monitor initialized")

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive database metrics.

        Returns:
            Dictionary with all database metrics
        """
        try:
            # Get pool status for both engines
            main_pool = get_pool_status(use_service_role=True)
            rls_pool = get_pool_status(use_service_role=False)

            # Calculate pool metrics
            main_metrics = self._calculate_pool_metrics(main_pool, "main")
            rls_metrics = self._calculate_pool_metrics(rls_pool, "rls")

            # Test connection health
            main_health = test_connection(use_service_role=True)
            rls_health = test_connection(use_service_role=False)

            # Compile all metrics
            metrics = {
                "pools": {
                    "main": {
                        **main_pool,
                        **main_metrics,
                        "health_status": main_health.get("status"),
                        "healthy": main_health.get("status") == "healthy"
                    },
                    "rls": {
                        **rls_pool,
                        **rls_metrics,
                        "health_status": rls_health.get("status"),
                        "healthy": rls_health.get("status") == "healthy"
                    }
                },
                "health": {
                    "main": main_health,
                    "rls": rls_health,
                    "overall_healthy": (
                        main_health.get("status") == "healthy" and
                        rls_health.get("status") == "healthy"
                    )
                },
                "query_stats": self.query_stats,
                "uptime_seconds": time.time() - self.start_time,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            return metrics

        except Exception as e:
            logger.error(f"Error collecting database metrics: {e}", exc_info=True)
            return {
                "error": str(e),
                "error_type": type(e).__name__,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    def _calculate_pool_metrics(self, pool_status: Dict[str, Any], pool_name: str) -> Dict[str, Any]:
        """
        Calculate additional pool metrics.

        Args:
            pool_status: Raw pool status from SQLAlchemy
            pool_name: Name of the pool (main/rls)

        Returns:
            Calculated metrics dictionary
        """
        try:
            pool_size = pool_status.get("pool_size", 0)
            overflow = pool_status.get("overflow", 0)
            checked_out = pool_status.get("checked_out", 0)
            checked_in = pool_status.get("checked_in", 0)

            total_capacity = pool_size + overflow
            utilization = (checked_out / total_capacity * 100) if total_capacity > 0 else 0
            available = checked_in

            return {
                "total_capacity": total_capacity,
                "available_connections": available,
                "utilization_percent": round(utilization, 2),
                "utilization_status": self._get_utilization_status(utilization),
                "is_exhausted": checked_out >= total_capacity,
                "connections_in_use": checked_out,
                "connections_available": available
            }
        except Exception as e:
            logger.error(f"Error calculating pool metrics for {pool_name}: {e}")
            return {
                "error": str(e)
            }

    def _get_utilization_status(self, utilization: float) -> str:
        """
        Get utilization status based on percentage.

        Args:
            utilization: Utilization percentage

        Returns:
            Status string (healthy/warning/critical)
        """
        if utilization < 60:
            return "healthy"
        elif utilization < 80:
            return "warning"
        else:
            return "critical"

    def record_query(self, duration: float, success: bool = True, slow_threshold: float = 1.0) -> None:
        """
        Record query execution for statistics.

        Args:
            duration: Query duration in seconds
            success: Whether query succeeded
            slow_threshold: Threshold for slow query in seconds
        """
        self.query_stats["total_queries"] += 1
        self.query_stats["total_duration"] += duration

        if duration > slow_threshold:
            self.query_stats["slow_queries"] += 1

        if not success:
            self.query_stats["failed_queries"] += 1

    def get_query_statistics(self) -> Dict[str, Any]:
        """
        Get query performance statistics.

        Returns:
            Query statistics dictionary
        """
        total_queries = self.query_stats["total_queries"]
        avg_duration = (
            self.query_stats["total_duration"] / total_queries
            if total_queries > 0 else 0
        )

        return {
            **self.query_stats,
            "average_duration": round(avg_duration, 3),
            "slow_query_rate": (
                self.query_stats["slow_queries"] / total_queries
                if total_queries > 0 else 0
            ),
            "failure_rate": (
                self.query_stats["failed_queries"] / total_queries
                if total_queries > 0 else 0
            )
        }

    def reset_statistics(self) -> None:
        """Reset query statistics."""
        self.query_stats = {
            "total_queries": 0,
            "slow_queries": 0,
            "failed_queries": 0,
            "total_duration": 0.0
        }
        logger.info("Query statistics reset")


# Global performance monitor instance
_performance_monitor: DatabasePerformanceMonitor = None


def get_performance_monitor() -> DatabasePerformanceMonitor:
    """
    Get global performance monitor instance.

    Returns:
        DatabasePerformanceMonitor singleton
    """
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = DatabasePerformanceMonitor()
    return _performance_monitor