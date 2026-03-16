"""
Taskiq saga monitoring tasks — async-native replacements for Celery saga_monitoring tasks (M009-S04).

3 tasks migrated from Celery to Taskiq:
  1. check_orphaned_sagas    — interval 3600s
  2. check_long_running_sagas — interval 900s
  3. generate_saga_metrics   — interval 3600s

Key translation patterns from Celery → Taskiq:
  - `get_scoped_session()` preserved for sync ORM — these tasks are already pure sync
  - No bridges to remove (no run_async, no async_to_sync)
  - Structured logging via log_task_start/success/error from taskiq_base
  - Helper functions (_alert_orphaned_saga, _generate_orphan_summary) remain in
    the Celery module — they're tightly coupled to the ORM session and are called
    inline, so we replicate the logic here (not pure stateless helpers)

Schedule labels (all 3 tasks are periodic):
  - check_orphaned_sagas:     interval 3600s
  - check_long_running_sagas: interval 900s
  - generate_saga_metrics:    interval 3600s
"""

import logging
from datetime import timedelta
from typing import Any, Dict, List

from sqlalchemy import and_

from app.database import get_scoped_session
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.models.enums import SagaStatus
from app.core.monitoring_config import capture_message, capture_exception
from app.taskiq_broker import broker
from app.tasks.taskiq_base import log_task_error, log_task_start, log_task_success
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger("app.tasks.saga_monitoring_taskiq")


# ===========================================================================
# 1. check_orphaned_sagas — periodic (interval 3600s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=2,
    delay=60,
    schedule=[{"interval": {"seconds": 3600}}],
)
async def check_orphaned_sagas() -> dict:
    """Check for orphaned sagas stuck in non-terminal states.

    An orphaned saga is one older than 4 hours that hasn't reached a
    terminal state (COMPLETED, FAILED, COMPENSATED).

    Returns:
        Dict with orphaned saga count and summary.
    """
    start_time = log_task_start("check_orphaned_sagas")

    with get_scoped_session() as db:
        try:
            terminal_states = [
                SagaStatus.COMPLETED,
                SagaStatus.FAILED,
                SagaStatus.COMPENSATED,
            ]

            orphan_threshold = now_sao_paulo() - timedelta(hours=4)

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
                log_task_success("check_orphaned_sagas", start_time, count=0)
                return {
                    "status": "success",
                    "message": "No orphaned sagas found",
                    "count": 0,
                }

            logger.warning("Found %d orphaned sagas", len(orphaned_sagas))

            # Alert for each orphaned saga
            for saga in orphaned_sagas:
                _alert_orphaned_saga(saga, db)

            summary = _generate_orphan_summary(orphaned_sagas)

            capture_message(
                f"Orphaned sagas detected: {len(orphaned_sagas)}",
                level="warning",
                extra={
                    "orphan_count": len(orphaned_sagas),
                    "summary": summary,
                },
            )

            log_task_success(
                "check_orphaned_sagas",
                start_time,
                count=len(orphaned_sagas),
            )
            return {
                "status": "success",
                "message": f"Found {len(orphaned_sagas)} orphaned sagas",
                "count": len(orphaned_sagas),
                "summary": summary,
            }

        except Exception as exc:
            log_task_error("check_orphaned_sagas", exc, start_time)
            capture_exception(exc)
            raise


# ===========================================================================
# 2. check_long_running_sagas — periodic (interval 900s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=2,
    delay=60,
    schedule=[{"interval": {"seconds": 900}}],
)
async def check_long_running_sagas() -> dict:
    """Check for sagas taking unusually long to complete.

    A long-running saga is one in STARTED/IN_PROGRESS or step states
    that has been running for more than 30 minutes.

    Returns:
        Dict with long-running saga count.
    """
    start_time = log_task_start("check_long_running_sagas")

    with get_scoped_session() as db:
        try:
            long_running_threshold = now_sao_paulo() - timedelta(minutes=30)

            long_running_sagas = (
                db.query(PatientOnboardingSaga)
                .filter(
                    and_(
                        PatientOnboardingSaga.started_at < long_running_threshold,
                        PatientOnboardingSaga.status.in_(
                            [
                                SagaStatus.STARTED,
                                SagaStatus.IN_PROGRESS,
                                SagaStatus.STEP_1_PATIENT_CREATED,
                                SagaStatus.STEP_3_FLOW_INITIALIZED,
                                SagaStatus.STEP_4_MESSAGE_SENT,
                            ]
                        ),
                        PatientOnboardingSaga.completed_at.is_(None),
                    )
                )
                .all()
            )

            if not long_running_sagas:
                log_task_success("check_long_running_sagas", start_time, count=0)
                return {
                    "status": "success",
                    "message": "No long-running sagas found",
                    "count": 0,
                }

            logger.warning("Found %d long-running sagas", len(long_running_sagas))

            for saga in long_running_sagas:
                duration = (now_sao_paulo() - saga.started_at).total_seconds() / 60
                logger.warning(
                    "Long-running saga detected: %s (running for %.1f minutes)",
                    saga.id,
                    duration,
                )

            log_task_success(
                "check_long_running_sagas",
                start_time,
                count=len(long_running_sagas),
            )
            return {
                "status": "success",
                "message": f"Found {len(long_running_sagas)} long-running sagas",
                "count": len(long_running_sagas),
            }

        except Exception as exc:
            log_task_error("check_long_running_sagas", exc, start_time)
            capture_exception(exc)
            raise


# ===========================================================================
# 3. generate_saga_metrics — periodic (interval 3600s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=2,
    delay=60,
    schedule=[{"interval": {"seconds": 3600}}],
)
async def generate_saga_metrics() -> dict:
    """Generate saga execution metrics for monitoring dashboards.

    Calculates total sagas, success/retry/compensation rates, and
    average execution time over the last 24 hours.

    Returns:
        Dict with saga metrics.
    """
    start_time = log_task_start("generate_saga_metrics")

    with get_scoped_session() as db:
        try:
            time_window = now_sao_paulo() - timedelta(hours=24)

            recent_sagas = (
                db.query(PatientOnboardingSaga)
                .filter(PatientOnboardingSaga.created_at >= time_window)
                .all()
            )

            if not recent_sagas:
                log_task_success("generate_saga_metrics", start_time, total_sagas=0)
                return {
                    "status": "success",
                    "message": "No recent sagas to analyze",
                    "metrics": {},
                }

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

            success_rate = (completed_sagas / total_sagas * 100) if total_sagas > 0 else 0
            retry_rate = (retried_sagas / total_sagas * 100) if total_sagas > 0 else 0
            compensation_rate = (
                (compensated_sagas / total_sagas * 100) if total_sagas > 0 else 0
            )

            completed_with_time = [
                s
                for s in recent_sagas
                if s.status == SagaStatus.COMPLETED and s.completed_at
            ]
            if completed_with_time:
                avg_execution_time = sum(
                    (s.completed_at - s.started_at).total_seconds()
                    for s in completed_with_time
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

            logger.info("Saga metrics generated: %s", metrics)

            log_task_success(
                "generate_saga_metrics",
                start_time,
                total_sagas=total_sagas,
                success_rate=metrics["success_rate_percent"],
            )
            return {
                "status": "success",
                "message": "Saga metrics generated",
                "metrics": metrics,
            }

        except Exception as exc:
            log_task_error("generate_saga_metrics", exc, start_time)
            capture_exception(exc)
            raise


# ============================================================================
# Helper Functions — inline (tightly coupled to ORM session, not pure helpers)
# ============================================================================


def _alert_orphaned_saga(saga: PatientOnboardingSaga, db: Any) -> None:
    """Send alert for an orphaned saga."""
    try:
        duration = (now_sao_paulo() - saga.created_at).total_seconds() / 3600

        logger.error(
            "ORPHANED SAGA DETECTED: %s (age: %.1fh, status: %s, step: %s)",
            saga.id,
            duration,
            saga.status,
            saga.current_step,
        )

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

        from app.models.alert import Alert, AlertType, AlertPriority

        alert = Alert(
            alert_type=AlertType.SYSTEM,
            priority=AlertPriority.MEDIUM,
            title=f"Orphaned Saga Detected: {saga.id}",
            message=(
                f"Saga has been stuck in {saga.status} state for {duration:.1f} hours. "
                f"Current step: {saga.current_step}. Manual investigation required."
            ),
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

    except Exception as e:
        logger.error("Failed to send orphaned saga alert for %s: %s", saga.id, e)


def _generate_orphan_summary(sagas: List[PatientOnboardingSaga]) -> Dict[str, Any]:
    """Generate summary of orphaned sagas."""
    status_counts: Dict[str, int] = {}
    step_counts: Dict[str, int] = {}

    for saga in sagas:
        status = saga.status.value if saga.status else "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        step_counts[saga.current_step] = step_counts.get(saga.current_step, 0) + 1

    return {
        "total": len(sagas),
        "by_status": status_counts,
        "by_step": step_counts,
        "oldest_saga_age_hours": round(
            max(
                (now_sao_paulo() - s.created_at).total_seconds() / 3600
                for s in sagas
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
