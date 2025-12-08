"""
Patient context builder for AI processing.
Constructs comprehensive patient context from various data sources.
"""
import logging
from uuid import UUID

from app.services.ai.ai_service import PatientContext
from app.models.message import MessageDirection
from app.repositories.message import MessageRepository
from app.repositories.flow import FlowStateRepository

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds patient context for AI processing."""

    def __init__(self, message_repo: MessageRepository, flow_state_repo: FlowStateRepository):
        """
        Initialize context builder.

        Args:
            message_repo: Message repository for conversation history
            flow_state_repo: Flow state repository for treatment info
        """
        self.message_repo = message_repo
        self.flow_state_repo = flow_state_repo

    def build_patient_context(self, patient_id: UUID, patient) -> PatientContext:
        """
        Build patient context for AI processing.

        Args:
            patient_id: Patient UUID
            patient: Patient model instance

        Returns:
            PatientContext for AI service
        """
        try:
            # Get recent messages
            recent_messages = self.message_repo.get_conversation_history(patient_id, limit=5)
            recent_responses = [
                msg.content for msg in recent_messages
                if msg.direction == MessageDirection.INBOUND and msg.content
            ]

            # Get flow state
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            treatment_day = flow_state.current_step if flow_state else 1

            return PatientContext(
                patient_id=str(patient_id),
                name=patient.name,
                treatment_type=getattr(patient, 'treatment_type', 'general'),
                treatment_day=treatment_day,
                age=getattr(patient, 'age', None),
                recent_responses=recent_responses,
                medical_history=getattr(patient, 'medical_history', {}),
                preferences=getattr(patient, 'preferences', {})
            )

        except Exception as e:
            logger.error(f"Failed to build patient context: {e}")
            raise
