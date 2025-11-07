"""
Error classification and recovery strategy selection for flow operations.
Handles error categorization, severity determination, and strategy selection.
"""
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List
from sqlalchemy.exc import SQLAlchemyError

from app.exceptions import (
    FlowStateError,
    FlowOperationError,
    ExternalServiceError,
    ValidationError
)

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""
    MESSAGE_DELIVERY = "message_delivery"
    FLOW_PROCESSING = "flow_processing"
    EXTERNAL_SERVICE = "external_service"
    DATA_CORRUPTION = "data_corruption"
    SYSTEM_ERROR = "system_error"
    VALIDATION_ERROR = "validation_error"


class RecoveryStrategy(Enum):
    """Recovery strategies for different error types."""
    RETRY_EXPONENTIAL = "retry_exponential"
    RETRY_LINEAR = "retry_linear"
    FALLBACK_MESSAGE = "fallback_message"
    SKIP_AND_CONTINUE = "skip_and_continue"
    PAUSE_FLOW = "pause_flow"
    ESCALATE_MANUAL = "escalate_manual"
    RESET_FLOW = "reset_flow"


class ErrorHandlerConstants:
    """Constants for error handler configuration."""

    # Retry delays (in seconds)
    DEFAULT_EXPONENTIAL_DELAYS = [60, 300, 900, 1800, 3600]  # 1min, 5min, 15min, 30min, 1hr
    DEFAULT_LINEAR_DELAY = 300  # 5 minutes

    # Timeouts and expiration
    REDIS_ERROR_TTL = 604800  # 7 days
    REDIS_RETRY_BUFFER = 60  # 1 minute buffer
    FLOW_RESUME_DELAY_HOURS = 1

    # Error keywords for classification
    MESSAGE_KEYWORDS = ["evolution", "whatsapp", "message"]
    EXTERNAL_SERVICE_KEYWORDS = ["gemini", "redis", "api"]
    TIMEOUT_KEYWORDS = ["timeout", "connection"]
    RATE_LIMIT_KEYWORDS = ["rate limit", "quota", "limit"]
    DATABASE_KEYWORDS = ["database", "constraint", "integrity"]
    SYSTEM_RESOURCE_KEYWORDS = ["memory", "disk"]

    # Fallback messages
    FALLBACK_MESSAGE_TEMPLATES = {
        "message_delivery": "Olá {name}! Estou com algumas dificuldades técnicas, mas estou aqui para você. Nossa equipe médica foi notificada e entrará em contato em breve.",
        "external_service": "Oi {name}! Estou passando por uma atualização no sistema. Enquanto isso, se precisar de algo urgente, entre em contato diretamente com nossa equipe médica.",
        "flow_processing": "Olá {name}! Houve um pequeno problema no processamento da sua mensagem. Nossa equipe técnica foi notificada e resolverá em breve.",
        "default": "Olá {name}! Estou enfrentando algumas dificuldades técnicas temporárias. Nossa equipe foi notificada e entrará em contato em breve."
    }


@dataclass
class ErrorHandlerConfig:
    """Configuration for error handler."""
    max_retry_attempts: dict[ErrorCategory, int] = field(default_factory=lambda: {
        ErrorCategory.MESSAGE_DELIVERY: 5,
        ErrorCategory.FLOW_PROCESSING: 3,
        ErrorCategory.EXTERNAL_SERVICE: 7,
        ErrorCategory.DATA_CORRUPTION: 1,
        ErrorCategory.SYSTEM_ERROR: 2,
        ErrorCategory.VALIDATION_ERROR: 1
    })

    retry_delays: dict[RecoveryStrategy, List[int]] = field(default_factory=lambda: {
        RecoveryStrategy.RETRY_EXPONENTIAL: [60, 300, 900, 1800, 3600],  # 1min, 5min, 15min, 30min, 1hr
        RecoveryStrategy.RETRY_LINEAR: [300, 300, 300, 300, 300],  # 5min intervals
    })


class ErrorClassifier:
    """Handles error classification and severity determination."""

    def classify_error(self, error: Exception) -> tuple[ErrorCategory, ErrorSeverity]:
        """Classify error by category and severity."""
        error_type = type(error).__name__
        error_message = str(error).lower()

        # Message delivery errors
        if any(keyword in error_message for keyword in ErrorHandlerConstants.MESSAGE_KEYWORDS):
            if any(keyword in error_message for keyword in ErrorHandlerConstants.TIMEOUT_KEYWORDS):
                return ErrorCategory.MESSAGE_DELIVERY, ErrorSeverity.MEDIUM
            elif any(keyword in error_message for keyword in ErrorHandlerConstants.RATE_LIMIT_KEYWORDS):
                return ErrorCategory.MESSAGE_DELIVERY, ErrorSeverity.LOW
            else:
                return ErrorCategory.MESSAGE_DELIVERY, ErrorSeverity.MEDIUM

        # External service errors
        elif any(keyword in error_message for keyword in ErrorHandlerConstants.EXTERNAL_SERVICE_KEYWORDS):
            if any(keyword in error_message for keyword in ErrorHandlerConstants.TIMEOUT_KEYWORDS):
                return ErrorCategory.EXTERNAL_SERVICE, ErrorSeverity.HIGH
            elif any(keyword in error_message for keyword in ErrorHandlerConstants.RATE_LIMIT_KEYWORDS):
                return ErrorCategory.EXTERNAL_SERVICE, ErrorSeverity.MEDIUM
            else:
                return ErrorCategory.EXTERNAL_SERVICE, ErrorSeverity.MEDIUM

        # Database and data errors
        elif isinstance(error, SQLAlchemyError) or any(keyword in error_message for keyword in ErrorHandlerConstants.DATABASE_KEYWORDS):
            if "constraint" in error_message or "integrity" in error_message:
                return ErrorCategory.DATA_CORRUPTION, ErrorSeverity.HIGH
            else:
                return ErrorCategory.SYSTEM_ERROR, ErrorSeverity.HIGH

        # Flow processing errors
        elif isinstance(error, (FlowStateError, FlowOperationError)):
            if "not found" in error_message:
                return ErrorCategory.FLOW_PROCESSING, ErrorSeverity.MEDIUM
            elif "invalid state" in error_message:
                return ErrorCategory.DATA_CORRUPTION, ErrorSeverity.HIGH
            else:
                return ErrorCategory.FLOW_PROCESSING, ErrorSeverity.MEDIUM

        # Validation errors
        elif isinstance(error, ValidationError):
            return ErrorCategory.VALIDATION_ERROR, ErrorSeverity.LOW

        # System errors
        else:
            if any(keyword in error_message for keyword in ErrorHandlerConstants.SYSTEM_RESOURCE_KEYWORDS):
                return ErrorCategory.SYSTEM_ERROR, ErrorSeverity.CRITICAL
            else:
                return ErrorCategory.SYSTEM_ERROR, ErrorSeverity.MEDIUM


class RecoveryStrategySelector:
    """Determines appropriate recovery strategies for different error types."""

    def determine_recovery_strategy(self,
                                   category: ErrorCategory,
                                   severity: ErrorSeverity) -> RecoveryStrategy:
        """Determine appropriate recovery strategy based on category and severity."""
        if severity == ErrorSeverity.CRITICAL:
            return RecoveryStrategy.ESCALATE_MANUAL

        strategy_map = {
            ErrorCategory.MESSAGE_DELIVERY: RecoveryStrategy.RETRY_EXPONENTIAL,
            ErrorCategory.FLOW_PROCESSING: RecoveryStrategy.RETRY_LINEAR,
            ErrorCategory.EXTERNAL_SERVICE: RecoveryStrategy.RETRY_EXPONENTIAL,
            ErrorCategory.DATA_CORRUPTION: RecoveryStrategy.ESCALATE_MANUAL,
            ErrorCategory.SYSTEM_ERROR: RecoveryStrategy.RETRY_LINEAR,
            ErrorCategory.VALIDATION_ERROR: RecoveryStrategy.SKIP_AND_CONTINUE
        }

        return strategy_map.get(category, RecoveryStrategy.RETRY_EXPONENTIAL)
