"""
Background tasks for automatic retry of failed patient onboarding sagas.

This module implements the retry mechanism for sagas that failed during
patient onboarding, ensuring eventual consistency and high success rates.

Features:
- Periodic scanning for failed sagas
- Exponential backoff retry strategy
- Maximum retry limit (3 attempts)
- Admin alerting after max retries exceeded
- Metrics tracking for monitoring
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.database import get_db
from app.task_queue import task_queue as celery_app
from app.utils.async_helpers import run_async
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.models.enums import SagaStatus
from app.orchestration.saga_orchestrator import SagaOrchestrator
from app.core.redis_client import get_redis_client
from app.core.monitoring_config import capture_exception, capture_message
from app.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(
    name="retry_patient_onboarding_saga",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def retry_patient_onboarding_saga(self, saga_id: str) -> dict:
    """
    Retry a specific failed patient onboarding saga.

    This task attempts to resume a failed saga from the last successful step.
    If the saga fails again, it will be retried with exponential backoff.

    Args:
        saga_id: UUID of the saga to retry

    Returns:
        dict: Result of the retry attempt with status and details

    Raises:
        Exception: If retry fails after max attempts
    """
    db = next(get_db())
    redis_client = get_redis_client()

    try:
        # Fetch saga from database
        saga = (
            db.query(PatientOnboardingSaga)
            .filter(PatientOnboardingSaga.id == UUID(saga_id))
            .first()
        )

        if not saga:
            logger.error(f"Saga not found: {saga_id}")
            return {"status": "error", "message": "Saga not found"}

        # Check if saga is eligible for retry
        if saga.status not in [SagaStatus.FAILED, SagaStatus.COMPENSATING]:
            logger.info(f"Saga {saga_id} is not in a retryable state: {saga.status}")
            return {
                "status": "skipped",
                "message": f"Saga status is {saga.status}, not retryable",
            }

        # Check retry count
        if saga.retry_count >= getattr(settings, "SAGA_MAX_RETRIES", 3):
            logger.warning(
                f"Saga {saga_id} has exceeded max retries ({saga.retry_count})"
            )
            run_async(_alert_admin_max_retries_exceeded(saga, db))
            return {
                "status": "max_retries_exceeded",
                "message": f"Saga has been retried {saga.retry_count} times",
                "saga_id": saga_id,
            }

        # Calculate backoff delay
        backoff_seconds = _calculate_exponential_backoff(saga.retry_count)
        if saga.last_retry_at:
            next_retry_time = saga.last_retry_at + timedelta(seconds=backoff_seconds)
            if datetime.now(timezone.utc) < next_retry_time:
                logger.info(
                    f"Saga {saga_id} not ready for retry yet (backoff: {backoff_seconds}s)"
                )
                return {
                    "status": "backoff",
                    "message": f"Waiting for backoff period ({backoff_seconds}s)",
                    "next_retry_at": next_retry_time.isoformat(),
                }

        # Increment retry count
        saga.retry_count += 1
        saga.last_retry_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            f"Retrying saga {saga_id} (attempt {saga.retry_count}/{getattr(settings, 'SAGA_MAX_RETRIES', 3)})"
        )

        # Initialize saga orchestrator
        orchestrator = SagaOrchestrator(db=db, redis_client=redis_client)

        # Attempt to resume saga from last successful step (using run_async for event loop reuse)
        result = run_async(orchestrator.resume_saga(saga_id=UUID(saga_id)))

        if result["status"] == "completed":
            logger.info(f"Saga {saga_id} completed successfully on retry")
            capture_message(
                f"Saga retry successful: {saga_id}",
                level="info",
                extra={"saga_id": saga_id, "retry_count": saga.retry_count},
            )
            return {
                "status": "success",
                "message": "Saga completed successfully",
                "saga_id": saga_id,
                "retry_count": saga.retry_count,
            }
        else:
            logger.warning(
                f"Saga {saga_id} failed again on retry: {result.get('error')}"
            )
            # Will be retried by scheduler if under max retries
            return {
                "status": "failed",
                "message": result.get("error", "Unknown error"),
                "saga_id": saga_id,
                "retry_count": saga.retry_count,
            }

    except Exception as e:
        logger.error(f"Error retrying saga {saga_id}: {e}", exc_info=True)
        capture_exception(e)

        # Retry this task with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2**self.request.retries))

    finally:
        db.close()


@celery_app.task(
    name="scan_and_retry_failed_sagas",
    bind=True,
)
def scan_and_retry_failed_sagas(self) -> dict:
    """
    Periodic task to scan for failed sagas and schedule retries.

    This task runs every 5 minutes (configured in Celery beat schedule)
    and identifies sagas that are eligible for retry.

    Returns:
        dict: Summary of sagas found and retry tasks scheduled
    """
    db = next(get_db())

    try:
        logger.info("Starting scan for failed sagas...")

        # Find failed sagas eligible for retry
        failed_sagas = _find_failed_sagas_for_retry(db)

        if not failed_sagas:
            logger.info("No failed sagas found for retry")
            return {
                "status": "success",
                "message": "No failed sagas to retry",
                "count": 0,
            }

        logger.info(f"Found {len(failed_sagas)} failed sagas eligible for retry")

        # Schedule retry tasks for each saga
        scheduled_count = 0
        max_retries_count = 0

        for saga in failed_sagas:
            try:
                # Check if already at max retries
                if saga.retry_count >= getattr(settings, "SAGA_MAX_RETRIES", 3):
                    logger.warning(f"Saga {saga.id} has exceeded max retries, skipping")
                    max_retries_count += 1
                    continue

                # Schedule retry task
                retry_patient_onboarding_saga.apply_async(
                    args=[str(saga.id)],
                    countdown=_calculate_exponential_backoff(saga.retry_count),
                )

                scheduled_count += 1
                logger.info(f"Scheduled retry for saga {saga.id}")

            except Exception as e:
                logger.error(f"Failed to schedule retry for saga {saga.id}: {e}")
                continue

        logger.info(
            f"Scan complete: {scheduled_count} retries scheduled, {max_retries_count} max retries exceeded"
        )

        return {
            "status": "success",
            "message": f"Scheduled {scheduled_count} retry tasks",
            "total_found": len(failed_sagas),
            "scheduled": scheduled_count,
            "max_retries_exceeded": max_retries_count,
        }

    except Exception as e:
        logger.error(f"Error scanning for failed sagas: {e}", exc_info=True)
        capture_exception(e)
        return {
            "status": "error",
            "message": str(e),
        }

    finally:
        db.close()


@celery_app.task(name="cleanup_old_completed_sagas")
def cleanup_old_completed_sagas() -> dict:
    """
    Clean up completed sagas older than retention period.

    This task runs daily and removes completed saga records older than
    the configured retention period (default: 30 days).

    Returns:
        dict: Summary of cleanup operation
    """
    db = next(get_db())

    try:
        retention_days = getattr(settings, "SAGA_RETENTION_DAYS", 30)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        logger.info(
            f"Starting cleanup of completed sagas older than {retention_days} days"
        )

        # Find old completed sagas
        old_sagas = (
            db.query(PatientOnboardingSaga)
            .filter(
                and_(
                    PatientOnboardingSaga.status == SagaStatus.COMPLETED,
                    PatientOnboardingSaga.completed_at < cutoff_date,
                )
            )
            .all()
        )

        if not old_sagas:
            logger.info("No old completed sagas to clean up")
            return {
                "status": "success",
                "message": "No old sagas to clean up",
                "deleted_count": 0,
            }

        # Delete old sagas
        deleted_count = 0
        for saga in old_sagas:
            try:
                db.delete(saga)
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete saga {saga.id}: {e}")
                continue

        db.commit()

        logger.info(f"Cleanup complete: {deleted_count} old sagas deleted")

        return {
            "status": "success",
            "message": f"Deleted {deleted_count} old completed sagas",
            "deleted_count": deleted_count,
        }

    except Exception as e:
        logger.error(f"Error cleaning up old sagas: {e}", exc_info=True)
        capture_exception(e)
        db.rollback()
        return {
            "status": "error",
            "message": str(e),
        }

    finally:
        db.close()


# ============================================================================
# Helper Functions
# ============================================================================


def _find_failed_sagas_for_retry(db: Session) -> List[PatientOnboardingSaga]:
    """
    Find failed sagas that are eligible for retry.

    A saga is eligible if:
    - Status is FAILED or COMPENSATING
    - Retry count < max retries
    - Last retry was more than backoff period ago (or never retried)

    Args:
        db: Database session

    Returns:
        List of PatientOnboardingSaga objects eligible for retry
    """
    max_retries = getattr(settings, "SAGA_MAX_RETRIES", 3)

    # Query for failed sagas
    query = db.query(PatientOnboardingSaga).filter(
        and_(
            PatientOnboardingSaga.status.in_(
                [SagaStatus.FAILED, SagaStatus.COMPENSATING]
            ),
            PatientOnboardingSaga.retry_count < max_retries,
        )
    )

    failed_sagas = query.all()

    # Filter by backoff period
    eligible_sagas = []
    for saga in failed_sagas:
        if _is_ready_for_retry(saga):
            eligible_sagas.append(saga)

    return eligible_sagas


def _is_ready_for_retry(saga: PatientOnboardingSaga) -> bool:
    """
    Check if saga is ready for retry based on backoff period.

    Args:
        saga: PatientOnboardingSaga object

    Returns:
        bool: True if saga is ready for retry
    """
    # If never retried, ready immediately
    if not saga.last_retry_at:
        return True

    # Calculate backoff period
    backoff_seconds = _calculate_exponential_backoff(saga.retry_count)
    next_retry_time = saga.last_retry_at + timedelta(seconds=backoff_seconds)

    # Check if backoff period has elapsed
    return datetime.now(timezone.utc) >= next_retry_time


def _calculate_exponential_backoff(retry_count: int) -> int:
    """Calculate exponential backoff delay in seconds."""
    # Backoff formula: base_delay * (2 ^ retry_count)
    # Examples:
    #   Retry 1 -> 60s (1 min)
    #   Retry 2 -> 120s (2 min)
    #   Retry 3 -> 240s (4 min)
    base_delay = getattr(settings, "SAGA_RETRY_BASE_DELAY_SECONDS", 60)
    max_delay = getattr(settings, "SAGA_RETRY_MAX_DELAY_SECONDS", 600)  # 10 min

    delay = base_delay * (2**retry_count)

    # Cap at max delay
    return min(delay, max_delay)


async def _alert_admin_max_retries_exceeded(
    saga: PatientOnboardingSaga, db: Session
) -> None:
    """
    Alert admin when a saga exceeds maximum retry attempts.

    Sends alerts via:
    - Sentry (error tracking)
    - Email (if configured)
    - Database alert record

    Args:
        saga: PatientOnboardingSaga that exceeded max retries
        db: Database session
    """
    try:
        logger.error(f"ALERT: Saga {saga.id} exceeded max retries ({saga.retry_count})")

        # Send to Sentry
        capture_message(
            f"Saga max retries exceeded: {saga.id}",
            level="error",
            extra={
                "saga_id": str(saga.id),
                "patient_id": str(saga.patient_id) if saga.patient_id else None,
                "doctor_id": str(saga.doctor_id),
                "retry_count": saga.retry_count,
                "error_message": saga.error_message,
                "last_step": saga.current_step,
                "created_at": saga.created_at.isoformat(),
            },
        )

        # Create alert record in database
        from app.models.alert import Alert, AlertType, AlertPriority

        alert = Alert(
            alert_type=AlertType.SYSTEM,
            priority=AlertPriority.HIGH,
            title=f"Patient Onboarding Saga Failed: {saga.id}",
            message=f"Saga for patient onboarding exceeded max retry attempts ({saga.retry_count}). "
            f"Last error: {saga.error_message or 'Unknown error'}. "
            f"Manual intervention required.",
            metadata={
                "saga_id": str(saga.id),
                "patient_id": str(saga.patient_id) if saga.patient_id else None,
                "doctor_id": str(saga.doctor_id),
                "retry_count": saga.retry_count,
                "current_step": saga.current_step,
                "error_message": saga.error_message,
            },
            doctor_id=saga.doctor_id,
        )

        db.add(alert)
        db.commit()

        logger.info(f"Alert created for saga {saga.id} max retries exceeded")

        # Send email if configured
        if getattr(settings, "ENABLE_ADMIN_EMAIL_ALERTS", False):
            await _send_admin_email_alert(saga)

    except Exception as e:
        logger.error(f"Failed to send admin alert for saga {saga.id}: {e}")
        capture_exception(e)


async def _send_admin_email_alert(saga: PatientOnboardingSaga) -> None:
    """
    Send email alert to admin about failed saga.

    Args:
        saga: PatientOnboardingSaga that failed
    """
    try:
        from app.services.email import send_email

        subject = f"[URGENT] Patient Onboarding Saga Failed: {saga.id}"

        body = f'''
        <h2>Patient Onboarding Saga Failed</h2>

        <p>A patient onboarding saga has exceeded the maximum retry attempts and requires manual intervention.</p>

        <h3>Saga Details:</h3>
        <ul>
            <li><strong>Saga ID:</strong> {saga.id}</li>
            <li><strong>Patient ID:</strong> {saga.patient_id or "Not created yet"}</li>
            <li><strong>Doctor ID:</strong> {saga.doctor_id}</li>
            <li><strong>Status:</strong> {saga.status}</li>
            <li><strong>Retry Count:</strong> {saga.retry_count}</li>
            <li><strong>Last Step:</strong> {saga.current_step}</li>
            <li><strong>Created At:</strong> {saga.created_at}</li>
            <li><strong>Last Retry:</strong> {saga.last_retry_at}</li>
        </ul>

        <h3>Error Details:</h3>
        <pre>{saga.error_message or "No error message available"}</pre>

        <h3>Action Required:</h3>
        <p>Please review the saga logs and take appropriate action to resolve the issue.</p>

        <p><strong>View Saga:</strong> <a href="{settings.APP_ADMIN_DASHBOARD_URL}/sagas/{saga.id}">Click here</a></p>
        '''

        admin_email = getattr(settings, "ADMIN_EMAIL", "admin@example.com")

        await send_email(
            to_email=admin_email,
            subject=subject,
            html_content=body,
            priority="high",
        )

        logger.info(f"Admin email alert sent for saga {saga.id}")

    except Exception as e:
        logger.error(f"Failed to send admin email for saga {saga.id}: {e}")
        # Don't raise - email is not critical
