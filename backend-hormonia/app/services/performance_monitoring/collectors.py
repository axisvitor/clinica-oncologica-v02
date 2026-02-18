"""
Metric collection methods for performance monitoring.
Handles gathering various performance metrics from different components.
"""

import logging
import statistics
import json
from typing import Any, List
from datetime import datetime, timedelta, timezone

from redis import Redis

from app.services.performance_monitoring.models import MetricType, PerformanceMetric
from app.models.message import Message
from sqlalchemy import text
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class MetricCollector:
    """Collects performance metrics from various sources."""

    def __init__(self, db: Any, redis: Redis):
        self.db = db
        self.redis = redis

    async def collect_response_time_metrics(self) -> List[PerformanceMetric]:
        """Collect response time metrics."""
        metrics = []

        try:
            # Get recent response times from Redis
            response_times = await self.redis.lrange("response_times", 0, 99)  # type: ignore[misc]

            if response_times:
                times = [float(t) for t in response_times]
                avg_response_time = statistics.mean(times)
                p95_response_time = (
                    statistics.quantiles(times, n=20)[18]
                    if len(times) > 1
                    else times[0]
                )

                metrics.append(
                    PerformanceMetric(
                        metric_type=MetricType.RESPONSE_TIME,
                        value=avg_response_time,
                        component="api",
                        timestamp=now_sao_paulo(),
                        metadata={
                            "p95": p95_response_time,
                            "sample_count": len(times),
                            "min": min(times),
                            "max": max(times),
                        },
                    )
                )

            return metrics

        except Exception as e:
            logger.error(f"Error collecting response time metrics: {e}")
            return []

    async def collect_throughput_metrics(self) -> List[PerformanceMetric]:
        """Collect throughput metrics."""
        metrics = []

        try:
            # Get message count from last minute
            one_minute_ago = now_sao_paulo() - timedelta(minutes=1)

            message_count = (
                self.db.query(Message)
                .filter(Message.sent_at >= one_minute_ago)
                .count()
            )

            metrics.append(
                PerformanceMetric(
                    metric_type=MetricType.THROUGHPUT,
                    value=float(message_count),
                    component="flow_processing",
                    timestamp=now_sao_paulo(),
                    metadata={
                        "messages_per_minute": message_count,
                        "time_window": "1_minute",
                    },
                )
            )

            return metrics

        except Exception as e:
            logger.error(f"Error collecting throughput metrics: {e}")
            return []

    async def collect_error_rate_metrics(self) -> List[PerformanceMetric]:
        """Collect error rate metrics."""
        metrics = []

        try:
            # Get error count from Redis
            error_count = await self.redis.llen("flow_errors")  # type: ignore[misc]
            total_operations = await self.redis.get("total_operations")
            total_operations = int(total_operations) if total_operations else 1

            error_rate = error_count / max(total_operations, 1)

            metrics.append(
                PerformanceMetric(
                    metric_type=MetricType.ERROR_RATE,
                    value=error_rate,
                    component="flow_processing",
                    timestamp=now_sao_paulo(),
                    metadata={
                        "error_count": error_count,
                        "total_operations": total_operations,
                    },
                )
            )

            return metrics

        except Exception as e:
            logger.error(f"Error collecting error rate metrics: {e}")
            return []

    async def collect_queue_depth_metrics(self) -> List[PerformanceMetric]:
        """Collect queue depth metrics."""
        metrics = []

        try:
            # This would integrate with your actual queue system (Celery, etc.)
            # For now, return a placeholder
            queue_depth = 0

            metrics.append(
                PerformanceMetric(
                    metric_type=MetricType.QUEUE_DEPTH,
                    value=float(queue_depth),
                    component="message_queue",
                    timestamp=now_sao_paulo(),
                    metadata={"queue_name": "flow_processing"},
                )
            )

            return metrics

        except Exception as e:
            logger.error(f"Error collecting queue depth metrics: {e}")
            return []

    async def collect_memory_usage_metrics(self) -> List[PerformanceMetric]:
        """Collect memory usage metrics."""
        metrics = []

        try:
            # Redis memory usage
            redis_info = await self.redis.info("memory")
            used_memory = redis_info.get("used_memory", 0)
            max_memory = redis_info.get("maxmemory", 0)

            if max_memory > 0:
                memory_usage = used_memory / max_memory

                metrics.append(
                    PerformanceMetric(
                        metric_type=MetricType.MEMORY_USAGE,
                        value=memory_usage,
                        component="redis",
                        timestamp=now_sao_paulo(),
                        metadata={
                            "used_memory_mb": used_memory / (1024 * 1024),
                            "max_memory_mb": max_memory / (1024 * 1024),
                        },
                    )
                )

            return metrics

        except Exception as e:
            logger.error(f"Error collecting memory usage metrics: {e}")
            return []

    async def collect_cache_hit_rate_metrics(self) -> List[PerformanceMetric]:
        """Collect cache hit rate metrics."""
        metrics = []

        try:
            # Get cache statistics from Redis
            cache_hits = await self.redis.get("cache_hits") or 0
            cache_misses = await self.redis.get("cache_misses") or 0

            total_requests = int(cache_hits) + int(cache_misses)
            hit_rate = int(cache_hits) / max(total_requests, 1)

            metrics.append(
                PerformanceMetric(
                    metric_type=MetricType.CACHE_HIT_RATE,
                    value=hit_rate,
                    component="redis",
                    timestamp=now_sao_paulo(),
                    metadata={
                        "cache_hits": int(cache_hits),
                        "cache_misses": int(cache_misses),
                        "total_requests": total_requests,
                    },
                )
            )

            return metrics

        except Exception as e:
            logger.error(f"Error collecting cache hit rate metrics: {e}")
            return []

    async def collect_database_connection_metrics(self) -> List[PerformanceMetric]:
        """Collect database connection metrics."""
        metrics = []

        try:
            # Get database connection count
            result = self.db.execute(text("SELECT count(*) FROM pg_stat_activity"))
            connection_count = result.scalar()

            metrics.append(
                PerformanceMetric(
                    metric_type=MetricType.DATABASE_CONNECTIONS,
                    value=float(connection_count),
                    component="database",
                    timestamp=now_sao_paulo(),
                    metadata={"active_connections": connection_count},
                )
            )

            return metrics

        except Exception as e:
            logger.error(f"Error collecting database connection metrics: {e}")
            return []

    async def store_metrics(self, metrics: List[PerformanceMetric]) -> None:
        """Store metrics in Redis for trend analysis."""
        try:
            for metric in metrics:
                key = f"metrics:{metric.component}:{metric.metric_type.value}"

                metric_data = {
                    "value": metric.value,
                    "timestamp": metric.timestamp.isoformat(),
                    "metadata": metric.metadata,
                }

                # Store in time series (keep last 1000 data points)
                await self.redis.lpush(key, json.dumps(metric_data))  # type: ignore[misc]
                await self.redis.ltrim(key, 0, 999)  # type: ignore[misc]
                await self.redis.expire(key, 86400 * 7)  # Keep for 7 days

        except Exception as e:
            logger.error(f"Error storing metrics: {e}")

    async def get_metrics_for_range(
        self, start_time: datetime, end_time: datetime
    ) -> List[PerformanceMetric]:
        """Get metrics for a specific time range."""
        metrics = []

        try:
            # Get all metric keys (non-blocking scan)
            metric_keys = []
            async for key in self.redis.scan_iter(match="metrics:*", count=100):
                metric_keys.append(key)

            for key in metric_keys:
                # Parse key to get component and metric type
                parts = key.decode().split(":")
                if len(parts) >= 3:
                    component = parts[1]
                    metric_type_str = parts[2]

                    try:
                        metric_type = MetricType(metric_type_str)
                    except ValueError:
                        continue

                    # Get metric data
                    metric_data_list = await self.redis.lrange(key, 0, -1)  # type: ignore[misc]

                    for data_str in metric_data_list:
                        try:
                            data = json.loads(data_str)
                            timestamp = datetime.fromisoformat(data["timestamp"])

                            if start_time <= timestamp <= end_time:
                                metrics.append(
                                    PerformanceMetric(
                                        metric_type=metric_type,
                                        value=data["value"],
                                        component=component,
                                        timestamp=timestamp,
                                        metadata=data.get("metadata", {}),
                                    )
                                )
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue

            return sorted(metrics, key=lambda x: x.timestamp)

        except Exception as e:
            logger.error(f"Error getting metrics for range: {e}")
            return []
