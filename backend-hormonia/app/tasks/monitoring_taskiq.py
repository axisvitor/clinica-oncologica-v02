"""
Taskiq monitoring tasks — async-native replacements for Celery monitoring tasks (M009-S04).

8 tasks migrated from Celery to Taskiq, flattened from class hierarchy
into standalone async task functions:
  1. system_health_check          — interval 300s
  2. performance_metrics_collection — interval 600s
  3. bottleneck_detection          — interval 900s
  4. alert_monitoring              — interval 300s
  5. escalation_check              — interval 1800s
  6. automated_recovery            — interval 3600s
  7. data_integrity_guardrails     — interval 900s
  8. cleanup_old_data              — interval 86400s

Key translation patterns from Celery → Taskiq:
  - Class hierarchy flattened: each `run(self)` → standalone async function
  - Celery's sync bridge removed → `await service.method()` directly
  - `self.log_task_start/success/error()` → module-level log_task_start/success/error()
  - `self.create_success_result(...)` → explicit dict return
  - `self.get_task_logger()` → module logger
  - `get_sync_redis_client()` preserved for sync-only services (cleanup_old_data)
  - `get_scoped_session()` preserved for sync ORM services (DataCorruptionDetector, etc.)
  - Structured logging via log_task_start/success/error from taskiq_base

Schedule labels (all 8 tasks are periodic):
  - system_health_check:           interval 300s
  - performance_metrics_collection: interval 600s
  - bottleneck_detection:           interval 900s
  - alert_monitoring:               interval 300s
  - escalation_check:               interval 1800s
  - automated_recovery:             interval 3600s
  - data_integrity_guardrails:      interval 900s
  - cleanup_old_data:               interval 86400s
"""

import logging
from typing import Any, Dict

from sqlalchemy import inspect, text

from app.core.redis_manager import get_sync_redis_client
from app.database import get_scoped_session
from app.taskiq_broker import broker
from app.tasks.taskiq_base import log_task_error, log_task_start, log_task_success
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger("app.tasks.monitoring_taskiq")


# ===========================================================================
# 1. system_health_check — periodic (interval 300s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
    schedule=[{"interval": {"seconds": 300}}],
)
async def system_health_check() -> Dict[str, Any]:
    """Periodic system health check.

    Checks DB connectivity, Redis health, and flow monitoring service status.
    Stores health snapshot in Redis with 1-hour TTL.

    Returns:
        Dict with health_status and timestamp.
    """
    start_time = log_task_start("system_health_check")

    try:
        with get_scoped_session() as db:
            redis = get_sync_redis_client()

            from app.repositories.flow import FlowStateRepository
            from app.services.data_corruption import DataCorruptionDetector
            from app.services.flow_monitoring import FlowMonitoringService

            flow_repo = FlowStateRepository(db)
            corruption_detector = DataCorruptionDetector(db)

            monitoring_service = FlowMonitoringService(
                db=db,
                redis=redis,
                flow_repository=flow_repo,
                corruption_detector=corruption_detector,
            )

            # Async-native: call directly with await (Celery used sync bridge)
            health_status = await monitoring_service.get_system_health()

            # Store health snapshot in Redis
            health_key = (
                f"system_health:{now_sao_paulo().strftime('%Y-%m-%d-%H-%M')}"
            )
            redis.setex(health_key, 3600, str(health_status))

            log_task_success(
                "system_health_check",
                start_time,
                health_status=health_status.get("status", "unknown"),
            )
            return {
                "success": True,
                "health_status": health_status.get("status", "unknown"),
                "timestamp": now_sao_paulo().isoformat(),
            }

    except Exception as exc:
        log_task_error("system_health_check", exc, start_time)
        raise


# ===========================================================================
# 2. performance_metrics_collection — periodic (interval 600s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
    schedule=[{"interval": {"seconds": 600}}],
)
async def performance_metrics_collection() -> Dict[str, Any]:
    """Periodic performance metrics collection.

    Collects system performance metrics including response times,
    throughput, and resource utilization.

    Returns:
        Dict with metrics_collected count and timestamp.
    """
    start_time = log_task_start("performance_metrics_collection")

    try:
        with get_scoped_session() as db:
            redis = get_sync_redis_client()

            from app.repositories.flow import FlowStateRepository
            from app.services.performance_monitoring import PerformanceMonitoringService

            flow_repo = FlowStateRepository(db)
            performance_service = PerformanceMonitoringService(
                db=db, redis=redis, flow_repository=flow_repo
            )

            # Async-native: call directly with await (Celery used sync bridge)
            metrics = await performance_service.collect_performance_metrics()

            log_task_success(
                "performance_metrics_collection",
                start_time,
                metrics_collected=len(metrics),
            )
            return {
                "success": True,
                "metrics_collected": len(metrics),
                "timestamp": now_sao_paulo().isoformat(),
            }

    except Exception as exc:
        log_task_error("performance_metrics_collection", exc, start_time)
        raise


# ===========================================================================
# 3. bottleneck_detection — periodic (interval 900s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
    schedule=[{"interval": {"seconds": 900}}],
)
async def bottleneck_detection() -> Dict[str, Any]:
    """Periodic bottleneck detection.

    Analyzes system performance to identify bottlenecks and performance issues.
    Logs critical bottlenecks for immediate attention.

    Returns:
        Dict with bottleneck counts and timestamp.
    """
    start_time = log_task_start("bottleneck_detection")

    try:
        with get_scoped_session() as db:
            redis = get_sync_redis_client()

            from app.repositories.flow import FlowStateRepository
            from app.services.performance_monitoring import PerformanceMonitoringService

            flow_repo = FlowStateRepository(db)
            performance_service = PerformanceMonitoringService(
                db=db, redis=redis, flow_repository=flow_repo
            )

            # Async-native: call directly with await (Celery used sync bridge)
            bottlenecks = await performance_service.detect_bottlenecks()

            critical_bottlenecks = [
                b for b in bottlenecks if b.severity == "critical"
            ]
            if critical_bottlenecks:
                logger.warning(
                    "Detected %d critical bottlenecks", len(critical_bottlenecks)
                )
                for bottleneck in critical_bottlenecks:
                    logger.warning("Critical bottleneck: %s", bottleneck.description)

            log_task_success(
                "bottleneck_detection",
                start_time,
                bottlenecks_detected=len(bottlenecks),
                critical_bottlenecks=len(critical_bottlenecks),
            )
            return {
                "success": True,
                "bottlenecks_detected": len(bottlenecks),
                "critical_bottlenecks": len(critical_bottlenecks),
                "timestamp": now_sao_paulo().isoformat(),
            }

    except Exception as exc:
        log_task_error("bottleneck_detection", exc, start_time)
        raise


# ===========================================================================
# 4. alert_monitoring — periodic (interval 300s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
    schedule=[{"interval": {"seconds": 300}}],
)
async def alert_monitoring() -> Dict[str, Any]:
    """Periodic alert monitoring and creation.

    Monitors system conditions and creates alerts when thresholds are exceeded.
    Critical alerts are logged immediately for urgent attention.

    Returns:
        Dict with alerts_created, critical_alerts, and timestamp.
    """
    start_time = log_task_start("alert_monitoring")

    try:
        with get_scoped_session() as db:
            redis = get_sync_redis_client()

            from app.repositories.flow import FlowStateRepository
            from app.services.data_corruption import DataCorruptionDetector
            from app.services.flow_monitoring import FlowMonitoringService

            flow_repo = FlowStateRepository(db)
            corruption_detector = DataCorruptionDetector(db)

            monitoring_service = FlowMonitoringService(
                db=db,
                redis=redis,
                flow_repository=flow_repo,
                corruption_detector=corruption_detector,
            )

            # Async-native: call directly with await (Celery used sync bridge)
            alerts = await monitoring_service.check_and_create_alerts()

            critical_alerts = [a for a in alerts if a.severity.value == "critical"]
            if critical_alerts:
                logger.critical(
                    "Created %d critical alerts", len(critical_alerts)
                )
                for alert in critical_alerts:
                    logger.critical(
                        "Critical alert: %s - %s", alert.title, alert.message
                    )

            log_task_success(
                "alert_monitoring",
                start_time,
                alerts_created=len(alerts),
                critical_alerts=len(critical_alerts),
            )
            return {
                "success": True,
                "alerts_created": len(alerts),
                "critical_alerts": len(critical_alerts),
                "timestamp": now_sao_paulo().isoformat(),
            }

    except Exception as exc:
        log_task_error("alert_monitoring", exc, start_time)
        raise


# ===========================================================================
# 5. escalation_check — periodic (interval 1800s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
    schedule=[{"interval": {"seconds": 1800}}],
)
async def escalation_check() -> Dict[str, Any]:
    """Periodic escalation check.

    Checks for alerts that need escalation based on time thresholds
    and executes escalation via the escalation manager.

    Returns:
        Dict with escalations_processed count and timestamp.
    """
    start_time = log_task_start("escalation_check")

    try:
        with get_scoped_session():
            from app.services.alerts.notification.escalation import get_escalation_manager

            escalation_manager = get_escalation_manager()
            pending_escalations = escalation_manager.get_pending_escalations()
            escalations = []

            for escalation in pending_escalations:
                # Async-native: call directly with await (Celery used sync bridge)
                await escalation_manager.execute_escalation(escalation.id)
                escalations.append(escalation)

            log_task_success(
                "escalation_check",
                start_time,
                escalations_processed=len(escalations),
            )
            return {
                "success": True,
                "escalations_processed": len(escalations),
                "timestamp": now_sao_paulo().isoformat(),
            }

    except Exception as exc:
        log_task_error("escalation_check", exc, start_time)
        raise


# ===========================================================================
# 6. automated_recovery — periodic (interval 3600s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
    schedule=[{"interval": {"seconds": 3600}}],
)
async def automated_recovery() -> Dict[str, Any]:
    """Periodic automated recovery cycle.

    Runs automated recovery procedures to fix detected issues and restore
    system functionality without manual intervention.

    Returns:
        Dict with recovery_results and timestamp.
    """
    start_time = log_task_start("automated_recovery")

    try:
        with get_scoped_session() as db:
            redis = get_sync_redis_client()

            from app.domain.messaging.delivery.idempotent_sender import IdempotentMessageSender
            from app.repositories.flow import FlowStateRepository
            from app.services.automated_recovery_pkg import AutomatedRecoveryService
            from app.services.data_corruption import DataCorruptionDetector
            from app.services.error_recovery import ErrorRecoveryService
            from app.services.flow_monitoring import FlowMonitoringService
            from app.services.manual_correction import ManualCorrectionService

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

            # Async-native: call directly with await (Celery used sync bridge)
            recovery_results = await recovery_service.run_automated_recovery_cycle()

            successful_recoveries = recovery_results.get("recoveries_successful", 0)
            failed_recoveries = recovery_results.get("recoveries_failed", 0)

            if failed_recoveries > 0:
                logger.warning(
                    "Automated recovery had %d failed recovery attempts",
                    failed_recoveries,
                )

            log_task_success(
                "automated_recovery",
                start_time,
                successful_recoveries=successful_recoveries,
                failed_recoveries=failed_recoveries,
            )
            return {
                "success": True,
                "recovery_results": recovery_results,
                "timestamp": now_sao_paulo().isoformat(),
            }

    except Exception as exc:
        log_task_error("automated_recovery", exc, start_time)
        raise


# ===========================================================================
# 7. data_integrity_guardrails — periodic (interval 900s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
    schedule=[{"interval": {"seconds": 900}}],
)
async def data_integrity_guardrails() -> Dict[str, Any]:
    """Periodic data integrity guardrails check.

    Computes integrity counters for key database invariants and reports
    anomalies. Checks for:
    - Failed messages missing failure context
    - Terminal status / delivery status mismatches
    - Active patients without assigned doctor
    - Patient flow states with null status

    Returns:
        Dict with integrity counters and any skipped checks.
    """
    start_time = log_task_start("data_integrity_guardrails")

    try:
        with get_scoped_session() as db:
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
                logger.warning(
                    "Data integrity guardrails detected issues: %s",
                    non_zero_counters,
                )

            log_task_success(
                "data_integrity_guardrails",
                start_time,
                counters=counters,
            )
            return {
                "success": True,
                "counters": counters,
                "skipped_checks": skipped_checks,
                "timestamp": now_sao_paulo().isoformat(),
            }

    except Exception as exc:
        log_task_error("data_integrity_guardrails", exc, start_time)
        raise


# ===========================================================================
# 8. cleanup_old_data — periodic (interval 86400s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=2,
    delay=300,
    schedule=[{"interval": {"seconds": 86400}}],
)
async def cleanup_old_data() -> Dict[str, Any]:
    """Cleanup old monitoring data from Redis.

    Removes expired monitoring keys (metrics, alert, escalation, bottleneck)
    from Redis to maintain optimal performance and prevent storage bloat.
    Uses SCAN to avoid blocking Redis.

    Returns:
        Dict with keys_deleted, total_keys_checked, and timestamp.
    """
    start_time = log_task_start("cleanup_old_data")

    try:
        redis = get_sync_redis_client()

        total_keys = 0
        deleted_count = 0
        patterns = ("metrics:*", "alert:*", "escalation:*", "bottleneck:*")

        for pattern in patterns:
            # Use SCAN to stream keys without blocking Redis
            if hasattr(redis, "scan_iter"):
                key_iter = redis.scan_iter(match=pattern, count=200)
            else:
                # Fallback for clients without scan_iter
                key_iter = _scan_keys(redis, pattern, count=200)

            for key in key_iter:
                total_keys += 1
                ttl = redis.ttl(key)
                # Redis semantics: -2 missing, -1 no expiry
                if ttl == -2:
                    continue
                if ttl < 3600:
                    if hasattr(redis, "unlink"):
                        redis.unlink(key)
                    else:
                        redis.delete(key)
                    deleted_count += 1

        log_task_success(
            "cleanup_old_data",
            start_time,
            keys_deleted=deleted_count,
            total_keys_checked=total_keys,
        )
        return {
            "success": True,
            "keys_deleted": deleted_count,
            "total_keys_checked": total_keys,
            "timestamp": now_sao_paulo().isoformat(),
        }

    except Exception as exc:
        log_task_error("cleanup_old_data", exc, start_time)
        raise


def _scan_keys(redis_client, pattern: str, count: int = 200):
    """Iterate keys using SCAN to avoid blocking Redis (fallback for sync clients)."""
    cursor = 0
    while True:
        cursor, batch = redis_client.scan(cursor=cursor, match=pattern, count=count)
        for key in batch:
            yield key
        if cursor in (0, "0"):
            break


__all__ = [
    "system_health_check",
    "performance_metrics_collection",
    "bottleneck_detection",
    "alert_monitoring",
    "escalation_check",
    "automated_recovery",
    "data_integrity_guardrails",
    "cleanup_old_data",
]
