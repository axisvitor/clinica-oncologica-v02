"""
Quiz Response Tasks.

Handles quiz response processing and report generation.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID
from app.task_queue import task_queue as celery_app

from app.database import get_scoped_session
from app.exceptions import NotFoundError
from app.tasks.quiz_flow.helpers import _notify_providers_of_quiz_completion
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


def _parse_uuid(value: str, field_name: str) -> UUID:
    """Parse UUID input and raise explicit validation error."""
    try:
        return UUID(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field_name}: {value}") from exc


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
        patient_uuid = _parse_uuid(patient_id, "patient_id")
        message_uuid = _parse_uuid(message_id, "message_id")

        with get_scoped_session() as db:
            from asgiref.sync import async_to_sync
            from app.domain.quizzes.integration.flow_integration.response_handler import (
                ConversationalQuizService,
            )
            from app.repositories.message import MessageRepository

            quiz_flow_service = ConversationalQuizService(db)

            # Get message
            message_repo = MessageRepository(db)
            message = message_repo.get(message_uuid)

            if not message:
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

            message_metadata = dict(message.message_metadata or {})
            if message_metadata.get("quiz_response_processed_at"):
                logger.info(
                    "Ignoring duplicate quiz response processing for message %s", message_id
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

            # FIX: Use async_to_sync instead of asyncio.run() to avoid
            # "cannot be called from a running event loop" errors
            result = async_to_sync(quiz_flow_service.process_quiz_response)(
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

    except (ValueError, NotFoundError) as exc:
        logger.error(f"Non-retryable quiz response error: {exc}")
        return {
            "success": False,
            "error": str(exc),
            "non_retryable": True,
            "final_failure": True,
        }

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
        patient_uuid = _parse_uuid(patient_id, "patient_id")
        quiz_session_uuid = _parse_uuid(quiz_session_id, "quiz_session_id")

        with get_scoped_session() as db:
            from app.models.report import Report, ReportType
            from app.services.quiz import QuizSessionService, QuizResponseService
            from app.services.reporting.quiz_report_generator import (
                get_quiz_report_generator,
            )
            from app.utils.async_helpers import run_async

            quiz_session_service = QuizSessionService(db)
            quiz_response_service = QuizResponseService(db)

            # Get quiz session and responses
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

            # Check for existing persisted report for this quiz session before generating a new one.
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

            report_generator = get_quiz_report_generator(db)
            report_id = run_async(report_generator.generate_quiz_report(quiz_session_uuid))
            session_metadata["quiz_report_id"] = str(report_id)
            session_metadata["quiz_report_generated_at"] = now_sao_paulo().isoformat()
            quiz_session.session_metadata = session_metadata
            db.commit()

            # Notify healthcare providers
            _notify_providers_of_quiz_completion(patient_id, quiz_session_id, report_id)

            logger.info(f"Quiz report generated for patient {patient_id}: {report_id}")

            return {
                "success": True,
                "report_id": str(report_id),
                "patient_id": patient_id,
                "quiz_session_id": quiz_session_id,
            }

    except ValueError as exc:
        logger.error(f"Non-retryable quiz report error: {exc}")
        return {
            "success": False,
            "error": str(exc),
            "non_retryable": True,
            "final_failure": True,
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
