"""Composed flow monitoring service."""

from typing import TypeAlias

from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.alert import AlertSeverity
from app.repositories.flow import FlowStateRepository
from app.services.data_corruption import DataCorruptionDetector
from app.utils.timezone import now_sao_paulo

from .alerting import FlowMonitoringAlertingMixin
from .health import FlowMonitoringHealthMixin
from .metrics import FlowMonitoringMetricsMixin
from .trends import FlowMonitoringTrendsMixin

DBSession: TypeAlias = Session | AsyncSession


class FlowMonitoringService(
    FlowMonitoringMetricsMixin,
    FlowMonitoringHealthMixin,
    FlowMonitoringAlertingMixin,
    FlowMonitoringTrendsMixin,
):
    """Service for monitoring flow operations and system health."""

    def __init__(
        self,
        db: DBSession,
        redis: Redis,
        flow_repository: FlowStateRepository,
        corruption_detector: DataCorruptionDetector,
    ):
        self.db: DBSession = db
        self.redis = redis
        self.flow_repository = flow_repository
        self.corruption_detector = corruption_detector
        self._last_completion_counts: dict[str, int] = {}
        self._last_metrics_check = now_sao_paulo()

        self.thresholds = {
            "error_rate_warning": 0.05,
            "error_rate_critical": 0.15,
            "response_time_warning": 5.0,
            "response_time_critical": 15.0,
            "queue_depth_warning": 100,
            "queue_depth_critical": 500,
            "redis_memory_warning": 0.8,
            "redis_memory_critical": 0.95,
            "stale_flows_warning": 10,
            "stale_flows_critical": 50,
            "corruption_rate_warning": 0.02,
            "corruption_rate_critical": 0.1,
        }

        self.alert_cooldowns = {
            AlertSeverity.LOW: 3600,
            AlertSeverity.MEDIUM: 1800,
            AlertSeverity.HIGH: 900,
            AlertSeverity.CRITICAL: 300,
        }
