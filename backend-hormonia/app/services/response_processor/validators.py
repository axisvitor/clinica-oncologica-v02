"""
Response validation logic.
"""
import logging
from typing import Optional

from app.models.flow import PatientFlowState

from .models import (
    ResponseValidationResult,
    ResponseType,
    InboundMessage,
    InteractiveResponse
)

logger = logging.getLogger(__name__)


class ResponseValidator:
    """Validates patient responses against expected contexts."""

    def __init__(self, message_limit: int = 4096):
        """
        Initialize response validator.

        Args:
            message_limit: Maximum message length
        """
        self.message_limit = message_limit

    async def validate_response(self,
                               inbound_message: InboundMessage,
                               response_type: ResponseType,
                               flow_state: Optional[PatientFlowState]) -> ResponseValidationResult:
        """
        Validate response based on expected context.

        Args:
            inbound_message: Inbound message data
            response_type: Type of response
            flow_state: Optional current flow state

        Returns:
            Validation result
        """
        try:
            errors = []

            # Basic content validation
            if not inbound_message.content or not inbound_message.content.strip():
                errors.append("Empty message content")

            # Flow context validation
            if flow_state:
                expected_responses = flow_state.state_data.get('expected_responses', [])
                if expected_responses and response_type == ResponseType.BUTTON:
                    # Validate button response against expected options
                    if inbound_message.content not in expected_responses:
                        errors.append(f"Invalid button response: {inbound_message.content}")

            # Content length validation
            if len(inbound_message.content) > self.message_limit:
                errors.append("Message too long")

            is_valid = len(errors) == 0
            extracted_value = inbound_message.content if is_valid else None

            return ResponseValidationResult(
                is_valid=is_valid,
                response_type=response_type,
                extracted_value=extracted_value,
                validation_errors=errors
            )

        except Exception as e:
            logger.error(f"Response validation failed: {e}")
            return ResponseValidationResult(
                is_valid=False,
                response_type=response_type,
                validation_errors=[f"Validation error: {str(e)}"]
            )

    async def validate_interactive_response(self,
                                           interactive_response: InteractiveResponse,
                                           flow_state: PatientFlowState) -> ResponseValidationResult:
        """
        Validate interactive response against flow context.

        Args:
            interactive_response: Interactive response data
            flow_state: Current flow state

        Returns:
            Validation result
        """
        try:
            errors = []

            # Check if response value is provided
            if not interactive_response.response_value:
                errors.append("Empty response value")

            # Validate against expected responses in flow state
            expected_responses = flow_state.state_data.get('expected_responses', [])
            if expected_responses:
                if interactive_response.response_value not in expected_responses:
                    errors.append(f"Unexpected response: {interactive_response.response_value}")

            # Validate response type consistency
            expected_type = flow_state.state_data.get('expected_response_type')
            if expected_type and expected_type != interactive_response.response_type.value:
                errors.append(
                    f"Response type mismatch: expected {expected_type}, "
                    f"got {interactive_response.response_type.value}"
                )

            is_valid = len(errors) == 0

            return ResponseValidationResult(
                is_valid=is_valid,
                response_type=interactive_response.response_type,
                extracted_value=interactive_response.response_value if is_valid else None,
                validation_errors=errors
            )

        except Exception as e:
            logger.error(f"Interactive response validation failed: {e}")
            return ResponseValidationResult(
                is_valid=False,
                response_type=interactive_response.response_type,
                validation_errors=[f"Validation error: {str(e)}"]
            )
