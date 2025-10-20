"""
Analytics Cache Module.

Specialized cache wrapper for analytics data (metrics, reports, dashboards).
Provides optimized caching for aggregated data with longer TTLs.

Author: Backend Team
Date: 2025-01-20
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

from app.services.ai.cache_layer import CacheLayer, get_cache_layer


class AnalyticsCache:
    """
    Specialized cache for analytics data.

    Features:
    - Metrics caching (counters, sums, averages)
    - Reports caching (aggregated data)
    - Dashboard data caching
    - Longer TTLs for analytics data
    - Automatic key namespacing
    """

    def __init__(self, cache_layer: Optional[CacheLayer] = None):
        """
        Initialize Analytics Cache.

        Args:
            cache_layer: Optional CacheLayer instance. If not provided, uses singleton.
        """
        self.cache = cache_layer or get_cache_layer()
        self.prefix = "analytics"

        # TTLs específicos para analytics
        self.metric_ttl = 300  # 5 minutos para métricas
        self.report_ttl = 1800  # 30 minutos para relatórios
        self.dashboard_ttl = 600  # 10 minutos para dashboards
        self.aggregated_ttl = 3600  # 1 hora para dados agregados

    def _make_key(self, namespace: str, key: str) -> str:
        """
        Create namespaced cache key.

        Args:
            namespace: Cache namespace (metrics, reports, dashboards)
            key: Cache key

        Returns:
            Namespaced key
        """
        return f"{self.prefix}:{namespace}:{key}"

    # ==================== METRICS ====================

    async def get_metric(
        self, metric_name: str, scope: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached metric value.

        Args:
            metric_name: Name of the metric
            scope: Optional scope (e.g., "daily", "monthly", "user:123")

        Returns:
            Cached metric data or None
        """
        key = f"{metric_name}:{scope}" if scope else metric_name
        return await self.cache.get(self._make_key("metrics", key))

    async def set_metric(
        self,
        metric_name: str,
        value: Dict[str, Any],
        scope: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache metric value.

        Args:
            metric_name: Name of the metric
            value: Metric data (value, timestamp, metadata)
            scope: Optional scope
            ttl: Optional TTL override

        Returns:
            True if successful
        """
        key = f"{metric_name}:{scope}" if scope else metric_name
        ttl = ttl or self.metric_ttl
        return await self.cache.set(self._make_key("metrics", key), value, ttl)

    async def increment_counter(
        self, counter_name: str, scope: Optional[str] = None, increment: int = 1
    ) -> int:
        """
        Increment a counter metric.

        Args:
            counter_name: Name of the counter
            scope: Optional scope
            increment: Increment value (default: 1)

        Returns:
            New counter value
        """
        key = f"{counter_name}:{scope}" if scope else counter_name
        full_key = self._make_key("counters", key)

        # Get current value
        current = await self.cache.get(full_key)
        new_value = (current or 0) + increment

        # Set with extended TTL for counters
        await self.cache.set(full_key, new_value, self.aggregated_ttl)

        return new_value

    async def get_counter(self, counter_name: str, scope: Optional[str] = None) -> int:
        """
        Get counter value.

        Args:
            counter_name: Name of the counter
            scope: Optional scope

        Returns:
            Counter value (0 if not found)
        """
        key = f"{counter_name}:{scope}" if scope else counter_name
        value = await self.cache.get(self._make_key("counters", key))
        return value or 0

    # ==================== REPORTS ====================

    async def get_report(
        self, report_id: str, filters: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached report data.

        Args:
            report_id: Report identifier
            filters: Optional filters applied to report

        Returns:
            Cached report data or None
        """
        key = report_id
        if filters:
            # Create stable key from filters
            filter_str = ":".join(f"{k}={v}" for k, v in sorted(filters.items()))
            key = f"{report_id}:{filter_str}"

        return await self.cache.get(self._make_key("reports", key))

    async def set_report(
        self,
        report_id: str,
        data: Dict[str, Any],
        filters: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache report data.

        Args:
            report_id: Report identifier
            data: Report data
            filters: Optional filters applied to report
            ttl: Optional TTL override

        Returns:
            True if successful
        """
        key = report_id
        if filters:
            filter_str = ":".join(f"{k}={v}" for k, v in sorted(filters.items()))
            key = f"{report_id}:{filter_str}"

        ttl = ttl or self.report_ttl
        return await self.cache.set(self._make_key("reports", key), data, ttl)

    async def invalidate_report(
        self, report_id: str, filters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Invalidate cached report.

        Args:
            report_id: Report identifier
            filters: Optional filters

        Returns:
            True if deleted
        """
        key = report_id
        if filters:
            filter_str = ":".join(f"{k}={v}" for k, v in sorted(filters.items()))
            key = f"{report_id}:{filter_str}"

        return await self.cache.delete(self._make_key("reports", key))

    # ==================== DASHBOARDS ====================

    async def get_dashboard(
        self, dashboard_id: str, user_id: Optional[UUID] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached dashboard data.

        Args:
            dashboard_id: Dashboard identifier
            user_id: Optional user ID for personalized dashboards

        Returns:
            Cached dashboard data or None
        """
        key = f"{dashboard_id}:{user_id}" if user_id else dashboard_id
        return await self.cache.get(self._make_key("dashboards", key))

    async def set_dashboard(
        self,
        dashboard_id: str,
        data: Dict[str, Any],
        user_id: Optional[UUID] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache dashboard data.

        Args:
            dashboard_id: Dashboard identifier
            data: Dashboard data (widgets, metrics, charts)
            user_id: Optional user ID
            ttl: Optional TTL override

        Returns:
            True if successful
        """
        key = f"{dashboard_id}:{user_id}" if user_id else dashboard_id
        ttl = ttl or self.dashboard_ttl
        return await self.cache.set(self._make_key("dashboards", key), data, ttl)

    async def invalidate_dashboard(
        self, dashboard_id: str, user_id: Optional[UUID] = None
    ) -> bool:
        """
        Invalidate cached dashboard.

        Args:
            dashboard_id: Dashboard identifier
            user_id: Optional user ID

        Returns:
            True if deleted
        """
        key = f"{dashboard_id}:{user_id}" if user_id else dashboard_id
        return await self.cache.delete(self._make_key("dashboards", key))

    # ==================== AGGREGATIONS ====================

    async def get_aggregation(
        self,
        entity_type: str,
        aggregation_type: str,
        filters: Optional[Dict[str, Any]] = None,
        period: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached aggregation result.

        Args:
            entity_type: Type of entity (patients, treatments, etc)
            aggregation_type: Type of aggregation (count, sum, avg, etc)
            filters: Optional filters
            period: Optional time period (daily, weekly, monthly)

        Returns:
            Cached aggregation or None
        """
        key_parts = [entity_type, aggregation_type]

        if period:
            key_parts.append(period)

        if filters:
            filter_str = ":".join(f"{k}={v}" for k, v in sorted(filters.items()))
            key_parts.append(filter_str)

        key = ":".join(key_parts)
        return await self.cache.get(self._make_key("aggregations", key))

    async def set_aggregation(
        self,
        entity_type: str,
        aggregation_type: str,
        data: Dict[str, Any],
        filters: Optional[Dict[str, Any]] = None,
        period: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache aggregation result.

        Args:
            entity_type: Type of entity
            aggregation_type: Type of aggregation
            data: Aggregation result
            filters: Optional filters
            period: Optional time period
            ttl: Optional TTL override

        Returns:
            True if successful
        """
        key_parts = [entity_type, aggregation_type]

        if period:
            key_parts.append(period)

        if filters:
            filter_str = ":".join(f"{k}={v}" for k, v in sorted(filters.items()))
            key_parts.append(filter_str)

        key = ":".join(key_parts)
        ttl = ttl or self.aggregated_ttl
        return await self.cache.set(self._make_key("aggregations", key), data, ttl)

    # ==================== BULK OPERATIONS ====================

    async def invalidate_all_metrics(self) -> int:
        """
        Invalidate all cached metrics.

        Returns:
            Number of keys deleted
        """
        pattern = f"{self.prefix}:metrics:*"
        return await self.cache.delete_pattern(pattern)

    async def invalidate_all_reports(self) -> int:
        """
        Invalidate all cached reports.

        Returns:
            Number of keys deleted
        """
        pattern = f"{self.prefix}:reports:*"
        return await self.cache.delete_pattern(pattern)

    async def invalidate_all_dashboards(self) -> int:
        """
        Invalidate all cached dashboards.

        Returns:
            Number of keys deleted
        """
        pattern = f"{self.prefix}:dashboards:*"
        return await self.cache.delete_pattern(pattern)

    async def clear_all(self) -> int:
        """
        Clear all analytics cache.

        Returns:
            Total number of keys deleted
        """
        pattern = f"{self.prefix}:*"
        return await self.cache.delete_pattern(pattern)

    # ==================== STATS ====================

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get analytics cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        stats = await self.cache.get_stats()

        # Add analytics-specific stats
        stats["namespaces"] = {
            "metrics": await self._count_keys("metrics"),
            "reports": await self._count_keys("reports"),
            "dashboards": await self._count_keys("dashboards"),
            "counters": await self._count_keys("counters"),
            "aggregations": await self._count_keys("aggregations"),
        }

        return stats

    async def _count_keys(self, namespace: str) -> int:
        """
        Count keys in namespace.

        Args:
            namespace: Cache namespace

        Returns:
            Number of keys
        """
        pattern = f"{self.prefix}:{namespace}:*"
        keys = await self.cache.get_keys(pattern)
        return len(keys) if keys else 0


# Singleton instance
_analytics_cache_instance: Optional[AnalyticsCache] = None


def get_analytics_cache() -> AnalyticsCache:
    """
    Get singleton AnalyticsCache instance.

    Returns:
        AnalyticsCache instance
    """
    global _analytics_cache_instance
    if _analytics_cache_instance is None:
        _analytics_cache_instance = AnalyticsCache()
    return _analytics_cache_instance
