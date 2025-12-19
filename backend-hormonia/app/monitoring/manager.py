"""
Monitoring System Manager.

Central manager for all monitoring components with lifecycle management.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.engine import Engine

from app.core.redis_unified import get_async_redis
from .config import MonitoringConfig, get_monitoring_config
from .apm import APMCollector
from .database_monitor import DatabasePerformanceMonitor
from .resource_monitor import ResourceMonitor
from .business_metrics import BusinessMetricsCollector
from .dashboard import RealTimeDashboard
from .anomaly_detector import AnomalyDetector
from .metrics_exporter import MetricsExporter
from .middleware import MonitoringMiddleware


logger = logging.getLogger(__name__)


class MonitoringManager:
    """Central manager for the monitoring system."""

    def __init__(self, config: Optional[MonitoringConfig] = None):
        self.config = config or get_monitoring_config()
        self.redis_client = None

        # Monitoring components
        self.apm_collector: Optional[APMCollector] = None
        self.db_monitor: Optional[DatabasePerformanceMonitor] = None
        self.resource_monitor: Optional[ResourceMonitor] = None
        self.business_metrics: Optional[BusinessMetricsCollector] = None
        self.dashboard: Optional[RealTimeDashboard] = None
        self.anomaly_detector: Optional[AnomalyDetector] = None
        self.metrics_exporter: Optional[MetricsExporter] = None
        self.middleware: Optional[MonitoringMiddleware] = None

        # State
        self._initialized = False
        self._started = False

    async def initialize(self) -> None:
        """Initialize all monitoring components."""
        if self._initialized:
            return

        if not self.config.enabled:
            logger.info("Monitoring system disabled by configuration")
            return

        logger.info("Initializing monitoring system...")

        try:
            # Initialize Redis connection if enabled
            if self.config.redis.enabled:
                await self._initialize_redis()

            # Initialize monitoring components
            await self._initialize_components()

            # Setup anomaly detection with metrics integration
            await self._setup_anomaly_integration()

            self._initialized = True
            logger.info("Monitoring system initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize monitoring system: {e}")
            raise

    async def _initialize_redis(self) -> None:
        """Initialize Redis connection with proper fallback handling."""
        try:
            logger.info(
                "Attempting to connect to Redis for monitoring via unified client"
            )

            # Use unified Redis client
            self.redis_client = await get_async_redis()

            # Test connection
            await self.redis_client.ping()
            logger.info("Redis connection established for monitoring")

        except Exception as e:
            logger.error(f"Redis connection failed for monitoring: {e}")
            self.redis_client = None
            logger.warning(
                "Continuing without Redis - some monitoring features will be limited"
            )
            if self.config.debug:
                raise

    async def _initialize_components(self) -> None:
        """Initialize monitoring components."""
        # APM Collector
        if self.config.apm.enabled:
            self.apm_collector = APMCollector(self.redis_client)
            logger.info("APM collector initialized")

        # Database Monitor
        if self.config.database.enabled:
            self.db_monitor = DatabasePerformanceMonitor(self.redis_client)
            logger.info("Database monitor initialized")

        # Resource Monitor
        if self.config.resources.enabled:
            self.resource_monitor = ResourceMonitor(
                self.redis_client, self.config.resources.sample_interval
            )
            logger.info("Resource monitor initialized")

        # Business Metrics Collector
        if self.config.business_metrics.enabled:
            self.business_metrics = BusinessMetricsCollector(self.redis_client)
            logger.info("Business metrics collector initialized")

        # Real-time Dashboard
        if self.config.dashboard.enabled and all(
            [
                self.apm_collector,
                self.db_monitor,
                self.resource_monitor,
                self.business_metrics,
            ]
        ):
            self.dashboard = RealTimeDashboard(
                self.apm_collector,
                self.db_monitor,
                self.resource_monitor,
                self.business_metrics,
                self.redis_client,
            )
            self.dashboard.update_interval = self.config.dashboard.update_interval
            logger.info("Real-time dashboard initialized")

        # Anomaly Detector
        if self.config.anomaly_detection.enabled:
            self.anomaly_detector = AnomalyDetector(self.redis_client)
            logger.info("Anomaly detector initialized")

        # Metrics Exporter
        if self.config.export.enabled and all(
            [
                self.apm_collector,
                self.db_monitor,
                self.resource_monitor,
                self.business_metrics,
            ]
        ):
            self.metrics_exporter = MetricsExporter(
                self.apm_collector,
                self.db_monitor,
                self.resource_monitor,
                self.business_metrics,
                self.redis_client,
            )
            self.metrics_exporter.export_interval = self.config.export.export_interval
            logger.info("Metrics exporter initialized")

        # Monitoring Middleware
        if all([self.apm_collector, self.db_monitor, self.business_metrics]):
            self.middleware = MonitoringMiddleware(
                None,  # App will be set later
                self.apm_collector,
                self.db_monitor,
                self.business_metrics,
            )
            logger.info("Monitoring middleware initialized")

    async def _setup_anomaly_integration(self) -> None:
        """Setup integration between anomaly detector and metrics collectors."""
        if not self.anomaly_detector:
            return

        # Configure anomaly detection for different metrics
        metric_configs = self.config.anomaly_detection.metric_configs

        for metric_name, config in metric_configs.items():
            self.anomaly_detector.update_metric_config(metric_name, config)

        logger.info("Anomaly detection integration configured")

    async def start(self) -> None:
        """Start all monitoring services."""
        if not self._initialized:
            await self.initialize()

        if self._started or not self.config.enabled:
            return

        logger.info("Starting monitoring services...")

        try:
            # Start resource monitoring
            if self.resource_monitor:
                await self.resource_monitor.start_monitoring()

            # Start dashboard streaming
            if self.dashboard:
                await self.dashboard.start_streaming()

            # Start metrics export
            if self.metrics_exporter:
                await self.metrics_exporter.start_export()

            self._started = True
            logger.info("Monitoring services started successfully")

        except Exception as e:
            logger.error(f"Failed to start monitoring services: {e}")
            raise

    async def stop(self) -> None:
        """Stop all monitoring services."""
        if not self._started:
            return

        logger.info("Stopping monitoring services...")

        try:
            # Stop metrics export
            if self.metrics_exporter:
                await self.metrics_exporter.stop_export()

            # Stop dashboard streaming
            if self.dashboard:
                await self.dashboard.stop_streaming()

            # Stop resource monitoring
            if self.resource_monitor:
                await self.resource_monitor.stop_monitoring()

            # Close Redis connection
            if self.redis_client:
                try:
                    # Use aclose() for proper async cleanup (redis 5.x)
                    await self.redis_client.aclose()
                except Exception as redis_close_error:
                    logger.error(
                        f"Error closing monitoring Redis connection: {redis_close_error}"
                    )

            self._started = False
            logger.info("Monitoring services stopped successfully")

        except Exception as e:
            logger.error(f"Error stopping monitoring services: {e}")

    def setup_database_monitoring(self, engine: Engine) -> None:
        """Setup database monitoring for SQLAlchemy engine."""
        if self.db_monitor and self.config.database.enabled:
            self.db_monitor.setup_sqlalchemy_monitoring(engine)
            logger.info("Database monitoring setup completed")

    def get_middleware(self, app):
        """Get monitoring middleware for FastAPI app."""
        if self.middleware:
            self.middleware.app = app
            return self.middleware
        return None

    async def process_metric_for_anomalies(
        self, metric_name: str, value: float, timestamp: Optional[datetime] = None
    ) -> None:
        """Process a metric value through anomaly detection."""
        if self.anomaly_detector and self.config.anomaly_detection.enabled:
            await self.anomaly_detector.process_metric(metric_name, value, timestamp)

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall monitoring system health status."""
        status = {
            "initialized": self._initialized,
            "started": self._started,
            "enabled": self.config.enabled,
            "components": {},
            "redis_connected": self.redis_client is not None,
        }

        # Check component status
        components = [
            ("apm", self.apm_collector),
            ("database", self.db_monitor),
            ("resources", self.resource_monitor),
            ("business_metrics", self.business_metrics),
            ("dashboard", self.dashboard),
            ("anomaly_detector", self.anomaly_detector),
            ("metrics_exporter", self.metrics_exporter),
        ]

        for name, component in components:
            # Get component config
            component_config = (
                getattr(self.config, name, None) if hasattr(self.config, name) else None
            )
            is_enabled = (
                getattr(component_config, "enabled", False)
                if component_config
                else False
            )

            status["components"][name] = {
                "initialized": component is not None,
                "enabled": is_enabled,
            }

        return status

    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics from all collectors."""
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "system_health": self.get_health_status(),
        }

        try:
            # APM metrics
            if self.apm_collector:
                metrics["apm"] = self.apm_collector.get_global_stats()

            # Database metrics
            if self.db_monitor:
                metrics["database"] = {
                    "query_stats": self.db_monitor.get_query_stats(),
                    "connection_pool": self.db_monitor.get_connection_pool_stats(),
                    "slow_queries": self.db_monitor.get_slow_queries(5),
                }

            # Resource metrics
            if self.resource_monitor:
                metrics["resources"] = {
                    "current": self.resource_monitor.get_current_stats(),
                    "historical": self.resource_monitor.get_historical_stats(60),
                }

            # Business metrics
            if self.business_metrics:
                metrics["business"] = self.business_metrics.get_all_metrics_summary(24)

            # Anomalies
            if self.anomaly_detector:
                metrics["anomalies"] = {
                    "recent": self.anomaly_detector.get_recent_anomalies(24),
                    "summary": self.anomaly_detector.get_anomaly_summary(24),
                }

        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            metrics["error"] = str(e)

        return metrics

    async def reset_all_stats(self) -> None:
        """Reset all monitoring statistics."""
        logger.info("Resetting all monitoring statistics...")

        if self.apm_collector:
            self.apm_collector.reset_stats()

        if self.db_monitor:
            self.db_monitor.reset_stats()

        if self.resource_monitor:
            self.resource_monitor.reset_stats()

        if self.business_metrics:
            self.business_metrics.reset_stats()

        if self.anomaly_detector:
            self.anomaly_detector.reset_detectors()

        logger.info("All monitoring statistics reset")


# Global monitoring manager instance
_monitoring_manager: Optional[MonitoringManager] = None


def get_monitoring_manager() -> MonitoringManager:
    """Get global monitoring manager instance."""
    global _monitoring_manager
    if _monitoring_manager is None:
        _monitoring_manager = MonitoringManager()
    return _monitoring_manager


async def initialize_monitoring() -> MonitoringManager:
    """Initialize monitoring system."""
    manager = get_monitoring_manager()
    await manager.initialize()
    return manager


async def start_monitoring() -> None:
    """Start monitoring services."""
    manager = get_monitoring_manager()
    await manager.start()


async def stop_monitoring() -> None:
    """Stop monitoring services."""
    manager = get_monitoring_manager()
    await manager.stop()
