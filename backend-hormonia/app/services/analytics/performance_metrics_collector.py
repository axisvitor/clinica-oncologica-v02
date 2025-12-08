"""
Performance Metrics Collector Service.

Comprehensive system for gathering, storing, and analyzing performance metrics
including query execution times, connection counts, error rates, and system health.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import json
import statistics
import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_unified import get_async_redis


logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of performance metrics."""
    QUERY_TIME = "query_time"
    CONNECTION_COUNT = "connection_count"
    ERROR_RATE = "error_rate"
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    RESOURCE_USAGE = "resource_usage"
    BUSINESS_METRIC = "business_metric"


@dataclass
class MetricPoint:
    """A single metric data point."""
    timestamp: datetime
    metric_name: str
    metric_type: MetricType
    value: float
    labels: Dict[str, str]
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "metric_name": self.metric_name,
            "metric_type": self.metric_type.value,
            "value": self.value,
            "labels": self.labels,
            "metadata": self.metadata or {}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricPoint":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metric_name=data["metric_name"],
            metric_type=MetricType(data["metric_type"]),
            value=data["value"],
            labels=data["labels"],
            metadata=data.get("metadata", {})
        )


@dataclass
class MetricSummary:
    """Summary statistics for a metric."""
    metric_name: str
    count: int
    min_value: float
    max_value: float
    avg_value: float
    median_value: float
    p95_value: float
    p99_value: float
    std_dev: float
    time_range: Dict[str, datetime]


class PerformanceMetricsCollector:
    """
    Comprehensive performance metrics collector.
    
    Collects, stores, and analyzes various performance metrics including:
    - Query execution times
    - Connection counts and pool statistics
    - Error rates and types
    - Response times and throughput
    - Resource usage metrics
    - Business-specific metrics
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.metrics_buffer: List[MetricPoint] = []
        self.buffer_size = 1000
        self.flush_interval = 30.0  # seconds
        self.retention_days = 7
        
        # Metric storage keys
        self.redis_prefix = "performance_metrics:"
        self.summary_prefix = "metrics_summary:"
        
        # Collection state
        self._collecting = False
        self._flush_task: Optional[asyncio.Task] = None
        
        # Metric configurations
        self.metric_configs = {
            MetricType.QUERY_TIME: {"threshold": 1.0, "alert_threshold": 5.0},
            MetricType.ERROR_RATE: {"threshold": 5.0, "alert_threshold": 10.0},
            MetricType.RESPONSE_TIME: {"threshold": 1.0, "alert_threshold": 3.0},
            MetricType.CONNECTION_COUNT: {"threshold": 80, "alert_threshold": 95},
            MetricType.RESOURCE_USAGE: {"threshold": 80.0, "alert_threshold": 90.0}
        }

    async def initialize(self) -> None:
        """Initialize the metrics collector."""
        if not self.redis_client:
            try:
                self.redis_client = await get_async_redis()
                logger.info("Performance metrics collector initialized with Redis")
            except Exception as e:
                logger.warning(f"Redis not available for metrics collector: {e}")
                logger.info("Performance metrics collector initialized without Redis")

    async def start_collection(self) -> None:
        """Start metrics collection."""
        if self._collecting:
            return
            
        await self.initialize()
        self._collecting = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info("Performance metrics collection started")

    async def stop_collection(self) -> None:
        """Stop metrics collection."""
        self._collecting = False
        
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None
            
        # Flush remaining metrics
        await self._flush_metrics()
        logger.info("Performance metrics collection stopped")

    async def record_metric(self, 
                          metric_name: str,
                          metric_type: MetricType,
                          value: float,
                          labels: Optional[Dict[str, str]] = None,
                          metadata: Optional[Dict[str, Any]] = None,
                          timestamp: Optional[datetime] = None) -> None:
        """Record a performance metric."""
        if not self._collecting:
            return
            
        metric_point = MetricPoint(
            timestamp=timestamp or datetime.utcnow(),
            metric_name=metric_name,
            metric_type=metric_type,
            value=value,
            labels=labels or {},
            metadata=metadata
        )
        
        self.metrics_buffer.append(metric_point)
        
        # Check if buffer needs flushing
        if len(self.metrics_buffer) >= self.buffer_size:
            await self._flush_metrics()

    async def record_query_time(self, 
                              query: str,
                              execution_time: float,
                              table: Optional[str] = None,
                              operation: Optional[str] = None) -> None:
        """Record database query execution time."""
        labels = {
            "operation": operation or "unknown",
            "table": table or "unknown"
        }
        
        metadata = {
            "query_hash": hash(query) % 1000000,  # Simple hash for identification
            "query_length": len(query)
        }
        
        await self.record_metric(
            metric_name="db_query_execution_time",
            metric_type=MetricType.QUERY_TIME,
            value=execution_time,
            labels=labels,
            metadata=metadata
        )

    async def record_connection_count(self, 
                                    active_connections: int,
                                    pool_size: int,
                                    connection_type: str = "database") -> None:
        """Record connection pool statistics."""
        utilization = (active_connections / pool_size * 100) if pool_size > 0 else 0
        
        labels = {"connection_type": connection_type}
        metadata = {
            "active_connections": active_connections,
            "pool_size": pool_size,
            "utilization_percent": utilization
        }
        
        await self.record_metric(
            metric_name="connection_pool_utilization",
            metric_type=MetricType.CONNECTION_COUNT,
            value=utilization,
            labels=labels,
            metadata=metadata
        )

    async def record_error_rate(self, 
                              error_count: int,
                              total_requests: int,
                              error_type: str = "general",
                              endpoint: Optional[str] = None) -> None:
        """Record error rate metrics."""
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0
        
        labels = {
            "error_type": error_type,
            "endpoint": endpoint or "unknown"
        }
        
        metadata = {
            "error_count": error_count,
            "total_requests": total_requests
        }
        
        await self.record_metric(
            metric_name="error_rate",
            metric_type=MetricType.ERROR_RATE,
            value=error_rate,
            labels=labels,
            metadata=metadata
        )

    async def record_response_time(self, 
                                 endpoint: str,
                                 method: str,
                                 response_time: float,
                                 status_code: int) -> None:
        """Record API response time."""
        labels = {
            "endpoint": endpoint,
            "method": method,
            "status_code": str(status_code)
        }
        
        await self.record_metric(
            metric_name="api_response_time",
            metric_type=MetricType.RESPONSE_TIME,
            value=response_time,
            labels=labels
        )

    async def record_throughput(self, 
                              endpoint: str,
                              requests_per_second: float,
                              time_window: int = 60) -> None:
        """Record API throughput metrics."""
        labels = {
            "endpoint": endpoint,
            "time_window": str(time_window)
        }
        
        await self.record_metric(
            metric_name="api_throughput",
            metric_type=MetricType.THROUGHPUT,
            value=requests_per_second,
            labels=labels
        )

    async def record_resource_usage(self, 
                                  resource_type: str,
                                  usage_percent: float,
                                  additional_metrics: Optional[Dict[str, float]] = None) -> None:
        """Record system resource usage."""
        labels = {"resource_type": resource_type}
        metadata = additional_metrics or {}
        
        await self.record_metric(
            metric_name="system_resource_usage",
            metric_type=MetricType.RESOURCE_USAGE,
            value=usage_percent,
            labels=labels,
            metadata=metadata
        )

    async def get_metrics(self, 
                         metric_name: Optional[str] = None,
                         metric_type: Optional[MetricType] = None,
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None,
                         labels: Optional[Dict[str, str]] = None,
                         limit: int = 1000) -> List[MetricPoint]:
        """Retrieve metrics based on filters."""
        if not self.redis_client:
            # Return from buffer if Redis not available
            filtered_metrics = self.metrics_buffer.copy()
        else:
            # Get from Redis
            filtered_metrics = await self._get_metrics_from_redis(
                metric_name, metric_type, start_time, end_time, labels, limit
            )
        
        # Apply additional filtering
        if start_time:
            filtered_metrics = [m for m in filtered_metrics if m.timestamp >= start_time]
        if end_time:
            filtered_metrics = [m for m in filtered_metrics if m.timestamp <= end_time]
        if metric_name:
            filtered_metrics = [m for m in filtered_metrics if m.metric_name == metric_name]
        if metric_type:
            filtered_metrics = [m for m in filtered_metrics if m.metric_type == metric_type]
        if labels:
            filtered_metrics = [
                m for m in filtered_metrics 
                if all(m.labels.get(k) == v for k, v in labels.items())
            ]
        
        return filtered_metrics[:limit]

    async def get_metric_summary(self, 
                               metric_name: str,
                               start_time: Optional[datetime] = None,
                               end_time: Optional[datetime] = None,
                               labels: Optional[Dict[str, str]] = None) -> Optional[MetricSummary]:
        """Get summary statistics for a metric."""
        metrics = await self.get_metrics(
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            labels=labels
        )
        
        if not metrics:
            return None
            
        values = [m.value for m in metrics]
        
        return MetricSummary(
            metric_name=metric_name,
            count=len(values),
            min_value=min(values),
            max_value=max(values),
            avg_value=statistics.mean(values),
            median_value=statistics.median(values),
            p95_value=self._percentile(values, 95),
            p99_value=self._percentile(values, 99),
            std_dev=statistics.stdev(values) if len(values) > 1 else 0.0,
            time_range={
                "start": min(m.timestamp for m in metrics),
                "end": max(m.timestamp for m in metrics)
            }
        )

    async def get_slow_queries(self, 
                             threshold: float = 1.0,
                             limit: int = 10,
                             hours: int = 24) -> List[Dict[str, Any]]:
        """Get slow database queries."""
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        query_metrics = await self.get_metrics(
            metric_name="db_query_execution_time",
            metric_type=MetricType.QUERY_TIME,
            start_time=start_time
        )
        
        slow_queries = [
            {
                "timestamp": m.timestamp.isoformat(),
                "execution_time": m.value,
                "operation": m.labels.get("operation", "unknown"),
                "table": m.labels.get("table", "unknown"),
                "query_hash": m.metadata.get("query_hash") if m.metadata else None
            }
            for m in query_metrics
            if m.value >= threshold
        ]
        
        # Sort by execution time (descending)
        slow_queries.sort(key=lambda x: x["execution_time"], reverse=True)
        
        return slow_queries[:limit]

    async def get_error_analysis(self, hours: int = 24) -> Dict[str, Any]:
        """Get error rate analysis."""
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        error_metrics = await self.get_metrics(
            metric_name="error_rate",
            metric_type=MetricType.ERROR_RATE,
            start_time=start_time
        )
        
        if not error_metrics:
            return {"total_errors": 0, "error_rate": 0.0, "by_type": {}, "by_endpoint": {}}
        
        # Analyze by error type
        by_type = {}
        by_endpoint = {}
        total_errors = 0
        
        for metric in error_metrics:
            error_type = metric.labels.get("error_type", "unknown")
            endpoint = metric.labels.get("endpoint", "unknown")
            error_count = metric.metadata.get("error_count", 0) if metric.metadata else 0
            
            by_type[error_type] = by_type.get(error_type, 0) + error_count
            by_endpoint[endpoint] = by_endpoint.get(endpoint, 0) + error_count
            total_errors += error_count
        
        # Calculate overall error rate
        total_requests = sum(
            metric.metadata.get("total_requests", 0) if metric.metadata else 0
            for metric in error_metrics
        )
        overall_error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0.0
        
        return {
            "total_errors": total_errors,
            "total_requests": total_requests,
            "error_rate": overall_error_rate,
            "by_type": by_type,
            "by_endpoint": by_endpoint,
            "time_range": {
                "start": start_time.isoformat(),
                "end": datetime.utcnow().isoformat()
            }
        }

    async def get_performance_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive performance data for dashboard."""
        now = datetime.utcnow()
        last_hour = now - timedelta(hours=1)
        last_24h = now - timedelta(hours=24)
        
        # Get recent metrics summaries
        query_summary = await self.get_metric_summary(
            "db_query_execution_time", start_time=last_hour
        )
        
        response_summary = await self.get_metric_summary(
            "api_response_time", start_time=last_hour
        )
        
        # Get slow queries and errors
        slow_queries = await self.get_slow_queries(hours=1)
        error_analysis = await self.get_error_analysis(hours=1)
        
        # Get connection metrics
        connection_metrics = await self.get_metrics(
            metric_name="connection_pool_utilization",
            start_time=last_hour
        )
        
        avg_connection_utilization = 0.0
        if connection_metrics:
            avg_connection_utilization = statistics.mean(m.value for m in connection_metrics)
        
        return {
            "timestamp": now.isoformat(),
            "query_performance": {
                "avg_time": query_summary.avg_value if query_summary else 0.0,
                "p95_time": query_summary.p95_value if query_summary else 0.0,
                "slow_queries_count": len(slow_queries),
                "total_queries": query_summary.count if query_summary else 0
            },
            "api_performance": {
                "avg_response_time": response_summary.avg_value if response_summary else 0.0,
                "p95_response_time": response_summary.p95_value if response_summary else 0.0,
                "total_requests": response_summary.count if response_summary else 0
            },
            "connection_health": {
                "avg_utilization": avg_connection_utilization,
                "status": "healthy" if avg_connection_utilization < 80 else "warning"
            },
            "error_metrics": error_analysis,
            "slow_queries": slow_queries[:5]  # Top 5 slow queries
        }

    async def _flush_loop(self) -> None:
        """Background task to flush metrics periodically."""
        while self._collecting:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._flush_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics flush loop: {e}")

    async def _flush_metrics(self) -> None:
        """Flush metrics buffer to storage."""
        if not self.metrics_buffer:
            return
            
        metrics_to_flush = self.metrics_buffer.copy()
        self.metrics_buffer.clear()
        
        if self.redis_client:
            await self._store_metrics_in_redis(metrics_to_flush)
        else:
            logger.debug(f"Flushed {len(metrics_to_flush)} metrics (Redis not available)")

    async def _store_metrics_in_redis(self, metrics: List[MetricPoint]) -> None:
        """Store metrics in Redis with time-series structure."""
        try:
            pipe = self.redis_client.pipeline()
            
            for metric in metrics:
                # Create time-series key
                timestamp_key = metric.timestamp.strftime("%Y%m%d%H")
                redis_key = f"{self.redis_prefix}{metric.metric_name}:{timestamp_key}"
                
                # Store metric data
                metric_data = metric.to_dict()
                pipe.lpush(redis_key, json.dumps(metric_data))
                
                # Set expiration (retention period)
                pipe.expire(redis_key, self.retention_days * 24 * 3600)
            
            await pipe.execute()
            logger.debug(f"Stored {len(metrics)} metrics in Redis")
            
        except Exception as e:
            logger.error(f"Failed to store metrics in Redis: {e}")

    async def _get_metrics_from_redis(self, 
                                    metric_name: Optional[str],
                                    metric_type: Optional[MetricType],
                                    start_time: Optional[datetime],
                                    end_time: Optional[datetime],
                                    labels: Optional[Dict[str, str]],
                                    limit: int) -> List[MetricPoint]:
        """Retrieve metrics from Redis."""
        try:
            if not metric_name:
                return []
                
            # Generate time range keys
            keys = self._generate_redis_keys(metric_name, start_time, end_time)
            
            metrics = []
            for key in keys:
                # Get metrics from this time bucket
                raw_metrics = await self.redis_client.lrange(key, 0, -1)
                
                for raw_metric in raw_metrics:
                    try:
                        metric_data = json.loads(raw_metric)
                        metric_point = MetricPoint.from_dict(metric_data)
                        metrics.append(metric_point)
                        
                        if len(metrics) >= limit:
                            break
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"Invalid metric data in Redis: {e}")
                        continue
                
                if len(metrics) >= limit:
                    break
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to retrieve metrics from Redis: {e}")
            return []

    def _generate_redis_keys(self, 
                           metric_name: str,
                           start_time: Optional[datetime],
                           end_time: Optional[datetime]) -> List[str]:
        """Generate Redis keys for time range."""
        if not start_time:
            start_time = datetime.utcnow() - timedelta(hours=24)
        if not end_time:
            end_time = datetime.utcnow()
            
        keys = []
        current_time = start_time.replace(minute=0, second=0, microsecond=0)
        
        while current_time <= end_time:
            timestamp_key = current_time.strftime("%Y%m%d%H")
            redis_key = f"{self.redis_prefix}{metric_name}:{timestamp_key}"
            keys.append(redis_key)
            current_time += timedelta(hours=1)
            
        return keys

    def _percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile value."""
        if not values:
            return 0.0
            
        sorted_values = sorted(values)
        index = (percentile / 100) * (len(sorted_values) - 1)
        
        if index.is_integer():
            return sorted_values[int(index)]
        else:
            lower_index = int(index)
            upper_index = lower_index + 1
            weight = index - lower_index
            
            if upper_index >= len(sorted_values):
                return sorted_values[lower_index]
                
            return (sorted_values[lower_index] * (1 - weight) + 
                   sorted_values[upper_index] * weight)

    async def cleanup_old_metrics(self) -> None:
        """Clean up old metrics beyond retention period."""
        if not self.redis_client:
            return
            
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=self.retention_days)
            
            # Find keys older than retention period
            pattern = f"{self.redis_prefix}*"
            keys = await self.redis_client.keys(pattern)
            
            deleted_count = 0
            for key in keys:
                # Extract timestamp from key
                try:
                    key_parts = key.decode().split(":")
                    if len(key_parts) >= 3:
                        timestamp_str = key_parts[-1]
                        key_time = datetime.strptime(timestamp_str, "%Y%m%d%H")
                        
                        if key_time < cutoff_time:
                            await self.redis_client.delete(key)
                            deleted_count += 1
                except (ValueError, IndexError):
                    continue
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old metric keys")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old metrics: {e}")

    def get_collection_status(self) -> Dict[str, Any]:
        """Get metrics collection status."""
        return {
            "collecting": self._collecting,
            "buffer_size": len(self.metrics_buffer),
            "max_buffer_size": self.buffer_size,
            "flush_interval": self.flush_interval,
            "retention_days": self.retention_days,
            "redis_available": self.redis_client is not None,
            "metric_types": [mt.value for mt in MetricType]
        }
