"""
Flow-related helper functions for response processing.
"""

import logging
from typing import List, Optional, Any

from app.services.ai import ConcernLevel
from app.models.flow import PatientFlowState

from .models import StructuredResponse, FlowAction, ResponseType

logger = logging.getLogger(__name__)


class FlowHelpers:
    """Helper functions for flow-related operations."""

    @staticmethod
    async def determine_flow_actions(
        structured_response: StructuredResponse, flow_state: Optional[PatientFlowState]
    ) -> List[FlowAction]:
        """
        Determine flow actions based on response analysis.

        Args:
            structured_response: Structured response data
            flow_state: Optional current flow state

        Returns:
            List of flow actions
        """
        actions = []

        try:
            # Action based on concern level
            if structured_response.concern_level == ConcernLevel.CRITICAL:
                actions.append(
                    FlowAction(
                        action_type="escalate_immediately",
                        parameters={
                            "concern_level": "critical",
                            "medical_concerns": structured_response.medical_concerns,
                            "patient_message": structured_response.original_message,
                        },
                        priority="critical",
                        delay_seconds=0,
                    )
                )

            elif structured_response.concern_level == ConcernLevel.HIGH:
                actions.append(
                    FlowAction(
                        action_type="schedule_provider_review",
                        parameters={
                            "concern_level": "high",
                            "medical_concerns": structured_response.medical_concerns,
                            "review_within_hours": 4,
                        },
                        priority="high",
                        delay_seconds=300,  # 5 minutes
                    )
                )

            # Action based on response type
            if structured_response.response_type == ResponseType.BUTTON:
                actions.append(
                    FlowAction(
                        action_type="process_button_response",
                        parameters={
                            "button_value": structured_response.extracted_data.get(
                                "button_value"
                            ),
                            "flow_context": structured_response.extracted_data.get(
                                "flow_context", {}
                            ),
                        },
                        priority="normal",
                        delay_seconds=0,
                    )
                )

            # Action based on extracted patterns
            if structured_response.extracted_data.get("boolean_response") is not None:
                actions.append(
                    FlowAction(
                        action_type="process_boolean_response",
                        parameters={
                            "response_value": structured_response.extracted_data[
                                "boolean_response"
                            ],
                            "context": structured_response.extracted_data.get(
                                "flow_context", {}
                            ),
                        },
                        priority="normal",
                        delay_seconds=0,
                    )
                )

            return actions

        except Exception as e:
            logger.error(f"Failed to determine flow actions: {e}")
            return []

    @staticmethod
    async def generate_follow_up_message(
        structured_response: StructuredResponse, flow_state: Optional[PatientFlowState]
    ) -> Optional[str]:
        """
        Generate follow-up message based on response analysis.

        Args:
            structured_response: Structured response data
            flow_state: Optional current flow state

        Returns:
            Follow-up message or None
        """
        try:
            # Generate empathetic follow-up for high concern responses
            if structured_response.concern_level in [
                ConcernLevel.HIGH,
                ConcernLevel.CRITICAL,
            ]:
                return "Obrigada por compartilhar isso comigo. Vou conectar você com sua equipe médica."

            # Generate acknowledgment for positive responses
            if structured_response.extracted_data.get("mood_indicator") == "positive":
                return "Que bom saber! Continue assim!"

            # Generate supportive message for negative responses
            if structured_response.extracted_data.get("mood_indicator") == "negative":
                return "Entendo. Estou aqui para apoiá-la."

            # Generate confirmation for boolean responses
            if structured_response.extracted_data.get("boolean_response") is True:
                return "Perfeito! Obrigada por confirmar."
            elif structured_response.extracted_data.get("boolean_response") is False:
                return "Entendi. Obrigada por me avisar."

            return None

        except Exception as e:
            logger.error(f"Failed to generate follow-up message: {e}")
            return None

    @staticmethod
    async def prepare_state_updates(
        structured_response: StructuredResponse, flow_state: Optional[PatientFlowState]
    ) -> Optional[dict[str, Any]]:
        """
        Prepare state updates based on response analysis.

        Args:
            structured_response: Structured response data
            flow_state: Optional current flow state

        Returns:
            State updates dictionary or None
        """
        try:
            if not flow_state:
                return None

            updates = {}

            # Update last response data
            updates["last_response"] = {
                "timestamp": structured_response.timestamp.isoformat(),
                "type": structured_response.response_type.value,
                "sentiment": structured_response.sentiment_analysis.get("sentiment"),
                "concern_level": structured_response.concern_level.value,
                "requires_attention": structured_response.requires_attention,
            }

            # Update extracted patterns
            if structured_response.extracted_data:
                updates["extracted_patterns"] = structured_response.extracted_data

            # Update medical concerns if any
            if structured_response.medical_concerns:
                updates["medical_concerns"] = structured_response.medical_concerns

            return updates

        except Exception as e:
            logger.error(f"Failed to prepare state updates: {e}")
            return None

    @staticmethod
    def check_escalation_required(structured_response: StructuredResponse) -> bool:
        """
        Check if escalation is required based on response analysis.

        Args:
            structured_response: Structured response data

        Returns:
            True if escalation required
        """
        return (
            structured_response.concern_level
            in [ConcernLevel.HIGH, ConcernLevel.CRITICAL]
            or structured_response.requires_attention
            or bool(structured_response.medical_concerns)
        )
