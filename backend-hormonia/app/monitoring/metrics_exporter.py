"""
Metrics Exporter for Grafana and Prometheus Integration.

Exports metrics in Prometheus format and provides Grafana-compatible API.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Generator
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
import redis.asyncio as redis
from prometheus_client import CollectorRegistry, Gauge, Counter, Histogram, generate_latest


logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """A single metric data point."""
    timestamp: datetime
    value: float
    labels: Dict[str, str]


class PrometheusExporter:
    """
    Prometheus metrics exporter.

    IMPORTANT: All histogram and counter metrics MUST be called with their required labels
    to prevent "histogram metric is missing label values" errors. This class provides
    safe methods to ensure all metrics are properly labeled, especially for global
    aggregation statistics.

    Default Labels:
    - HTTP metrics: method='ALL', endpoint='ALL' for global stats
    - Database metrics: operation='ALL', table='ALL' for global stats
    - Component health: component=<component_name>
    """

    def __init__(self):
        self.registry = CollectorRegistry()
        self._setup_metrics()

    def _setup_metrics(self) -> None:
        """Setup Prometheus metrics."""
        # APM Metrics
        self.http_requests_total = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status'],
            registry=self.registry
        )

        self.http_request_duration = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration',
            ['method', 'endpoint'],
            registry=self.registry
        )

        self.http_errors_total = Counter(
            'http_errors_total',
            'Total HTTP errors',
            ['method', 'endpoint', 'error_type'],
            registry=self.registry
        )

        # Database Metrics
        self.db_queries_total = Counter(
            'db_queries_total',
            'Total database queries',
            ['operation', 'table'],
            registry=self.registry
        )

        self.db_query_duration = Histogram(
            'db_query_duration_seconds',
            'Database query duration',
            ['operation', 'table'],
            registry=self.registry
        )

        self.db_connections_active = Gauge(
            'db_connections_active',
            'Active database connections',
            registry=self.registry
        )

        self.db_connections_pool_size = Gauge(
            'db_connections_pool_size',
            'Database connection pool size',
            registry=self.registry
        )

        # Resource Metrics
        self.cpu_usage_percent = Gauge(
            'cpu_usage_percent',
            'CPU usage percentage',
            registry=self.registry
        )

        self.memory_usage_percent = Gauge(
            'memory_usage_percent',
            'Memory usage percentage',
            registry=self.registry
        )

        self.memory_usage_bytes = Gauge(
            'memory_usage_bytes',
            'Memory usage in bytes',
            registry=self.registry
        )

        self.disk_io_bytes = Counter(
            'disk_io_bytes_total',
            'Total disk I/O bytes',
            ['direction'],  # read/write
            registry=self.registry
        )

        self.network_io_bytes = Counter(
            'network_io_bytes_total',
            'Total network I/O bytes',
            ['direction'],  # sent/received
            registry=self.registry
        )

        # Business Metrics
        self.patient_flows_total = Counter(
            'patient_flows_total',
            'Total patient flows',
            ['flow_type', 'status'],
            registry=self.registry
        )

        self.messages_total = Counter(
            'messages_total',
            'Total messages',
            ['type', 'status'],
            registry=self.registry
        )

        self.ai_responses_total = Counter(
            'ai_responses_total',
            'Total AI responses',
            ['response_type'],
            registry=self.registry
        )

        self.ai_accuracy_score = Gauge(
            'ai_accuracy_score',
            'AI response accuracy score',
            ['response_type'],
            registry=self.registry
        )

        # System Health
        self.system_health_score = Gauge(
            'system_health_score',
            'Overall system health score',
            registry=self.registry
        )

        self.component_health = Gauge(
            'component_health',
            'Component health status (1=healthy, 0=unhealthy)',
            ['component'],
            registry=self.registry
        )

    def update_apm_metrics(self, apm_stats: Dict[str, Any]) -> None:
        """Update APM metrics."""
        try:
            # Global stats - always use default labels for aggregated metrics
            avg_response_time = apm_stats.get('avg_response_time', 0) / 1000  # Convert to seconds

            # Use safe histogram observe with default labels
            self._safe_histogram_observe(
                self.http_request_duration,
                avg_response_time,
                {'method': 'ALL', 'endpoint': 'ALL'}
            )

            # Update HTTP request counters with default labels for global stats
            total_requests = apm_stats.get('total_requests', 0)
            if total_requests > 0:
                # Use increment based on current vs previous total (simplified approach)
                for status_code, count in apm_stats.get('status_codes', {}).items():
                    self._safe_counter_increment(
                        self.http_requests_total,
                        count,
                        {
                            'method': 'ALL',
                            'endpoint': 'ALL',
                            'status': str(status_code)
                        }
                    )

            # Update error metrics if error rate is available
            error_rate = apm_stats.get('error_rate', 0)
            if error_rate > 0:
                # Update error counter with default labels
                error_count = int(total_requests * error_rate / 100)
                self._safe_counter_increment(
                    self.http_errors_total,
                    error_count,
                    {
                        'method': 'ALL',
                        'endpoint': 'ALL',
                        'error_type': 'application_error'
                    }
                )

        except Exception as e:
            logger.error(f"Failed to update APM metrics: {e}")

    def update_database_metrics(self, db_stats: Dict[str, Any]) -> None:
        """Update database metrics."""
        try:
            pool_stats = db_stats.get('connection_pool', {})

            self.db_connections_active.set(pool_stats.get('checked_out', 0))
            self.db_connections_pool_size.set(pool_stats.get('pool_size', 0))

            # Update database query metrics with default labels for global stats
            query_stats = db_stats.get('query_stats', {})
            avg_query_time = query_stats.get('avg_query_time', 0)

            # Use safe histogram observe for database query duration
            self._safe_histogram_observe(
                self.db_query_duration,
                avg_query_time / 1000,  # Convert to seconds
                {'operation': 'ALL', 'table': 'ALL'}
            )

            # Update database query counters with default labels
            total_queries = query_stats.get('total_queries', 0)
            if total_queries > 0:
                for operation, count in query_stats.get('operations', {}).items():
                    self._safe_counter_increment(
                        self.db_queries_total,
                        count,
                        {
                            'operation': operation,
                            'table': 'ALL'
                        }
                    )

        except Exception as e:
            logger.error(f"Failed to update database metrics: {e}")

    def update_resource_metrics(self, resource_stats: Dict[str, Any]) -> None:
        """Update resource metrics."""
        try:
            cpu_stats = resource_stats.get('cpu', {})
            memory_stats = resource_stats.get('memory', {})

            self.cpu_usage_percent.set(cpu_stats.get('percent', 0))
            self.memory_usage_percent.set(memory_stats.get('percent', 0))
            self.memory_usage_bytes.set(memory_stats.get('used_gb', 0) * 1024**3)

        except Exception as e:
            logger.error(f"Failed to update resource metrics: {e}")

    def update_business_metrics(self, business_stats: Dict[str, Any]) -> None:
        """Update business metrics."""
        try:
            metrics = business_stats.get('metrics', {})

            # Update patient flow metrics
            flow_metrics = metrics.get('patient_flow', {})
            if flow_metrics:
                # These would need to be updated incrementally
                pass

            # Update message metrics
            message_metrics = metrics.get('message_delivery', {})
            if message_metrics:
                # These would need to be updated incrementally
                pass

        except Exception as e:
            logger.error(f"Failed to update business metrics: {e}")

    def update_system_health(self, health_stats: Dict[str, Any]) -> None:
        """Update system health metrics."""
        try:
            self.system_health_score.set(health_stats.get('score', 0))

            components = health_stats.get('components', {})
            for component, status in components.items():
                health_value = 1 if status == 'healthy' else 0
                self.component_health.labels(component=component).set(health_value)

        except Exception as e:
            logger.error(f"Failed to update system health metrics: {e}")

    def _safe_histogram_observe(self, histogram, value: float, default_labels: Dict[str, str]) -> None:
        """
        Safely observe a histogram value with default labels.

        This prevents "histogram metric is missing label values" errors by ensuring
        all histograms are called with the required labels.

        Args:
            histogram: The Prometheus histogram metric
            value: The value to observe
            default_labels: Dictionary of default label values
        """
        try:
            if value > 0:
                histogram.labels(**default_labels).observe(value)
        except Exception as e:
            logger.error(f"Failed to observe histogram metric: {e}")

    def _safe_counter_increment(self, counter, increment: int, default_labels: Dict[str, str]) -> None:
        """
        Safely increment a counter with default labels.

        Args:
            counter: The Prometheus counter metric
            increment: The amount to increment by
            default_labels: Dictionary of default label values
        """
        try:
            if increment > 0:
                # Use internal counter increment to avoid creating multiple metrics
                counter.labels(**default_labels)._value._value += increment
        except Exception as e:
            logger.error(f"Failed to increment counter metric: {e}")

    def get_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        return generate_latest(self.registry).decode('utf-8')


class GrafanaExporter:
    """Grafana-compatible metrics exporter."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client

    async def query_metrics(self, target: str, from_time: datetime,
                          to_time: datetime, max_data_points: int = 1000) -> List[Dict[str, Any]]:
        """Query metrics for Grafana."""
        try:
            # Parse target to determine metric type
            metric_type, metric_name = self._parse_target(target)

            # Get data from Redis or in-memory storage
            data_points = await self._get_metric_data(
                metric_type, metric_name, from_time, to_time, max_data_points
            )

            return [{
                "target": target,
                "datapoints": data_points
            }]

        except Exception as e:
            logger.error(f"Failed to query metrics for Grafana: {e}")
            return []

    def _parse_target(self, target: str) -> tuple[str, str]:
        """Parse Grafana target string."""
        # Example targets:
        # apm.response_time.p95
        # database.query_time.avg
        # resources.cpu.percent
        # business.patient_flow.completion_rate

        parts = target.split('.')
        if len(parts) >= 2:
            return parts[0], '.'.join(parts[1:])
        else:
            return "unknown", target

    async def _get_metric_data(self, metric_type: str, metric_name: str,
                             from_time: datetime, to_time: datetime,
                             max_data_points: int) -> List[List[float]]:
        """Get metric data points."""
        if not self.redis_client:
            return []

        try:
            # Calculate time interval
            time_range = to_time - from_time
            interval = time_range / max_data_points

            data_points = []
            current_time = from_time

            while current_time <= to_time:
                timestamp_ms = int(current_time.timestamp() * 1000)

                # Get value for this timestamp
                value = await self._get_metric_value(metric_type, metric_name, current_time)

                if value is not None:
                    data_points.append([value, timestamp_ms])

                current_time += interval

            return data_points

        except Exception as e:
            logger.error(f"Failed to get metric data: {e}")
            return []

    async def _get_metric_value(self, metric_type: str, metric_name: str,
                              timestamp: datetime) -> Optional[float]:
        """Get metric value for a specific timestamp."""
        try:
            if metric_type == "apm":
                return await self._get_apm_metric(metric_name, timestamp)
            elif metric_type == "database":
                return await self._get_database_metric(metric_name, timestamp)
            elif metric_type == "resources":
                return await self._get_resource_metric(metric_name, timestamp)
            elif metric_type == "business":
                return await self._get_business_metric(metric_name, timestamp)
            else:
                return None

        except Exception as e:
            logger.error(f"Failed to get metric value: {e}")
            return None

    async def _get_apm_metric(self, metric_name: str, timestamp: datetime) -> Optional[float]:
        """Get APM metric value."""
        # This would fetch from Redis APM data
        # For now, return dummy data
        return 100.0  # Placeholder

    async def _get_database_metric(self, metric_name: str, timestamp: datetime) -> Optional[float]:
        """Get database metric value."""
        # This would fetch from Redis database data
        return 50.0  # Placeholder

    async def _get_resource_metric(self, metric_name: str, timestamp: datetime) -> Optional[float]:
        """Get resource metric value."""
        # This would fetch from Redis resource data
        return 75.0  # Placeholder

    async def _get_business_metric(self, metric_name: str, timestamp: datetime) -> Optional[float]:
        """Get business metric value."""
        # This would fetch from Redis business data
        return 85.0  # Placeholder


class MetricsExporter:
    """Main metrics exporter for external monitoring systems."""

    def __init__(self, apm_collector, db_monitor, resource_monitor,
                 business_metrics, redis_client: Optional[redis.Redis] = None):
        self.apm_collector = apm_collector
        self.db_monitor = db_monitor
        self.resource_monitor = resource_monitor
        self.business_metrics = business_metrics
        self.redis_client = redis_client

        self.prometheus_exporter = PrometheusExporter()
        self.grafana_exporter = GrafanaExporter(redis_client)

        # Export configuration
        self.export_interval = 30.0  # 30 seconds
        self.export_active = False
        self.export_task: Optional[asyncio.Task] = None

    async def start_export(self) -> None:
        """Start periodic metrics export."""
        if self.export_active:
            return

        self.export_active = True
        self.export_task = asyncio.create_task(self._export_loop())
        logger.info("Metrics export started")

    async def stop_export(self) -> None:
        """Stop metrics export."""
        self.export_active = False

        if self.export_task:
            self.export_task.cancel()
            try:
                await self.export_task
            except asyncio.CancelledError:
                pass
            self.export_task = None

        logger.info("Metrics export stopped")

    async def _export_loop(self) -> None:
        """Main export loop."""
        while self.export_active:
            try:
                await self._update_prometheus_metrics()
                await asyncio.sleep(self.export_interval)

            except Exception as e:
                logger.error(f"Error in metrics export loop: {e}")
                await asyncio.sleep(self.export_interval)

    async def _update_prometheus_metrics(self) -> None:
        """Update Prometheus metrics."""
        try:
            # Get current stats from all collectors
            apm_stats = self.apm_collector.get_global_stats()
            db_stats = self.db_monitor.get_query_stats()
            db_pool_stats = self.db_monitor.get_connection_pool_stats()
            db_stats.update({"connection_pool": db_pool_stats})
            resource_stats = self.resource_monitor.get_current_stats()
            business_stats = self.business_metrics.get_all_metrics_summary(time_range_hours=1)

            # Calculate system health
            system_health = self._calculate_system_health(
                apm_stats, db_stats, resource_stats, business_stats
            )

            # Update Prometheus metrics
            self.prometheus_exporter.update_apm_metrics(apm_stats)
            self.prometheus_exporter.update_database_metrics(db_stats)
            self.prometheus_exporter.update_resource_metrics(resource_stats)
            self.prometheus_exporter.update_business_metrics(business_stats)
            self.prometheus_exporter.update_system_health(system_health)

        except Exception as e:
            logger.error(f"Failed to update Prometheus metrics: {e}")

    def _calculate_system_health(self, apm_stats: Dict[str, Any],
                               db_stats: Dict[str, Any],
                               resource_stats: Dict[str, Any],
                               business_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate system health metrics."""
        health_score = 100
        components = {}

        # APM health
        if apm_stats.get("error_rate", 0) > 5:
            health_score -= 15
            components["api"] = "unhealthy"
        else:
            components["api"] = "healthy"

        # Database health
        if not db_stats.get("connection_pool", {}).get("is_healthy", True):
            health_score -= 20
            components["database"] = "unhealthy"
        else:
            components["database"] = "healthy"

        # Resource health
        cpu_percent = resource_stats.get("cpu", {}).get("percent", 0)
        memory_percent = resource_stats.get("memory", {}).get("percent", 0)

        if cpu_percent > 80 or memory_percent > 85:
            health_score -= 15
            components["resources"] = "unhealthy"
        else:
            components["resources"] = "healthy"

        # Business health
        message_metrics = business_stats.get("metrics", {}).get("message_delivery", {})
        if message_metrics.get("failure_rate", 0) > 10:
            health_score -= 10
            components["business"] = "unhealthy"
        else:
            components["business"] = "healthy"

        return {
            "score": max(0, health_score),
            "components": components
        }

    def get_prometheus_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        return self.prometheus_exporter.get_metrics()

    async def query_grafana_metrics(self, targets: List[str], from_time: datetime,
                                  to_time: datetime, max_data_points: int = 1000) -> List[Dict[str, Any]]:
        """Query metrics for Grafana."""
        results = []

        for target in targets:
            target_results = await self.grafana_exporter.query_metrics(
                target, from_time, to_time, max_data_points
            )
            results.extend(target_results)

        return results

    def get_export_status(self) -> Dict[str, Any]:
        """Get export status information."""
        return {
            "export_active": self.export_active,
            "export_interval_seconds": self.export_interval,
            "prometheus_metrics_count": len(self.prometheus_exporter.registry._collector_to_names),
            "grafana_compatibility": True
        }