"""
Flow-specific exception classes for error handling and recovery.
"""
from typing import Optional, Dict, Any
from uuid import UUID


class FlowException(Exception):
    """Base exception for all flow-related errors."""
    
    def __init__(self, message: str, patient_id: Optional[UUID] = None, 
                 flow_type: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.patient_id = patient_id
        self.flow_type = flow_type
        self.context = context or {}


class MessageDeliveryError(FlowException):
    """Exception raised when message delivery fails."""
    
    def __init__(self, message: str, patient_id: UUID, message_id: Optional[UUID] = None,
                 retry_count: int = 0, last_error: Optional[str] = None):
        super().__init__(message, patient_id=patient_id)
        self.message_id = message_id
        self.retry_count = retry_count
        self.last_error = last_error


class FlowStateCorruptionError(FlowException):
    """Exception raised when flow state data is corrupted or invalid."""
    
    def __init__(self, message: str, patient_id: UUID, flow_state_data: Optional[Dict[str, Any]] = None,
                 corruption_type: str = "unknown"):
        super().__init__(message, patient_id=patient_id)
        self.flow_state_data = flow_state_data
        self.corruption_type = corruption_type


class FlowProcessingError(FlowException):
    """Exception raised during flow processing operations."""
    
    def __init__(self, message: str, patient_id: UUID, flow_type: str, 
                 current_day: Optional[int] = None, operation: Optional[str] = None):
        super().__init__(message, patient_id=patient_id, flow_type=flow_type)
        self.current_day = current_day
        self.operation = operation


class ExternalServiceError(FlowException):
    """Exception raised when external services fail."""
    
    def __init__(self, message: str, service_name: str, error_code: Optional[str] = None,
                 is_recoverable: bool = True, retry_after: Optional[int] = None):
        super().__init__(message)
        self.service_name = service_name
        self.error_code = error_code
        self.is_recoverable = is_recoverable
        self.retry_after = retry_after


class TemplateLoadError(FlowException):
    """Exception raised when flow templates cannot be loaded."""
    
    def __init__(self, message: str, template_path: str, flow_type: Optional[str] = None):
        super().__init__(message, flow_type=flow_type)
        self.template_path = template_path


class AIServiceError(ExternalServiceError):
    """Exception raised when AI services (Gemini, OpenAI) fail."""
    
    def __init__(self, message: str, ai_service: str, prompt: Optional[str] = None,
                 error_code: Optional[str] = None, is_recoverable: bool = True):
        super().__init__(message, service_name=ai_service, error_code=error_code, 
                        is_recoverable=is_recoverable)
        self.prompt = prompt


class RedisConnectionError(ExternalServiceError):
    """Exception raised when Redis connection fails."""
    
    def __init__(self, message: str, operation: str, key: Optional[str] = None):
        super().__init__(message, service_name="redis", is_recoverable=True)
        self.operation = operation
        self.key = key


class DatabaseError(FlowException):
    """Exception raised for database-related flow errors."""
    
    def __init__(self, message: str, operation: str, table: Optional[str] = None,
                 patient_id: Optional[UUID] = None, is_recoverable: bool = True):
        super().__init__(message, patient_id=patient_id)
        self.operation = operation
        self.table = table
        self.is_recoverable = is_recoverable


class FlowValidationError(FlowException):
    """Exception raised when flow data validation fails."""
    
    def __init__(self, message: str, validation_errors: Dict[str, str],
                 patient_id: Optional[UUID] = None, flow_type: Optional[str] = None):
        super().__init__(message, patient_id=patient_id, flow_type=flow_type)
        self.validation_errors = validation_errors


class ConcurrencyError(FlowException):
    """Exception raised when concurrent flow operations conflict."""
    
    def __init__(self, message: str, patient_id: UUID, conflicting_operation: str):
        super().__init__(message, patient_id=patient_id)
        self.conflicting_operation = conflicting_operation