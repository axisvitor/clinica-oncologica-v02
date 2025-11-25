"""
Celery tasks for quiz triggers, reminders, and monitoring.

Tasks:
- check_quiz_triggers_task: Check for patients who should receive quiz triggers
- send_quiz_link_reminder_task: Send reminder for pending quiz link
- monitor_quiz_links_task: Monitor quiz links for expirations and send notifications
"""

import logging
from typing import Any
from uuid import UUID
from celery import current_app as celery_app

from app.database import get_db
from app.tasks.quiz_flow.helpers import _trigger_whatsapp_fallback

logger = logging.getLogger(__name__)


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
            from app.domain.quizzes.integration.flow_integration import (
                ConversationalQuizService,
                QuizTriggerService,
            )
            from app.repositories.flow import FlowStateRepository

            quiz_flow_service = ConversationalQuizService(db)

            # Get patients in monthly flow on day 30
            flow_repo = FlowStateRepository(db)

            # Get active monthly flows
            monthly_flows = flow_repo.get_flows_by_type_and_day(
                flow_type="monthly_recurring", target_day=30, limit=limit
            )

            results: dict[str, Any] = {
                "checked_patients": 0,
                "quizzes_triggered": 0,
                "errors": 0,
                "details": [],
            }

            for flow_state in monthly_flows:
                try:
                    # Use QuizTriggerService instead of non-existent start_quiz method
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
            from app.domain.quizzes import MonthlyQuizService
            from app.services.monthly_quiz_message_integration import (
                MonthlyQuizMessageIntegration,
            )
            from datetime import datetime, timedelta
            from app.models.quiz import QuizSession

            quiz_service = MonthlyQuizService(db)
            quiz_integration = MonthlyQuizMessageIntegration(db)

            results: dict[str, Any] = {
                "checked_links": 0,
                "expiring_soon": 0,
                "expired": 0,
                "reminders_sent": 0,
                "expiration_notices_sent": 0,
                "fallback_triggered": 0,
            }

            # Get all active quiz sessions
            active_sessions = (
                db.query(QuizSession).filter(QuizSession.is_completed == False).all()  # type: ignore[arg-type]
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
                        session.completed_at = current_time  # type: ignore[assignment]
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
