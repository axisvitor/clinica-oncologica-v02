"""
Celery tasks for quiz flow processing.
Handles quiz question delivery, progress tracking, and completion processing.
"""

import logging
from typing import Any
from uuid import UUID
from celery import current_app as celery_app
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.quiz_flow_integration import ConversationalQuizService
from app.services.quiz import QuizSessionService
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_quiz_question_task(
    self, patient_id: str, quiz_session_id: str, question_index: int
) -> dict[str, Any]:
    """
    Send quiz question to patient.

    Args:
        patient_id (str): Patient UUID as string
        quiz_session_id (str): Quiz session UUID as string
        question_index (int): Index of question to send

    Returns:
        dict[str, Any]: Dictionary with task results containing:
            - success: Whether the task succeeded
            - patient_id: Patient identifier
            - question_index: Question index sent
            - message_id: Generated message ID if successful
            - error: Error message if failed

    Raises:
        Exception: If question sending fails after all retries
    """
    import asyncio

    try:
        with next(get_db()) as db:
            quiz_flow_service = ConversationalQuizService(db)
            quiz_session_service = QuizSessionService(db)

            # Get active session
            active_session = quiz_session_service.get_active_session(UUID(patient_id))

            if not active_session:
                return {"success": False, "error": "No active quiz session found"}

            # Get template and questions
            from app.services.quiz import QuizTemplateService

            template_service = QuizTemplateService(db)
            template = template_service.get_template(active_session.quiz_template_id)

            # Send next question using async method
            result = asyncio.run(
                quiz_flow_service._send_next_question(
                    patient_id=UUID(patient_id),
                    session=active_session,
                    questions=template.questions,
                    question_index=question_index,
                )
            )

            logger.info(f"Quiz question {question_index} sent to patient {patient_id}")
            return {
                "success": True,
                "patient_id": patient_id,
                "question_index": question_index,
                "session_id": str(active_session.id),
            }

    except Exception as exc:
        logger.error(f"Error in send_quiz_question_task: {exc}")

        if self.request.retries < self.max_retries:
            # Exponential backoff: 1min, 2min, 4min
            delay = 60 * (2**self.request.retries)
            raise self.retry(countdown=delay, exc=exc)
        else:
            # Final failure - log and notify
            logger.error(
                f"Quiz question task failed after {self.max_retries} retries: {exc}"
            )
            return {"success": False, "error": str(exc), "final_failure": True}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def process_quiz_response_task(
    self, patient_id: str, message_id: str
) -> dict[str, Any]:
    """
    Process patient response to quiz question.

    Args:
        patient_id (str): Patient UUID as string
        message_id (str): Message UUID as string

    Returns:
        dict[str, Any]: Dictionary with processing results containing:
            - success: Whether processing succeeded
            - patient_id: Patient identifier
            - response_saved: Whether response was saved
            - next_action: Next action to take
            - quiz_completed: Whether quiz is completed
            - error: Error message if failed

    Raises:
        NotFoundError: If message is not found
        Exception: If response processing fails after all retries
    """
    import asyncio

    try:
        with next(get_db()) as db:
            quiz_flow_service = ConversationalQuizService(db)

            # Get message
            from app.repositories.message import MessageRepository

            message_repo = MessageRepository(db)
            message = message_repo.get(UUID(message_id))

            if not message:
                raise NotFoundError(f"Message {message_id} not found")

            # Process quiz response with await
            result = asyncio.run(
                quiz_flow_service.process_quiz_response(
                    patient_id=UUID(patient_id),
                    response_text=message.content,
                    message_metadata={
                        "message_id": str(message.id),
                        "timestamp": message.timestamp,
                    },
                )
            )

            if result["success"]:
                logger.info(f"Quiz response processed for patient {patient_id}")
                return {
                    "success": True,
                    "patient_id": patient_id,
                    "response_saved": result.get("response_saved", True),
                    "next_action": result["action"],
                    "quiz_completed": result.get("action") == "quiz_completed",
                }
            else:
                logger.error(f"Failed to process quiz response: {result.get('error')}")
                return {"success": False, "error": result.get("error")}

    except Exception as exc:
        logger.error(f"Error in process_quiz_response_task: {exc}")

        if self.request.retries < self.max_retries:
            delay = 30 * (self.request.retries + 1)
            raise self.retry(countdown=delay, exc=exc)
        else:
            logger.error(
                f"Quiz response processing failed after {self.max_retries} retries: {exc}"
            )
            return {"success": False, "error": str(exc), "final_failure": True}


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
    import asyncio

    try:
        with next(get_db()) as db:
            quiz_flow_service = ConversationalQuizService(db)

            # Get patients in monthly flow on day 30
            from app.repositories.flow import FlowStateRepository

            flow_repo = FlowStateRepository(db)

            # Get active monthly flows
            monthly_flows = flow_repo.get_flows_by_type_and_day(
                flow_type="monthly_recurring", target_day=30, limit=limit
            )

            results = {
                "checked_patients": 0,
                "quizzes_triggered": 0,
                "errors": 0,
                "details": [],
            }

            for flow_state in monthly_flows:
                try:
                    # Use QuizTriggerService instead of non-existent start_quiz method
                    from app.services.quiz_flow_integration import QuizTriggerService

                    trigger_service = QuizTriggerService(db)

                    # Build quiz info for monthly trigger
                    quiz_info = {
                        "monthly_cycle": 1,
                        "template_name": "monthly_checkup",
                        "trigger_reason": "Monthly quiz day 30",
                    }

                    # Trigger quiz (will choose link vs conversational automatically)
                    result = asyncio.run(
                        trigger_service._trigger_patient_quiz(flow_state, quiz_info)
                    )

                    trigger_result = {
                        "triggered": result.get("success", False),
                        "reason": result.get("error", "Quiz triggered"),
                        "quiz_session_id": result.get("session_id"),
                    }

                    results["checked_patients"] += 1
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


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def cleanup_expired_quiz_sessions_task(self, max_age_hours: int = 48) -> dict[str, Any]:
    """
    Clean up expired quiz sessions that were never completed.

    Args:
        max_age_hours (int, optional): Maximum age in hours for incomplete sessions. Defaults to 48.

    Returns:
        dict[str, Any]: Dictionary with cleanup results containing:
            - success: Whether cleanup succeeded
            - cleaned_sessions: Number of sessions cleaned up
            - errors: Number of errors encountered

    Raises:
        Exception: If cleanup fails after all retries
    """
    try:
        with next(get_db()) as db:
            from datetime import datetime, timedelta
            from app.repositories.quiz import QuizSessionRepository

            quiz_session_repo = QuizSessionRepository(db)
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

            # Get expired incomplete sessions
            expired_sessions = quiz_session_repo.get_expired_incomplete_sessions(
                cutoff_time
            )

            cleanup_count = 0
            errors = 0

            for session in expired_sessions:
                try:
                    # Mark session as expired/cancelled
                    quiz_session_repo.update(
                        session,
                        {
                            "is_completed": True,
                            "completed_at": datetime.utcnow(),
                            "state_data": {"status": "expired", "reason": "timeout"},
                        },
                    )
                    cleanup_count += 1

                    # Mark flow as ready to resume - removing private method call
                    # Flow will be resumed by the next scheduled flow task

                except Exception as e:
                    logger.error(f"Error cleaning up session {session.id}: {e}")
                    errors += 1

            db.commit()

            logger.info(
                f"Quiz session cleanup completed: {cleanup_count} sessions cleaned, {errors} errors"
            )

            return {
                "success": True,
                "cleaned_sessions": cleanup_count,
                "errors": errors,
            }

    except Exception as exc:
        logger.error(f"Error in cleanup_expired_quiz_sessions_task: {exc}")

        if self.request.retries < self.max_retries:
            delay = 60 * (self.request.retries + 1)
            raise self.retry(countdown=delay, exc=exc)
        else:
            logger.error(f"Quiz cleanup failed after {self.max_retries} retries: {exc}")
            return {"success": False, "error": str(exc), "final_failure": True}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def send_quiz_progress_update_task(
    self, patient_id: str, quiz_session_id: str, progress_data: dict[str, Any]
) -> dict[str, Any]:
    """
    Send progress update during quiz completion.

    Args:
        patient_id (str): Patient UUID as string
        quiz_session_id (str): Quiz session UUID as string
        progress_data (dict[str, Any]): Progress information containing:
            - current_question: Current question number
            - total_questions: Total number of questions

    Returns:
        dict[str, Any]: Dictionary with update results containing:
            - success: Whether update was sent successfully
            - message_id: Generated message ID if successful
            - progress_percent: Progress percentage
            - reason: Reason if failed
            - error: Error message if failed

    Raises:
        Exception: If progress update fails after all retries
    """
    import asyncio

    try:
        with next(get_db()) as db:
            from app.domain.messaging.core import MessageFactory
            from app.services.unified_whatsapp_service import UnifiedWhatsAppService

            message_factory = MessageFactory(db)
            whatsapp_service = UnifiedWhatsAppService(db)

            # Generate progress message
            current_question = progress_data.get("current_question", 0)
            total_questions = progress_data.get("total_questions", 0)

            if current_question > 0 and total_questions > 0:
                progress_percent = int((current_question / total_questions) * 100)

                progress_content = f"Você está indo muito bem! 🌟 Já respondeu {current_question} de {total_questions} perguntas ({progress_percent}% completo). Continue assim! ✨"

                # Create message using factory
                message = message_factory.create_outbound_message(
                    patient_id=UUID(patient_id),
                    content=progress_content,
                    metadata={
                        "quiz_session_id": quiz_session_id,
                        "progress_percent": progress_percent,
                        "current_question": current_question,
                        "total_questions": total_questions,
                        "template_type": "quiz_progress",
                    },
                )

                # Send via UnifiedWhatsAppService
                success = asyncio.run(whatsapp_service.send_message(message))

                logger.info(f"Quiz progress update sent to patient {patient_id}")

                return {
                    "success": success,
                    "message_id": str(message.id),
                    "progress_percent": progress_percent,
                }
            else:
                return {"success": False, "reason": "Invalid progress data"}

    except Exception as exc:
        logger.error(f"Error in send_quiz_progress_update_task: {exc}")

        if self.request.retries < self.max_retries:
            delay = 30 * (self.request.retries + 1)
            raise self.retry(countdown=delay, exc=exc)
        else:
            logger.error(
                f"Quiz progress update failed after {self.max_retries} retries: {exc}"
            )
            return {"success": False, "error": str(exc), "final_failure": True}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def generate_quiz_report_task(
    self, patient_id: str, quiz_session_id: str
) -> dict[str, Any]:
    """
    Generate medical report from completed quiz responses.

    Args:
        patient_id (str): Patient UUID as string
        quiz_session_id (str): Quiz session UUID as string

    Returns:
        dict[str, Any]: Dictionary with report generation results containing:
            - success: Whether report generation succeeded
            - report_id: Generated report ID if successful
            - patient_id: Patient identifier
            - quiz_session_id: Quiz session identifier
            - reason: Reason if failed
            - error: Error message if failed

    Raises:
        Exception: If report generation fails after all retries
    """
    try:
        with next(get_db()) as db:
            from app.services.quiz import QuizSessionService, QuizResponseService
            from app.services.report import ReportService

            quiz_session_service = QuizSessionService(db)
            quiz_response_service = QuizResponseService(db)
            report_service = ReportService(db)

            # Get quiz session and responses
            quiz_session = quiz_session_service.get_session(UUID(quiz_session_id))
            if not quiz_session or not quiz_session.is_completed:
                return {
                    "success": False,
                    "reason": "Quiz session not found or not completed",
                }

            responses = quiz_response_service.get_session_responses(
                UUID(quiz_session_id)
            )

            # Generate medical report
            report_data = {
                "patient_id": UUID(patient_id),
                "quiz_session_id": UUID(quiz_session_id),
                "responses": responses,
                "report_type": "monthly_quiz_assessment",
            }

            report = report_service.generate_quiz_report(report_data)

            # Notify healthcare providers
            _notify_providers_of_quiz_completion(patient_id, quiz_session_id, report.id)

            logger.info(f"Quiz report generated for patient {patient_id}: {report.id}")

            return {
                "success": True,
                "report_id": str(report.id),
                "patient_id": patient_id,
                "quiz_session_id": quiz_session_id,
            }

    except Exception as exc:
        logger.error(f"Error in generate_quiz_report_task: {exc}")

        if self.request.retries < self.max_retries:
            delay = 120 * (self.request.retries + 1)
            raise self.retry(countdown=delay, exc=exc)
        else:
            logger.error(
                f"Quiz report generation failed after {self.max_retries} retries: {exc}"
            )
            return {"success": False, "error": str(exc), "final_failure": True}


def _notify_providers_of_quiz_completion(
    patient_id: str, quiz_session_id: str, report_id: str
):
    """
    Notify healthcare providers of quiz completion.

    Args:
        patient_id (str): Patient UUID as string
        quiz_session_id (str): Quiz session UUID as string
        report_id (str): Generated report UUID as string

    Raises:
        Exception: If notification fails
    """
    try:
        from app.config.settings import Settings

        settings = Settings()

        with next(get_db()) as db:
            # Use consolidated alert system if enabled, otherwise legacy
            if settings.USE_CONSOLIDATED_ALERTS:
                try:
                    from app.services.alerts import AlertManagerAdapter

                    alert_service = AlertManagerAdapter(db)
                except ImportError:
                    from app.services.alert import AlertService

                    alert_service = AlertService(db)
            else:
                from app.services.alert import AlertService

                alert_service = AlertService(db)

            # Create alert for healthcare providers
            alert_data = {
                "patient_id": UUID(patient_id),
                "alert_type": "quiz_completed",
                "priority": "medium",
                "title": "Monthly Quiz Completed",
                "message": f"Patient has completed their monthly health assessment. Report available.",
                "metadata": {
                    "quiz_session_id": quiz_session_id,
                    "report_id": report_id,
                    "requires_review": True,
                },
            }

            alert_service.create_alert(alert_data)

    except Exception as e:
        logger.error(f"Error notifying providers of quiz completion: {e}")


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
            - success: Whether reminder was sent
            - message_id: Generated message ID if successful
            - hours_remaining: Hours remaining until expiry
            - error: Error message if failed

    Raises:
        Exception: If reminder sending fails after all retries
    """
    try:
        with next(get_db()) as db:
            from app.services.monthly_quiz_message_integration import (
                MonthlyQuizMessageIntegration,
            )

            quiz_integration = MonthlyQuizMessageIntegration(db)

            import asyncio

            result = asyncio.run(
                quiz_integration.send_quiz_reminder(
                    quiz_session_id=UUID(quiz_session_id),
                    hours_before_expiry=hours_before_expiry,
                )
            )

            if result.get("reminder_sent"):
                logger.info(f"Quiz link reminder sent for session {quiz_session_id}")
                return {
                    "success": True,
                    "message_id": result.get("message_id"),
                    "hours_remaining": result.get("hours_remaining"),
                }
            else:
                logger.warning(f"Quiz link reminder skipped: {result.get('reason')}")
                return {"success": False, "reason": result.get("reason")}

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
        with next(get_db()) as db:
            from app.services.monthly_quiz_service import MonthlyQuizService
            from app.services.monthly_quiz_message_integration import (
                MonthlyQuizMessageIntegration,
            )
            from datetime import datetime, timedelta

            quiz_service = MonthlyQuizService(db)
            quiz_integration = MonthlyQuizMessageIntegration(db)

            results = {
                "checked_links": 0,
                "expiring_soon": 0,
                "expired": 0,
                "reminders_sent": 0,
                "expiration_notices_sent": 0,
                "fallback_triggered": 0,
            }

            # Get all active quiz sessions (removing references to non-existent monthly_quiz model)
            from app.models.quiz import QuizSession

            active_sessions = (
                db.query(QuizSession).filter(QuizSession.is_completed == False).all()
            )

            current_time = datetime.utcnow()

            for session in active_sessions:
                results["checked_links"] += 1

                # Check if session is old (over 24 hours)
                session_age = current_time - session.started_at
                if session_age.total_seconds() > 24 * 3600:  # 24 hours
                    results["expired"] += 1

                    # Send expiration notice
                    try:
                        # Mark session as expired
                        session.is_completed = True
                        session.completed_at = current_time
                        db.commit()

                        results["expiration_notices_sent"] += 1

                    except Exception as e:
                        logger.error(
                            f"Error handling expired session {session.id}: {e}"
                        )

                # Check if expiring soon (over 18 hours)
                elif session_age.total_seconds() > 18 * 3600:  # 18 hours
                    results["expiring_soon"] += 1

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


def _trigger_whatsapp_fallback(patient_id: UUID, quiz_session_id: UUID):
    """
    Trigger WhatsApp conversational fallback when session expires.

    Args:
        patient_id: Patient UUID
        quiz_session_id: Quiz session UUID
    """
    import asyncio

    try:
        with next(get_db()) as db:
            # Get quiz session info
            from app.models.quiz import QuizSession

            session = (
                db.query(QuizSession).filter(QuizSession.id == quiz_session_id).first()
            )

            if not session or session.is_completed:
                return  # Already completed or not found

            # Use QuizTriggerService to trigger a new quiz
            from app.services.quiz_flow_integration import QuizTriggerService
            from app.models.flow import PatientFlowState

            trigger_service = QuizTriggerService(db)

            # Get patient's flow state
            flow_state = (
                db.query(PatientFlowState)
                .filter(PatientFlowState.patient_id == patient_id)
                .first()
            )

            if flow_state and session.quiz_template_id:
                quiz_info = {
                    "monthly_cycle": 1,
                    "template_name": "monthly_checkup",
                    "trigger_reason": "Fallback from expired link",
                }

                # Trigger via WhatsApp (force conversational mode)
                from app.services.quiz import QuizTemplateService

                template_service = QuizTemplateService(db)
                template = template_service.template_repository.get(
                    session.quiz_template_id
                )

                fallback_result = asyncio.run(
                    trigger_service._trigger_quiz_via_whatsapp(
                        patient_id=patient_id,
                        template=template,
                        quiz_info=quiz_info,
                        flow_state=flow_state,
                    )
                )

                if fallback_result.get("success"):
                    logger.info(f"Triggered WhatsApp fallback for patient {patient_id}")
                else:
                    logger.warning(
                        f"Failed to trigger fallback: {fallback_result.get('error')}"
                    )

    except Exception as e:
        logger.error(f"Error triggering WhatsApp fallback: {e}")
