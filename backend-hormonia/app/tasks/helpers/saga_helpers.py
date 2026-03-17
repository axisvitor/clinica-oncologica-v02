"""Saga retry helpers extracted from app.tasks.saga_retry."""

import logging
from html import escape as html_escape
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.config import settings
from app.core.monitoring_config import capture_exception, capture_message
from app.models.patient_onboarding_saga import PatientOnboardingSaga

logger = logging.getLogger(__name__)


def _calculate_exponential_backoff(retry_count: int) -> int:
    """Calculate exponential backoff delay in seconds."""
    base_delay = getattr(settings, "SAGA_RETRY_DELAY", None)
    if base_delay is None:
        base_delay = getattr(settings, "SAGA_RETRY_INITIAL_DELAY_SECONDS", 60)
    max_delay = getattr(settings, "SAGA_RETRY_MAX_DELAY_SECONDS", base_delay)
    if max_delay < base_delay:
        max_delay = base_delay

    delay = base_delay * (2**retry_count)

    return min(delay, max_delay)


async def _alert_admin_max_retries_exceeded(
    saga: PatientOnboardingSaga, db: Session
) -> None:
    """Alert admin when a saga exceeds maximum retry attempts."""
    try:
        logger.error(f"ALERT: Saga {saga.id} exceeded max retries ({saga.retry_count})")

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

        if getattr(settings, "ENABLE_ADMIN_EMAIL_ALERTS", False):
            await _send_admin_email_alert(saga)

    except Exception as e:
        logger.error(f"Failed to send admin alert for saga {saga.id}: {e}")
        capture_exception(e)


async def _send_admin_email_alert(saga: PatientOnboardingSaga) -> None:
    """Send email alert to admin about failed saga."""
    try:
        admin_email = getattr(settings, "ADMIN_EMAIL", None)
        if not admin_email:
            logger.warning("ADMIN_EMAIL not configured, skipping email alert")
            return

        subject = f"[ALERT] Patient Onboarding Saga Failed: {saga.id}"
        body = (
            f"Saga ID: {saga.id}\n"
            f"Patient ID: {saga.patient_id}\n"
            f"Doctor ID: {saga.doctor_id}\n"
            f"Retry Count: {saga.retry_count}\n"
            f"Error: {saga.error_message}\n"
            f"Current Step: {saga.current_step}\n"
        )

        logger.info(f"Would send email to {admin_email}: {subject}")

    except Exception as e:
        logger.error(f"Failed to send admin email alert: {e}")
