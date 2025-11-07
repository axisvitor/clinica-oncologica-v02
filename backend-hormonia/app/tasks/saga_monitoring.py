"""
Celery tasks for saga monitoring and health checks.

This module implements monitoring tasks to detect and alert on saga anomalies:
- Orphaned sagas (stuck in non-terminal states)
- Long-running sagas
- Saga health metrics
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from uuid import UUID

from celery import shared_task
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient_onboarding_saga import PatientOnboardingSaga, SagaStatus
from app.core.monitoring import capture_message, capture_exception
from app.config import settings

logger = logging.getLogger(__name__)


@shared_task(name="app.tasks.saga_monitoring.check_orphaned_sagas")
def check_orphaned_sagas() -> dict:
    """
    Check for orphaned sagas that are stuck in non-terminal states.

    An orphaned saga is one that:
    - Is older than 24 hours
    - Is not in a terminal state (COMPLETED, FAILED, COMPENSATED)
    - Has not been updated recently

    Returns:
        dict: Summary of orphaned sagas found and alerts sent
    """
    db = next(get_db())

    try:
        logger.info("Starting orphaned saga detection...")

        # Define terminal states
        terminal_states = [
            SagaStatus.COMPLETED,
            SagaStatus.FAILED,
            SagaStatus.COMPENSATED,
        ]

        # Define threshold for orphan detection (24 hours)
        orphan_threshold = datetime.utcnow() - timedelta(hours=24)

        # Query for orphaned sagas
        orphaned_sagas = (
            db.query(PatientOnboardingSaga)
            .filter(
                and_(
                    PatientOnboardingSaga.created_at < orphan_threshold,
                    PatientOnboardingSaga.status.notin_(terminal_states),
                )
            )
            .all()
        )

        if not orphaned_sagas:
            logger.info("No orphaned sagas detected")
            return {
                "status": "success",
                "message": "No orphaned sagas found",
                "count": 0,
            }

        logger.warning(f"Found {len(orphaned_sagas)} orphaned sagas")

        # Send alerts for each orphaned saga
        for saga in orphaned_sagas:
            _alert_orphaned_saga(saga, db)

        # Log summary
        summary = _generate_orphan_summary(orphaned_sagas)

        logger.warning(
            f"Orphaned saga detection complete: {len(orphaned_sagas)} sagas found"
        )

        # Send summary to monitoring
        capture_message(
            f"Orphaned sagas detected: {len(orphaned_sagas)}",
            level="warning",
            extra={
                "orphan_count": len(orphaned_sagas),
                "summary": summary,
            },
        )

        return {
            "status": "success",
            "message": f"Found {len(orphaned_sagas)} orphaned sagas",
            "count": len(orphaned_sagas),
            "summary": summary,
        }

    except Exception as e:
        logger.error(f"Error checking for orphaned sagas: {e}", exc_info=True)
        capture_exception(e)
        return {
            "status": "error",
            "message": str(e),
        }

    finally:
        db.close()


@shared_task(name="app.tasks.saga_monitoring.check_long_running_sagas")
def check_long_running_sagas() -> dict:
    """
    Check for sagas that are taking unusually long to complete.

    A long-running saga is one that:
    - Is still in STARTED or IN_PROGRESS state
    - Has been running for more than 30 minutes

    Returns:
        dict: Summary of long-running sagas found
    """
    db = next(get_db())

    try:
        logger.info("Starting long-running saga detection...")

        # Define threshold for long-running detection (30 minutes)
        long_running_threshold = datetime.utcnow() - timedelta(minutes=30)

        # Query for long-running sagas
        long_running_sagas = (
            db.query(PatientOnboardingSaga)
            .filter(
                and_(
                    PatientOnboardingSaga.started_at < long_running_threshold,
                    PatientOnboardingSaga.status.in_(
                        [SagaStatus.STARTED, SagaStatus.IN_PROGRESS]
                    ),
                    PatientOnboardingSaga.completed_at.is_(None),
                )
            )
            .all()
        )

        if not long_running_sagas:
            logger.info("No long-running sagas detected")
            return {
                "status": "success",
                "message": "No long-running sagas found",
                "count": 0,
            }

        logger.warning(f"Found {len(long_running_sagas)} long-running sagas")

        # Send alerts
        for saga in long_running_sagas:
            duration = (datetime.utcnow() - saga.started_at).total_seconds() / 60
            logger.warning(
                f"Long-running saga detected: {saga.id} (running for {duration:.1f} minutes)"
            )

        return {
            "status": "success",
            "message": f"Found {len(long_running_sagas)} long-running sagas",
            "count": len(long_running_sagas),
        }

    except Exception as e:
        logger.error(f"Error checking for long-running sagas: {e}", exc_info=True)
        capture_exception(e)
        return {
            "status": "error",
            "message": str(e),
        }

    finally:
        db.close()


@shared_task(name="app.tasks.saga_monitoring.generate_saga_metrics")
def generate_saga_metrics() -> dict:
    """
    Generate saga execution metrics for monitoring dashboards.

    Metrics calculated:
    - Total sagas created (last 24h)
    - Success rate
    - Average execution time
    - Retry rate
    - Compensation rate

    Returns:
        dict: Saga metrics
    """
    db = next(get_db())

    try:
        logger.info("Generating saga metrics...")

        # Define time window (last 24 hours)
        time_window = datetime.utcnow() - timedelta(hours=24)

        # Query sagas in time window
        recent_sagas = (
            db.query(PatientOnboardingSaga)
            .filter(PatientOnboardingSaga.created_at >= time_window)
            .all()
        )

        if not recent_sagas:
            return {
                "status": "success",
                "message": "No recent sagas to analyze",
                "metrics": {},
            }

        # Calculate metrics
        total_sagas = len(recent_sagas)
        completed_sagas = len(
            [s for s in recent_sagas if s.status == SagaStatus.COMPLETED]
        )
        failed_sagas = len(
            [s for s in recent_sagas if s.status == SagaStatus.FAILED]
        )
        compensated_sagas = len(
            [s for s in recent_sagas if s.status == SagaStatus.COMPENSATED]
        )
        retried_sagas = len([s for s in recent_sagas if s.retry_count > 0])

        # Calculate rates
        success_rate = (completed_sagas / total_sagas * 100) if total_sagas > 0 else 0
        retry_rate = (retried_sagas / total_sagas * 100) if total_sagas > 0 else 0
        compensation_rate = (
            (compensated_sagas / total_sagas * 100) if total_sagas > 0 else 0
        )

        # Calculate average execution time (for completed sagas)
        completed_with_time = [
            s
            for s in recent_sagas
            if s.status == SagaStatus.COMPLETED and s.completed_at
        ]
        if completed_with_time:
            avg_execution_time = sum(
                [
                    (s.completed_at - s.started_at).total_seconds()
                    for s in completed_with_time
                ]
            ) / len(completed_with_time)
        else:
            avg_execution_time = 0

        metrics = {
            "time_window_hours": 24,
            "total_sagas": total_sagas,
            "completed": completed_sagas,
            "failed": failed_sagas,
            "compensated": compensated_sagas,
            "retried": retried_sagas,
            "success_rate_percent": round(success_rate, 2),
            "retry_rate_percent": round(retry_rate, 2),
            "compensation_rate_percent": round(compensation_rate, 2),
            "avg_execution_time_seconds": round(avg_execution_time, 2),
        }

        logger.info(f"Saga metrics generated: {metrics}")

        return {
            "status": "success",
            "message": "Saga metrics generated",
            "metrics": metrics,
        }

    except Exception as e:
        logger.error(f"Error generating saga metrics: {e}", exc_info=True)
        capture_exception(e)
        return {
            "status": "error",
            "message": str(e),
        }

    finally:
        db.close()


# ============================================================================
# Helper Functions
# ============================================================================


def _alert_orphaned_saga(saga: PatientOnboardingSaga, db: Session) -> None:
    """
    Send alert for orphaned saga.

    Args:
        saga: Orphaned saga instance
        db: Database session
    """
    try:
        duration = (datetime.utcnow() - saga.created_at).total_seconds() / 3600

        logger.error(
            f"ORPHANED SAGA DETECTED: {saga.id} "
            f"(age: {duration:.1f}h, status: {saga.status}, step: {saga.current_step})"
        )

        # Send to Sentry
        capture_message(
            f"Orphaned saga detected: {saga.id}",
            level="error",
            extra={
                "saga_id": str(saga.id),
                "patient_id": str(saga.patient_id) if saga.patient_id else None,
                "doctor_id": str(saga.doctor_id),
                "status": saga.status.value if saga.status else None,
                "current_step": saga.current_step,
                "created_at": saga.created_at.isoformat() if saga.created_at else None,
                "age_hours": round(duration, 2),
                "retry_count": saga.retry_count,
            },
        )

        # Create database alert
        from app.models.alert import Alert, AlertType, AlertPriority

        alert = Alert(
            alert_type=AlertType.SYSTEM,
            priority=AlertPriority.MEDIUM,
            title=f"Orphaned Saga Detected: {saga.id}",
            message=f"Saga has been stuck in {saga.status} state for {duration:.1f} hours. "
            f"Current step: {saga.current_step}. Manual investigation required.",
            metadata={
                "saga_id": str(saga.id),
                "patient_id": str(saga.patient_id) if saga.patient_id else None,
                "doctor_id": str(saga.doctor_id),
                "status": saga.status.value if saga.status else None,
                "current_step": saga.current_step,
                "age_hours": round(duration, 2),
                "retry_count": saga.retry_count,
            },
            doctor_id=saga.doctor_id,
        )

        db.add(alert)
        db.commit()

        logger.info(f"Alert created for orphaned saga {saga.id}")

    except Exception as e:
        logger.error(f"Failed to send orphaned saga alert for {saga.id}: {e}")


def _generate_orphan_summary(sagas: List[PatientOnboardingSaga]) -> Dict[str, Any]:
    """
    Generate summary of orphaned sagas.

    Args:
        sagas: List of orphaned sagas

    Returns:
        Summary dictionary
    """
    status_counts = {}
    step_counts = {}

    for saga in sagas:
        # Count by status
        status = saga.status.value if saga.status else "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1

        # Count by step
        step_counts[saga.current_step] = step_counts.get(saga.current_step, 0) + 1

    return {
        "total": len(sagas),
        "by_status": status_counts,
        "by_step": step_counts,
        "oldest_saga_age_hours": round(
            max(
                [
                    (datetime.utcnow() - s.created_at).total_seconds() / 3600
                    for s in sagas
                ]
            ),
            2,
        )
        if sagas
        else 0,
    }


__all__ = [
    "check_orphaned_sagas",
    "check_long_running_sagas",
    "generate_saga_metrics",
]
