"""
Taskiq quiz flow tasks — async-native replacements for Celery quiz_flow subpackage (M009-S04).

8 tasks consolidated from 4 Celery subpackage files into a single Taskiq module:
  From cleanup_tasks.py:
    1. cleanup_expired_quiz_sessions  — interval 7200s (periodic session cleanup)
  From trigger_tasks.py:
    2. check_quiz_triggers            — on-demand (patient quiz trigger evaluation)
    3. send_quiz_link_reminder        — on-demand (reminder for pending quiz link)
    4. monitor_quiz_links             — on-demand (quiz link expiration monitoring)
  From response_tasks.py:
    5. process_quiz_response          — on-demand (process patient quiz response)
    6. generate_quiz_report           — on-demand (generate report from quiz)
  From question_tasks.py:
    7. send_quiz_question             — on-demand (deliver quiz question to patient)
    8. send_quiz_progress_update      — on-demand (send progress notification)

Key translation patterns from Celery → Taskiq:
  - async_to_sync(service.method)() → await service.method()
  - run_async(coro) → await coro
  - self (bind=True) removed: SmartRetryMiddleware handles retries externally
  - self.request.retries / self.retry() → SmartRetryMiddleware exponential backoff
  - send_quiz_reminder.delay() → await send_quiz_reminder.kiq() from quiz_link_taskiq
  - send_quiz_link_reminder_task.delay() → await send_quiz_link_reminder.kiq() (self-dispatch)
  - Pure helpers imported from Celery subpackage to avoid duplication
  - trigger_service.py NOT modified — sync caller keeps Celery per D010

Cross-module imports:
  - quiz_link_taskiq.send_quiz_reminder — used by send_quiz_link_reminder

Schedule labels (1 task is periodic):
  - cleanup_expired_quiz_sessions: interval 7200s (every 2 hours)
"""

import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_

from app.database import get_scoped_session
from app.repositories.patient import PatientRepository
from app.taskiq_broker import broker
from app.tasks.quiz_flow.cleanup_tasks import _sanitize_max_age_hours
from app.tasks.quiz_flow.helpers import _notify_providers_of_quiz_completion
from app.tasks.quiz_flow.question_tasks import _parse_uuid
from app.tasks.quiz_flow.trigger_tasks import _sanitize_hours_before_expiry, _sanitize_limit
from app.tasks.taskiq_base import log_task_error, log_task_start, log_task_success
from app.utils.timezone import SAO_PAULO_TZ, now_sao_paulo

logger = logging.getLogger("app.tasks.quiz_flow_taskiq")


# ===========================================================================
# 1. cleanup_expired_quiz_sessions — periodic (interval 7200s)
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=2,
    delay=60,
    schedule=[{"interval": {"seconds": 7200}}],
)
async def cleanup_expired_quiz_sessions(max_age_hours: int = 48) -> dict[str, Any]:
    """Clean up expired quiz sessions that were never completed.

    Marks sessions as 'expired' after expiration_date, sends notifications
    to doctors about expired sessions, and triggers flow resumption.

    Args:
        max_age_hours: Maximum age in hours for incomplete sessions.

    Returns:
        Dict with cleanup results.
    """
    start_time = log_task_start("cleanup_expired_quiz_sessions", max_age_hours=max_age_hours)
    max_age_hours = _sanitize_max_age_hours(max_age_hours)

    try:
        with get_scoped_session() as db:
            from app.models.quiz import QuizSession
            from app.models.patient import Patient

            current_time = now_sao_paulo()
            max_age_cutoff = current_time - timedelta(hours=max_age_hours)

            expired_sessions = (
                db.query(QuizSession)
                .filter(
                    QuizSession.status == "started",
                    or_(
                        and_(
                            QuizSession.expiration_date.isnot(None),
                            QuizSession.expiration_date <= current_time,
                        ),
                        and_(
                            QuizSession.expiration_date.is_(None),
                            QuizSession.started_at <= max_age_cutoff,
                        ),
                    ),
                )
                .with_for_update(skip_locked=True)
                .all()
            )

            cleanup_count = 0
            notifications_sent = 0
            flows_resumed = 0
            errors = 0
            session_details = []

            for session in expired_sessions:
                try:
                    patient = (
                        db.query(Patient)
                        .filter(Patient.id == session.patient_id)
                        .first()
                    )

                    session.status = "expired"  # type: ignore[assignment]
                    session.completed_at = current_time  # type: ignore[assignment]

                    session_metadata = dict(session.session_metadata or {})
                    session_metadata.update(
                        {
                            "expired_at": current_time.isoformat(),
                            "expiration_reason": "timeout",
                            "expiration_source": (
                                "expiration_date" if session.expiration_date else "max_age"
                            ),
                            "original_expiration_date": (
                                session.expiration_date.isoformat()
                                if session.expiration_date
                                else None
                            ),
                            "questions_answered": session.answered_questions or 0,
                            "total_questions": session.total_questions or 0,
                        }
                    )

                    # Doctor notification
                    notification_sent = False
                    try:
                        notification_sent = _notify_doctor_of_expired_session(
                            db=db, session=session, patient=patient
                        )
                    except Exception as notify_exc:
                        errors += 1
                        logger.error(
                            "Error notifying doctor for session %s: %s",
                            session.id,
                            notify_exc,
                            exc_info=True,
                        )

                    if notification_sent:
                        notifications_sent += 1
                    else:
                        session_metadata["doctor_notification_pending"] = True

                    # Flow resumption
                    flow_resumed = False
                    try:
                        flow_resumed = _resume_patient_flow_after_expiration(
                            db=db,
                            patient_id=session.patient_id,  # type: ignore[arg-type]
                            quiz_session_id=session.id,  # type: ignore[arg-type]
                        )
                    except Exception as flow_exc:
                        errors += 1
                        logger.error(
                            "Error resuming patient flow for session %s: %s",
                            session.id,
                            flow_exc,
                            exc_info=True,
                        )

                    if flow_resumed:
                        flows_resumed += 1
                    else:
                        session_metadata["flow_resume_pending"] = True

                    session.session_metadata = session_metadata
                    cleanup_count += 1

                    session_details.append(
                        {
                            "session_id": str(session.id),
                            "patient_id": str(session.patient_id),
                            "patient_name": patient.name if patient and patient.name else "Unknown",
                            "started_at": session.started_at.isoformat(),
                            "expired_at": current_time.isoformat(),
                            "questions_answered": session.answered_questions or 0,
                            "notification_sent": notification_sent,
                            "flow_resumed": flow_resumed,
                        }
                    )

                except Exception as e:
                    logger.error(
                        "Error cleaning up session %s: %s", session.id, e, exc_info=True
                    )
                    errors += 1
                    session_details.append(
                        {"session_id": str(session.id), "error": str(e)}
                    )

            db.commit()

            log_task_success(
                "cleanup_expired_quiz_sessions",
                start_time,
                cleaned_sessions=cleanup_count,
                notifications_sent=notifications_sent,
                flows_resumed=flows_resumed,
            )
            return {
                "success": True,
                "cleaned_sessions": cleanup_count,
                "notifications_sent": notifications_sent,
                "flows_resumed": flows_resumed,
                "errors": errors,
                "session_details": session_details,
            }

    except Exception as exc:
        log_task_error("cleanup_expired_quiz_sessions", exc, start_time)
        raise


def _notify_doctor_of_expired_session(db, session, patient) -> bool:
    """Notify doctor about an expired quiz session via alert."""
    try:
        from app.models.alert import Alert, AlertSeverity

        patient_name = patient.name if patient and patient.name else "Unknown Patient"
        questions_answered = session.answered_questions or 0
        total_questions = session.total_questions or 0
        completion_rate = (
            (questions_answered / total_questions * 100) if total_questions > 0 else 0
        )

        alert = Alert(
            patient_id=session.patient_id,
            alert_type="quiz_expired",
            severity=AlertSeverity.MEDIUM,
            description=(
                f"Quiz Session Expired: Quiz session for {patient_name} has expired "
                f"without completion. Patient answered {questions_answered} of "
                f"{total_questions} questions ({completion_rate:.0f}%). "
                f"Session started at {session.started_at.strftime('%Y-%m-%d %H:%M')}."
            ),
            data={
                "quiz_session_id": str(session.id),
                "quiz_template_id": str(session.quiz_template_id),
                "started_at": session.started_at.isoformat(),
                "expired_at": now_sao_paulo().isoformat(),
                "questions_answered": questions_answered,
                "total_questions": total_questions,
                "completion_rate": completion_rate,
                "requires_follow_up": completion_rate < 50,
            },
            acknowledged=False,
        )
        db.add(alert)
        db.flush()
        logger.info("Doctor notification sent for expired session %s", session.id)
        return True

    except Exception as e:
        logger.error("Failed to notify doctor about expired session %s: %s", session.id, e)
        return False


def _resume_patient_flow_after_expiration(db, patient_id: UUID, quiz_session_id: UUID) -> bool:
    """Resume patient flow after quiz session expires."""
    try:
        from app.models.flow import PatientFlowState

        flow_state = (
            db.query(PatientFlowState)
            .filter(PatientFlowState.patient_id == patient_id)
            .first()
        )

        if not flow_state:
            logger.warning("No flow state found for patient %s", patient_id)
            return False

        state_data = dict(flow_state.state_data or {})
        state_data.update(
            {
                "quiz_expired": True,
                "expired_quiz_session_id": str(quiz_session_id),
                "flow_resumed_at": now_sao_paulo().isoformat(),
                "waiting_for_quiz": False,
            }
        )
        flow_state.state_data = state_data
        flow_state.last_message_at = now_sao_paulo()

        db.flush()
        logger.info("Patient flow resumed for patient %s after quiz expiration", patient_id)
        return True

    except Exception as e:
        logger.error("Failed to resume flow for patient %s: %s", patient_id, e)
        return False


# ===========================================================================
# 2. check_quiz_triggers — on-demand
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=120,
)
async def check_quiz_triggers(limit: int = 100) -> dict[str, Any]:
    """Check for patients who should receive quiz triggers.

    Evaluates monthly quiz trigger policy for active patients.

    Args:
        limit: Maximum number of patients to check.

    Returns:
        Dict with trigger check results.
    """
    start_time = log_task_start("check_quiz_triggers", limit=limit)
    limit = _sanitize_limit(limit)

    try:
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

            flow_repo = FlowStateRepository(db)
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
                    from app.domain.quizzes.quiz_trigger_policy import QuizTriggerPolicy

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
                            enrollment_date = enrollment_date.replace(tzinfo=SAO_PAULO_TZ)
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
                        QuizTriggerPolicy.calculate_monthly_cycle(days_since_enrollment)
                    )

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

                    # Async-native: await directly instead of async_to_sync
                    existing_session = await trigger_service.get_current_month_quiz_session(
                        flow_state.patient_id, monthly_cycle
                    )
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

                    # Async-native: await directly instead of async_to_sync
                    result = await trigger_service.trigger_patient_quiz(
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
                        "Error checking quiz trigger for patient %s: %s",
                        flow_state.patient_id,
                        e,
                    )
                    results["errors"] += 1
                    results["details"].append(
                        {"patient_id": str(flow_state.patient_id), "error": str(e)}
                    )

            log_task_success(
                "check_quiz_triggers",
                start_time,
                quizzes_triggered=results["quizzes_triggered"],
                errors=results["errors"],
            )
            return results

    except Exception as exc:
        log_task_error("check_quiz_triggers", exc, start_time)
        raise


# ===========================================================================
# 3. send_quiz_link_reminder — on-demand
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
)
async def send_quiz_link_reminder(
    quiz_session_id: str, hours_before_expiry: int = 24
) -> dict[str, Any]:
    """Send reminder for pending quiz link.

    Cross-dispatches to quiz_link_taskiq.send_quiz_reminder for actual delivery.

    Args:
        quiz_session_id: Quiz session UUID string.
        hours_before_expiry: Hours before expiry when reminder triggers.

    Returns:
        Dict with reminder results.
    """
    start_time = log_task_start(
        "send_quiz_link_reminder", quiz_session_id=quiz_session_id
    )

    try:
        session_uuid = UUID(quiz_session_id)
        hours_before_expiry = _sanitize_hours_before_expiry(hours_before_expiry)

        with get_scoped_session() as db:
            from app.models.quiz import QuizSession
            from app.services.quiz.quiz_service import MonthlyQuizService

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
                        last_reminder_at = last_reminder_at.replace(tzinfo=SAO_PAULO_TZ)
                    if (now - last_reminder_at).total_seconds() < 30 * 60:
                        return {
                            "success": True,
                            "queued": False,
                            "reason": "Reminder already queued recently",
                            "idempotent": True,
                        }
                except ValueError:
                    pass

            # Async-native: await directly instead of async_to_sync
            quiz_link = await quiz_service.get_quiz_link_status(session_uuid)

            if quiz_link.status.value != "active":
                reason = f"Quiz link status is {quiz_link.status.value}"
                logger.warning("Quiz link reminder skipped: %s", reason)
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
                logger.info("Quiz link reminder skipped: %s", reason)
                return {"success": False, "reason": reason}

            # Cross-dispatch to quiz_link_taskiq.send_quiz_reminder
            from app.tasks.quiz_link_taskiq import send_quiz_reminder

            await send_quiz_reminder.kiq(
                session_id=str(quiz_session_id),
                patient_id=str(quiz_link.patient_id),
                token=None,
                is_regenerated=False,
            )

            metadata["last_link_reminder_at"] = now.isoformat()
            metadata["last_link_reminder_hours_remaining"] = hours_remaining
            metadata["last_reminder_sent_at"] = now.isoformat()
            session.session_metadata = metadata
            db.commit()

            logger.info("Quiz link reminder queued for session %s", quiz_session_id)
            log_task_success(
                "send_quiz_link_reminder",
                start_time,
                hours_remaining=hours_remaining,
            )
            return {
                "success": True,
                "queued": True,
                "hours_remaining": hours_remaining,
            }

    except ValueError as exc:
        logger.error("Invalid reminder input: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "non_retryable": True,
            "final_failure": True,
        }

    except Exception as exc:
        log_task_error("send_quiz_link_reminder", exc, start_time)
        raise


# ===========================================================================
# 4. monitor_quiz_links — on-demand
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=2,
    delay=120,
)
async def monitor_quiz_links() -> dict[str, Any]:
    """Monitor quiz links for expirations and trigger reminders.

    Returns:
        Dict with monitoring results.
    """
    start_time = log_task_start("monitor_quiz_links")

    try:
        with get_scoped_session() as db:
            from app.models.quiz import QuizSession

            results: dict[str, Any] = {
                "checked_links": 0,
                "expiring_soon": 0,
                "expired": 0,
                "reminders_sent": 0,
                "expiration_notices_sent": 0,
                "fallback_triggered": 0,
            }

            active_sessions = (
                db.query(QuizSession).filter(QuizSession.status == "started").all()
            )

            current_time = now_sao_paulo()

            for session in active_sessions:
                results["checked_links"] += 1

                expiration_at = session.expiration_date or (
                    session.started_at + timedelta(hours=48)
                )
                time_to_expire = expiration_at - current_time

                if time_to_expire.total_seconds() <= 0:
                    results["expired"] += 1
                elif time_to_expire.total_seconds() <= 6 * 3600:
                    results["expiring_soon"] += 1
                    await send_quiz_link_reminder.kiq(str(session.id), 6)
                    results["reminders_sent"] += 1

            log_task_success(
                "monitor_quiz_links",
                start_time,
                checked_links=results["checked_links"],
            )
            return results

    except Exception as exc:
        log_task_error("monitor_quiz_links", exc, start_time)
        raise


# ===========================================================================
# 5. process_quiz_response — on-demand
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=2,
    delay=30,
)
async def process_quiz_response(patient_id: str, message_id: str) -> dict[str, Any]:
    """Process patient response to quiz question.

    Args:
        patient_id: Patient UUID string.
        message_id: Message UUID string.

    Returns:
        Dict with processing results.
    """
    start_time = log_task_start(
        "process_quiz_response", patient_id=patient_id, message_id=message_id
    )

    try:
        patient_uuid = _parse_uuid(patient_id, "patient_id")
        message_uuid = _parse_uuid(message_id, "message_id")

        with get_scoped_session() as db:
            from app.domain.quizzes.integration.flow_integration.response_handler import (
                ConversationalQuizService,
            )
            from app.repositories.message import MessageRepository

            quiz_flow_service = ConversationalQuizService(db)

            message_repo = MessageRepository(db)
            message = message_repo.get(message_uuid)

            if not message:
                from app.exceptions import NotFoundError

                raise NotFoundError(f"Message {message_id} not found")

            if message.patient_id != patient_uuid:
                logger.warning(
                    "Skipping quiz response processing due to patient/message mismatch: "
                    "message_id=%s expected_patient_id=%s actual_patient_id=%s",
                    message_id,
                    patient_id,
                    message.patient_id,
                )
                return {
                    "success": False,
                    "error": "Message does not belong to patient",
                    "non_retryable": True,
                }

            # Idempotency guard
            message_metadata = dict(message.message_metadata or {})
            if message_metadata.get("quiz_response_processed_at"):
                logger.info(
                    "Ignoring duplicate quiz response processing for message %s",
                    message_id,
                )
                cached_result = message_metadata.get("quiz_response_result") or {}
                return {
                    "success": True,
                    "patient_id": patient_id,
                    "response_saved": cached_result.get("response_saved", True),
                    "next_action": cached_result.get("action"),
                    "quiz_completed": cached_result.get("action") == "quiz_completed",
                    "idempotent": True,
                }

            # Async-native: await directly instead of async_to_sync
            result = await quiz_flow_service.process_quiz_response(
                patient_id=patient_uuid,
                response_text=message.content,  # type: ignore[arg-type]
                message_metadata={
                    "message_id": str(message.id),
                    "timestamp": message.timestamp,
                },
            )

            if result["success"]:
                message_metadata["quiz_response_processed_at"] = now_sao_paulo().isoformat()
                message_metadata["quiz_response_result"] = {
                    "action": result.get("action"),
                    "response_saved": result.get("response_saved", True),
                }
                message.message_metadata = message_metadata
                db.commit()

                logger.info("Quiz response processed for patient %s", patient_id)
                log_task_success(
                    "process_quiz_response",
                    start_time,
                    patient_id=patient_id,
                    action=result.get("action"),
                )
                return {
                    "success": True,
                    "patient_id": patient_id,
                    "response_saved": result.get("response_saved", True),
                    "next_action": result["action"],
                    "quiz_completed": result.get("action") == "quiz_completed",
                }
            else:
                logger.error("Failed to process quiz response: %s", result.get("error"))
                return {"success": False, "error": result.get("error")}

    except ValueError as exc:
        logger.error("Non-retryable quiz response error: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "non_retryable": True,
            "final_failure": True,
        }

    except Exception as exc:
        log_task_error("process_quiz_response", exc, start_time, patient_id=patient_id)
        raise


# ===========================================================================
# 6. generate_quiz_report — on-demand
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=2,
    delay=120,
)
async def generate_quiz_report(
    patient_id: str, quiz_session_id: str
) -> dict[str, Any]:
    """Generate medical report from completed quiz responses.

    Args:
        patient_id: Patient UUID string.
        quiz_session_id: Quiz session UUID string.

    Returns:
        Dict with report generation results.
    """
    start_time = log_task_start(
        "generate_quiz_report",
        patient_id=patient_id,
        quiz_session_id=quiz_session_id,
    )

    try:
        patient_uuid = _parse_uuid(patient_id, "patient_id")
        quiz_session_uuid = _parse_uuid(quiz_session_id, "quiz_session_id")

        with get_scoped_session() as db:
            from app.models.report import Report, ReportType
            from app.services.quiz import QuizResponseService, QuizSessionService
            from app.services.reporting.quiz_report_generator import (
                get_quiz_report_generator,
            )

            quiz_session_service = QuizSessionService(db)
            quiz_response_service = QuizResponseService(db)

            quiz_session = quiz_session_service.get_session(quiz_session_uuid)  # type: ignore[attr-defined]
            if not quiz_session or not quiz_session.is_completed:
                return {
                    "success": False,
                    "reason": "Quiz session not found or not completed",
                }

            if quiz_session.patient_id != patient_uuid:
                return {
                    "success": False,
                    "error": "Quiz session does not belong to patient",
                    "non_retryable": True,
                }

            # Idempotency: check if report already exists in session metadata
            session_metadata = dict(quiz_session.session_metadata or {})
            existing_report_id = session_metadata.get("quiz_report_id")
            if existing_report_id:
                return {
                    "success": True,
                    "report_id": str(existing_report_id),
                    "patient_id": patient_id,
                    "quiz_session_id": quiz_session_id,
                    "idempotent": True,
                }

            # Check for existing persisted report
            existing_reports = (
                db.query(Report)
                .filter(
                    Report.patient_id == patient_uuid,
                    Report.type == ReportType.QUIZ_ANALYSIS,
                )
                .order_by(Report.generated_at.desc())
                .all()
            )
            for report in existing_reports:
                report_metadata = getattr(report, "report_metadata", None) or {}
                if report_metadata.get("quiz_session_id") == str(quiz_session_uuid):
                    session_metadata["quiz_report_id"] = str(report.id)
                    session_metadata["quiz_report_generated_at"] = now_sao_paulo().isoformat()
                    quiz_session.session_metadata = session_metadata
                    db.commit()
                    return {
                        "success": True,
                        "report_id": str(report.id),
                        "patient_id": patient_id,
                        "quiz_session_id": quiz_session_id,
                        "idempotent": True,
                    }

            responses = quiz_response_service.get_session_responses(  # type: ignore[attr-defined]
                quiz_session_uuid
            )
            if not responses:
                return {
                    "success": False,
                    "reason": "No quiz responses found for session",
                    "non_retryable": True,
                }

            # Async-native: await directly instead of run_async
            report_generator = get_quiz_report_generator(db)
            report_id = await report_generator.generate_quiz_report(quiz_session_uuid)

            session_metadata["quiz_report_id"] = str(report_id)
            session_metadata["quiz_report_generated_at"] = now_sao_paulo().isoformat()
            quiz_session.session_metadata = session_metadata
            db.commit()

            # Notify healthcare providers
            _notify_providers_of_quiz_completion(patient_id, quiz_session_id, report_id)

            logger.info("Quiz report generated for patient %s: %s", patient_id, report_id)
            log_task_success(
                "generate_quiz_report",
                start_time,
                report_id=str(report_id),
            )
            return {
                "success": True,
                "report_id": str(report_id),
                "patient_id": patient_id,
                "quiz_session_id": quiz_session_id,
            }

    except ValueError as exc:
        logger.error("Non-retryable quiz report error: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "non_retryable": True,
            "final_failure": True,
        }

    except Exception as exc:
        log_task_error(
            "generate_quiz_report",
            exc,
            start_time,
            patient_id=patient_id,
        )
        raise


# ===========================================================================
# 7. send_quiz_question — on-demand
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=3,
    delay=60,
)
async def send_quiz_question(
    patient_id: str, quiz_session_id: str, question_index: int
) -> dict[str, Any]:
    """Send quiz question to patient.

    Args:
        patient_id: Patient UUID string.
        quiz_session_id: Quiz session UUID string.
        question_index: Index of question to send.

    Returns:
        Dict with delivery results.
    """
    start_time = log_task_start(
        "send_quiz_question",
        patient_id=patient_id,
        question_index=question_index,
    )

    try:
        if question_index < 0:
            return {
                "success": False,
                "error": "question_index must be non-negative",
                "non_retryable": True,
            }

        patient_uuid = _parse_uuid(patient_id, "patient_id")
        session_uuid = _parse_uuid(quiz_session_id, "quiz_session_id")

        with get_scoped_session() as db:
            from app.domain.quizzes.integration.flow_integration.response_handler import (
                ConversationalQuizService,
            )
            from app.services.quiz import QuizSessionService, QuizTemplateService

            quiz_flow_service = ConversationalQuizService(db)
            quiz_session_service = QuizSessionService(db)

            target_session = quiz_session_service.get_session(session_uuid)
            if not target_session:
                return {"success": False, "error": "Quiz session not found"}
            if target_session.patient_id != patient_uuid:
                return {
                    "success": False,
                    "error": "Quiz session does not belong to patient",
                }
            if getattr(target_session, "status", None) != "started":
                return {"success": False, "error": "Quiz session is not active"}
            if getattr(target_session, "is_expired", False):
                return {"success": False, "error": "Quiz session expired"}

            template_service = QuizTemplateService(db)
            template = template_service.get_template(target_session.quiz_template_id)
            questions = list(template.questions or [])
            if question_index >= len(questions):
                return {
                    "success": False,
                    "error": "question_index out of range for quiz template",
                    "non_retryable": True,
                }

            # Idempotency guard
            session_metadata = dict(target_session.session_metadata or {})
            last_sent_index = session_metadata.get("last_question_sent_index")
            if last_sent_index == question_index:
                logger.info(
                    "Skipping duplicate quiz question dispatch for session %s at index %s",
                    target_session.id,
                    question_index,
                )
                return {
                    "success": True,
                    "patient_id": patient_id,
                    "question_index": question_index,
                    "session_id": str(target_session.id),
                    "idempotent": True,
                }

            # Async-native: await directly instead of async_to_sync
            await quiz_flow_service._send_next_question(
                patient_id=patient_uuid,
                session=target_session,
                questions=questions,
                question_index=question_index,
            )
            session_metadata["last_question_sent_index"] = question_index
            session_metadata["last_question_sent_at"] = now_sao_paulo().isoformat()
            target_session.session_metadata = session_metadata
            db.commit()

            logger.info("Quiz question %d sent to patient %s", question_index, patient_id)
            log_task_success(
                "send_quiz_question",
                start_time,
                question_index=question_index,
            )
            return {
                "success": True,
                "patient_id": patient_id,
                "question_index": question_index,
                "session_id": str(target_session.id),
            }

    except ValueError as exc:
        logger.error("Non-retryable quiz question error: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "non_retryable": True,
            "final_failure": True,
        }

    except Exception as exc:
        log_task_error(
            "send_quiz_question", exc, start_time, patient_id=patient_id
        )
        raise


# ===========================================================================
# 8. send_quiz_progress_update — on-demand
# ===========================================================================

@broker.task(
    retry_on_error=True,
    max_retries=2,
    delay=30,
)
async def send_quiz_progress_update(
    patient_id: str, quiz_session_id: str, progress_data: dict[str, Any]
) -> dict[str, Any]:
    """Send progress update during quiz completion.

    Args:
        patient_id: Patient UUID string.
        quiz_session_id: Quiz session UUID string.
        progress_data: Dict with current_question and total_questions.

    Returns:
        Dict with progress update results.
    """
    start_time = log_task_start(
        "send_quiz_progress_update",
        patient_id=patient_id,
    )

    try:
        patient_uuid = _parse_uuid(patient_id, "patient_id")
        session_uuid = _parse_uuid(quiz_session_id, "quiz_session_id")

        if not isinstance(progress_data, dict):
            return {
                "success": False,
                "reason": "Invalid progress data",
                "non_retryable": True,
            }

        current_question = int(progress_data.get("current_question", 0))
        total_questions = int(progress_data.get("total_questions", 0))

        if current_question <= 0 or total_questions <= 0:
            return {"success": False, "reason": "Invalid progress data"}
        if current_question > total_questions:
            return {
                "success": False,
                "reason": "current_question exceeds total_questions",
                "non_retryable": True,
            }

        progress_percent = int((current_question / total_questions) * 100)
        progress_content = (
            "Você está indo muito bem! 🌟 Já respondeu "
            f"{current_question} de {total_questions} perguntas "
            f"({progress_percent}% completo). Continue assim! ✨"
        )

        from app.core.database.async_engine import get_async_session_factory
        from app.models.message import (
            Message,
            MessageDirection,
            MessageStatus,
            MessageType,
        )
        from app.services.unified_whatsapp_service import (
            create_unified_whatsapp_service,
        )

        async_session_factory = get_async_session_factory()
        async with async_session_factory() as db:
            from sqlalchemy import select
            from app.models.quiz import QuizSession

            session_result = await db.execute(
                select(QuizSession).where(QuizSession.id == session_uuid)
            )
            session = session_result.scalar_one_or_none()
            if not session:
                return {
                    "success": False,
                    "reason": "Quiz session not found",
                    "non_retryable": True,
                }
            if session.patient_id != patient_uuid:
                return {
                    "success": False,
                    "reason": "Quiz session does not belong to patient",
                    "non_retryable": True,
                }

            message = Message(
                patient_id=patient_uuid,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=progress_content,
                status=MessageStatus.PENDING,
                message_metadata={
                    "quiz_session_id": quiz_session_id,
                    "progress_percent": progress_percent,
                    "current_question": current_question,
                    "total_questions": total_questions,
                    "template_type": "quiz_progress",
                },
            )
            db.add(message)
            await db.commit()
            await db.refresh(message)

            whatsapp_service = create_unified_whatsapp_service(db)
            success = await whatsapp_service.send_message(message)

            if success:
                message.status = MessageStatus.SENT
                message.sent_at = now_sao_paulo()
            else:
                message.status = MessageStatus.FAILED
                message.message_metadata["failure_reason"] = "Message sending failed"

            await db.commit()

            logger.info("Quiz progress update sent to patient %s", patient_id)
            log_task_success(
                "send_quiz_progress_update",
                start_time,
                progress_percent=progress_percent,
            )
            return {
                "success": success,
                "message_id": str(message.id),
                "progress_percent": progress_percent,
            }

    except ValueError as exc:
        logger.error("Non-retryable progress update error: %s", exc)
        return {
            "success": False,
            "error": str(exc),
            "non_retryable": True,
            "final_failure": True,
        }

    except Exception as exc:
        log_task_error("send_quiz_progress_update", exc, start_time, patient_id=patient_id)
        raise


__all__ = [
    "cleanup_expired_quiz_sessions",
    "check_quiz_triggers",
    "send_quiz_link_reminder",
    "monitor_quiz_links",
    "process_quiz_response",
    "generate_quiz_report",
    "send_quiz_question",
    "send_quiz_progress_update",
]
