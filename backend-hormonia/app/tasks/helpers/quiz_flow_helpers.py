"""Quiz flow helpers extracted from quiz_flow/ subpackage."""

from __future__ import annotations

import logging
from uuid import UUID

from app.database import get_scoped_session

logger = logging.getLogger(__name__)

# ── cleanup_tasks helpers ────────────────────────────────────────────────────

_DEFAULT_MAX_AGE_HOURS = 48
_MAX_MAX_AGE_HOURS = 24 * 30  # 30 days


def _sanitize_max_age_hours(max_age_hours: int) -> int:
    """Clamp cleanup window to a safe range."""
    try:
        hours = int(max_age_hours)
    except (TypeError, ValueError):
        return _DEFAULT_MAX_AGE_HOURS
    return max(1, min(hours, _MAX_MAX_AGE_HOURS))


# ── helpers.py ───────────────────────────────────────────────────────────────

def _notify_providers_of_quiz_completion(
    patient_id: str, quiz_session_id: str, report_id: str
):
    """Notify healthcare providers of quiz completion."""
    try:
        from app.config.settings import Settings

        Settings()

        with get_scoped_session() as db:
            from app.models.alert import Alert, AlertSeverity

            alert = Alert(
                patient_id=UUID(patient_id),
                alert_type="quiz_completed",
                severity=AlertSeverity.MEDIUM,
                description=(
                    "Monthly Quiz Completed: "
                    "Patient has completed their monthly health assessment. Report available."
                ),
                data={
                    "quiz_session_id": quiz_session_id,
                    "report_id": report_id,
                    "requires_review": True,
                },
                acknowledged=False,
            )
            db.add(alert)
            db.commit()

    except Exception as e:
        logger.error(f"Error notifying providers of quiz completion: {e}")


# ── question_tasks helpers ───────────────────────────────────────────────────

def _parse_uuid(value: str, field_name: str) -> UUID:
    try:
        return UUID(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field_name}: {value}") from exc


# ── trigger_tasks helpers ────────────────────────────────────────────────────

_QF_DEFAULT_LIMIT = 100
_QF_MAX_LIMIT = 500
_DEFAULT_REMINDER_HOURS = 24
_MAX_REMINDER_HOURS = 72


def _sanitize_hours_before_expiry(hours: int) -> int:
    """Validate reminder window to avoid invalid/surprising values."""
    try:
        hours_value = int(hours)
    except (TypeError, ValueError):
        return _DEFAULT_REMINDER_HOURS
    return max(1, min(hours_value, _MAX_REMINDER_HOURS))


def _sanitize_limit(limit: int) -> int:
    """Clamp batch size to a safe operational range (quiz_flow variant)."""
    try:
        limit_value = int(limit)
    except (TypeError, ValueError):
        return _QF_DEFAULT_LIMIT
    return max(1, min(limit_value, _QF_MAX_LIMIT))
