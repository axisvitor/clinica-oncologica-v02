"""
Medical concern follow-up generator.
Handles medical concerns with appropriate follow-up actions.
"""

import logging
from typing import List
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from .base import BaseGenerator
from ..enums import FollowUpType
from ..models import FollowUpAction
from app.services.analytics.data_extraction import ConcernLevel

logger = logging.getLogger(__name__)


class MedicalConcernGenerator(BaseGenerator):
    """Generates follow-up actions for medical concerns."""

    async def handle_medical_concerns(
        self, patient_id: UUID, medical_concerns: List[str], original_message: str
    ) -> List[FollowUpAction]:
        """
        Handle medical concerns with appropriate follow-up actions.

        Args:
            patient_id: Patient UUID
            medical_concerns: List of medical concerns
            original_message: Original patient message

        Returns:
            List of follow-up actions
        """
        actions = []

        try:
            for concern in medical_concerns:
                # Determine concern severity and type
                concern_level = self.assess_concern_severity(concern)
                concern_type = self.classify_concern_type(concern)

                # Create appropriate follow-up action
                if concern_level in [ConcernLevel.HIGH, ConcernLevel.CRITICAL]:
                    # High priority medical clarification
                    action = FollowUpAction(
                        action_id=uuid4(),
                        patient_id=patient_id,
                        follow_up_type=FollowUpType.MEDICAL_CLARIFICATION,
                        priority="high",
                        scheduled_for=datetime.utcnow() + timedelta(minutes=10),
                        parameters={
                            "concern": concern,
                            "concern_type": concern_type.value
                            if concern_type
                            else "general",
                            "original_message": original_message,
                            "clarification_questions": self.generate_clarification_questions(
                                concern
                            ),
                        },
                    )
                    actions.append(action)

                elif concern_level == ConcernLevel.MEDIUM:
                    # Provider notification
                    action = FollowUpAction(
                        action_id=uuid4(),
                        patient_id=patient_id,
                        follow_up_type=FollowUpType.PROVIDER_ALERT,
                        priority="medium",
                        scheduled_for=datetime.utcnow() + timedelta(minutes=30),
                        parameters={
                            "concern": concern,
                            "concern_type": concern_type.value
                            if concern_type
                            else "general",
                            "original_message": original_message,
                            "review_required": True,
                        },
                    )
                    actions.append(action)

            return actions

        except Exception as e:
            logger.error(f"Failed to handle medical concerns: {e}")
            return actions

    async def handle_response_type_specific_actions(
        self, patient_id: UUID, structured_response
    ) -> List[FollowUpAction]:
        """
        Handle response type specific follow-up actions.

        Args:
            patient_id: Patient UUID
            structured_response: Processed response data

        Returns:
            List of follow-up actions
        """
        actions = []

        try:
            extracted_data = structured_response.extracted_data

            # Handle pain scale responses
            if "pain_scale" in extracted_data:
                pain_level = extracted_data["pain_scale"]
                if pain_level >= 7:
                    action = FollowUpAction(
                        action_id=uuid4(),
                        patient_id=patient_id,
                        follow_up_type=FollowUpType.MEDICAL_CLARIFICATION,
                        priority="high",
                        scheduled_for=datetime.utcnow() + timedelta(minutes=15),
                        parameters={
                            "pain_level": pain_level,
                            "follow_up_questions": [
                                "A dor está interferindo em suas atividades?",
                                "Você tomou algum analgésico?",
                                "A dor mudou desde ontem?",
                            ],
                        },
                    )
                    actions.append(action)

            # Handle medication mentions
            if extracted_data.get("medication_mentioned"):
                action = FollowUpAction(
                    action_id=uuid4(),
                    patient_id=patient_id,
                    follow_up_type=FollowUpType.MEDICATION_GUIDANCE,
                    priority="normal",
                    scheduled_for=datetime.utcnow() + timedelta(hours=2),
                    parameters={
                        "medication_context": structured_response.original_message,
                        "guidance_type": "general_medication_support",
                    },
                )
                actions.append(action)

            # Handle negative mood indicators
            if extracted_data.get("mood_indicator") == "negative":
                action = FollowUpAction(
                    action_id=uuid4(),
                    patient_id=patient_id,
                    follow_up_type=FollowUpType.EMOTIONAL_SUPPORT,
                    priority="normal",
                    scheduled_for=datetime.utcnow() + timedelta(hours=1),
                    parameters={
                        "emotional_state": "negative",
                        "support_type": "encouragement_and_resources",
                    },
                )
                actions.append(action)

            # Handle positive responses with encouragement
            elif structured_response.sentiment_analysis.get("sentiment") == "positive":
                action = FollowUpAction(
                    action_id=uuid4(),
                    patient_id=patient_id,
                    follow_up_type=FollowUpType.TREATMENT_ENCOURAGEMENT,
                    priority="low",
                    scheduled_for=datetime.utcnow() + timedelta(hours=4),
                    parameters={
                        "encouragement_type": "positive_reinforcement",
                        "progress_acknowledgment": True,
                    },
                )
                actions.append(action)

            return actions

        except Exception as e:
            logger.error(f"Failed to handle response type specific actions: {e}")
            return actions
