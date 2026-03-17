"""
Taskiq alert tasks — async-native replacements for Celery alert tasks (M009-S04).

7 tasks migrated from Celery to Taskiq:
  1. check_patient_alerts      — interval 300s (periodic patient alert evaluation)
  2. periodic_alert_check      — on-demand wrapper (delegates to check_patient_alerts)
  3. process_alert_notification — on-demand (dispatched when alerts are created)
  4. process_alert_escalation   — on-demand (dispatched for alert escalation)
  5. periodic_escalation_check  — on-demand (checks pending alerts needing escalation)
  6. cleanup_resolved_alerts    — on-demand (archives old resolved alerts)
  7. generate_alert_metrics     — on-demand (generates alert stats for dashboards)

Key translation patterns from Celery → Taskiq:
  - Celery's sync bridge removed → `await alert_manager.method()` directly
  - `self` (bind=True) removed: SmartRetryMiddleware handles retries externally
  - `get_scoped_session()` preserved for sync ORM (PatientRepository, AlertRepository)
  - Celery `.delay(...)` cross-dispatch → `await .kiq(...)` for Taskiq
  - Structured logging via log_task_start/success/error from taskiq_base
  - PII redaction via _ALERT_METADATA_REDACTED_FIELDS (imported from Celery module)

Schedule labels (1 task is periodic):
  - check_patient_alerts: interval 300s (every 5 minutes)
"""

import logging
from datetime import timedelta
from typing import Any, Dict
from uuid import UUID

from app.database import get_scoped_session
from app.taskiq_broker import broker
from app.tasks.taskiq_base import log_task_error, log_task_start, log_task_success
from app.tasks.helpers.alerts_helpers import (
    _ALERT_METADATA_REDACTED_FIELDS,
    _sanitize_alert_metadata,
    _build_patient_context,
)
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger("app.tasks.alerts_taskiq")


# ===========================================================================
# 1. check_patient_alerts — periodic (interval 300s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
    schedule=[{"interval": {"seconds": 300}}],
)
async def check_patient_alerts() -> Dict[str, Any]:
    """Periodic task to check all patients for alert conditions.

    Runs every 5 minutes to evaluate patient data against alert rules
    and trigger notifications for any matches.

    Returns:
        Dict with alerts_checked, alerts_triggered, execution_time.
    """
    start_time = log_task_start("check_patient_alerts")
    wall_clock_start = now_sao_paulo()
    alerts_checked = 0
    alerts_triggered = 0

    try:
        with get_scoped_session() as db:
            from app.services.alerts import get_alert_manager, initialize_alert_system
            from app.repositories.patient import PatientRepository

            alert_manager = get_alert_manager()
            if not getattr(alert_manager, "rule_engine", None):
                alert_manager = initialize_alert_system()

            patient_repo = PatientRepository(db)
            patients = patient_repo.get_active_patients(limit=500)

            for patient in patients:
                alerts_checked += 1
                try:
                    context = _build_patient_context(db, patient.id)
                    triggered = await alert_manager.evaluate_patient_alerts(
                        patient_id=patient.id, context=context
                    )
                    alerts_triggered += len(triggered) if triggered else 0
                except Exception as e:
                    logger.warning(
                        "Error checking alerts for patient %s: %s",
                        patient.id,
                        e,
                    )
                    continue

            execution_time = (now_sao_paulo() - wall_clock_start).total_seconds()

            log_task_success(
                "check_patient_alerts",
                start_time,
                alerts_checked=alerts_checked,
                alerts_triggered=alerts_triggered,
            )
            return {
                "success": True,
                "alerts_checked": alerts_checked,
                "alerts_triggered": alerts_triggered,
                "execution_time": execution_time,
            }

    except Exception as exc:
        log_task_error(
            "check_patient_alerts",
            exc,
            start_time,
            alerts_checked=alerts_checked,
            alerts_triggered=alerts_triggered,
        )
        raise


# ===========================================================================
# 2. periodic_alert_check — on-demand wrapper
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
)
async def periodic_alert_check() -> Dict[str, Any]:
    """Wrapper for check_patient_alerts for on-demand scheduling.

    Delegates to check_patient_alerts inline (same logic, no re-dispatch).

    Returns:
        Dict with check_patient_alerts result.
    """
    return await check_patient_alerts()


# ===========================================================================
# 3. process_alert_notification — on-demand
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=5,
    delay=30,
)
async def process_alert_notification(alert_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process and dispatch an alert notification.

    Creates alert record in DB and dispatches WebSocket notifications
    to doctor dashboard and admin channel.

    Args:
        alert_data: Dict with patient_id, doctor_id, priority, alert_type, message.

    Returns:
        Dict with alert_id and notification_sent status.
    """
    patient_id = alert_data.get("patient_id")
    alert_type = alert_data.get("alert_type") or alert_data.get("concern_type", "unknown")
    priority = alert_data.get("priority") or alert_data.get("escalation_level", "unknown")

    start_time = log_task_start(
        "process_alert_notification",
        patient_id=patient_id,
        alert_type=alert_type,
        priority=priority,
    )

    try:
        doctor_id = alert_data.get("doctor_id")
        patient_uuid = None
        doctor_uuid = None

        if patient_id:
            try:
                patient_uuid = UUID(str(patient_id))
            except ValueError:
                logger.warning("Invalid patient_id in alert payload", extra={"patient_id": patient_id})
                return {"success": False, "error": "invalid_patient_id"}

        if doctor_id:
            try:
                doctor_uuid = UUID(str(doctor_id))
            except ValueError:
                logger.warning("Invalid doctor_id in alert payload", extra={"doctor_id": doctor_id})
                return {"success": False, "error": "invalid_doctor_id"}

        message = alert_data.get("message") or alert_data.get("description", "")
        metadata = _sanitize_alert_metadata(alert_data)

        with get_scoped_session() as db:
            from app.repositories.alert import AlertRepository

            alert_repo = AlertRepository(db)

            alert = alert_repo.create(
                {
                    "patient_id": patient_uuid,
                    "doctor_id": doctor_uuid,
                    "alert_type": alert_type,
                    "severity": priority,
                    "message": message,
                    "metadata": metadata,
                    "status": "pending",
                    "created_at": now_sao_paulo(),
                }
            )

            # Dispatch WebSocket notification for real-time dashboard
            from app.services.websocket_events import websocket_events
            from app.schemas.websocket import WebSocketEventType

            notification_data = {
                "alert_id": str(alert.id) if hasattr(alert, "id") else None,
                "patient_id": patient_id,
                "alert_type": alert_type,
                "priority": priority,
                "message": message,
                "timestamp": now_sao_paulo().isoformat(),
            }

            if doctor_id:
                websocket_events.emit(
                    event_type=WebSocketEventType.ALERT_CREATED,
                    data=notification_data,
                    target_user_id=doctor_id,
                )

            websocket_events.emit(
                event_type=WebSocketEventType.ALERT_CREATED,
                data=notification_data,
                target_role="admin",
            )

            log_task_success(
                "process_alert_notification",
                start_time,
                alert_id=str(alert.id) if hasattr(alert, "id") else None,
            )
            return {
                "success": True,
                "alert_id": str(alert.id) if hasattr(alert, "id") else None,
                "notification_sent": True,
            }

    except Exception as exc:
        log_task_error(
            "process_alert_notification",
            exc,
            start_time,
            patient_id=patient_id,
            alert_type=alert_type,
        )
        raise


# ===========================================================================
# 4. process_alert_escalation — on-demand
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
)
async def process_alert_escalation(
    alert_id: str, escalation_level: str = "high"
) -> Dict[str, Any]:
    """Process escalation for an existing alert.

    Updates alert severity, marks it as escalated, and notifies admins
    via WebSocket.

    Args:
        alert_id: UUID string of alert to escalate.
        escalation_level: Target escalation level.

    Returns:
        Dict with escalation result.
    """
    start_time = log_task_start(
        "process_alert_escalation",
        alert_id=alert_id,
        escalation_level=escalation_level,
    )

    try:
        alert_uuid = UUID(alert_id)
    except ValueError:
        logger.warning("Invalid alert_id for escalation", extra={"alert_id": alert_id})
        return {"success": False, "error": "invalid_alert_id", "alert_id": alert_id}

    try:
        with get_scoped_session() as db:
            from app.repositories.alert import AlertRepository

            alert_repo = AlertRepository(db)
            alert = alert_repo.get(alert_uuid)

            if not alert:
                return {"success": False, "error": f"Alert {alert_id} not found"}

            alert_repo.update(
                alert_uuid,
                {
                    "severity": escalation_level,
                    "escalated_at": now_sao_paulo(),
                    "status": "escalated",
                },
            )

            from app.services.websocket_events import websocket_events
            from app.schemas.websocket import WebSocketEventType

            websocket_events.emit(
                event_type=WebSocketEventType.ALERT_UPDATED,
                data={
                    "alert_id": alert_id,
                    "escalation_level": escalation_level,
                    "escalated_at": now_sao_paulo().isoformat(),
                },
                target_role="admin",
            )

            log_task_success(
                "process_alert_escalation",
                start_time,
                alert_id=alert_id,
                escalated_to=escalation_level,
            )
            return {
                "success": True,
                "alert_id": alert_id,
                "escalated_to": escalation_level,
            }

    except Exception as exc:
        log_task_error(
            "process_alert_escalation",
            exc,
            start_time,
            alert_id=alert_id,
            escalation_level=escalation_level,
        )
        raise


# ===========================================================================
# 5. periodic_escalation_check — on-demand
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
)
async def periodic_escalation_check() -> Dict[str, Any]:
    """Check for alerts that need escalation based on time thresholds.

    Finds pending alerts older than 30 minutes and dispatches
    escalation tasks via process_alert_escalation.kiq().

    Returns:
        Dict with escalation check results.
    """
    start_time = log_task_start("periodic_escalation_check")
    escalated_count = 0

    try:
        with get_scoped_session() as db:
            from app.repositories.alert import AlertRepository

            alert_repo = AlertRepository(db)

            threshold_minutes = 30
            threshold_time = now_sao_paulo() - timedelta(minutes=threshold_minutes)

            pending_alerts = alert_repo.get_pending_alerts_before(threshold_time)

            for alert in pending_alerts:
                try:
                    await process_alert_escalation.kiq(
                        str(alert.id), escalation_level="high"
                    )
                    escalated_count += 1
                except Exception as e:
                    logger.warning(
                        "Failed to queue escalation for alert %s: %s",
                        alert.id,
                        e,
                    )

        log_task_success(
            "periodic_escalation_check",
            start_time,
            alerts_escalated=escalated_count,
        )
        return {"success": True, "alerts_escalated": escalated_count}

    except Exception as exc:
        log_task_error(
            "periodic_escalation_check",
            exc,
            start_time,
            alerts_escalated=escalated_count,
        )
        raise


# ===========================================================================
# 6. cleanup_resolved_alerts — on-demand
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=2,
    delay=60,
)
async def cleanup_resolved_alerts(days_old: int = 30) -> Dict[str, Any]:
    """Archive or delete old resolved alerts.

    Args:
        days_old: Number of days after which to archive resolved alerts.

    Returns:
        Dict with cleanup results.
    """
    start_time = log_task_start("cleanup_resolved_alerts", days_old=days_old)

    try:
        with get_scoped_session() as db:
            from app.repositories.alert import AlertRepository

            alert_repo = AlertRepository(db)

            cutoff_date = now_sao_paulo() - timedelta(days=days_old)
            cleaned_count = alert_repo.archive_resolved_before(cutoff_date)

            log_task_success(
                "cleanup_resolved_alerts",
                start_time,
                alerts_cleaned=cleaned_count,
            )
            return {
                "success": True,
                "alerts_cleaned": cleaned_count,
                "cutoff_date": cutoff_date.isoformat(),
            }

    except Exception as exc:
        log_task_error("cleanup_resolved_alerts", exc, start_time, days_old=days_old)
        raise


# ===========================================================================
# 7. generate_alert_metrics — on-demand
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=2,
    delay=60,
)
async def generate_alert_metrics(time_range_hours: int = 24) -> Dict[str, Any]:
    """Generate alert metrics for monitoring and reporting.

    Args:
        time_range_hours: Hours to look back for metrics.

    Returns:
        Dict with alert metrics.
    """
    start_time = log_task_start("generate_alert_metrics", time_range_hours=time_range_hours)

    try:
        with get_scoped_session() as db:
            from app.repositories.alert import AlertRepository

            alert_repo = AlertRepository(db)

            since = now_sao_paulo() - timedelta(hours=time_range_hours)

            metrics = {
                "total_alerts": alert_repo.count_since(since),
                "pending_alerts": alert_repo.count_by_status("pending"),
                "resolved_alerts": alert_repo.count_by_status_since("resolved", since),
                "escalated_alerts": alert_repo.count_by_status("escalated"),
                "average_resolution_time": alert_repo.get_avg_resolution_time(since),
                "alerts_by_type": alert_repo.count_by_type_since(since),
                "alerts_by_severity": alert_repo.count_by_severity_since(since),
                "time_range_hours": time_range_hours,
                "generated_at": now_sao_paulo().isoformat(),
            }

            log_task_success(
                "generate_alert_metrics",
                start_time,
                total_alerts=metrics["total_alerts"],
            )
            return {"success": True, "metrics": metrics}

    except Exception as exc:
        log_task_error("generate_alert_metrics", exc, start_time)
        raise


__all__ = [
    "check_patient_alerts",
    "periodic_alert_check",
    "process_alert_notification",
    "process_alert_escalation",
    "periodic_escalation_check",
    "cleanup_resolved_alerts",
    "generate_alert_metrics",
]
