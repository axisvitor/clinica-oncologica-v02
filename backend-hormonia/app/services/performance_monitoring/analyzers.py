"""
Performance analysis and bottleneck detection methods.
Analyzes metrics to identify performance issues and trends.
"""

import logging
import statistics
from typing import Any, List
from datetime import datetime, timezone
from collections import defaultdict

from redis import Redis

from app.services.performance_monitoring.models import (
    MetricType,
    BottleneckType,
    PerformanceMetric,
    PerformanceBottleneck,
)

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """Analyzes performance metrics and detects bottlenecks."""

    def __init__(self, redis: Redis, thresholds: dict[str, float]):
        self.redis = redis
        self.thresholds = thresholds

    async def analyze_database_performance(
        self, metrics: List[PerformanceMetric]
    ) -> List[PerformanceBottleneck]:
        """Analyze database performance for bottlenecks."""
        bottlenecks = []

        try:
            # Check for slow queries
            db_metrics = [m for m in metrics if m.component == "database"]

            for metric in db_metrics:
                if metric.metric_type == MetricType.RESPONSE_TIME:
                    if metric.value > self.thresholds["response_time_critical"]:
                        bottlenecks.append(
                            PerformanceBottleneck(
                                bottleneck_type=BottleneckType.DATABASE_SLOW_QUERIES,
                                severity="critical",
                                description=f"Database response time is {metric.value:.2f}s, exceeding critical threshold",
                                affected_components=["database", "api"],
                                recommendations=[
                                    "Review and optimize slow queries",
                                    "Add database indexes for frequently queried columns",
                                    "Consider database connection pooling optimization",
                                    "Review database configuration parameters",
                                ],
                                detected_at=datetime.now(timezone.utc),
                                metrics=[metric],
                            )
                        )

            return bottlenecks

        except Exception as e:
            logger.error(f"Error analyzing database performance: {e}")
            return []

    async def analyze_memory_usage(
        self, metrics: List[PerformanceMetric]
    ) -> List[PerformanceBottleneck]:
        """Analyze memory usage for bottlenecks."""
        bottlenecks = []

        try:
            memory_metrics = [
                m for m in metrics if m.metric_type == MetricType.MEMORY_USAGE
            ]

            for metric in memory_metrics:
                if metric.value > self.thresholds["memory_usage_critical"]:
                    bottlenecks.append(
                        PerformanceBottleneck(
                            bottleneck_type=BottleneckType.HIGH_MEMORY_USAGE,
                            severity="critical",
                            description=f"Memory usage is {metric.value:.1%}, exceeding critical threshold",
                            affected_components=[metric.component],
                            recommendations=[
                                "Review memory-intensive operations",
                                "Implement memory cleanup routines",
                                "Consider increasing available memory",
                                "Optimize data structures and caching strategies",
                            ],
                            detected_at=datetime.now(timezone.utc),
                            metrics=[metric],
                        )
                    )

            return bottlenecks

        except Exception as e:
            logger.error(f"Error analyzing memory usage: {e}")
            return []

    async def analyze_queue_performance(
        self, metrics: List[PerformanceMetric]
    ) -> List[PerformanceBottleneck]:
        """Analyze queue performance for bottlenecks."""
        bottlenecks = []

        try:
            queue_metrics = [
                m for m in metrics if m.metric_type == MetricType.QUEUE_DEPTH
            ]

            for metric in queue_metrics:
                if metric.value > self.thresholds["queue_depth_critical"]:
                    bottlenecks.append(
                        PerformanceBottleneck(
                            bottleneck_type=BottleneckType.QUEUE_BACKLOG,
                            severity="critical",
                            description=f"Queue depth is {metric.value}, indicating processing backlog",
                            affected_components=["message_queue", "flow_processing"],
                            recommendations=[
                                "Increase worker processes",
                                "Optimize message processing logic",
                                "Review queue configuration",
                                "Consider horizontal scaling",
                            ],
                            detected_at=datetime.now(timezone.utc),
                            metrics=[metric],
                        )
                    )

            return bottlenecks

        except Exception as e:
            logger.error(f"Error analyzing queue performance: {e}")
            return []

    async def analyze_external_api_performance(self) -> List[PerformanceBottleneck]:
        """Analyze external API performance."""
        bottlenecks = []

        try:
            # Check external API response times from Redis
            api_response_times = await self.redis.lrange("external_api_times", 0, 99)  # type: ignore[misc]

            if api_response_times:
                times = [float(t) for t in api_response_times]
                avg_time = statistics.mean(times)

                if avg_time > 10.0:  # 10 seconds threshold
                    bottlenecks.append(
                        PerformanceBottleneck(
                            bottleneck_type=BottleneckType.EXTERNAL_API_LATENCY,
                            severity="high",
                            description=f"External API average response time is {avg_time:.2f}s",
                            affected_components=["external_apis", "flow_processing"],
                            recommendations=[
                                "Implement API response caching",
                                "Add timeout and retry logic",
                                "Consider API rate limiting",
                                "Monitor external service status",
                            ],
                            detected_at=datetime.now(timezone.utc),
                            metrics=[],
                        )
                    )

            return bottlenecks

        except Exception as e:
            logger.error(f"Error analyzing external API performance: {e}")
            return []

    async def analyze_redis_performance(
        self, metrics: List[PerformanceMetric]
    ) -> List[PerformanceBottleneck]:
        """Analyze Redis performance for bottlenecks."""
        bottlenecks = []

        try:
            redis_metrics = [m for m in metrics if m.component == "redis"]

            for metric in redis_metrics:
                if metric.metric_type == MetricType.MEMORY_USAGE and metric.value > 0.9:
                    bottlenecks.append(
                        PerformanceBottleneck(
                            bottleneck_type=BottleneckType.REDIS_MEMORY_PRESSURE,
                            severity="high",
                            description=f"Redis memory usage is {metric.value:.1%}",
                            affected_components=["redis", "caching"],
                            recommendations=[
                                "Review Redis memory configuration",
                                "Implement key expiration policies",
                                "Consider Redis clustering",
                                "Optimize data structures",
                            ],
                            detected_at=datetime.now(timezone.utc),
                            metrics=[metric],
                        )
                    )

            return bottlenecks

        except Exception as e:
            logger.error(f"Error analyzing Redis performance: {e}")
            return []

    async def analyze_concurrency_limits(
        self, metrics: List[PerformanceMetric]
    ) -> List[PerformanceBottleneck]:
        """Analyze concurrent processing limits."""
        bottlenecks = []

        try:
            # Check if we're hitting concurrency limits
            throughput_metrics = [
                m for m in metrics if m.metric_type == MetricType.THROUGHPUT
            ]

            for metric in throughput_metrics:
                if metric.value < self.thresholds["throughput_critical"]:
                    bottlenecks.append(
                        PerformanceBottleneck(
                            bottleneck_type=BottleneckType.CONCURRENT_PROCESSING_LIMIT,
                            severity="medium",
                            description=f"Throughput is {metric.value} messages/minute, below expected levels",
                            affected_components=["flow_processing"],
                            recommendations=[
                                "Increase concurrent worker processes",
                                "Optimize processing algorithms",
                                "Review resource allocation",
                                "Consider async processing patterns",
                            ],
                            detected_at=datetime.now(timezone.utc),
                            metrics=[metric],
                        )
                    )

            return bottlenecks

        except Exception as e:
            logger.error(f"Error analyzing concurrency limits: {e}")
            return []

    def calculate_performance_statistics(
        self, metrics: List[PerformanceMetric]
    ) -> dict[str, Any]:
        """Calculate performance statistics from metrics."""
        stats = {}

        try:
            # Group metrics by type
            metrics_by_type = defaultdict(list)
            for metric in metrics:
                metrics_by_type[metric.metric_type].append(metric.value)

            # Calculate statistics for each metric type
            for metric_type, values in metrics_by_type.items():
                if values:
                    stats[metric_type.value] = {
                        "mean": statistics.mean(values),
                        "median": statistics.median(values),
                        "min": min(values),
                        "max": max(values),
                        "std_dev": statistics.stdev(values) if len(values) > 1 else 0,
                        "count": len(values),
                    }

            return stats

        except Exception as e:
            logger.error(f"Error calculating performance statistics: {e}")
            return {}

    def calculate_performance_trends(
        self, metrics: List[PerformanceMetric]
    ) -> dict[str, Any]:
        """Calculate performance trends."""
        trends = {}

        try:
            # Group metrics by type and calculate trends
            metrics_by_type = defaultdict(list)
            for metric in metrics:
                metrics_by_type[metric.metric_type].append(
                    (metric.timestamp, metric.value)
                )

            for metric_type, time_values in metrics_by_type.items():
                if len(time_values) > 1:
                    # Sort by timestamp
                    time_values.sort(key=lambda x: x[0])

                    # Calculate trend (simple linear regression slope)
                    values = [v for _, v in time_values]
                    n = len(values)

                    if n > 1:
                        x_mean = (n - 1) / 2
                        y_mean = statistics.mean(values)

                        numerator = sum(
                            (i - x_mean) * (values[i] - y_mean) for i in range(n)
                        )
                        denominator = sum((i - x_mean) ** 2 for i in range(n))

                        slope = numerator / denominator if denominator != 0 else 0

                        trends[metric_type.value] = {
                            "slope": slope,
                            "direction": "increasing"
                            if slope > 0
                            else "decreasing"
                            if slope < 0
                            else "stable",
                            "recent_value": values[-1],
                            "previous_value": values[0],
                            "change_percent": (
                                (values[-1] - values[0]) / values[0] * 100
                            )
                            if values[0] != 0
                            else 0,
                        }

            return trends

        except Exception as e:
            logger.error(f"Error calculating performance trends: {e}")
            return {}

    def calculate_health_score(self, stats: dict[str, Any]) -> float:
        """Calculate overall system health score (0-100)."""
        try:
            score = 100.0

            # Deduct points based on performance metrics
            if "response_time" in stats:
                avg_response_time = stats["response_time"]["mean"]
                if avg_response_time > self.thresholds["response_time_critical"]:
                    score -= 30
                elif avg_response_time > self.thresholds["response_time_warning"]:
                    score -= 15

            if "error_rate" in stats:
                error_rate = stats["error_rate"]["mean"]
                if error_rate > self.thresholds["error_rate_critical"]:
                    score -= 25
                elif error_rate > self.thresholds["error_rate_warning"]:
                    score -= 10

            if "memory_usage" in stats:
                memory_usage = stats["memory_usage"]["mean"]
                if memory_usage > self.thresholds["memory_usage_critical"]:
                    score -= 20
                elif memory_usage > self.thresholds["memory_usage_warning"]:
                    score -= 10

            return max(0.0, score)

        except Exception as e:
            logger.error(f"Error calculating health score: {e}")
            return 50.0  # Default moderate score

    def generate_performance_recommendations(
        self, stats: dict[str, Any], bottlenecks: List[PerformanceBottleneck]
    ) -> List[str]:
        """Generate performance optimization recommendations."""
        recommendations = []

        try:
            # General recommendations based on statistics
            if "response_time" in stats:
                avg_response_time = stats["response_time"]["mean"]
                if avg_response_time > self.thresholds["response_time_warning"]:
                    recommendations.append(
                        "Consider implementing response caching to reduce average response times"
                    )

            if "error_rate" in stats:
                error_rate = stats["error_rate"]["mean"]
                if error_rate > self.thresholds["error_rate_warning"]:
                    recommendations.append(
                        "Implement better error handling and retry mechanisms"
                    )

            # Recommendations from bottlenecks
            for bottleneck in bottlenecks:
                recommendations.extend(bottleneck.recommendations)

            # Remove duplicates
            recommendations = list(set(recommendations))

            return recommendations

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return []

    def get_metric_status(self, metric: PerformanceMetric) -> str:
        """Get status of a metric based on thresholds."""
        try:
            if metric.metric_type == MetricType.RESPONSE_TIME:
                if metric.value > self.thresholds["response_time_critical"]:
                    return "critical"
                elif metric.value > self.thresholds["response_time_warning"]:
                    return "warning"
            elif metric.metric_type == MetricType.ERROR_RATE:
                if metric.value > self.thresholds["error_rate_critical"]:
                    return "critical"
                elif metric.value > self.thresholds["error_rate_warning"]:
                    return "warning"
            elif metric.metric_type == MetricType.MEMORY_USAGE:
                if metric.value > self.thresholds["memory_usage_critical"]:
                    return "critical"
                elif metric.value > self.thresholds["memory_usage_warning"]:
                    return "warning"

            return "healthy"

        except Exception:
            return "unknown"
