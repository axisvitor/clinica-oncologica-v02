"""
Context builder for flow execution.
Builds execution context with patient data, flow state, quiz responses, and messages.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.patient import Patient
from app.models.flow import PatientFlowState
from app.repositories.message import MessageRepository
from app.repositories.quiz import QuizResponseRepository


class ContextBuilder:
    """Context builder for flow execution."""

    def __init__(self, db: Session):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.quiz_repo = QuizResponseRepository(db)

    def build_context(
        self,
        patient: Patient,
        flow_state: PatientFlowState,
        additional_context: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Build execution context for flow processing.

        Args:
            patient: Patient model
            flow_state: Current flow state
            additional_context: Additional context data

        Returns:
            Dict containing all context data
        """
        context = {
            "patient_id": patient.id,
            "patient_data": {
                "name": patient.name,
                "phone": patient.phone,
                "treatment_type": patient.treatment_type,
                "treatment_start_date": patient.treatment_start_date,
                "current_day": patient.current_day,
                "flow_state": patient.flow_state.value,
                "metadata": patient.patient_data or {}
            },
            "flow_start_time": flow_state.started_at,
            "current_time": datetime.utcnow(),
            "flow_data": flow_state.state_data or {},
            "quiz_responses": self._get_recent_quiz_responses(patient.id),
            "message_count": self._get_message_count(patient.id),
            "recent_messages": self._get_recent_messages(patient.id)
        }

        if additional_context:
            context.update(additional_context)

        return context

    def _get_recent_quiz_responses(self, patient_id: UUID) -> dict[str, Any]:
        """Get recent quiz responses for the patient."""
        # Get responses from last 7 days
        since_date = datetime.utcnow() - timedelta(days=7)
        responses = self.quiz_repo.get_by_patient_since(patient_id, since_date)

        # Convert to dict format for easy access
        quiz_data = {}
        for response in responses:
            quiz_data[response.question_id] = response.response_value

        return quiz_data

    def _get_message_count(self, patient_id: UUID) -> int:
        """Get total message count for the patient."""
        return self.message_repo.count_by_patient(patient_id)

    def _get_recent_messages(self, patient_id: UUID) -> List[dict[str, Any]]:
        """Get recent messages for the patient."""
        messages = self.message_repo.get_by_patient(patient_id, limit=10)

        return [
            {
                "id": str(msg.id),
                "direction": msg.direction.value,
                "type": msg.type.value,
                "content": msg.content,
                "status": msg.status.value,
                "created_at": msg.created_at
            }
            for msg in messages
        ]
