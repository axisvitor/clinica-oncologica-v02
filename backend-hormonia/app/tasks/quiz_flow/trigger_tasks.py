"""
Celery tasks for quiz triggers, reminders, and monitoring.

Tasks:
- check_quiz_triggers_task: Check for patients who should receive quiz triggers
- send_quiz_link_reminder_task: Send reminder for pending quiz link
- monitor_quiz_links_task: Monitor quiz links for expirations and send notifications
"""

from __future__ import annotations

import logging
from datetime import timedelta, datetime
from typing import Any
from uuid import UUID
from app.task_queue import task_queue as celery_app

from app.database import get_scoped_session
from app.repositories.patient import PatientRepository
from app.utils.timezone import now_sao_paulo, SAO_PAULO_TZ

logger = logging.getLogger(__name__)

_DEFAULT_LIMIT = 100
_MAX_LIMIT = 500
_DEFAULT_REMINDER_HOURS = 24
_MAX_REMINDER_HOURS = 72


def _sanitize_limit(limit: int) -> int:
    """Clamp batch size to a safe operational range."""
    try:
        limit_value = int(limit)
    except (TypeError, ValueError):
        return _DEFAULT_LIMIT
    return max(1, min(limit_value, _MAX_LIMIT))


def _sanitize_hours_before_expiry(hours: int) -> int:
    """Validate reminder window to avoid invalid/surprising values."""
    try:
        hours_value = int(hours)
    except (TypeError, ValueError):
        return _DEFAULT_REMINDER_HOURS
    return max(1, min(hours_value, _MAX_REMINDER_HOURS))


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def check_quiz_triggers_task(self, limit: int = 100) -> dict[str, Any]:
    """
    Check for patients who should receive quiz triggers.

    Args:
        limit (int, optional): Maximum number of patients to check. Defaults to 100.

    Returns:
        dict[str, Any]: Dictionary with check results containing:
            - checked_patients: Number of patients checked
            - quizzes_triggered: Number of quizzes triggered
            - errors: Number of errors encountered
            - details: List of detailed results per patient

    Raises:
        Exception: If quiz trigger checking fails after all retries
    """

    try:
        limit = _sanitize_limit(limit)
        with get_scoped_session() as db:
            from app.domain.quizzes.integration.flow_integration.response_handler import (
                ConversationalQuizService,
            )
            from app.domain.quizzes.integration.flow_integration.trigger_service import (
                QuizTriggerService,
            )
            from app.repositories.flow import FlowStateRepository

            ConversationalQuizService(db)
            trigger_service = QuizTriggerService(db)

            # Get patients in monthly flow and evaluate quiz day per policy
            flow_repo = FlowStateRepository(db)

            # Get active monthly flows (filter by policy below)
            monthly_flows = flow_repo.get_flows_by_type(
                flow_type="quiz_mensal", limit=limit
            )

            results: dict[str, Any] = {
                "checked_patients": 0,
                "quizzes_triggered": 0,
                "errors": 0,
                "details": [],
            }

            for flow_state in monthly_flows:
                try:
                    # Build quiz info for monthly trigger
                    from app.domain.quizzes.quiz_trigger_policy import QuizTriggerPolicy
                    from asgiref.sync import async_to_sync

                    # Get patient to calculate monthly cycle
                    patient_repo = PatientRepository(db)
                    patient = patient_repo.get(flow_state.patient_id)

                    if not patient:
                        results["errors"] += 1
                        results["details"].append(
                            {"patient_id": str(flow_state.patient_id), "error": "Patient not found"}
                        )
                        continue

                    results["checked_patients"] += 1

                    enrollment_date = (
                        patient.enrollment_date
                        or patient.created_at
                        or now_sao_paulo()
                    )
                    if isinstance(enrollment_date, datetime):
                        if enrollment_date.tzinfo is None:
                            enrollment_date = enrollment_date.replace(
                                tzinfo=SAO_PAULO_TZ
                            )
                        else:
                            enrollment_date = enrollment_date.astimezone(SAO_PAULO_TZ)
                        days_since_enrollment = (
                            now_sao_paulo().date() - enrollment_date.date()
                        ).days
                    else:
                        days_since_enrollment = (
                            now_sao_paulo().date() - enrollment_date
                        ).days

                    monthly_cycle, days_in_current_cycle = (
                        QuizTriggerPolicy.calculate_monthly_cycle(
                            days_since_enrollment
                        )
                    )

                    # Skip if not quiz day for monthly flow
                    if not QuizTriggerPolicy.is_quiz_day(
                        days_in_current_cycle,
                        "quiz_mensal",
                        days_since_enrollment,
                    ):
                        results["details"].append(
                            {
                                "patient_id": str(flow_state.patient_id),
                                "triggered": False,
                                "reason": f"Not quiz day (day {days_in_current_cycle} of cycle {monthly_cycle})",
                            }
                        )
                        continue

                    # Avoid duplicate sessions if already created this cycle (e.g., via flow message)
                    existing_session = async_to_sync(
                        trigger_service.get_current_month_quiz_session
                    )(flow_state.patient_id, monthly_cycle)
                    if existing_session:
                        results["details"].append(
                            {
                                "patient_id": str(flow_state.patient_id),
                                "triggered": False,
                                "reason": "Quiz session already exists for this cycle",
                                "quiz_session_id": str(existing_session.id),
                            }
                        )
                        continue

                    from app.core.monthly_quiz_config import get_monthly_quiz_config

                    quiz_info = {
                        "monthly_cycle": monthly_cycle,
                        "template_name": get_monthly_quiz_config().MONTHLY_QUIZ_DEFAULT_TEMPLATE,
                        "trigger_reason": f"Monthly quiz day {QuizTriggerPolicy.MONTHLY_QUIZ_DAY}",
                    }

                    # Trigger quiz using async_to_sync instead of asyncio.run
                    # This prevents "asyncio.run() cannot be called from a running event loop" error
                    result = async_to_sync(trigger_service.trigger_patient_quiz)(
                        flow_state, quiz_info
                    )

                    trigger_result = {
                        "triggered": result.get("success", False),
                        "reason": result.get("error", "Quiz triggered"),
                        "quiz_session_id": result.get("session_id"),
                    }

                    results["details"].append(
                        {
                            "patient_id": str(flow_state.patient_id),
                            "triggered": trigger_result["triggered"],
                            "reason": trigger_result.get("reason"),
                            "quiz_session_id": trigger_result.get("quiz_session_id"),
                        }
                    )

                    if trigger_result["triggered"]:
                        results["quizzes_triggered"] += 1

                except Exception as e:
                    logger.error(
                        f"Error checking quiz trigger for patient {flow_state.patient_id}: {e}"
                    )
                    results["errors"] += 1
                    results["details"].append(
                        {"patient_id": str(flow_state.patient_id), "error": str(e)}
                    )

            logger.info(
                f"Quiz trigger check completed: {results['quizzes_triggered']} triggered, "
                f"{results['errors']} errors"
            )

            return results

    except Exception as exc:
        logger.error(f"Error in check_quiz_triggers_task: {exc}")

        if self.request.retries < self.max_retries:
            delay = 120 * (2**self.request.retries)
            raise self.retry(countdown=delay, exc=exc)
        else:
            logger.error(
                f"Quiz trigger check failed after {self.max_retries} retries: {exc}"
            )
            return {"success": False, "error": str(exc), "final_failure": True}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_quiz_link_reminder_task(
    self, quiz_session_id: str, hours_before_expiry: int = 24
) -> dict[str, Any]:
    """
    Send reminder for pending quiz link.

    Args:
        quiz_session_id (str): Quiz session UUID as string
        hours_before_expiry (int): Hours before expiry when reminder is sent

    Returns:
        dict[str, Any]: Dictionary with reminder results containing:
            - success: Whether reminder was queued
            - queued: Whether reminder task was queued
            - hours_remaining: Hours remaining until expiry
            - error: Error message if failed

    Raises:
        Exception: If reminder sending fails after all retries
    """
    try:
        session_uuid = UUID(quiz_session_id)
        hours_before_expiry = _sanitize_hours_before_expiry(hours_before_expiry)

        with get_scoped_session() as db:
            from asgiref.sync import async_to_sync
            from app.models.quiz import QuizSession
            from app.services.quiz.quiz_service import MonthlyQuizService
            from app.tasks.quiz_link_tasks import send_quiz_reminder

            quiz_service = MonthlyQuizService(db)
            session = db.query(QuizSession).filter(QuizSession.id == session_uuid).first()
            if not session:
                return {
                    "success": False,
                    "reason": "Quiz session not found",
                    "non_retryable": True,
                }

            now = now_sao_paulo()
            metadata = dict(session.session_metadata or {})
            last_reminder_at_raw = metadata.get(
                "last_link_reminder_at"
            ) or metadata.get("last_reminder_sent_at")
            if isinstance(last_reminder_at_raw, str):
                try:
                    last_reminder_at = datetime.fromisoformat(last_reminder_at_raw)
                    if last_reminder_at.tzinfo is None:
                        last_reminder_at = last_reminder_at.replace(
                            tzinfo=SAO_PAULO_TZ
                        )
                    if (now - last_reminder_at).total_seconds() < 30 * 60:
                        return {
                            "success": True,
                            "queued": False,
                            "reason": "Reminder already queued recently",
                            "idempotent": True,
                        }
                except ValueError:
                    pass

            quiz_link = async_to_sync(quiz_service.get_quiz_link_status)(
                session_uuid
            )

            if quiz_link.status.value != "active":
                reason = f"Quiz link status is {quiz_link.status.value}"
                logger.warning(f"Quiz link reminder skipped: {reason}")
                return {"success": False, "reason": reason}
            if str(quiz_link.patient_id) != str(session.patient_id):
                return {
                    "success": False,
                    "reason": "Quiz link/session patient mismatch",
                    "non_retryable": True,
                }

            hours_remaining = int(
                (quiz_link.expires_at - now).total_seconds() / 3600
            )
            if hours_remaining > hours_before_expiry:
                reason = f"Quiz link has {hours_remaining} hours remaining"
                logger.info(f"Quiz link reminder skipped: {reason}")
                return {"success": False, "reason": reason}

            send_result = send_quiz_reminder.delay(
                str(quiz_session_id),
                str(quiz_link.patient_id),
                None,
                False,
            )

            metadata["last_link_reminder_at"] = now.isoformat()
            metadata["last_link_reminder_hours_remaining"] = hours_remaining
            metadata["last_link_reminder_task_id"] = send_result.id
            # Keep compatibility with reminder fields used by quiz_link_tasks.
            metadata["last_reminder_sent_at"] = now.isoformat()
            session.session_metadata = metadata
            db.commit()

            logger.info(f"Quiz link reminder queued for session {quiz_session_id}")
            return {
                "success": True,
                "queued": True,
                "hours_remaining": hours_remaining,
                "task_id": send_result.id,
            }

    except ValueError as exc:
        logger.error(f"Invalid reminder input: {exc}")
        return {
            "success": False,
            "error": str(exc),
            "non_retryable": True,
            "final_failure": True,
        }

    except Exception as exc:
        logger.error(f"Error in send_quiz_link_reminder_task: {exc}")

        if self.request.retries < self.max_retries:
            delay = 60 * (2**self.request.retries)
            raise self.retry(countdown=delay, exc=exc)
        else:
            logger.error(
                f"Quiz reminder failed after {self.max_retries} retries: {exc}"
            )
            return {"success": False, "error": str(exc), "final_failure": True}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def monitor_quiz_links_task(self) -> dict[str, Any]:
    """
    Monitor quiz links for expirations and send notifications.
    Should run periodically (e.g., every hour).

    Returns:
        dict[str, Any]: Dictionary with monitoring results containing:
            - checked_links: Number of links checked
            - expiring_soon: Number of links expiring soon
            - expired: Number of expired links
            - reminders_sent: Number of reminders sent
            - expiration_notices_sent: Number of expiration notices sent

    Raises:
        Exception: If monitoring fails after all retries
    """
    try:
        with get_scoped_session() as db:
            from app.services.quiz.quiz_service import MonthlyQuizService
            from app.models.quiz import QuizSession

            MonthlyQuizService(db)

            results: dict[str, Any] = {
                "checked_links": 0,
                "expiring_soon": 0,
                "expired": 0,
                "reminders_sent": 0,
                "expiration_notices_sent": 0,
                "fallback_triggered": 0,
            }

            # Get all active quiz sessions (status-based)
            active_sessions = (
                db.query(QuizSession).filter(QuizSession.status == "started").all()
            )

            current_time = now_sao_paulo()

            for session in active_sessions:
                results["checked_links"] += 1

                expiration_at = session.expiration_date or (session.started_at + timedelta(hours=48))
                time_to_expire = expiration_at - current_time

                if time_to_expire.total_seconds() <= 0:
                    results["expired"] += 1
                elif time_to_expire.total_seconds() <= 6 * 3600:
                    results["expiring_soon"] += 1
                    send_quiz_link_reminder_task.delay(str(session.id), 6)
                    results["reminders_sent"] += 1

            logger.info(f"Quiz link monitoring completed: {results}")
            return results

    except Exception as exc:
        logger.error(f"Error in monitor_quiz_links_task: {exc}")

        if self.request.retries < self.max_retries:
            delay = 120 * (self.request.retries + 1)
            raise self.retry(countdown=delay, exc=exc)
        else:
            logger.error(
                f"Quiz link monitoring failed after {self.max_retries} retries: {exc}"
            )
            return {"success": False, "error": str(exc), "final_failure": True}
