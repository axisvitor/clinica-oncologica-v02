"""
Quiz Question Tasks.

Handles quiz question delivery and progress updates.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID
from app.task_queue import task_queue as celery_app

from app.database import get_scoped_session
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


def _parse_uuid(value: str, field_name: str) -> UUID:
    try:
        return UUID(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field_name}: {value}") from exc


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

            # Validate target session explicitly (do not fallback to any active session).
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

            # Get template and questions
            template_service = QuizTemplateService(db)
            template = template_service.get_template(target_session.quiz_template_id)
            questions = list(template.questions or [])
            if question_index >= len(questions):
                return {
                    "success": False,
                    "error": "question_index out of range for quiz template",
                    "non_retryable": True,
                }

            # Idempotency guard: avoid duplicate delivery for the same question index.
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

            # Send next question using async method (async_to_sync for Celery compatibility)
            async_to_sync(quiz_flow_service._send_next_question)(
                patient_id=patient_uuid,
                session=target_session,
                questions=questions,
                question_index=question_index,
            )
            session_metadata["last_question_sent_index"] = question_index
            session_metadata["last_question_sent_at"] = now_sao_paulo().isoformat()
            target_session.session_metadata = session_metadata
            db.commit()

            logger.info(f"Quiz question {question_index} sent to patient {patient_id}")
            return {
                "success": True,
                "patient_id": patient_id,
                "question_index": question_index,
                "session_id": str(target_session.id),
            }

    except ValueError as exc:
        logger.error(f"Non-retryable quiz question error: {exc}")
        return {
            "success": False,
            "error": str(exc),
            "non_retryable": True,
            "final_failure": True,
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
    try:
        patient_uuid = _parse_uuid(patient_id, "patient_id")
        session_uuid = _parse_uuid(quiz_session_id, "quiz_session_id")

        if not isinstance(progress_data, dict):
            return {
                "success": False,
                "reason": "Invalid progress data",
                "non_retryable": True,
            }

        from app.database import get_async_session_factory
        from app.models.message import (
            Message,
            MessageDirection,
            MessageStatus,
            MessageType,
        )
        from app.services.unified_whatsapp_service import (
            create_unified_whatsapp_service,
        )
        from app.utils.async_helpers import run_async

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

        async def _send_progress_async() -> dict[str, Any]:
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
                    message.message_metadata["failure_reason"] = (
                        "Message sending failed"
                    )

                await db.commit()

                return {
                    "success": success,
                    "message_id": str(message.id),
                    "progress_percent": progress_percent,
                }

        result = run_async(_send_progress_async())
        logger.info(f"Quiz progress update sent to patient {patient_id}")
        return result

    except ValueError as exc:
        logger.error(f"Non-retryable progress update error: {exc}")
        return {
            "success": False,
            "error": str(exc),
            "non_retryable": True,
            "final_failure": True,
        }

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
