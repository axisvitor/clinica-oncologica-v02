"""
Quiz Question Tasks.

Handles quiz question delivery and progress updates.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID
from celery import current_app as celery_app

from app.database import get_db

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
    from asgiref.sync import async_to_sync

    try:
        with next(get_db()) as db:
            from app.domain.quizzes.integration.flow_integration import (
                ConversationalQuizService,
            )
            from app.services.quiz import QuizSessionService, QuizTemplateService

            quiz_flow_service = ConversationalQuizService(db)
            quiz_session_service = QuizSessionService(db)

            # Get active session
            active_session = quiz_session_service.get_active_session(UUID(patient_id))  # type: ignore[attr-defined]

            if not active_session:
                return {"success": False, "error": "No active quiz session found"}

            # Get template and questions
            template_service = QuizTemplateService(db)
            template = template_service.get_template(active_session.quiz_template_id)

            # Send next question using async method (async_to_sync for Celery compatibility)
            async_to_sync(quiz_flow_service._send_next_question)(
                patient_id=UUID(patient_id),
                session=active_session,
                questions=template.questions,
                question_index=question_index,
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
    from asgiref.sync import async_to_sync

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

                # Send via UnifiedWhatsAppService (async_to_sync for Celery compatibility)
                success = async_to_sync(whatsapp_service.send_message)(message)

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
