"""
Response handlers for invalid and quiz responses.
"""

import logging
from datetime import datetime
from uuid import UUID

from app.services.ai import ConcernLevel
from app.utils.constants import ERROR_MESSAGES

from .models import (
    ResponseProcessingResult,
    StructuredResponse,
    InboundMessage,
    InteractiveResponse,
    ResponseValidationResult,
    ResponseType,
    ResponseFactory,
    FlowAction,
)

logger = logging.getLogger(__name__)


class ResponseHandlers:
    """Handles invalid and special case responses."""

    async def handle_invalid_response(
        self,
        patient_id: UUID,
        inbound_message: InboundMessage,
        validation_result: ResponseValidationResult,
    ) -> ResponseProcessingResult:
        """
        Handle invalid response by creating appropriate error response.

        Args:
            patient_id: Patient identifier
            inbound_message: Inbound message data
            validation_result: Validation result

        Returns:
            Response processing result
        """
        try:
            # Create a basic structured response for invalid input
            structured_response = ResponseFactory.create_error_response(
                patient_id=patient_id,
                original_message=inbound_message.content,
                response_type=validation_result.response_type,
                validation_errors=validation_result.validation_errors,
            )

            # Generate helpful error message
            if "Empty message content" in validation_result.validation_errors:
                error_message = ERROR_MESSAGES.get("empty_content", "Mensagem vazia")
            elif "Invalid button response" in str(validation_result.validation_errors):
                error_message = ERROR_MESSAGES.get(
                    "invalid_button", "Resposta inválida"
                )
            else:
                error_message = ERROR_MESSAGES.get("generic_error", "Erro genérico")

            return ResponseProcessingResult(
                patient_id=patient_id,
                structured_response=structured_response,
                flow_actions=[],
                follow_up_message=error_message,
                state_updates=None,
                escalation_required=False,
            )

        except Exception as e:
            logger.error(f"Failed to handle invalid response: {e}")
            raise

    async def handle_invalid_interactive_response(
        self,
        patient_id: UUID,
        interactive_response: InteractiveResponse,
        validation_result: ResponseValidationResult,
    ) -> ResponseProcessingResult:
        """
        Handle invalid interactive response.

        Args:
            patient_id: Patient identifier
            interactive_response: Interactive response data
            validation_result: Validation result

        Returns:
            Response processing result
        """
        try:
            structured_response = StructuredResponse(
                patient_id=patient_id,
                original_message=interactive_response.response_value,
                response_type=interactive_response.response_type,
                extracted_data={
                    "validation_errors": validation_result.validation_errors
                },
                sentiment_analysis={"sentiment": "neutral", "confidence": 0.0},
                medical_concerns=[],
                concern_level=ConcernLevel.LOW,
                requires_attention=False,
                confidence_score=0.0,
            )

            error_message = ERROR_MESSAGES.get(
                "invalid_interactive", "Resposta interativa inválida"
            )

            return ResponseProcessingResult(
                patient_id=patient_id,
                structured_response=structured_response,
                flow_actions=[],
                follow_up_message=error_message,
                state_updates=None,
                escalation_required=False,
            )

        except Exception as e:
            logger.error(f"Failed to handle invalid interactive response: {e}")
            raise


class QuizResponseHandler:
    """Handles quiz-specific response processing."""

    def __init__(self, quiz_service):
        """
        Initialize quiz response handler.

        Args:
            quiz_service: Quiz service instance
        """
        self.quiz_service = quiz_service

    async def handle_quiz_response(
        self, patient_id: UUID, inbound_message: InboundMessage
    ) -> ResponseProcessingResult:
        """
        Handle patient response during quiz session.

        Args:
            patient_id: Patient identifier
            inbound_message: Inbound message data

        Returns:
            Response processing result
        """
        try:
            # Process quiz response
            quiz_result = await self.quiz_service.process_quiz_response(
                patient_id=patient_id,
                response_text=inbound_message.content,
                message_metadata=inbound_message.metadata,
            )

            # Create structured response based on quiz processing result
            structured_response = StructuredResponse(
                patient_id=patient_id,
                original_message=inbound_message.content,
                response_type=ResponseType.TEXT,
                extracted_data={
                    "quiz_response": True,
                    "quiz_result": quiz_result,
                    "raw_text": inbound_message.content,
                },
                sentiment_analysis={"sentiment": "neutral", "confidence": 0.8},
                medical_concerns=[],
                concern_level=ConcernLevel.LOW,
                requires_attention=False,
                confidence_score=0.8,
            )

            # Determine flow actions based on quiz result
            flow_actions = []
            state_updates = {}
            follow_up_message = None

            if quiz_result["action"] == "quiz_completed":
                # Quiz completed - return to normal flow
                flow_actions.append(
                    FlowAction(
                        action_type="quiz_completed",
                        parameters={"session_id": quiz_result.get("session_id")},
                        priority="normal",
                    )
                )

                state_updates = {
                    "quiz_state": "completed",
                    "quiz_completed_at": datetime.utcnow().isoformat(),
                }

            elif quiz_result["action"] == "next_question":
                # Continue with quiz
                state_updates = {
                    "quiz_state": "awaiting_response",
                    "current_question_index": quiz_result.get("question_index", 0),
                }

            elif quiz_result["action"] == "request_clarification":
                # Invalid response - clarification already sent
                state_updates = {
                    "quiz_state": "awaiting_response",
                    "last_clarification_at": datetime.utcnow().isoformat(),
                }

            elif quiz_result["action"] == "error":
                # Quiz processing error
                structured_response.requires_attention = True
                structured_response.concern_level = ConcernLevel.MEDIUM

                flow_actions.append(
                    FlowAction(
                        action_type="escalate_quiz_error",
                        parameters={"error": quiz_result.get("error")},
                        priority="high",
                    )
                )

            return ResponseProcessingResult(
                patient_id=patient_id,
                structured_response=structured_response,
                flow_actions=flow_actions,
                follow_up_message=follow_up_message,
                state_updates=state_updates,
                escalation_required=quiz_result.get("action") == "error",
            )

        except Exception as e:
            logger.error(f"Error handling quiz response: {e}")

            # Fallback response
            structured_response = ResponseFactory.create_fallback_response(
                patient_id=patient_id,
                original_message=inbound_message.content,
                response_type=ResponseType.TEXT,
            )

            return ResponseProcessingResult(
                patient_id=patient_id,
                structured_response=structured_response,
                flow_actions=[],
                follow_up_message="Desculpe, houve um problema ao processar sua resposta do quiz. Nossa equipe foi notificada.",
                state_updates=None,
                escalation_required=True,
            )
