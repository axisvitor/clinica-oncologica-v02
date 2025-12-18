"""
Redis-based Metrics Storage Service for Hormonia Healthcare System.

This service provides high-performance Redis storage for metrics data with:
- Time-series data management
- Automated data retention policies
- Efficient aggregation and querying
- Real-time metric updates
- Memory-optimized storage patterns
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import redis.asyncio as redis
import logging
from dataclasses import dataclass, asdict
from enum import Enum

from app.config import settings

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Metric data types for optimized storage."""

    GAUGE = "gauge"  # Single value at point in time
    COUNTER = "counter"  # Monotonically increasing value
    HISTOGRAM = "histogram"  # Distribution of values
    TIMER = "timer"  # Duration measurements


@dataclass
class MetricPoint:
    """Individual metric data point."""

    timestamp: int
    value: Union[float, int]
    tags: Dict[str, str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = {}
        if self.metadata is None:
            self.metadata = {}


class MetricsRedisStorage:
    """
    High-performance Redis storage for healthcare metrics.

    Implements time-series patterns optimized for healthcare KPIs including:
    - Patient engagement tracking
    - Quiz completion rates
    - AI personalization metrics
    - System performance monitoring
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.key_prefix = "hormonia:metrics:"

        # Storage configuration
        self.retention_policies = {
            # Raw data retention periods
            "raw": timedelta(hours=24),  # 24 hours of raw data
            "hourly": timedelta(days=7),  # 7 days of hourly aggregates
            "daily": timedelta(days=90),  # 90 days of daily aggregates
            "monthly": timedelta(days=365),  # 1 year of monthly aggregates
        }

        # Metric-specific configurations
        self.metric_configs = {
            # Healthcare KPIs
            "engagement_rate": {
                "type": MetricType.GAUGE,
                "unit": "percent",
                "retention": "monthly",
            },
            "quiz_completion_rate": {
                "type": MetricType.GAUGE,
                "unit": "percent",
                "retention": "monthly",
            },
            "ai_personalization_impact": {
                "type": MetricType.GAUGE,
                "unit": "percent",
                "retention": "monthly",
            },
            "active_patients": {
                "type": MetricType.GAUGE,
                "unit": "count",
                "retention": "daily",
            },
            "daily_messages": {
                "type": MetricType.COUNTER,
                "unit": "count",
                "retention": "daily",
            },
            # Patient engagement metrics
            "patient_responses": {
                "type": MetricType.COUNTER,
                "unit": "count",
                "retention": "daily",
            },
            "avg_response_time": {
                "type": MetricType.TIMER,
                "unit": "hours",
                "retention": "daily",
            },
            "daily_active_users": {
                "type": MetricType.GAUGE,
                "unit": "count",
                "retention": "daily",
            },
            "weekly_active_users": {
                "type": MetricType.GAUGE,
                "unit": "count",
                "retention": "daily",
            },
            "monthly_active_users": {
                "type": MetricType.GAUGE,
                "unit": "count",
                "retention": "daily",
            },
            # Quiz metrics
            "quiz_sessions_started": {
                "type": MetricType.COUNTER,
                "unit": "count",
                "retention": "daily",
            },
            "quiz_sessions_completed": {
                "type": MetricType.COUNTER,
                "unit": "count",
                "retention": "daily",
            },
            "quiz_completion_time": {
                "type": MetricType.TIMER,
                "unit": "minutes",
                "retention": "daily",
            },
            # AI metrics
            "ai_messages_processed": {
                "type": MetricType.COUNTER,
                "unit": "count",
                "retention": "daily",
            },
            "ai_personalization_rate": {
                "type": MetricType.GAUGE,
                "unit": "percent",
                "retention": "daily",
            },
            "ai_safety_interventions": {
                "type": MetricType.COUNTER,
                "unit": "count",
                "retention": "daily",
            },
            "ai_fallback_rate": {
                "type": MetricType.GAUGE,
                "unit": "percent",
                "retention": "daily",
            },
            "ai_quality_score": {
                "type": MetricType.GAUGE,
                "unit": "score",
                "retention": "daily",
            },
            # System metrics
            "cpu_usage": {
                "type": MetricType.GAUGE,
                "unit": "percent",
                "retention": "hourly",
            },
            "memory_usage": {
                "type": MetricType.GAUGE,
                "unit": "percent",
                "retention": "hourly",
            },
            "disk_usage": {
                "type": MetricType.GAUGE,
                "unit": "percent",
                "retention": "hourly",
            },
            "response_time": {
                "type": MetricType.TIMER,
                "unit": "milliseconds",
                "retention": "hourly",
            },
            "error_rate": {
                "type": MetricType.GAUGE,
                "unit": "percent",
                "retention": "hourly",
            },
            "throughput": {
                "type": MetricType.GAUGE,
                "unit": "rps",
                "retention": "hourly",
            },
            "active_connections": {
                "type": MetricType.GAUGE,
                "unit": "count",
                "retention": "hourly",
            },
        }

    async def _get_redis_client(self) -> redis.Redis:
        """Get Redis client, create if needed."""
        if self.redis_client is None:
            try:
                # Use unified Redis client
                from app.core.redis_unified import get_async_redis

                self.redis_client = await get_async_redis()
                logger.info("MetricsRedisStorage connected to Redis via unified client")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                # Fallback to direct connection
                self.redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_timeout=30.0,
                    socket_connect_timeout=30.0,
                    retry_on_timeout=True,
                    retry_on_error=[redis.ConnectionError, redis.TimeoutError],
                    socket_keepalive=True,
                    socket_keepalive_options={},
                    health_check_interval=30,
                )
                logger.warning(
                    "MetricsRedisStorage using direct Redis connection as fallback"
                )
        return self.redis_client

    def _get_metric_key(
        self,
        metric_name: str,
        granularity: str = "raw",
        timestamp: Optional[int] = None,
    ) -> str:
        """Generate Redis key for metric storage."""
        if timestamp is None:
            timestamp = int(time.time())

        if granularity == "raw":
            # Bucket by hour for raw data
            hour_bucket = timestamp - (timestamp % 3600)
            return f"{self.key_prefix}raw:{metric_name}:{hour_bucket}"
        else:
            # Use date-based keys for aggregated data
            date = datetime.fromtimestamp(timestamp)
            if granularity == "hourly":
                date_key = date.strftime("%Y%m%d%H")
            elif granularity == "daily":
                date_key = date.strftime("%Y%m%d")
            elif granularity == "monthly":
                date_key = date.strftime("%Y%m")
            else:
                date_key = str(timestamp)

            return f"{self.key_prefix}{granularity}:{metric_name}:{date_key}"

    async def record_metric(
        self,
        metric_name: str,
        value: Union[float, int],
        timestamp: Optional[int] = None,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Record a single metric point.

        Args:
            metric_name: Name of the metric
            value: Metric value
            timestamp: Unix timestamp (current time if None)
            tags: Optional tags for filtering/grouping
            metadata: Additional metadata

        Returns:
            True if successful, False otherwise
        """
        try:
            if timestamp is None:
                timestamp = int(time.time())

            redis_client = await self._get_redis_client()

            # Create metric point
            point = MetricPoint(
                timestamp=timestamp,
                value=value,
                tags=tags or {},
                metadata=metadata or {},
            )

            # Store raw data point
            raw_key = self._get_metric_key(metric_name, "raw", timestamp)
            point_data = json.dumps(asdict(point))

            # Use sorted set for time-ordered storage
            await redis_client.zadd(raw_key, {point_data: timestamp})

            # Set TTL based on retention policy
            retention = self.retention_policies["raw"]
            await redis_client.expire(raw_key, int(retention.total_seconds()))

            # Update real-time current value
            current_key = f"{self.key_prefix}current:{metric_name}"
            await redis_client.set(current_key, value, ex=3600)  # 1 hour TTL

            # Record in metric catalog for discovery
            catalog_key = f"{self.key_prefix}catalog"
            metric_info = {
                "last_updated": timestamp,
                "latest_value": value,
                **self.metric_configs.get(metric_name, {}),
            }
            await redis_client.hset(catalog_key, metric_name, json.dumps(metric_info))

            # Trigger aggregation for configured metrics
            if metric_name in self.metric_configs:
                await self._schedule_aggregation(metric_name, timestamp)

            return True

        except Exception as e:
            logger.error(f"Error recording metric {metric_name}: {e}")
            return False

    async def record_batch_metrics(self, metrics: List[Dict[str, Any]]) -> int:
        """
        Record multiple metrics in a single operation.

        Args:
            metrics: List of metric dictionaries with keys: name, value, timestamp, tags, metadata

        Returns:
            Number of successfully recorded metrics
        """
        successful = 0

        try:
            redis_client = await self._get_redis_client()
            pipe = redis_client.pipeline()

            current_time = int(time.time())

            for metric in metrics:
                metric_name = metric.get("name")
                value = metric.get("value")
                timestamp = metric.get("timestamp", current_time)
                tags = metric.get("tags", {})
                metadata = metric.get("metadata", {})

                if not metric_name or value is None:
                    continue

                # Create metric point
                point = MetricPoint(
                    timestamp=timestamp, value=value, tags=tags, metadata=metadata
                )

                # Add to pipeline
                raw_key = self._get_metric_key(metric_name, "raw", timestamp)
                point_data = json.dumps(asdict(point))
                pipe.zadd(raw_key, {point_data: timestamp})
                pipe.expire(
                    raw_key, int(self.retention_policies["raw"].total_seconds())
                )

                # Update current value
                current_key = f"{self.key_prefix}current:{metric_name}"
                pipe.set(current_key, value, ex=3600)

                successful += 1

            if successful > 0:
                await pipe.execute()

        except Exception as e:
            logger.error(f"Error recording batch metrics: {e}")

        return successful

    async def get_current_value(self, metric_name: str) -> Optional[float]:
        """Get the current/latest value for a metric."""
        try:
            redis_client = await self._get_redis_client()
            current_key = f"{self.key_prefix}current:{metric_name}"
            value = await redis_client.get(current_key)
            return float(value) if value else None
        except Exception as e:
            logger.error(f"Error getting current value for {metric_name}: {e}")
            return None

    async def get_metric_history(
        self, metric_name: str, start_time: int, end_time: int, granularity: str = "raw"
    ) -> List[MetricPoint]:
        """
        Get historical metric data for a time range.

        Args:
            metric_name: Name of the metric
            start_time: Start timestamp
            end_time: End timestamp
            granularity: Data granularity (raw, hourly, daily, monthly)

        Returns:
            List of metric points
        """
        try:
            redis_client = await self._get_redis_client()
            points = []

            if granularity == "raw":
                # For raw data, we need to query multiple hour buckets
                current_time = start_time
                while current_time <= end_time:
                    hour_bucket = current_time - (current_time % 3600)
                    raw_key = self._get_metric_key(metric_name, "raw", hour_bucket)

                    # Get points in time range from this bucket
                    bucket_points = await redis_client.zrangebyscore(
                        raw_key, start_time, end_time, withscores=False
                    )

                    for point_data in bucket_points:
                        try:
                            point_dict = json.loads(point_data)
                            point = MetricPoint(**point_dict)
                            if start_time <= point.timestamp <= end_time:
                                points.append(point)
                        except (json.JSONDecodeError, TypeError):
                            continue

                    current_time = hour_bucket + 3600
            else:
                # For aggregated data, use single key per time unit
                aggregated_key = self._get_metric_key(
                    metric_name, granularity, start_time
                )
                points_data = await redis_client.zrangebyscore(
                    aggregated_key, start_time, end_time, withscores=False
                )

                for point_data in points_data:
                    try:
                        point_dict = json.loads(point_data)
                        points.append(MetricPoint(**point_dict))
                    except (json.JSONDecodeError, TypeError):
                        continue

            return sorted(points, key=lambda p: p.timestamp)

        except Exception as e:
            logger.error(f"Error getting metric history for {metric_name}: {e}")
            return []

    async def get_aggregated_metrics(
        self,
        metric_names: List[str],
        start_time: int,
        end_time: int,
        aggregation: str = "avg",
    ) -> Dict[str, float]:
        """
        Get aggregated values for multiple metrics.

        Args:
            metric_names: List of metric names
            start_time: Start timestamp
            end_time: End timestamp
            aggregation: Aggregation type (avg, sum, min, max, count)

        Returns:
            Dictionary of metric names to aggregated values
        """
        results = {}

        for metric_name in metric_names:
            try:
                history = await self.get_metric_history(
                    metric_name, start_time, end_time
                )
                if not history:
                    results[metric_name] = 0.0
                    continue

                values = [point.value for point in history]

                if aggregation == "avg":
                    results[metric_name] = sum(values) / len(values)
                elif aggregation == "sum":
                    results[metric_name] = sum(values)
                elif aggregation == "min":
                    results[metric_name] = min(values)
                elif aggregation == "max":
                    results[metric_name] = max(values)
                elif aggregation == "count":
                    results[metric_name] = len(values)
                else:
                    results[metric_name] = values[-1] if values else 0.0

            except Exception as e:
                logger.error(f"Error aggregating {metric_name}: {e}")
                results[metric_name] = 0.0

        return results

    async def get_metrics_catalog(self) -> Dict[str, Dict[str, Any]]:
        """Get catalog of all available metrics."""
        try:
            redis_client = await self._get_redis_client()
            catalog_key = f"{self.key_prefix}catalog"
            catalog_raw = await redis_client.hgetall(catalog_key)

            catalog = {}
            for metric_name, info_json in catalog_raw.items():
                try:
                    catalog[metric_name] = json.loads(info_json)
                except json.JSONDecodeError:
                    continue

            return catalog

        except Exception as e:
            logger.error(f"Error getting metrics catalog: {e}")
            return {}

    async def _schedule_aggregation(self, metric_name: str, timestamp: int):
        """Schedule aggregation task for a metric (placeholder for actual implementation)."""
        # This would typically trigger a background task
        # For now, we'll do simple in-memory aggregation
        try:
            await self._aggregate_hourly(metric_name, timestamp)
        except Exception as e:
            logger.error(f"Error scheduling aggregation for {metric_name}: {e}")

    async def _aggregate_hourly(self, metric_name: str, timestamp: int):
        """Aggregate raw data into hourly buckets."""
        try:
            redis_client = await self._get_redis_client()

            # Calculate hour boundaries
            hour_start = timestamp - (timestamp % 3600)
            hour_end = hour_start + 3599

            # Get raw data for the hour
            raw_key = self._get_metric_key(metric_name, "raw", hour_start)
            raw_points = await redis_client.zrangebyscore(
                raw_key, hour_start, hour_end, withscores=False
            )

            if not raw_points:
                return

            # Parse and aggregate
            values = []
            for point_data in raw_points:
                try:
                    point_dict = json.loads(point_data)
                    values.append(point_dict["value"])
                except (json.JSONDecodeError, KeyError):
                    continue

            if not values:
                return

            # Create aggregated point
            aggregated_point = MetricPoint(
                timestamp=hour_start,
                value=sum(values) / len(values),  # Average for hourly aggregation
                metadata={
                    "aggregation": "hourly",
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "sum": sum(values),
                },
            )

            # Store aggregated data
            hourly_key = self._get_metric_key(metric_name, "hourly", hour_start)
            point_data = json.dumps(asdict(aggregated_point))
            await redis_client.zadd(hourly_key, {point_data: hour_start})

            # Set TTL
            retention = self.retention_policies["hourly"]
            await redis_client.expire(hourly_key, int(retention.total_seconds()))

        except Exception as e:
            logger.error(f"Error aggregating hourly data for {metric_name}: {e}")

    async def cleanup_expired_data(self):
        """Clean up expired metric data (should be run periodically)."""
        try:
            redis_client = await self._get_redis_client()
            int(time.time())

            # Get all metric keys
            all_keys = await redis_client.keys(f"{self.key_prefix}*")

            for key in all_keys:
                try:
                    # Check if key has expired
                    ttl = await redis_client.ttl(key)
                    if ttl == -1:  # No expiry set
                        # Set appropriate expiry based on key type
                        if ":raw:" in key:
                            await redis_client.expire(
                                key, int(self.retention_policies["raw"].total_seconds())
                            )
                        elif ":hourly:" in key:
                            await redis_client.expire(
                                key,
                                int(self.retention_policies["hourly"].total_seconds()),
                            )
                        elif ":daily:" in key:
                            await redis_client.expire(
                                key,
                                int(self.retention_policies["daily"].total_seconds()),
                            )
                        elif ":monthly:" in key:
                            await redis_client.expire(
                                key,
                                int(self.retention_policies["monthly"].total_seconds()),
                            )

                except Exception as e:
                    logger.error(f"Error cleaning up key {key}: {e}")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        try:
            redis_client = await self._get_redis_client()

            # Get memory usage
            memory_info = await redis_client.info("memory")

            # Count keys by type
            key_counts = {
                "raw": len(await redis_client.keys(f"{self.key_prefix}raw:*")),
                "hourly": len(await redis_client.keys(f"{self.key_prefix}hourly:*")),
                "daily": len(await redis_client.keys(f"{self.key_prefix}daily:*")),
                "monthly": len(await redis_client.keys(f"{self.key_prefix}monthly:*")),
                "current": len(await redis_client.keys(f"{self.key_prefix}current:*")),
            }

            return {
                "memory_used_bytes": memory_info.get("used_memory", 0),
                "memory_used_human": memory_info.get("used_memory_human", "0B"),
                "key_counts": key_counts,
                "total_keys": sum(key_counts.values()),
                "retention_policies": {
                    k: v.total_seconds() for k, v in self.retention_policies.items()
                },
            }

        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {}

    async def close(self):
        """Close Redis connections."""
        if self.redis_client:
            await self.redis_client.close()
