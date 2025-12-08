"""
Main performance monitoring service.
Composes collectors, analyzers, and reporters for comprehensive monitoring.
"""
import logging
from typing import Any, List
from datetime import timedelta

from redis import Redis

from app.repositories.flow import FlowStateRepository
from app.services.performance_monitoring.models import (
    MetricType,
    PerformanceMetric,
    PerformanceBottleneck
)
from app.services.performance_monitoring.collectors import MetricCollector
from app.services.performance_monitoring.analyzers import PerformanceAnalyzer
from app.services.performance_monitoring.reporters import PerformanceReporter

logger = logging.getLogger(__name__)


class PerformanceMonitoringService:
    """Service for monitoring system performance and detecting bottlenecks."""

    def __init__(self, db: Any, redis: Redis, flow_repository: FlowStateRepository):
        self.db = db
        self.redis = redis
        self.flow_repository = flow_repository

        # Performance thresholds
        self.thresholds = {
            'response_time_warning': 2.0,  # seconds
            'response_time_critical': 5.0,  # seconds
            'throughput_warning': 10,  # messages per minute
            'throughput_critical': 5,  # messages per minute
            'error_rate_warning': 0.05,  # 5%
            'error_rate_critical': 0.15,  # 15%
            'queue_depth_warning': 50,
            'queue_depth_critical': 200,
            'memory_usage_warning': 0.8,  # 80%
            'memory_usage_critical': 0.95,  # 95%
            'cache_hit_rate_warning': 0.7,  # 70%
            'cache_hit_rate_critical': 0.5,  # 50%
            'db_connections_warning': 80,
            'db_connections_critical': 95
        }

        # Metric collection intervals (in seconds)
        self.collection_intervals = {
            MetricType.RESPONSE_TIME: 30,
            MetricType.THROUGHPUT: 60,
            MetricType.ERROR_RATE: 60,
            MetricType.QUEUE_DEPTH: 30,
            MetricType.MEMORY_USAGE: 60,
            MetricType.CACHE_HIT_RATE: 120,
            MetricType.DATABASE_CONNECTIONS: 60
        }

        # Initialize components
        self.collector = MetricCollector(db, redis)
        self.analyzer = PerformanceAnalyzer(redis, self.thresholds)
        self.reporter = PerformanceReporter(self.collector, self.analyzer)

    async def collect_performance_metrics(self) -> List[PerformanceMetric]:
        """Collect current performance metrics."""
        metrics = []

        try:
            # Response time metrics
            response_time_metrics = await self.collector.collect_response_time_metrics()
            metrics.extend(response_time_metrics)

            # Throughput metrics
            throughput_metrics = await self.collector.collect_throughput_metrics()
            metrics.extend(throughput_metrics)

            # Error rate metrics
            error_rate_metrics = await self.collector.collect_error_rate_metrics()
            metrics.extend(error_rate_metrics)

            # Queue depth metrics
            queue_depth_metrics = await self.collector.collect_queue_depth_metrics()
            metrics.extend(queue_depth_metrics)

            # Memory usage metrics
            memory_metrics = await self.collector.collect_memory_usage_metrics()
            metrics.extend(memory_metrics)

            # Cache hit rate metrics
            cache_metrics = await self.collector.collect_cache_hit_rate_metrics()
            metrics.extend(cache_metrics)

            # Database connection metrics
            db_metrics = await self.collector.collect_database_connection_metrics()
            metrics.extend(db_metrics)

            # Store metrics in Redis for trend analysis
            await self.collector.store_metrics(metrics)

            return metrics

        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")
            return []

    async def detect_bottlenecks(self) -> List[PerformanceBottleneck]:
        """Detect performance bottlenecks based on current metrics."""
        bottlenecks = []

        try:
            # Get recent metrics
            metrics = await self.collect_performance_metrics()

            # Analyze database performance
            db_bottlenecks = await self.analyzer.analyze_database_performance(metrics)
            bottlenecks.extend(db_bottlenecks)

            # Analyze memory usage
            memory_bottlenecks = await self.analyzer.analyze_memory_usage(metrics)
            bottlenecks.extend(memory_bottlenecks)

            # Analyze queue performance
            queue_bottlenecks = await self.analyzer.analyze_queue_performance(metrics)
            bottlenecks.extend(queue_bottlenecks)

            # Analyze external API performance
            api_bottlenecks = await self.analyzer.analyze_external_api_performance()
            bottlenecks.extend(api_bottlenecks)

            # Analyze Redis performance
            redis_bottlenecks = await self.analyzer.analyze_redis_performance(metrics)
            bottlenecks.extend(redis_bottlenecks)

            # Analyze concurrent processing limits
            concurrency_bottlenecks = await self.analyzer.analyze_concurrency_limits(metrics)
            bottlenecks.extend(concurrency_bottlenecks)

            return bottlenecks

        except Exception as e:
            logger.error(f"Error detecting bottlenecks: {e}")
            return []

    async def get_performance_report(self, time_range: timedelta) -> dict[str, Any]:
        """Generate comprehensive performance report."""
        try:
            bottlenecks = await self.detect_bottlenecks()
            return await self.reporter.generate_performance_report(time_range, bottlenecks)
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return {'error': str(e)}

    async def get_real_time_performance_dashboard(self) -> dict[str, Any]:
        """Get real-time performance dashboard data."""
        try:
            # Get current metrics
            current_metrics = await self.collect_performance_metrics()

            # Get active bottlenecks
            active_bottlenecks = await self.detect_bottlenecks()

            return await self.reporter.generate_real_time_dashboard(current_metrics, active_bottlenecks)

        except Exception as e:
            logger.error(f"Error getting performance dashboard: {e}")
            return {'error': str(e)}
