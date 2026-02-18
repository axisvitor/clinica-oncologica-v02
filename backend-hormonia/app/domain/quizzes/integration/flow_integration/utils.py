"""
Utility functions for quiz flow integration.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.flow import PatientFlowState
from app.schemas.monthly_quiz import DeliveryMethod

from .trigger_service import QuizTriggerService
from .response_handler import ConversationalQuizService


def get_quiz_trigger_service(db: Session) -> QuizTriggerService:
    """
    Get quiz trigger service instance.

    Args:
        db: Database session

    Returns:
        QuizTriggerService instance
    """
    return QuizTriggerService(db)


def get_conversational_quiz_service(db: Session) -> ConversationalQuizService:
    """
    Get conversational quiz service instance.

    Args:
        db: Database session

    Returns:
        ConversationalQuizService instance
    """
    return ConversationalQuizService(db)


async def process_quiz_response_with_debounce(
    db: Session,
    *,
    patient_id: UUID,
    quiz_session_id: UUID,
    current_question_id: str,
    response_text: str,
    message_metadata: Optional[dict[str, Any]] = None,
    debounce_window_seconds: int = 3,
) -> dict[str, Any]:
    """
    Canonical quiz response processing path with debounce + action handling.

    This utility consolidates duplicated behavior across webhook handlers and agents.
    """
    from app.services.quiz_response_debounce import get_quiz_debouncer

    debouncer = get_quiz_debouncer(debounce_window_seconds=debounce_window_seconds)
    metadata = dict(message_metadata or {})

    should_process = await debouncer.should_process_response(
        session_id=quiz_session_id,
        question_id=current_question_id,
        message_metadata=metadata,
    )

    if not should_process:
        return {
            "success": False,
            "action": "debounced",
            "message": "Response ignored - within debounce window",
        }

    quiz_service = ConversationalQuizService(db)
    result = await quiz_service.process_quiz_response(
        patient_id=patient_id,
        response_text=response_text,
        message_metadata=metadata,
    )

    action = result.get("action")
    if action == "quiz_completed":
        await debouncer.clear_debounce(quiz_session_id)
    elif action == "request_clarification":
        await debouncer.clear_debounce(quiz_session_id, current_question_id)
    elif action == "next_question":
        # ConversationalQuizService already sends the next question inline.
        result["next_question_sent"] = True

    return result


async def trigger_monthly_quiz_via_link(
    db: Session,
    patient_id: UUID,
    quiz_template_id: UUID,
    quiz_info: dict[str, Any],
    flow_state: PatientFlowState,
    delivery_method: DeliveryMethod | None = None,
) -> dict[str, Any]:
    """
    Convenience function to trigger monthly quiz via link.

    Args:
        db: Database session
        patient_id: Patient UUID
        quiz_template_id: Quiz template UUID
        quiz_info: Quiz information
        flow_state: Patient flow state
        delivery_method: Optional delivery method override

    Returns:
        Trigger result dictionary
    """
    quiz_trigger_service = QuizTriggerService(db)
    return await quiz_trigger_service._trigger_quiz_via_link(
        patient_id=patient_id,
        quiz_template_id=quiz_template_id,
        quiz_info=quiz_info,
        flow_state=flow_state,
    )
