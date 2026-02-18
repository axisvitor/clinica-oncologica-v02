"""Background tasks for monitoring and automated recovery (Cloud Tasks/Scheduler)."""

import logging
from typing import Dict, Any

from app.task_queue import task_queue
from sqlalchemy import inspect, text

from app.tasks.base import MonitoringTask, get_db_session
from app.core.redis_manager import get_sync_redis_client
from app.services.flow_monitoring import FlowMonitoringService
from app.services.performance_monitoring import PerformanceMonitoringService
from app.services.automated_recovery_pkg import AutomatedRecoveryService
from app.repositories.flow import FlowStateRepository
from app.services.data_corruption import DataCorruptionDetector
from app.services.error_recovery import ErrorRecoveryService
from app.services.manual_correction import ManualCorrectionService
from app.services.alerts.notification.escalation import get_escalation_manager
from app.domain.messaging.delivery.idempotent_sender import IdempotentMessageSender
from app.utils.async_helpers import run_async
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class SystemHealthCheckTask(MonitoringTask):
    """Task for performing system health checks."""

    def run(self) -> Dict[str, Any]:
        """Periodic system health check task.

        Performs comprehensive health checks on the system including database,
        Redis, and flow monitoring services.

        Returns:
            dict: Dictionary containing:
                - success (bool): Whether the health check completed successfully
                - health_status (str): Overall system health status
                - timestamp (str): ISO timestamp of the check
                - error (str): Error message (if failed)

        Raises:
            Exception: If health check operations fail
        """
        self.log_task_start(message="Starting system health check")

        try:
            with get_db_session() as db:
                redis = get_sync_redis_client()

                # Initialize services
                flow_repo = FlowStateRepository(db)
                corruption_detector = DataCorruptionDetector(db)

                monitoring_service = FlowMonitoringService(
                    db=db,
                    redis=redis,
                    flow_repository=flow_repo,
                    corruption_detector=corruption_detector,
                )

                # Run health checks
                health_status = run_async(monitoring_service.get_system_health())

                # Store health status
                health_key = (
                    f"system_health:{now_sao_paulo().strftime('%Y-%m-%d-%H-%M')}"
                )
                redis.setex(health_key, 3600, str(health_status))  # Keep for 1 hour

                result = self.create_success_result(
                    health_status=health_status.get("status", "unknown"),
                    timestamp=now_sao_paulo().isoformat(),
                )

                self.log_task_success(
                    f"System health check completed: {health_status.get('status', 'unknown')}"
                )
                return result

        except Exception as e:
            self.log_task_error(e, context="system_health_check")
            raise


class PerformanceMetricsCollectionTask(MonitoringTask):
    """Task for collecting performance metrics."""

    def run(self) -> Dict[str, Any]:
        """Periodic performance metrics collection task.

        Collects system performance metrics including response times,
        throughput, and resource utilization.

        Returns:
            dict: Dictionary containing:
                - success (bool): Whether metrics collection completed successfully
                - metrics_collected (int): Number of metrics collected
                - timestamp (str): ISO timestamp of the collection
                - error (str): Error message (if failed)

        Raises:
            Exception: If metrics collection fails
        """
        self.log_task_start(message="Starting performance metrics collection")

        try:
            with get_db_session() as db:
                redis = get_sync_redis_client()

                # Initialize services
                flow_repo = FlowStateRepository(db)
                performance_service = PerformanceMonitoringService(
                    db=db, redis=redis, flow_repository=flow_repo
                )

                # Collect metrics
                metrics = run_async(performance_service.collect_performance_metrics())

                result = self.create_success_result(
                    metrics_collected=len(metrics),
                    timestamp=now_sao_paulo().isoformat(),
                )

                self.log_task_success(f"Collected {len(metrics)} performance metrics")
                return result

        except Exception as e:
            self.log_task_error(e, context="performance_metrics_collection")
            raise


class BottleneckDetectionTask(MonitoringTask):
    """Task for detecting system bottlenecks."""

    def run(self) -> Dict[str, Any]:
        """Periodic bottleneck detection task.

        Analyzes system performance to identify bottlenecks and performance issues.
        Logs critical bottlenecks for immediate attention.

        Returns:
            dict: Dictionary containing:
                - success (bool): Whether detection completed successfully
                - bottlenecks_detected (int): Total number of bottlenecks found
                - critical_bottlenecks (int): Number of critical bottlenecks
                - timestamp (str): ISO timestamp of the detection
                - error (str): Error message (if failed)

        Raises:
            Exception: If bottleneck detection fails
        """
        self.log_task_start(message="Starting bottleneck detection")

        try:
            with get_db_session() as db:
                redis = get_sync_redis_client()

                # Initialize services
                flow_repo = FlowStateRepository(db)
                performance_service = PerformanceMonitoringService(
                    db=db, redis=redis, flow_repository=flow_repo
                )

                # Detect bottlenecks
                bottlenecks = run_async(performance_service.detect_bottlenecks())

                # Log critical bottlenecks
                critical_bottlenecks = [
                    b for b in bottlenecks if b.severity == "critical"
                ]
                if critical_bottlenecks:
                    self.get_task_logger().warning(
                        f"Detected {len(critical_bottlenecks)} critical bottlenecks"
                    )
                    for bottleneck in critical_bottlenecks:
                        self.get_task_logger().warning(
                            f"Critical bottleneck: {bottleneck.description}"
                        )

                result = self.create_success_result(
                    bottlenecks_detected=len(bottlenecks),
                    critical_bottlenecks=len(critical_bottlenecks),
                    timestamp=now_sao_paulo().isoformat(),
                )

                self.log_task_success(
                    f"Bottleneck detection completed: {len(bottlenecks)} bottlenecks found"
                )
                return result

        except Exception as e:
            self.log_task_error(e, context="bottleneck_detection")
            raise


class AlertMonitoringTask(MonitoringTask):
    """Task for monitoring and creating alerts."""

    def run(self) -> Dict[str, Any]:
        """Periodic alert monitoring and creation task.

        Monitors system conditions and creates alerts when thresholds are exceeded.
        Critical alerts are logged immediately for urgent attention.

        Returns:
            dict: Dictionary containing:
                - success (bool): Whether monitoring completed successfully
                - alerts_created (int): Number of alerts created
                - critical_alerts (int): Number of critical alerts created
                - timestamp (str): ISO timestamp of the monitoring
                - error (str): Error message (if failed)

        Raises:
            Exception: If alert monitoring fails
        """
        self.log_task_start(message="Starting alert monitoring")

        try:
            with get_db_session() as db:
                redis = get_sync_redis_client()

                # Initialize services
                flow_repo = FlowStateRepository(db)
                corruption_detector = DataCorruptionDetector(db)

                monitoring_service = FlowMonitoringService(
                    db=db,
                    redis=redis,
                    flow_repository=flow_repo,
                    corruption_detector=corruption_detector,
                )

                # Check and create alerts
                alerts = run_async(monitoring_service.check_and_create_alerts())

                # Log critical alerts
                critical_alerts = [a for a in alerts if a.severity.value == "critical"]
                if critical_alerts:
                    self.get_task_logger().critical(
                        f"Created {len(critical_alerts)} critical alerts"
                    )
                    for alert in critical_alerts:
                        self.get_task_logger().critical(
                            f"Critical alert: {alert.title} - {alert.message}"
                        )

                result = self.create_success_result(
                    alerts_created=len(alerts),
                    critical_alerts=len(critical_alerts),
                    timestamp=now_sao_paulo().isoformat(),
                )

                self.log_task_success(
                    f"Alert monitoring completed: {len(alerts)} alerts created"
                )
                return result

        except Exception as e:
            self.log_task_error(e, context="alert_monitoring")
            raise


class EscalationCheckTask(MonitoringTask):
    """Task for checking and processing alert escalations."""

    def run(self) -> Dict[str, Any]:
        """Periodic escalation check task.

        Checks for alerts that need escalation based on time thresholds
        and escalates them to higher priority levels or notification channels.

        Returns:
            dict: Dictionary containing:
                - success (bool): Whether escalation check completed successfully
                - escalations_processed (int): Number of escalations processed
                - timestamp (str): ISO timestamp of the check
                - error (str): Error message (if failed)

        Raises:
            Exception: If escalation check fails
        """
        self.log_task_start(message="Starting escalation check")

        try:
            with get_db_session():
                # Process pending escalations via escalation manager
                escalation_manager = get_escalation_manager()
                pending_escalations = escalation_manager.get_pending_escalations()
                escalations = []
                for escalation in pending_escalations:
                    run_async(escalation_manager.execute_escalation(escalation.id))
                    escalations.append(escalation)

                result = self.create_success_result(
                    escalations_processed=len(escalations),
                    timestamp=now_sao_paulo().isoformat(),
                )

                self.log_task_success(
                    f"Escalation check completed: {len(escalations)} escalations processed"
                )
                return result

        except Exception as e:
            self.log_task_error(e, context="escalation_check")
            raise


class AutomatedRecoveryTask(MonitoringTask):
    """Task for automated system recovery procedures."""

    def run(self) -> Dict[str, Any]:
        """Periodic automated recovery task.

        Runs automated recovery procedures to fix detected issues and restore
        system functionality without manual intervention.

        Returns:
            dict: Dictionary containing:
                - success (bool): Whether recovery cycle completed successfully
                - recovery_results (dict): Detailed recovery operation results
                - timestamp (str): ISO timestamp of the recovery cycle
                - error (str): Error message (if failed)

        Raises:
            Exception: If automated recovery fails
        """
        self.log_task_start(message="Starting automated recovery cycle")

        try:
            with get_db_session() as db:
                redis = get_sync_redis_client()

                # Initialize services
                flow_repo = FlowStateRepository(db)
                corruption_detector = DataCorruptionDetector(db)
                message_sender = IdempotentMessageSender(db, redis)

                monitoring_service = FlowMonitoringService(
                    db=db,
                    redis=redis,
                    flow_repository=flow_repo,
                    corruption_detector=corruption_detector,
                )

                error_recovery_service = ErrorRecoveryService(
                    db, redis, flow_repo, message_sender
                )
                manual_correction_service = ManualCorrectionService(
                    db, redis, flow_repo, corruption_detector
                )

                recovery_service = AutomatedRecoveryService(
                    db=db,
                    redis=redis,
                    monitoring_service=monitoring_service,
                    error_recovery_service=error_recovery_service,
                    corruption_detector=corruption_detector,
                    manual_correction_service=manual_correction_service,
                    flow_repository=flow_repo,
                )

                # Run automated recovery cycle
                recovery_results = run_async(
                    recovery_service.run_automated_recovery_cycle()
                )

                successful_recoveries = recovery_results.get("recoveries_successful", 0)
                failed_recoveries = recovery_results.get("recoveries_failed", 0)

                if successful_recoveries > 0:
                    self.get_task_logger().info(
                        f"Automated recovery completed: {successful_recoveries} successful recoveries"
                    )

                if failed_recoveries > 0:
                    self.get_task_logger().warning(
                        f"Automated recovery had {failed_recoveries} failed recovery attempts"
                    )

                result = self.create_success_result(
                    recovery_results=recovery_results,
                    timestamp=now_sao_paulo().isoformat(),
                )

                self.log_task_success(
                    f"Automated recovery cycle completed: {successful_recoveries} successful, {failed_recoveries} failed"
                )
                return result

        except Exception as e:
            self.log_task_error(e, context="automated_recovery")
            raise


class CleanupOldMonitoringDataTask(MonitoringTask):
    """Task for cleaning up old monitoring data."""

    @staticmethod
    def _scan_keys(redis_client, pattern: str, count: int = 200):
        """Iterate keys using SCAN to avoid blocking Redis."""
        if hasattr(redis_client, "scan_iter"):
            yield from redis_client.scan_iter(match=pattern, count=count)
            return

        cursor = 0
        while True:
            cursor, batch = redis_client.scan(
                cursor=cursor, match=pattern, count=count
            )
            for key in batch:
                yield key
            if cursor in (0, "0"):
                break

    def run(self) -> Dict[str, Any]:
        """Cleanup old monitoring data task.

        Removes expired monitoring data from Redis to maintain optimal performance
        and prevent storage bloat.

        Returns:
            dict: Dictionary containing:
                - success (bool): Whether cleanup completed successfully
                - keys_deleted (int): Number of Redis keys deleted
                - total_keys_checked (int): Total number of keys examined
                - timestamp (str): ISO timestamp of the cleanup
                - error (str): Error message (if failed)

        Raises:
            Exception: If cleanup operations fail
        """
        self.log_task_start(message="Starting monitoring data cleanup")

        try:
            # Get Redis connection
            redis = get_sync_redis_client()

            # Stream keys to avoid materializing large keyspaces in memory.
            total_keys = 0
            deleted_count = 0
            patterns = ("metrics:*", "alert:*", "escalation:*", "bottleneck:*")
            for pattern in patterns:
                for key in self._scan_keys(redis, pattern):
                    total_keys += 1
                    ttl = redis.ttl(key)
                    # Redis semantics: -2 missing, -1 no expiry.
                    if ttl == -2:
                        continue
                    if ttl < 3600:
                        if hasattr(redis, "unlink"):
                            redis.unlink(key)
                        else:
                            redis.delete(key)
                        deleted_count += 1

            result = self.create_success_result(
                keys_deleted=deleted_count,
                total_keys_checked=total_keys,
                timestamp=now_sao_paulo().isoformat(),
            )

            self.log_task_success(
                f"Monitoring data cleanup completed: {deleted_count} keys deleted out of {total_keys}"
            )
            return result

        except Exception as e:
            self.log_task_error(e, context="monitoring_data_cleanup")
            raise


class DataIntegrityGuardrailsTask(MonitoringTask):
    """Task for monitoring key database data integrity counters."""

    def run(self) -> Dict[str, Any]:
        """Compute integrity guardrail counters and report anomalies."""
        self.log_task_start(check="data_integrity_guardrails")

        try:
            with get_db_session() as db:
                counters: Dict[str, Any] = {
                    "failed_messages_missing_failure_context": int(
                        db.execute(
                            text(
                                """
                                SELECT COUNT(*)
                                FROM messages
                                WHERE status = 'failed'
                                  AND (
                                    failure_reason IS NULL
                                    OR TRIM(failure_reason) = ''
                                    OR last_retry_at IS NULL
                                  )
                                """
                            )
                        ).scalar_one()
                    ),
                    "terminal_status_delivery_mismatch": int(
                        db.execute(
                            text(
                                """
                                SELECT COUNT(*)
                                FROM messages
                                WHERE status IN ('sent', 'delivered', 'read', 'failed', 'cancelled')
                                  AND (
                                    delivery_status IS NULL
                                    OR CAST(delivery_status AS TEXT) <> CAST(status AS TEXT)
                                  )
                                """
                            )
                        ).scalar_one()
                    ),
                    "active_patients_without_doctor_id": int(
                        db.execute(
                            text(
                                """
                                SELECT COUNT(*)
                                FROM patients
                                WHERE deleted_at IS NULL
                                  AND flow_state = 'active'
                                  AND doctor_id IS NULL
                                """
                            )
                        ).scalar_one()
                    ),
                }

                skipped_checks: Dict[str, str] = {}
                inspector = inspect(db.get_bind())
                if inspector.has_table("patient_flow_states"):
                    counters["patient_flow_states_null_status"] = int(
                        db.execute(
                            text(
                                """
                                SELECT COUNT(*)
                                FROM patient_flow_states
                                WHERE status IS NULL
                                """
                            )
                        ).scalar_one()
                    )
                else:
                    counters["patient_flow_states_null_status"] = None
                    skipped_checks["patient_flow_states_null_status"] = "table_missing"

                non_zero_counters = {
                    name: count
                    for name, count in counters.items()
                    if isinstance(count, int) and count > 0
                }
                if non_zero_counters:
                    self.get_task_logger().warning(
                        "Data integrity guardrails detected issues: %s",
                        non_zero_counters,
                    )

                result = self.create_success_result(
                    counters=counters,
                    skipped_checks=skipped_checks,
                    timestamp=now_sao_paulo().isoformat(),
                )

                self.log_task_success(result=result)
                return result

        except Exception as e:
            self.log_task_error(e)
            raise


# Register tasks for the unified task queue.
# Use thin function wrappers so Celery sees zero-argument call signatures.


@task_queue.task(name="monitoring.system_health_check")
def system_health_check_task():
    return SystemHealthCheckTask().run()


@task_queue.task(name="monitoring.performance_metrics_collection")
def performance_metrics_collection_task():
    return PerformanceMetricsCollectionTask().run()


@task_queue.task(name="monitoring.bottleneck_detection")
def bottleneck_detection_task():
    return BottleneckDetectionTask().run()


@task_queue.task(name="monitoring.alert_monitoring")
def alert_monitoring_task():
    return AlertMonitoringTask().run()


@task_queue.task(name="monitoring.escalation_check")
def escalation_check_task():
    return EscalationCheckTask().run()


@task_queue.task(name="monitoring.automated_recovery")
def automated_recovery_task():
    return AutomatedRecoveryTask().run()


@task_queue.task(name="monitoring.cleanup_old_data")
def cleanup_old_monitoring_data_task():
    return CleanupOldMonitoringDataTask().run()


@task_queue.task(name="monitoring.data_integrity_guardrails")
def data_integrity_guardrails_task():
    return DataIntegrityGuardrailsTask().run()
