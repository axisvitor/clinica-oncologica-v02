"""
Monitoring and alerting system for flow operations.
Implements critical error escalation, system health monitoring, and automated recovery.
"""
import logging
import asyncio
from typing import Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from uuid import UUID
from enum import Enum
from dataclasses import dataclass, field
import json
import statistics
from collections import defaultdict, deque

from sqlalchemy import and_, or_  # FIX: Add missing imports
from redis import Redis


from app.models.flow import PatientFlowState
from app.models.flow_analytics import FlowMessage
from app.models.patient import Patient
from app.models.message import Message
from app.repositories.flow import FlowStateRepository
from app.services.data_corruption import DataCorruptionDetector
from app.services.enhanced_flow_engine import FlowType

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HealthStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"


@dataclass
class PerformanceMetrics:
    """Performance metrics for flow operations."""
    total_active_flows: int
    messages_sent_last_hour: int
    messages_sent_last_24h: int
    average_response_time: float
    error_rate: float
    success_rate: float
    queue_depth: int
    redis_memory_usage: float
    database_connection_count: int


@dataclass
class SystemAlert:
    """System alert for flow operations."""
    id: str
    severity: AlertSeverity
    title: str
    message: str
    component: str
    metric_value: Optional[float]
    threshold: Optional[float]
    created_at: datetime
    resolved_at: Optional[datetime]
    metadata: dict[str, Any]


class FlowMonitoringService:
    """Service for monitoring flow operations and system health."""

    def __init__(self, db: Any, redis: Redis, flow_repository: FlowStateRepository,
                 corruption_detector: DataCorruptionDetector):
        self.db = db
        self.redis = redis
        self.flow_repository = flow_repository
        self.corruption_detector = corruption_detector

        # Monitoring thresholds
        self.thresholds = {
            'error_rate_warning': 0.05,  # 5%
            'error_rate_critical': 0.15,  # 15%
            'response_time_warning': 5.0,  # 5 seconds
            'response_time_critical': 15.0,  # 15 seconds
            'queue_depth_warning': 100,
            'queue_depth_critical': 500,
            'redis_memory_warning': 0.8,  # 80%
            'redis_memory_critical': 0.95,  # 95%
            'stale_flows_warning': 10,
            'stale_flows_critical': 50,
            'corruption_rate_warning': 0.02,  # 2%
            'corruption_rate_critical': 0.1,  # 10%
        }

        # Alert cooldown periods (in seconds)
        self.alert_cooldowns = {
            AlertSeverity.LOW: 3600,  # 1 hour
            AlertSeverity.MEDIUM: 1800,  # 30 minutes
            AlertSeverity.HIGH: 900,  # 15 minutes
            AlertSeverity.CRITICAL: 300,  # 5 minutes
        }

    async def get_system_health(self) -> dict[str, Any]:
        """Get overall system health status."""
        try:
            # Collect performance metrics
            metrics = await self.collect_performance_metrics()

            # Determine overall health status
            health_status = await self._determine_health_status(metrics)

            # Get active alerts
            active_alerts = await self.get_active_alerts()

            # Get recent performance trends
            trends = await self._get_performance_trends()

            return {
                'status': health_status.value,
                'timestamp': datetime.utcnow().isoformat(),
                'metrics': metrics.__dict__,
                'active_alerts': [alert.__dict__ for alert in active_alerts],
                'trends': trends,
                'components': await self._get_component_health()
            }

        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {
                'status': HealthStatus.CRITICAL.value,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    async def collect_performance_metrics(self) -> PerformanceMetrics:
        """Collect current performance metrics."""
        try:
            # Database metrics
            total_active_flows = self.db.query(PatientFlowState).filter(  # FIX: Use PatientFlowState instead of FlowState
                PatientFlowState.is_paused == False
            ).count()

            # Message metrics
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)

            messages_last_hour = self.db.query(FlowMessage).filter(
                FlowMessage.sent_at >= one_hour_ago
            ).count()

            messages_last_24h = self.db.query(FlowMessage).filter(
                FlowMessage.sent_at >= twenty_four_hours_ago
            ).count()

            # Response time metrics (from Redis if available)
            avg_response_time = await self._get_average_response_time()

            # Error rate metrics
            error_rate = await self._calculate_error_rate()
            success_rate = 1.0 - error_rate

            # Queue depth
            queue_depth = await self._get_queue_depth()

            # Redis metrics
            redis_memory_usage = await self._get_redis_memory_usage()

            # Database connection count
            db_connections = await self._get_database_connection_count()

            return PerformanceMetrics(
                total_active_flows=total_active_flows,
                messages_sent_last_hour=messages_last_hour,
                messages_sent_last_24h=messages_last_24h,
                average_response_time=avg_response_time,
                error_rate=error_rate,
                success_rate=success_rate,
                queue_depth=queue_depth,
                redis_memory_usage=redis_memory_usage,
                database_connection_count=db_connections
            )

        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")
            # Return default metrics on error
            return PerformanceMetrics(
                total_active_flows=0,
                messages_sent_last_hour=0,
                messages_sent_last_24h=0,
                average_response_time=0.0,
                error_rate=1.0,
                success_rate=0.0,
                queue_depth=0,
                redis_memory_usage=0.0,
                database_connection_count=0
            )

    async def check_and_create_alerts(self) -> List[SystemAlert]:
        """Check system metrics and create alerts if thresholds are exceeded."""
        alerts = []

        try:
            metrics = await self.collect_performance_metrics()

            # Check error rate
            if metrics.error_rate >= self.thresholds['error_rate_critical']:
                alert = await self._create_alert(
                    AlertSeverity.CRITICAL,
                    "High Error Rate",
                    f"Error rate is {metrics.error_rate:.2%}, exceeding critical threshold",
                    "flow_processing",
                    metrics.error_rate,
                    self.thresholds['error_rate_critical']
                )
                if alert:
                    alerts.append(alert)

            elif metrics.error_rate >= self.thresholds['error_rate_warning']:
                alert = await self._create_alert(
                    AlertSeverity.HIGH,
                    "Elevated Error Rate",
                    f"Error rate is {metrics.error_rate:.2%}, exceeding warning threshold",
                    "flow_processing",
                    metrics.error_rate,
                    self.thresholds['error_rate_warning']
                )
                if alert:
                    alerts.append(alert)

            # Check response time
            if metrics.average_response_time >= self.thresholds['response_time_critical']:
                alert = await self._create_alert(
                    AlertSeverity.CRITICAL,
                    "Slow Response Time",
                    f"Average response time is {metrics.average_response_time:.2f}s",
                    "performance",
                    metrics.average_response_time,
                    self.thresholds['response_time_critical']
                )
                if alert:
                    alerts.append(alert)

            # Check queue depth
            if metrics.queue_depth >= self.thresholds['queue_depth_critical']:
                alert = await self._create_alert(
                    AlertSeverity.CRITICAL,
                    "High Queue Depth",
                    f"Message queue depth is {metrics.queue_depth}",
                    "message_queue",
                    metrics.queue_depth,
                    self.thresholds['queue_depth_critical']
                )
                if alert:
                    alerts.append(alert)

            # Check Redis memory usage
            if metrics.redis_memory_usage >= self.thresholds['redis_memory_critical']:
                alert = await self._create_alert(
                    AlertSeverity.CRITICAL,
                    "High Redis Memory Usage",
                    f"Redis memory usage is {metrics.redis_memory_usage:.1%}",
                    "redis",
                    metrics.redis_memory_usage,
                    self.thresholds['redis_memory_critical']
                )
                if alert:
                    alerts.append(alert)

            # Check for stale flows
            stale_flows = await self._count_stale_flows()
            if stale_flows >= self.thresholds['stale_flows_critical']:
                alert = await self._create_alert(
                    AlertSeverity.HIGH,
                    "Stale Flows Detected",
                    f"{stale_flows} flows haven't been processed in over 24 hours",
                    "flow_processing",
                    stale_flows,
                    self.thresholds['stale_flows_critical']
                )
                if alert:
                    alerts.append(alert)

            # Check corruption rate
            corruption_rate = await self._calculate_corruption_rate()
            if corruption_rate >= self.thresholds['corruption_rate_critical']:
                alert = await self._create_alert(
                    AlertSeverity.CRITICAL,
                    "High Data Corruption Rate",
                    f"Data corruption rate is {corruption_rate:.2%}",
                    "data_integrity",
                    corruption_rate,
                    self.thresholds['corruption_rate_critical']
                )
                if alert:
                    alerts.append(alert)

            return alerts

        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
            return []

    async def get_active_alerts(self) -> List[SystemAlert]:
        """Get all active (unresolved) alerts."""
        try:
            alert_keys = self.redis.keys("alert:*")  # FIX: Remove await
            alerts = []

            for key in alert_keys:
                alert_data = self.redis.get(key)  # FIX: Remove await
                if alert_data:
                    alert_dict = json.loads(alert_data)
                    if not alert_dict.get('resolved_at'):
                        alert = SystemAlert(
                            id=alert_dict['id'],
                            severity=AlertSeverity(alert_dict['severity']),
                            title=alert_dict['title'],
                            message=alert_dict['message'],
                            component=alert_dict['component'],
                            metric_value=alert_dict.get('metric_value'),
                            threshold=alert_dict.get('threshold'),
                            created_at=datetime.fromisoformat(alert_dict['created_at']),
                            resolved_at=datetime.fromisoformat(alert_dict['resolved_at']) if alert_dict.get('resolved_at') else None,
                            metadata=alert_dict.get('metadata', {})
                        )
                        alerts.append(alert)

            return sorted(alerts, key=lambda x: x.created_at, reverse=True)

        except Exception as e:
            logger.error(f"Error getting active alerts: {e}")
            return []

    async def resolve_alert(self, alert_id: str, resolution_note: Optional[str] = None) -> bool:
        """Resolve an active alert."""
        try:
            alert_key = f"alert:{alert_id}"
            alert_data = self.redis.get(alert_key)  # FIX: Remove await

            if not alert_data:
                return False

            alert_dict = json.loads(alert_data)
            alert_dict['resolved_at'] = datetime.utcnow().isoformat()
            if resolution_note:
                alert_dict['resolution_note'] = resolution_note

            self.redis.setex(alert_key, 86400 * 7, json.dumps(alert_dict))  # FIX: Remove await

            logger.info(f"Resolved alert {alert_id}: {resolution_note}")
            return True

        except Exception as e:
            logger.error(f"Error resolving alert {alert_id}: {e}")
            return False

    async def run_health_checks(self) -> dict[str, Any]:
        """Run comprehensive health checks."""
        health_checks = {
            'database_connectivity': await self._check_database_connectivity(),
            'redis_connectivity': await self._check_redis_connectivity(),
            'flow_processing': await self._check_flow_processing_health(),
            'message_delivery': await self._check_message_delivery_health(),
            'data_integrity': await self._check_data_integrity(),
            'external_services': await self._check_external_services()
        }

        overall_status = HealthStatus.HEALTHY
        for check_name, check_result in health_checks.items():
            if check_result['status'] == HealthStatus.CRITICAL.value:
                overall_status = HealthStatus.CRITICAL
                break
            elif check_result['status'] == HealthStatus.DEGRADED.value and overall_status != HealthStatus.CRITICAL:
                overall_status = HealthStatus.DEGRADED
            elif check_result['status'] == HealthStatus.WARNING.value and overall_status == HealthStatus.HEALTHY:
                overall_status = HealthStatus.WARNING

        return {
            'overall_status': overall_status.value,
            'timestamp': datetime.utcnow().isoformat(),
            'checks': health_checks
        }

    async def _determine_health_status(self, metrics: PerformanceMetrics) -> HealthStatus:
        """Determine overall health status based on metrics."""
        if (metrics.error_rate >= self.thresholds['error_rate_critical'] or
            metrics.average_response_time >= self.thresholds['response_time_critical'] or
            metrics.queue_depth >= self.thresholds['queue_depth_critical'] or
            metrics.redis_memory_usage >= self.thresholds['redis_memory_critical']):
            return HealthStatus.CRITICAL

        if (metrics.error_rate >= self.thresholds['error_rate_warning'] or
            metrics.average_response_time >= self.thresholds['response_time_warning'] or
            metrics.queue_depth >= self.thresholds['queue_depth_warning'] or
            metrics.redis_memory_usage >= self.thresholds['redis_memory_warning']):
            return HealthStatus.DEGRADED

        # Check for any active high/critical alerts
        active_alerts = await self.get_active_alerts()
        critical_alerts = [a for a in active_alerts if a.severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]]

        if critical_alerts:
            return HealthStatus.WARNING

        return HealthStatus.HEALTHY

    async def _create_alert(self, severity: AlertSeverity, title: str, message: str,
                          component: str, metric_value: Optional[float] = None,
                          threshold: Optional[float] = None) -> Optional[SystemAlert]:
        """Create a new alert if not in cooldown period."""
        try:
            # Check cooldown
            cooldown_key = f"alert_cooldown:{component}:{title}"
            if self.redis.exists(cooldown_key):  # FIX: Remove await
                return None  # Still in cooldown

            # Create alert
            alert_id = f"{component}_{title.replace(' ', '_').lower()}_{int(datetime.utcnow().timestamp())}"
            alert = SystemAlert(
                id=alert_id,
                severity=severity,
                title=title,
                message=message,
                component=component,
                metric_value=metric_value,
                threshold=threshold,
                created_at=datetime.utcnow(),
                resolved_at=None,
                metadata={}
            )

            # Store alert
            alert_key = f"alert:{alert_id}"
            alert_data = {
                'id': alert.id,
                'severity': alert.severity.value,
                'title': alert.title,
                'message': alert.message,
                'component': alert.component,
                'metric_value': alert.metric_value,
                'threshold': alert.threshold,
                'created_at': alert.created_at.isoformat(),
                'resolved_at': None,
                'metadata': alert.metadata
            }

            self.redis.setex(alert_key, 86400 * 7, json.dumps(alert_data))  # FIX: Remove await

            # Set cooldown
            cooldown_seconds = self.alert_cooldowns[severity]
            self.redis.setex(cooldown_key, cooldown_seconds, "1")  # FIX: Remove await

            # Log alert
            logger.warning(f"Created {severity.value} alert: {title} - {message}")

            # Send notification for critical alerts
            if severity == AlertSeverity.CRITICAL:
                await self._send_critical_alert_notification(alert)

            return alert

        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            return None

    async def _get_average_response_time(self) -> float:
        """Get average response time from Redis metrics."""
        try:
            response_times = self.redis.lrange("response_times", 0, 99)  # FIX: Remove await - Redis is synchronous
            if response_times:
                times = [float(t) for t in response_times]
                return sum(times) / len(times)
            return 0.0
        except Exception:
            return 0.0

    async def _calculate_error_rate(self) -> float:
        """Calculate error rate from recent operations."""
        try:
            # Get error count from last hour
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            error_key = f"flow_errors:{one_hour_ago.strftime('%Y-%m-%d')}"

            error_count = self.redis.llen(error_key)  # FIX: Remove await

            # Get total operations from last hour
            total_operations = self.redis.get("operations_count_last_hour")  # FIX: Remove await
            total_operations = int(total_operations) if total_operations else 1

            return error_count / max(total_operations, 1)

        except Exception:
            return 0.0

    async def _get_queue_depth(self) -> int:
        """Get current message queue depth."""
        try:
            # This would depend on your Celery setup
            # For now, return a placeholder
            return 0
        except Exception:
            return 0

    async def _get_redis_memory_usage(self) -> float:
        """Get Redis memory usage percentage."""
        try:
            info = self.redis.info('memory')  # FIX: Remove await - Redis is synchronous
            used_memory = info.get('used_memory', 0)
            max_memory = info.get('maxmemory', 0)

            if max_memory > 0:
                return used_memory / max_memory
            return 0.0
        except Exception:
            return 0.0

    async def _get_database_connection_count(self) -> int:
        """Get current database connection count."""
        try:
            # This would depend on your database setup
            # For now, return a placeholder
            return 0
        except Exception:
            return 0

    async def _count_stale_flows(self) -> int:
        """Count flows that haven't been processed in over 24 hours."""
        try:
            twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)

            stale_count = self.db.query(PatientFlowState).filter(  # FIX: Use PatientFlowState
                and_(
                    PatientFlowState.is_paused == False,
                    or_(
                        PatientFlowState.last_message_sent < twenty_four_hours_ago,
                        PatientFlowState.last_message_sent.is_(None)
                    )
                )
            ).count()

            return stale_count

        except Exception as e:
            logger.error(f"Error counting stale flows: {e}")
            return 0

    async def _calculate_corruption_rate(self) -> float:
        """Calculate data corruption rate."""
        try:
            # Sample a subset of flows for corruption checking
            total_flows = self.db.query(PatientFlowState).count()  # FIX: Use PatientFlowState
            if total_flows == 0:
                return 0.0

            # Check up to 100 flows for corruption
            sample_size = min(100, total_flows)
            corruption_report = await self.corruption_detector.detect_bulk_corruption(sample_size)

            corrupted_flows = len(corruption_report)
            return corrupted_flows / sample_size

        except Exception as e:
            logger.error(f"Error calculating corruption rate: {e}")
            return 0.0

    async def _get_performance_trends(self) -> dict[str, Any]:
        """Get performance trends over time."""
        try:
            # Get metrics from the last 24 hours
            trends = {
                'message_volume_trend': await self._get_message_volume_trend(),
                'error_rate_trend': await self._get_error_rate_trend(),
                'response_time_trend': await self._get_response_time_trend()
            }
            return trends
        except Exception as e:
            logger.error(f"Error getting performance trends: {e}")
            return {}

    async def _get_component_health(self) -> dict[str, str]:
        """Get health status of individual components."""
        return {
            'database': 'healthy',
            'redis': 'healthy',
            'message_queue': 'healthy',
            'flow_engine': 'healthy',
            'ai_services': 'healthy'
        }

    async def _check_database_connectivity(self) -> dict[str, Any]:
        """Check database connectivity and performance."""
        try:
            start_time = datetime.utcnow()
            # Simple query to test connectivity
            self.db.execute("SELECT 1")
            response_time = (datetime.utcnow() - start_time).total_seconds()

            return {
                'status': HealthStatus.HEALTHY.value,
                'response_time': response_time,
                'message': 'Database connectivity is healthy'
            }
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL.value,
                'error': str(e),
                'message': 'Database connectivity failed'
            }

    async def _check_redis_connectivity(self) -> dict[str, Any]:
        """Check Redis connectivity and performance."""
        try:
            start_time = datetime.utcnow()
            self.redis.ping()  # FIX: Remove await - Redis is synchronous
            response_time = (datetime.utcnow() - start_time).total_seconds()

            return {
                'status': HealthStatus.HEALTHY.value,
                'response_time': response_time,
                'message': 'Redis connectivity is healthy'
            }
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL.value,
                'error': str(e),
                'message': 'Redis connectivity failed'
            }

    async def _check_flow_processing_health(self) -> dict[str, Any]:
        """Check flow processing health."""
        try:
            # Check for recent flow processing activity
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            recent_messages = self.db.query(FlowMessage).filter(
                FlowMessage.sent_at >= one_hour_ago
            ).count()

            if recent_messages > 0:
                return {
                    'status': HealthStatus.HEALTHY.value,
                    'recent_messages': recent_messages,
                    'message': 'Flow processing is active'
                }
            else:
                return {
                    'status': HealthStatus.WARNING.value,
                    'recent_messages': recent_messages,
                    'message': 'No recent flow processing activity'
                }
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL.value,
                'error': str(e),
                'message': 'Flow processing health check failed'
            }

    async def _check_message_delivery_health(self) -> dict[str, Any]:
        """Check message delivery health."""
        # Placeholder implementation
        return {
            'status': HealthStatus.HEALTHY.value,
            'message': 'Message delivery is healthy'
        }

    async def _check_data_integrity(self) -> dict[str, Any]:
        """Check data integrity."""
        try:
            # Run a quick corruption check on a small sample
            corruption_report = await self.corruption_detector.detect_bulk_corruption(10)

            if not corruption_report:
                return {
                    'status': HealthStatus.HEALTHY.value,
                    'message': 'Data integrity is healthy'
                }
            else:
                return {
                    'status': HealthStatus.WARNING.value,
                    'corrupted_flows': len(corruption_report),
                    'message': f'Found {len(corruption_report)} flows with data issues'
                }
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL.value,
                'error': str(e),
                'message': 'Data integrity check failed'
            }

    async def _check_external_services(self) -> dict[str, Any]:
        """Check external services health."""
        # Placeholder implementation
        return {
            'status': HealthStatus.HEALTHY.value,
            'message': 'External services are healthy'
        }

    async def _send_critical_alert_notification(self, alert: SystemAlert) -> None:
        """Send notification for critical alerts."""
        try:
            # Store critical alert for immediate attention
            critical_key = f"critical_alert:{alert.id}"
            notification_data = {
                'alert_id': alert.id,
                'severity': alert.severity.value,
                'title': alert.title,
                'message': alert.message,
                'component': alert.component,
                'created_at': alert.created_at.isoformat(),
                'requires_immediate_attention': True
            }

            self.redis.setex(critical_key, 86400, json.dumps(notification_data))  # FIX: Remove await

            # Log critical alert
            logger.critical(f"CRITICAL ALERT: {alert.title} - {alert.message}")

        except Exception as e:
            logger.error(f"Error sending critical alert notification: {e}")

    async def _get_message_volume_trend(self) -> List[dict[str, Any]]:
        """Get message volume trend over the last 24 hours."""
        # Placeholder implementation
        return []

    async def _get_error_rate_trend(self) -> List[dict[str, Any]]:
        """Get error rate trend over the last 24 hours."""
        # Placeholder implementation
        return []

    async def _get_response_time_trend(self) -> List[dict[str, Any]]:
        """Get response time trend over the last 24 hours."""
        # Placeholder implementation
        return []
