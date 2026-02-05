"""
Quiz Flow Helper Functions.

Shared helper functions for quiz flow tasks.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.database import get_db, get_scoped_session

logger = logging.getLogger(__name__)


def _trigger_whatsapp_fallback(patient_id: UUID, quiz_session_id: UUID):
    """
    Trigger WhatsApp conversational fallback when session expires.

    Args:
        patient_id: Patient UUID
        quiz_session_id: Quiz session UUID
    """
    from asgiref.sync import async_to_sync

    try:
        with get_scoped_session() as db:
            # Get quiz session info
            from app.models.quiz import QuizSession

            session = (
                db.query(QuizSession).filter(QuizSession.id == quiz_session_id).first()
            )

            if not session or session.is_completed:
                return  # Already completed or not found

            # Use QuizTriggerService to trigger a new quiz
            from app.domain.quizzes.integration.flow_integration import (
                QuizTriggerService,
            )
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
                template = template_service.template_repository.get(  # type: ignore[attr-defined]
                    session.quiz_template_id
                )

                # FIX: Use async_to_sync instead of asyncio.run() to avoid
                # event loop conflicts in Celery tasks
                fallback_result = async_to_sync(
                    trigger_service._trigger_quiz_via_whatsapp
                )(
                    patient_id=patient_id,
                    template=template,
                    quiz_info=quiz_info,
                    flow_state=flow_state,
                )

                if fallback_result.get("success"):
                    logger.info(f"Triggered WhatsApp fallback for patient {patient_id}")
                else:
                    logger.warning(
                        f"Failed to trigger fallback: {fallback_result.get('error')}"
                    )

    except Exception as e:
        logger.error(f"Error triggering WhatsApp fallback: {e}")


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

        Settings()

        with get_scoped_session() as db:
            # Use consolidated alert system
            from app.services.alerts import AlertManagerAdapter

            alert_service = AlertManagerAdapter(db)

            # Create alert for healthcare providers
            alert_data = {
                "patient_id": UUID(patient_id),
                "alert_type": "quiz_completed",
                "priority": "medium",
                "title": "Monthly Quiz Completed",
                "message": "Patient has completed their monthly health assessment. Report available.",
                "metadata": {
                    "quiz_session_id": quiz_session_id,
                    "report_id": report_id,
                    "requires_review": True,
                },
            }

            alert_service.create_alert(alert_data)  # type: ignore[attr-defined]

    except Exception as e:
        logger.error(f"Error notifying providers of quiz completion: {e}")
