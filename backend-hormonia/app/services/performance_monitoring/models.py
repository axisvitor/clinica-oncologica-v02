"""
Data models for performance monitoring.
Defines enums and dataclasses for metrics and bottlenecks.
"""

from typing import Any, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass


class MetricType(Enum):
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    QUEUE_DEPTH = "queue_depth"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    DATABASE_CONNECTIONS = "database_connections"
    CACHE_HIT_RATE = "cache_hit_rate"


class BottleneckType(Enum):
    DATABASE_SLOW_QUERIES = "database_slow_queries"
    HIGH_MEMORY_USAGE = "high_memory_usage"
    QUEUE_BACKLOG = "queue_backlog"
    EXTERNAL_API_LATENCY = "external_api_latency"
    REDIS_MEMORY_PRESSURE = "redis_memory_pressure"
    CONCURRENT_PROCESSING_LIMIT = "concurrent_processing_limit"


@dataclass
class PerformanceMetric:
    """Performance metric data point."""

    metric_type: MetricType
    value: float
    component: str
    timestamp: datetime
    metadata: dict[str, Any]


@dataclass
class PerformanceBottleneck:
    """Detected performance bottleneck."""

    bottleneck_type: BottleneckType
    severity: str  # low, medium, high, critical
    description: str
    affected_components: List[str]
    recommendations: List[str]
    detected_at: datetime
    metrics: List[PerformanceMetric]
