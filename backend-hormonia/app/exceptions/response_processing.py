"""
Response processing specific exceptions.
"""

from typing import List, Optional
from uuid import UUID

from app.exceptions import ValidationError, ProcessingError


class ResponseValidationError(ValidationError):
    """Raised when response validation fails."""

    def __init__(
        self,
        message: str,
        validation_errors: List[str],
        patient_id: Optional[UUID] = None,
    ):
        super().__init__(message)
        self.validation_errors = validation_errors
        self.patient_id = patient_id


class ResponseProcessingError(ProcessingError):
    """Raised when response processing fails."""

    def __init__(
        self,
        message: str,
        patient_id: Optional[UUID] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.patient_id = patient_id
        self.original_error = original_error


class AIProcessingError(ProcessingError):
    """Raised when AI processing fails."""

    def __init__(
        self, message: str, service_name: str, patient_id: Optional[UUID] = None
    ):
        super().__init__(message)
        self.service_name = service_name
        self.patient_id = patient_id


class FlowStateError(ProcessingError):
    """Raised when flow state operations fail."""

    def __init__(
        self, message: str, patient_id: UUID, flow_state_id: Optional[UUID] = None
    ):
        super().__init__(message)
        self.patient_id = patient_id
        self.flow_state_id = flow_state_id
