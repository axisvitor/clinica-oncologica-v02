"""
Celery tasks for alert processing and escalation management.

Tasks for:
- Patient alert checking and monitoring
- Alert notification processing
- Alert escalation handling
- Metrics generation
"""
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from celery import shared_task

from app.celery_app import celery_app
from app.database import get_db
from app.tasks.base import BaseTask, get_db_session


logger = logging.getLogger(__name__)


# ============================================================================
# ALERT CHECKING TASKS
# ============================================================================

@celery_app.task(
    bind=True,
    base=BaseTask,
    name="app.tasks.alerts.check_patient_alerts",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def check_patient_alerts(self) -> Dict[str, Any]:
    """
    Periodic task to check all patients for alert conditions.

    Runs every 5 minutes to evaluate patient data against alert rules
    and trigger notifications for any matches.

    Returns:
        Dict containing:
        - alerts_checked: Number of patients checked
        - alerts_triggered: Number of alerts triggered
        - execution_time: Task execution time
    """
    start_time = datetime.utcnow()
    alerts_checked = 0
    alerts_triggered = 0

    try:
        with get_db_session() as db:
            from app.services.alerts.alert_manager import AlertManager
            from app.repositories.patient import PatientRepository

            alert_manager = AlertManager()
            patient_repo = PatientRepository(db)

            # Get patients with active monitoring
            patients = patient_repo.get_active_patients(limit=500)

            for patient in patients:
                alerts_checked += 1
                try:
                    # Evaluate alert rules for patient
                    context = _build_patient_context(db, patient.id)
                    triggered = alert_manager.evaluate_patient_alerts(
                        patient_id=patient.id,
                        context=context
                    )
                    alerts_triggered += len(triggered) if triggered else 0
                except Exception as e:
                    logger.warning(f"Error checking alerts for patient {patient.id}: {e}")
                    continue

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            logger.info(
                f"Alert check completed: checked={alerts_checked}, "
                f"triggered={alerts_triggered}, time={execution_time:.2f}s"
            )

            return {
                "success": True,
                "alerts_checked": alerts_checked,
                "alerts_triggered": alerts_triggered,
                "execution_time": execution_time
            }

    except Exception as e:
        logger.error(f"Check patient alerts failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "alerts_checked": alerts_checked,
            "alerts_triggered": alerts_triggered
        }


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="app.tasks.alerts.periodic_alert_check",
    max_retries=3,
)
def periodic_alert_check(self) -> Dict[str, Any]:
    """
    Wrapper for check_patient_alerts for periodic scheduling.
    """
    return check_patient_alerts()


# ============================================================================
# ALERT NOTIFICATION TASKS
# ============================================================================

@celery_app.task(
    bind=True,
    base=BaseTask,
    name="app.tasks.alerts.process_alert_notification",
    max_retries=5,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def process_alert_notification(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process and dispatch an alert notification.

    Args:
        alert_data: Dictionary containing:
            - patient_id: UUID string
            - patient_name: Patient name
            - doctor_id: Doctor UUID string (optional)
            - escalation_level/priority: Alert priority
            - concern_type/alert_type: Type of alert
            - description/message: Alert content

    Returns:
        Dict with notification result
    """
    try:
        patient_id = alert_data.get("patient_id")
        patient_name = alert_data.get("patient_name", "Unknown")
        doctor_id = alert_data.get("doctor_id")

        priority = alert_data.get("priority") or alert_data.get("escalation_level", "medium")
        alert_type = alert_data.get("alert_type") or alert_data.get("concern_type", "general")
        message = alert_data.get("message") or alert_data.get("description", "")

        logger.info(
            f"Processing alert notification for patient {patient_name} ({patient_id}): "
            f"type={alert_type}, priority={priority}"
        )

        with get_db_session() as db:
            # Create alert record
            from app.repositories.alert import AlertRepository

            alert_repo = AlertRepository(db)

            alert = alert_repo.create({
                "patient_id": UUID(patient_id) if patient_id else None,
                "doctor_id": UUID(doctor_id) if doctor_id else None,
                "alert_type": alert_type,
                "severity": priority,
                "message": message,
                "metadata": alert_data,
                "status": "pending",
                "created_at": datetime.utcnow()
            })

            # Dispatch notification via WebSocket for real-time dashboard
            from app.services.websocket_events import websocket_events
            from app.schemas.websocket import WebSocketEventType

            notification_data = {
                "alert_id": str(alert.id) if hasattr(alert, 'id') else None,
                "patient_id": patient_id,
                "patient_name": patient_name,
                "alert_type": alert_type,
                "priority": priority,
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }

            # Send to doctor's dashboard if doctor_id exists
            if doctor_id:
                websocket_events.emit(
                    event_type=WebSocketEventType.ALERT_CREATED,
                    data=notification_data,
                    target_user_id=doctor_id
                )

            # Also emit to admin channel
            websocket_events.emit(
                event_type=WebSocketEventType.ALERT_CREATED,
                data=notification_data,
                target_role="admin"
            )

            return {
                "success": True,
                "alert_id": str(alert.id) if hasattr(alert, 'id') else None,
                "notification_sent": True
            }

    except Exception as e:
        logger.error(f"Process alert notification failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# ALERT ESCALATION TASKS
# ============================================================================

@celery_app.task(
    bind=True,
    base=BaseTask,
    name="app.tasks.alerts.process_alert_escalation",
    max_retries=3,
    default_retry_delay=60,
)
def process_alert_escalation(self, alert_id: str, escalation_level: str = "high") -> Dict[str, Any]:
    """
    Process escalation for an existing alert.

    Args:
        alert_id: UUID string of alert to escalate
        escalation_level: Target escalation level

    Returns:
        Dict with escalation result
    """
    try:
        logger.info(f"Processing escalation for alert {alert_id} to level {escalation_level}")

        with get_db_session() as db:
            from app.repositories.alert import AlertRepository

            alert_repo = AlertRepository(db)
            alert = alert_repo.get(UUID(alert_id))

            if not alert:
                return {"success": False, "error": f"Alert {alert_id} not found"}

            # Update alert escalation
            alert_repo.update(UUID(alert_id), {
                "severity": escalation_level,
                "escalated_at": datetime.utcnow(),
                "status": "escalated"
            })

            # Notify relevant parties
            from app.services.websocket_events import websocket_events
            from app.schemas.websocket import WebSocketEventType

            websocket_events.emit(
                event_type=WebSocketEventType.ALERT_UPDATED,
                data={
                    "alert_id": alert_id,
                    "escalation_level": escalation_level,
                    "escalated_at": datetime.utcnow().isoformat()
                },
                target_role="admin"
            )

            return {
                "success": True,
                "alert_id": alert_id,
                "escalated_to": escalation_level
            }

    except Exception as e:
        logger.error(f"Process alert escalation failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="app.tasks.alerts.periodic_escalation_check",
    max_retries=3,
)
def periodic_escalation_check(self) -> Dict[str, Any]:
    """
    Check for alerts that need escalation based on time thresholds.

    Returns:
        Dict with escalation check results
    """
    escalated_count = 0

    try:
        with get_db_session() as db:
            from app.repositories.alert import AlertRepository

            alert_repo = AlertRepository(db)

            # Find pending alerts older than threshold
            threshold_minutes = 30
            threshold_time = datetime.utcnow() - timedelta(minutes=threshold_minutes)

            pending_alerts = alert_repo.get_pending_alerts_before(threshold_time)

            for alert in pending_alerts:
                try:
                    process_alert_escalation.delay(
                        str(alert.id),
                        escalation_level="high"
                    )
                    escalated_count += 1
                except Exception as e:
                    logger.warning(f"Failed to queue escalation for alert {alert.id}: {e}")

            return {
                "success": True,
                "alerts_escalated": escalated_count
            }

    except Exception as e:
        logger.error(f"Periodic escalation check failed: {e}", exc_info=True)
        return {"success": False, "error": str(e), "alerts_escalated": escalated_count}


# ============================================================================
# CLEANUP AND METRICS TASKS
# ============================================================================

@celery_app.task(
    bind=True,
    base=BaseTask,
    name="app.tasks.alerts.cleanup_resolved_alerts",
    max_retries=2,
)
def cleanup_resolved_alerts(self, days_old: int = 30) -> Dict[str, Any]:
    """
    Archive or delete old resolved alerts.

    Args:
        days_old: Number of days after which to cleanup resolved alerts

    Returns:
        Dict with cleanup results
    """
    try:
        with get_db_session() as db:
            from app.repositories.alert import AlertRepository

            alert_repo = AlertRepository(db)

            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            cleaned_count = alert_repo.archive_resolved_before(cutoff_date)

            logger.info(f"Cleaned up {cleaned_count} resolved alerts older than {days_old} days")

            return {
                "success": True,
                "alerts_cleaned": cleaned_count,
                "cutoff_date": cutoff_date.isoformat()
            }

    except Exception as e:
        logger.error(f"Cleanup resolved alerts failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="app.tasks.alerts.generate_alert_metrics",
    max_retries=2,
)
def generate_alert_metrics(self, time_range_hours: int = 24) -> Dict[str, Any]:
    """
    Generate alert metrics for monitoring and reporting.

    Args:
        time_range_hours: Hours to look back for metrics

    Returns:
        Dict with alert metrics
    """
    try:
        with get_db_session() as db:
            from app.repositories.alert import AlertRepository

            alert_repo = AlertRepository(db)

            since = datetime.utcnow() - timedelta(hours=time_range_hours)

            metrics = {
                "total_alerts": alert_repo.count_since(since),
                "pending_alerts": alert_repo.count_by_status("pending"),
                "resolved_alerts": alert_repo.count_by_status_since("resolved", since),
                "escalated_alerts": alert_repo.count_by_status("escalated"),
                "average_resolution_time": alert_repo.get_avg_resolution_time(since),
                "alerts_by_type": alert_repo.count_by_type_since(since),
                "alerts_by_severity": alert_repo.count_by_severity_since(since),
                "time_range_hours": time_range_hours,
                "generated_at": datetime.utcnow().isoformat()
            }

            logger.info(f"Alert metrics generated: {metrics['total_alerts']} total alerts in last {time_range_hours}h")

            return {
                "success": True,
                "metrics": metrics
            }

    except Exception as e:
        logger.error(f"Generate alert metrics failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _build_patient_context(db, patient_id: UUID) -> Dict[str, Any]:
    """
    Build context data for alert evaluation.

    Args:
        db: Database session
        patient_id: Patient UUID

    Returns:
        Dict with patient context data
    """
    try:
        from app.repositories.message import MessageRepository
        from app.repositories.quiz_response import QuizResponseRepository

        message_repo = MessageRepository(db)
        quiz_repo = QuizResponseRepository(db)

        # Get recent messages
        recent_messages = message_repo.get_recent_for_patient(
            patient_id,
            limit=10,
            days=7
        )

        # Get recent quiz responses
        recent_quizzes = quiz_repo.get_recent_for_patient(
            patient_id,
            limit=5,
            days=30
        )

        return {
            "patient_id": str(patient_id),
            "recent_messages": [
                {
                    "id": str(m.id),
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None
                }
                for m in (recent_messages or [])
            ],
            "recent_quizzes": [
                {
                    "id": str(q.id),
                    "score": getattr(q, 'score', None),
                    "completed_at": q.completed_at.isoformat() if hasattr(q, 'completed_at') and q.completed_at else None
                }
                for q in (recent_quizzes or [])
            ],
            "evaluation_time": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.warning(f"Failed to build patient context: {e}")
        return {
            "patient_id": str(patient_id),
            "evaluation_time": datetime.utcnow().isoformat(),
            "error": str(e)
        }


# Export all tasks
__all__ = [
    "check_patient_alerts",
    "periodic_alert_check",
    "process_alert_notification",
    "process_alert_escalation",
    "periodic_escalation_check",
    "cleanup_resolved_alerts",
    "generate_alert_metrics",
]
