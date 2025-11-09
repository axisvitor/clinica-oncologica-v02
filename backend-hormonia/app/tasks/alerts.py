"""
Celery tasks for alert processing.

Uses consolidated alert system (QW-020).
Legacy system archived in legacy/alerts_archive_2025-11-09/
"""

import logging
from uuid import UUID
from typing import List
from datetime import datetime, timedelta

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.patient import Patient
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.tasks.base import BaseTask, get_db_session
from app.services.alerts import AlertManagerAdapter

logger = logging.getLogger(__name__)


def _get_alert_service(db) -> AlertManagerAdapter:
    """
    Get the consolidated alert service.

    Returns:
        AlertManagerAdapter instance
    """
    return AlertManagerAdapter(db)


def _get_alert_processor(db) -> AlertManagerAdapter:
    """
    Get the consolidated alert processor.

    AlertManagerAdapter handles both service and processor functions.

    Returns:
        AlertManagerAdapter instance
    """
    return AlertManagerAdapter(db)


@celery_app.task(bind=True, base=BaseTask, max_retries=3)
def check_patient_alerts(self, patient_ids: List[str] = None):
    """Check for patient alerts across all patients or specific patients.

    Args:
        patient_ids (List[str], optional): List of patient UUIDs to check.
            If None, checks all active patients. Defaults to None.

    Returns:
        dict: Dictionary containing:
            - status (str): Task completion status
            - patients_checked (int): Number of patients checked
            - alerts_generated (int): Number of alerts generated

    Raises:
        Retry: If the task should be retried due to transient failures
    """
    self.log_task_start(patient_ids=patient_ids)

    try:
        with get_db_session() as db:
            alert_system = _get_alert_service(db)
            alert_processor = _get_alert_processor(db)

            # Get patients to check
            if patient_ids:
                patients = [
                    db.query(Patient).filter(Patient.id == UUID(pid)).first()
                    for pid in patient_ids
                ]
                patients = [p for p in patients if p]  # Filter out None values
            else:
                # Check all active patients
                patients = (
                    db.query(Patient)
                    .filter(Patient.flow_state.in_(["active", "onboarding"]))
                    .all()
                )

            total_alerts_generated = 0

            for patient in patients:
                try:
                    # Evaluate alerts for this patient
                    alerts = alert_system.evaluate_patient_alerts(patient.id)

                    # Process each generated alert
                    for alert in alerts:
                        result = alert_processor.process_alert(alert)
                        self.get_task_logger().info(
                            f"Processed alert for patient {patient.id}: {result}"
                        )
                        total_alerts_generated += 1

                except Exception as e:
                    self.get_task_logger().error(
                        f"Error checking alerts for patient {patient.id}: {e}"
                    )
                    continue

            result = self.create_success_result(
                status="completed",
                patients_checked=len(patients),
                alerts_generated=total_alerts_generated,
            )

            self.log_task_success(result, patient_ids=patient_ids)
            return result

    except Exception as e:
        self.log_task_error(e, patient_ids=patient_ids)
        return self.handle_retry(e, countdown=60)


@celery_app.task(bind=True, base=BaseTask, max_retries=3)
def process_alert_escalation(self, alert_id: str):
    """Process escalation for a specific alert.

    Args:
        alert_id (str): UUID of the alert to escalate

    Returns:
        dict: Escalation processing result

    Raises:
        Retry: If the task should be retried due to transient failures
    """
    self.log_task_start(alert_id=alert_id)

    try:
        with get_db_session() as db:
            alert_processor = _get_alert_processor(db)

            result = alert_processor.process_escalation(UUID(alert_id))

            self.log_task_success(result, alert_id=alert_id)
            return result

    except Exception as e:
        self.log_task_error(e, alert_id=alert_id)
        return self.handle_retry(e, countdown=300)  # Retry after 5 minutes


@celery_app.task(bind=True, base=BaseTask, max_retries=3)
def process_alert_notification(self, alert_id: str):
    """Process notifications for a specific alert.

    Args:
        alert_id (str): UUID of the alert to send notifications for

    Returns:
        dict: Dictionary containing:
            - status (str): Processing status
            - alert_id (str): The alert ID
            - notifications (dict): Notification results
            - message (str): Error message (if failed)

    Raises:
        Retry: If the task should be retried due to transient failures
    """
    self.log_task_start(alert_id=alert_id)

    try:
        with get_db_session() as db:
            alert_system = _get_alert_service(db)
            alert_processor = _get_alert_processor(db)

            alert = alert_system.alert_repo.get(UUID(alert_id))
            if not alert:
                error_msg = "Alert not found"
                self.get_task_logger().error(f"Alert {alert_id} not found")
                return self.create_error_result(error_msg, alert_id=alert_id)

            # Send notifications
            notification_results = alert_processor._send_notifications(alert)

            result = self.create_success_result(
                status="completed",
                alert_id=alert_id,
                notifications=notification_results,
            )

            self.log_task_success(result, alert_id=alert_id)
            return result

    except Exception as e:
        self.log_task_error(e, alert_id=alert_id)
        return self.handle_retry(e, countdown=60)


@celery_app.task(bind=True, base=BaseTask)
def cleanup_resolved_alerts(self):
    """Clean up old resolved alerts to maintain database performance.

    Deletes resolved alerts older than 90 days to keep the database optimized.

    Returns:
        dict: Dictionary containing:
            - status (str): Task completion status
            - deleted_count (int): Number of alerts deleted
            - cutoff_date (str): ISO timestamp of cutoff date

    Raises:
        Exception: If database operations fail
    """
    self.log_task_start()

    try:
        with get_db_session() as db:
            # Delete resolved alerts older than 90 days
            cutoff_date = datetime.utcnow() - timedelta(days=90)

            deleted_count = (
                db.query(Alert)
                .filter(Alert.status == AlertStatus.RESOLVED)
                .filter(Alert.resolved_at < cutoff_date)
                .delete()
            )

            db.commit()

            result = self.create_success_result(
                status="completed",
                deleted_count=deleted_count,
                cutoff_date=cutoff_date.isoformat(),
            )

            self.log_task_success(result)
            return result

    except Exception as e:
        self.log_task_error(e)
        raise


@celery_app.task(bind=True, base=BaseTask)
def generate_alert_metrics(self):
    """Generate alert system metrics for monitoring.

    Collects and calculates various metrics about the alert system performance
    including recent activity and response times.

    Returns:
        dict: Dictionary containing alert statistics and recent metrics:
            - recent_metrics (dict): Metrics from last 24 hours
            - alerts_last_24h (int): Number of alerts in last 24 hours
            - critical_last_24h (int): Number of critical alerts
            - escalation_rate (float): Rate of alerts that were escalated

    Raises:
        Exception: If metrics calculation fails
    """
    self.log_task_start()

    try:
        with get_db_session() as db:
            alert_system = _get_alert_service(db)

            stats = alert_system.get_alert_statistics()

            # Get alerts from last 24 hours
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_alerts = db.query(Alert).filter(Alert.created_at >= yesterday).all()

            stats["recent_metrics"] = {
                "alerts_last_24h": len(recent_alerts),
                "critical_last_24h": len(
                    [a for a in recent_alerts if a.severity == AlertSeverity.CRITICAL]
                ),
                "avg_response_time_minutes": 0,  # Would calculate from acknowledgment times
                "escalation_rate": len(
                    [
                        a
                        for a in recent_alerts
                        if a.data
                        and a.data.get("escalation", {}).get("current_escalation", 0)
                        > 0
                    ]
                )
                / len(recent_alerts)
                if recent_alerts
                else 0,
            }

            self.log_task_success(stats)
            return stats

    except Exception as e:
        self.log_task_error(e)
        raise


# Periodic task to check for alerts every 15 minutes
@celery_app.task
def periodic_alert_check():
    """Periodic task to check for new alerts.

    Scheduled task that runs every 15 minutes to check for new patient alerts.

    Returns:
        AsyncResult: Celery task result for the alert check
    """
    return check_patient_alerts.delay()


# Periodic task to process escalations every 5 minutes
@celery_app.task(bind=True, base=BaseTask)
def periodic_escalation_check(self):
    """Check for alerts that need escalation.

    Scheduled task that runs every 5 minutes to process alert escalations.

    Returns:
        dict: Results of escalation processing
    """
    self.log_task_start()

    try:
        with get_db_session() as db:
            # Find alerts that need escalation
            alerts_needing_escalation = (
                db.query(Alert).filter(Alert.status == AlertStatus.PENDING).all()
            )

            escalated_count = 0

            for alert in alerts_needing_escalation:
                if not alert.data or "escalation" not in alert.data:
                    continue

                escalation_data = alert.data["escalation"]
                next_escalation_str = escalation_data.get("next_escalation_at")

                if next_escalation_str:
                    next_escalation = datetime.fromisoformat(
                        next_escalation_str.replace("Z", "+00:00")
                    )
                    if datetime.utcnow() >= next_escalation:
                        # Schedule escalation task
                        process_alert_escalation.delay(str(alert.id))
                        escalated_count += 1

            result = self.create_success_result(escalated_count=escalated_count)
            self.log_task_success(result)
            return result

    except Exception as e:
        self.log_task_error(e)
        raise
