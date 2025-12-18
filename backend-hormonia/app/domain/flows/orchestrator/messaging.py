"""
Flow Orchestrator - Messaging Module

Handles message sending and composition orchestration for flow execution.
"""

import logging
from typing import Dict, Any, Optional
from uuid import UUID

from app.models.patient import Patient
from ..messaging import MessageComposer, MessageSender

logger = logging.getLogger(__name__)


class FlowMessagingOrchestrator:
    """Orchestrates message composition and sending for flow execution."""

    def __init__(
        self, message_composer: MessageComposer, message_sender: MessageSender
    ):
        """
        Initialize FlowMessagingOrchestrator.

        Args:
            message_composer: MessageComposer instance for content generation
            message_sender: MessageSender instance for message delivery
        """
        self.message_composer = message_composer
        self.message_sender = message_sender

    async def send_flow_message(
        self,
        patient: Patient,
        flow_state_id: UUID,
        flow_type: str,
        current_day: int,
        operation: str,
        message_template: Any,
        logger_instance: Optional[logging.Logger] = None,
    ) -> Dict[str, Any]:
        """
        Generate and send a personalized flow message.

        Args:
            patient: Patient model instance
            flow_state_id: UUID of flow state
            flow_type: Type of flow (e.g., 'early', 'mid', 'late')
            current_day: Current treatment day
            operation: Flow operation type
            message_template: Message template with intent and day info
            logger_instance: Optional logger for error tracking

        Returns:
            Dict containing success status and message details
        """
        log = logger_instance or logger

        try:
            # Generate personalized message using AI
            personalized_message = (
                await self.message_composer.generate_personalized_message(
                    patient, message_template, current_day, flow_type
                )
            )

            # Schedule message delivery
            message_result = await self.message_sender.schedule_flow_message(
                patient_id=patient.id,
                patient=patient,
                flow_state_id=flow_state_id,
                flow_type=flow_type,
                current_day=current_day,
                operation=operation,
                message_template_intent=message_template.intent,
                message_template_day=message_template.day,
                personalized_content=personalized_message,
            )

            return {
                "success": message_result.get("success", False),
                "message": "Flow message sent",
                "message_scheduled": message_result.get("message_id") is not None,
                "message_id": message_result.get("message_id"),
                "template_intent": message_template.intent,
                "personalized": True,
            }

        except Exception as e:
            log.error(
                f"Error sending flow message: {e}",
                extra={
                    "patient_id": str(patient.id),
                    "flow_type": flow_type,
                    "day": current_day,
                },
            )
            return {
                "success": False,
                "message": f"Message sending failed: {str(e)}",
                "error": str(e),
            }
