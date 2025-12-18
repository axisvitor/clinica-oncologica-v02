"""
Utility functions for quiz flow integration.
"""

from typing import Any
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
