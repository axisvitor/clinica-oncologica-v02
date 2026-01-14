"""
Quiz Response Tasks.

Handles quiz response processing and report generation.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID
from app.task_queue import task_queue as celery_app

from app.database import get_db
from app.exceptions import NotFoundError
from app.tasks.quiz_flow.helpers import _notify_providers_of_quiz_completion

logger = logging.getLogger(__name__)


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
    try:
        with next(get_db()) as db:
            from asgiref.sync import async_to_sync
            from app.domain.quizzes.integration.flow_integration import (
                ConversationalQuizService,
            )
            from app.repositories.message import MessageRepository

            quiz_flow_service = ConversationalQuizService(db)

            # Get message
            message_repo = MessageRepository(db)
            message = message_repo.get(UUID(message_id))

            if not message:
                raise NotFoundError(f"Message {message_id} not found")

            # FIX: Use async_to_sync instead of asyncio.run() to avoid
            # "cannot be called from a running event loop" errors
            result = async_to_sync(quiz_flow_service.process_quiz_response)(
                patient_id=UUID(patient_id),
                response_text=message.content,  # type: ignore[arg-type]
                message_metadata={
                    "message_id": str(message.id),
                    "timestamp": message.timestamp,
                },
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
            from app.services.reporting import ReportService

            quiz_session_service = QuizSessionService(db)
            quiz_response_service = QuizResponseService(db)
            report_service = ReportService(db)

            # Get quiz session and responses
            quiz_session = quiz_session_service.get_session(UUID(quiz_session_id))  # type: ignore[attr-defined]
            if not quiz_session or not quiz_session.is_completed:
                return {
                    "success": False,
                    "reason": "Quiz session not found or not completed",
                }

            responses = quiz_response_service.get_session_responses(  # type: ignore[attr-defined]
                UUID(quiz_session_id)
            )

            # Generate medical report
            report_data = {
                "patient_id": UUID(patient_id),
                "quiz_session_id": UUID(quiz_session_id),
                "responses": responses,
                "report_type": "monthly_quiz_assessment",
            }

            report = report_service.generate_quiz_report(report_data)  # type: ignore[attr-defined]

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
