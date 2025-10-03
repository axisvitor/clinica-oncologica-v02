"""
Comprehensive error handling and recovery mechanisms for flow operations.
Handles message delivery failures, flow processing errors, and external service failures.
"""
import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from uuid import UUID
from enum import Enum
from dataclasses import dataclass, field
import json
import traceback

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Constants
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

from app.models.flow import PatientFlowState
from app.models.flow_analytics import FlowMessage
from app.models.message import Message, MessageStatus
from app.models.patient import Patient
from app.repositories.flow import FlowStateRepository
from app.repositories.message import MessageRepository
from app.repositories.patient import PatientRepository
from app.services.conversation_memory import get_conversation_memory
from app.services.websocket_events import websocket_events
from app.schemas.websocket import WebSocketEventType
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


@dataclass
class ErrorContext:
    """Context information for error handling."""
    patient_id: UUID
    flow_state_id: Optional[UUID] = None
    message_id: Optional[UUID] = None
    operation: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    additional_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorRecord:
    """Record of an error occurrence."""
    id: str
    error_type: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    context: ErrorContext
    stack_trace: Optional[str] = None
    recovery_attempts: int = 0
    max_recovery_attempts: int = 3
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.RETRY_EXPONENTIAL
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RecoveryResult:
    """Result of error recovery attempt."""
    success: bool
    strategy_used: RecoveryStrategy
    attempts_made: int
    error_resolved: bool
    fallback_applied: bool = False
    next_retry_at: Optional[datetime] = None
    message: str = ""
    additional_data: dict[str, Any] = field(default_factory=dict)


class ErrorClassifier:
    """Handles error classification and severity determination."""
    
    def classify_error(self, error: Exception) -> tuple[ErrorCategory, ErrorSeverity]:
        """Classify error by category and severity."""
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Message delivery errors
        if "evolution" in error_message or "whatsapp" in error_message or "message" in error_message:
            if "timeout" in error_message or "connection" in error_message:
                return ErrorCategory.MESSAGE_DELIVERY, ErrorSeverity.MEDIUM
            elif "rate limit" in error_message:
                return ErrorCategory.MESSAGE_DELIVERY, ErrorSeverity.LOW
            else:
                return ErrorCategory.MESSAGE_DELIVERY, ErrorSeverity.MEDIUM
        
        # External service errors
        elif "gemini" in error_message or "redis" in error_message or "api" in error_message:
            if "timeout" in error_message or "connection" in error_message:
                return ErrorCategory.EXTERNAL_SERVICE, ErrorSeverity.HIGH
            elif "quota" in error_message or "limit" in error_message:
                return ErrorCategory.EXTERNAL_SERVICE, ErrorSeverity.MEDIUM
            else:
                return ErrorCategory.EXTERNAL_SERVICE, ErrorSeverity.MEDIUM
        
        # Database and data errors
        elif isinstance(error, SQLAlchemyError) or "database" in error_message:
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
            if "memory" in error_message or "disk" in error_message:
                return ErrorCategory.SYSTEM_ERROR, ErrorSeverity.CRITICAL
            else:
                return ErrorCategory.SYSTEM_ERROR, ErrorSeverity.MEDIUM


class RecoveryStrategySelector:
    """Determines appropriate recovery strategies for different error types."""
    
    def determine_recovery_strategy(self, 
                                   category: ErrorCategory, 
                                   severity: ErrorSeverity) -> RecoveryStrategy:
        """Determine appropriate recovery strategy."""
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


class FlowErrorHandler:
    """Comprehensive error handler for flow operations."""
    
    def __init__(self, 
                 db: Session, 
                 config: Optional[ErrorHandlerConfig] = None,
                 classifier: Optional[ErrorClassifier] = None,
                 strategy_selector: Optional[RecoveryStrategySelector] = None):
        self.db = db
        self.flow_repo = FlowStateRepository(db)
        self.message_repo = MessageRepository(db)
        self.patient_repo = PatientRepository(db)
        self.memory = get_conversation_memory()
        
        # Injected dependencies
        self.config = config or ErrorHandlerConfig()
        self.classifier = classifier or ErrorClassifier()
        self.strategy_selector = strategy_selector or RecoveryStrategySelector()
        
        # Error tracking
        self.error_records: dict[str, ErrorRecord] = {}
        self.recovery_callbacks: dict[ErrorCategory, List[Callable]] = {}
        
        logger.info("Flow error handler initialized")
    
    def _validate_error_context(self, context: ErrorContext) -> None:
        """Validate error context."""
        if not isinstance(context.patient_id, UUID):
            raise ValueError("patient_id must be a valid UUID")
        
        if not context.operation or not context.operation.strip():
            raise ValueError("operation cannot be empty")
        
        if context.flow_state_id is not None and not isinstance(context.flow_state_id, UUID):
            raise ValueError("flow_state_id must be a valid UUID or None")
        
        if context.message_id is not None and not isinstance(context.message_id, UUID):
            raise ValueError("message_id must be a valid UUID or None")

    def _generate_error_id(self, context: ErrorContext) -> str:
        """Generate unique error ID."""
        timestamp = int(datetime.utcnow().timestamp())
        operation_hash = hash(context.operation) % 10000  # Keep it short
        return f"{str(context.patient_id)[:8]}_{operation_hash}_{timestamp}"

    async def handle_error(self, 
                          error: Exception, 
                          context: ErrorContext,
                          recovery_strategy: Optional[RecoveryStrategy] = None) -> RecoveryResult:
        """
        Handle flow operation error with appropriate recovery strategy.
        
        Args:
            error: The exception that occurred
            context: Error context information
            recovery_strategy: Optional specific recovery strategy
            
        Returns:
            Recovery result
            
        Raises:
            ValueError: If context is invalid
        """
        if not isinstance(error, Exception):
            raise ValueError("error must be an Exception instance")
        
        if not isinstance(context, ErrorContext):
            raise ValueError("context must be an ErrorContext instance")
        
        try:
            # Validate context
            self._validate_error_context(context)
            
            # Classify error
            category, severity = self.classifier.classify_error(error)
            
            # Create error record
            error_record = ErrorRecord(
                id=self._generate_error_id(context),
                error_type=type(error).__name__,
                category=category,
                severity=severity,
                message=str(error)[:1000],  # Limit message length
                context=context,
                stack_trace=traceback.format_exc()[:5000],  # Limit stack trace length
                max_recovery_attempts=self.config.max_retry_attempts.get(category, 3),
                recovery_strategy=recovery_strategy or self.strategy_selector.determine_recovery_strategy(category, severity)
            )
            
            # Store error record
            self.error_records[error_record.id] = error_record
            await self._store_error_in_redis(error_record)
            
            # Log error
            logger.error(f"Flow error occurred: {error_record.error_type} - {error_record.message}")
            logger.error(f"Context: {context}")
            
            # Attempt recovery
            recovery_result = await self._attempt_recovery(error_record)
            
            # Publish error event
            await self._publish_error_event(error_record, recovery_result)
            
            # Escalate if critical or recovery failed
            if severity == ErrorSeverity.CRITICAL or not recovery_result.success:
                await self._escalate_error(error_record, recovery_result)
            
            return recovery_result
            
        except Exception as e:
            logger.error(f"Error in error handler: {e}")
            # Return basic failure result
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.ESCALATE_MANUAL,
                attempts_made=0,
                error_resolved=False,
                message="Error handler failed"
            )
    
    def _classify_error(self, error: Exception) -> tuple[ErrorCategory, ErrorSeverity]:
        """Classify error by category and severity."""
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Message delivery errors
        if "evolution" in error_message or "whatsapp" in error_message or "message" in error_message:
            if "timeout" in error_message or "connection" in error_message:
                return ErrorCategory.MESSAGE_DELIVERY, ErrorSeverity.MEDIUM
            elif "rate limit" in error_message:
                return ErrorCategory.MESSAGE_DELIVERY, ErrorSeverity.LOW
            else:
                return ErrorCategory.MESSAGE_DELIVERY, ErrorSeverity.MEDIUM
        
        # External service errors
        elif "gemini" in error_message or "redis" in error_message or "api" in error_message:
            if "timeout" in error_message or "connection" in error_message:
                return ErrorCategory.EXTERNAL_SERVICE, ErrorSeverity.HIGH
            elif "quota" in error_message or "limit" in error_message:
                return ErrorCategory.EXTERNAL_SERVICE, ErrorSeverity.MEDIUM
            else:
                return ErrorCategory.EXTERNAL_SERVICE, ErrorSeverity.MEDIUM
        
        # Database and data errors
        elif isinstance(error, SQLAlchemyError) or "database" in error_message:
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
            if "memory" in error_message or "disk" in error_message:
                return ErrorCategory.SYSTEM_ERROR, ErrorSeverity.CRITICAL
            else:
                return ErrorCategory.SYSTEM_ERROR, ErrorSeverity.MEDIUM
    
    def _determine_recovery_strategy(self, 
                                   category: ErrorCategory, 
                                   severity: ErrorSeverity) -> RecoveryStrategy:
        """Determine appropriate recovery strategy."""
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
    
class RecoveryAction(ABC):
    """Abstract base class for recovery actions."""
    
    @abstractmethod
    async def execute(self, 
                     error_record: ErrorRecord, 
                     context: 'FlowErrorHandler') -> RecoveryResult:
        """Execute the recovery action."""
        pass


class ExponentialBackoffRetry(RecoveryAction):
    """Retry with exponential backoff."""
    
    async def execute(self, error_record: ErrorRecord, context: 'FlowErrorHandler') -> RecoveryResult:
        if error_record.recovery_attempts >= error_record.max_recovery_attempts:
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.RETRY_EXPONENTIAL,
                attempts_made=error_record.recovery_attempts,
                error_resolved=False,
                message="Max retry attempts exceeded"
            )
        
        # Calculate next retry delay
        delays = context.config.retry_delays[RecoveryStrategy.RETRY_EXPONENTIAL]
        delay_index = min(error_record.recovery_attempts, len(delays) - 1)
        delay_seconds = delays[delay_index]
        
        next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
        
        # Schedule retry
        await context._schedule_retry(error_record, next_retry_at)
        
        error_record.recovery_attempts += 1
        
        return RecoveryResult(
            success=True,
            strategy_used=RecoveryStrategy.RETRY_EXPONENTIAL,
            attempts_made=error_record.recovery_attempts,
            error_resolved=False,
            next_retry_at=next_retry_at,
            message=f"Scheduled retry #{error_record.recovery_attempts} in {delay_seconds} seconds"
        )


class FallbackMessageAction(RecoveryAction):
    """Send fallback message when primary message fails."""
    
    async def execute(self, error_record: ErrorRecord, context: 'FlowErrorHandler') -> RecoveryResult:
        try:
            error_context = error_record.context
            
            # Get patient information
            patient = context.patient_repo.get(error_context.patient_id)
            if not patient:
                return RecoveryResult(
                    success=False,
                    strategy_used=RecoveryStrategy.FALLBACK_MESSAGE,
                    attempts_made=1,
                    error_resolved=False,
                    message="Patient not found for fallback message"
                )
            
            # Create fallback message
            fallback_content = self._generate_fallback_content(error_record, patient)
            
            # Create and send fallback message
            from app.models.message import Message, MessageType, MessageDirection
            fallback_message = Message(
                patient_id=error_context.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=fallback_content,
                message_metadata={
                    "fallback_message": True,
                    "original_error": error_record.error_type,
                    "error_id": error_record.id
                },
                status=MessageStatus.PENDING,
                scheduled_for=datetime.utcnow()
            )
            
            context.db.add(fallback_message)
            context.db.commit()
            
            # Send via message sender
            from app.services.message_sender import MessageSender
            message_sender = MessageSender(context.db)
            success = await message_sender.send_message(fallback_message)
            
            if success:
                error_record.resolved = True
                error_record.resolved_at = datetime.utcnow()
                
                return RecoveryResult(
                    success=True,
                    strategy_used=RecoveryStrategy.FALLBACK_MESSAGE,
                    attempts_made=1,
                    error_resolved=True,
                    fallback_applied=True,
                    message="Fallback message sent successfully"
                )
            else:
                return RecoveryResult(
                    success=False,
                    strategy_used=RecoveryStrategy.FALLBACK_MESSAGE,
                    attempts_made=1,
                    error_resolved=False,
                    message="Fallback message failed to send"
                )
                
        except Exception as e:
            logger.error(f"Fallback message failed: {e}")
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.FALLBACK_MESSAGE,
                attempts_made=1,
                error_resolved=False,
                message=f"Fallback message error: {str(e)}"
            )
    
    def _generate_fallback_content(self, error_record: ErrorRecord, patient: Patient) -> str:
        """Generate appropriate fallback message content."""
        patient_name = patient.name or "paciente"
        
        template_key = {
            ErrorCategory.MESSAGE_DELIVERY: "message_delivery",
            ErrorCategory.EXTERNAL_SERVICE: "external_service",
            ErrorCategory.FLOW_PROCESSING: "flow_processing",
        }.get(error_record.category, "default")
        
        template = ErrorHandlerConstants.FALLBACK_MESSAGE_TEMPLATES[template_key]
        return template.format(name=patient_name)


class LinearBackoffRetry(RecoveryAction):
    """Retry with linear backoff."""
    
    async def execute(self, error_record: ErrorRecord, context: 'FlowErrorHandler') -> RecoveryResult:
        if error_record.recovery_attempts >= error_record.max_recovery_attempts:
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.RETRY_LINEAR,
                attempts_made=error_record.recovery_attempts,
                error_resolved=False,
                message="Max retry attempts exceeded"
            )
        
        # Fixed delay for linear backoff
        delay_seconds = ErrorHandlerConstants.DEFAULT_LINEAR_DELAY
        next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
        
        # Schedule retry
        await context._schedule_retry(error_record, next_retry_at)
        
        error_record.recovery_attempts += 1
        
        return RecoveryResult(
            success=True,
            strategy_used=RecoveryStrategy.RETRY_LINEAR,
            attempts_made=error_record.recovery_attempts,
            error_resolved=False,
            next_retry_at=next_retry_at,
            message=f"Scheduled linear retry #{error_record.recovery_attempts} in {delay_seconds} seconds"
        )


class SkipAndContinueAction(RecoveryAction):
    """Skip current operation and continue with flow."""
    
    async def execute(self, error_record: ErrorRecord, context: 'FlowErrorHandler') -> RecoveryResult:
        try:
            error_context = error_record.context
            
            # Get flow state
            if error_context.flow_state_id:
                flow_state = context.flow_repo.get(error_context.flow_state_id)
                if flow_state:
                    # Mark error as resolved and continue
                    flow_state.state_data = flow_state.state_data or {}
                    flow_state.state_data["skipped_operations"] = flow_state.state_data.get("skipped_operations", [])
                    flow_state.state_data["skipped_operations"].append({
                        "operation": error_context.operation,
                        "error_id": error_record.id,
                        "skipped_at": datetime.utcnow().isoformat()
                    })
                    
                    context.db.commit()
            
            error_record.resolved = True
            error_record.resolved_at = datetime.utcnow()
            
            return RecoveryResult(
                success=True,
                strategy_used=RecoveryStrategy.SKIP_AND_CONTINUE,
                attempts_made=1,
                error_resolved=True,
                message="Operation skipped, flow continues"
            )
            
        except Exception as e:
            logger.error(f"Skip and continue failed: {e}")
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.SKIP_AND_CONTINUE,
                attempts_made=1,
                error_resolved=False,
                message=f"Skip operation failed: {str(e)}"
            )


class PauseFlowAction(RecoveryAction):
    """Pause flow temporarily for recovery."""
    
    async def execute(self, error_record: ErrorRecord, context: 'FlowErrorHandler') -> RecoveryResult:
        try:
            error_context = error_record.context
            
            # Get flow state
            if error_context.flow_state_id:
                flow_state = context.flow_repo.get(error_context.flow_state_id)
                if flow_state:
                    # Pause flow
                    flow_state.state_data = flow_state.state_data or {}
                    flow_state.state_data["paused"] = True
                    flow_state.state_data["pause_reason"] = f"Error recovery: {error_record.error_type}"
                    flow_state.state_data["paused_at"] = datetime.utcnow().isoformat()
                    flow_state.state_data["error_id"] = error_record.id
                    
                    context.db.commit()
                    
                    # Schedule resume
                    resume_at = datetime.utcnow() + timedelta(hours=ErrorHandlerConstants.FLOW_RESUME_DELAY_HOURS)
                    await context._schedule_flow_resume(error_context.patient_id, resume_at)
            
            return RecoveryResult(
                success=True,
                strategy_used=RecoveryStrategy.PAUSE_FLOW,
                attempts_made=1,
                error_resolved=False,
                message=f"Flow paused for recovery, will resume in {ErrorHandlerConstants.FLOW_RESUME_DELAY_HOURS} hour(s)"
            )
            
        except Exception as e:
            logger.error(f"Pause flow failed: {e}")
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.PAUSE_FLOW,
                attempts_made=1,
                error_resolved=False,
                message=f"Flow pause failed: {str(e)}"
            )


class ResetFlowAction(RecoveryAction):
    """Reset flow state to recover from corruption."""
    
    async def execute(self, error_record: ErrorRecord, context: 'FlowErrorHandler') -> RecoveryResult:
        try:
            error_context = error_record.context
            
            # Get flow state
            if error_context.flow_state_id:
                flow_state = context.flow_repo.get(error_context.flow_state_id)
                if flow_state:
                    # Backup current state
                    backup_data = {
                        "original_state": flow_state.state_data,
                        "reset_reason": error_record.error_type,
                        "reset_at": datetime.utcnow().isoformat(),
                        "error_id": error_record.id
                    }
                    
                    # Reset to safe state
                    flow_state.state_data = {
                        "reset": True,
                        "backup": backup_data,
                        "current_step": max(1, flow_state.current_step - 1),  # Go back one step
                        "reset_recovery": True
                    }
                    
                    context.db.commit()
                    
                    error_record.resolved = True
                    error_record.resolved_at = datetime.utcnow()
            
            return RecoveryResult(
                success=True,
                strategy_used=RecoveryStrategy.RESET_FLOW,
                attempts_made=1,
                error_resolved=True,
                message="Flow state reset to safe state"
            )
            
        except Exception as e:
            logger.error(f"Flow reset failed: {e}")
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.RESET_FLOW,
                attempts_made=1,
                error_resolved=False,
                message=f"Flow reset failed: {str(e)}"
            )


class EscalateManualAction(RecoveryAction):
    """Escalate error for manual intervention."""
    
    async def execute(self, error_record: ErrorRecord, context: 'FlowErrorHandler') -> RecoveryResult:
        try:
            # Create escalation notification
            escalation_data = {
                "error_id": error_record.id,
                "patient_id": str(error_record.context.patient_id),
                "error_type": error_record.error_type,
                "category": error_record.category.value,
                "severity": error_record.severity.value,
                "message": error_record.message,
                "context": {
                    "operation": error_record.context.operation,
                    "timestamp": error_record.created_at.isoformat()
                },
                "requires_manual_intervention": True
            }
            
            # Publish escalation event
            await websocket_events.publish_alert_event(
                event_type=WebSocketEventType.ALERT_CREATED,
                patient_id=error_record.context.patient_id,
                alert_type="flow_error_escalation",
                priority="high" if error_record.severity == ErrorSeverity.CRITICAL else "medium",
                message=f"Flow error requires manual intervention: {error_record.error_type}",
                metadata=escalation_data
            )
            
            return RecoveryResult(
                success=True,
                strategy_used=RecoveryStrategy.ESCALATE_MANUAL,
                attempts_made=1,
                error_resolved=False,
                message="Error escalated for manual intervention"
            )
            
        except Exception as e:
            logger.error(f"Escalation failed: {e}")
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.ESCALATE_MANUAL,
                attempts_made=1,
                error_resolved=False,
                message=f"Escalation failed: {str(e)}"
            )


class RecoveryActionFactory:
    """Factory for creating recovery actions."""
    
    _actions = {
        RecoveryStrategy.RETRY_EXPONENTIAL: ExponentialBackoffRetry,
        RecoveryStrategy.RETRY_LINEAR: LinearBackoffRetry,
        RecoveryStrategy.FALLBACK_MESSAGE: FallbackMessageAction,
        RecoveryStrategy.SKIP_AND_CONTINUE: SkipAndContinueAction,
        RecoveryStrategy.PAUSE_FLOW: PauseFlowAction,
        RecoveryStrategy.RESET_FLOW: ResetFlowAction,
        RecoveryStrategy.ESCALATE_MANUAL: EscalateManualAction,
    }
    
    @classmethod
    def create_action(cls, strategy: RecoveryStrategy) -> RecoveryAction:
        """Create recovery action for given strategy."""
        action_class = cls._actions.get(strategy)
        if not action_class:
            raise ValueError(f"Unknown recovery strategy: {strategy}")
        return action_class()


    async def _attempt_recovery(self, error_record: ErrorRecord) -> RecoveryResult:
        """Attempt error recovery using specified strategy."""
        try:
            action = RecoveryActionFactory.create_action(error_record.recovery_strategy)
            return await action.execute(error_record, self)
                
        except Exception as e:
            logger.error(f"Recovery attempt failed: {e}")
            return RecoveryResult(
                success=False,
                strategy_used=error_record.recovery_strategy,
                attempts_made=error_record.recovery_attempts,
                error_resolved=False,
                message=f"Recovery failed: {str(e)}"
            )
    
    async def _retry_with_exponential_backoff(self, error_record: ErrorRecord) -> RecoveryResult:
        """Retry operation with exponential backoff."""
        if error_record.recovery_attempts >= error_record.max_recovery_attempts:
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.RETRY_EXPONENTIAL,
                attempts_made=error_record.recovery_attempts,
                error_resolved=False,
                message="Max retry attempts exceeded"
            )
        
        # Calculate next retry delay
        delays = self.retry_delays[RecoveryStrategy.RETRY_EXPONENTIAL]
        delay_index = min(error_record.recovery_attempts, len(delays) - 1)
        delay_seconds = delays[delay_index]
        
        next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
        
        # Schedule retry
        await self._schedule_retry(error_record, next_retry_at)
        
        error_record.recovery_attempts += 1
        
        return RecoveryResult(
            success=True,
            strategy_used=RecoveryStrategy.RETRY_EXPONENTIAL,
            attempts_made=error_record.recovery_attempts,
            error_resolved=False,
            next_retry_at=next_retry_at,
            message=f"Scheduled retry #{error_record.recovery_attempts} in {delay_seconds} seconds"
        )
    
    async def _retry_with_linear_backoff(self, error_record: ErrorRecord) -> RecoveryResult:
        """Retry operation with linear backoff."""
        if error_record.recovery_attempts >= error_record.max_recovery_attempts:
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.RETRY_LINEAR,
                attempts_made=error_record.recovery_attempts,
                error_resolved=False,
                message="Max retry attempts exceeded"
            )
        
        # Fixed delay for linear backoff
        delay_seconds = self.retry_delays[RecoveryStrategy.RETRY_LINEAR][0]
        next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
        
        # Schedule retry
        await self._schedule_retry(error_record, next_retry_at)
        
        error_record.recovery_attempts += 1
        
        return RecoveryResult(
            success=True,
            strategy_used=RecoveryStrategy.RETRY_LINEAR,
            attempts_made=error_record.recovery_attempts,
            error_resolved=False,
            next_retry_at=next_retry_at,
            message=f"Scheduled linear retry #{error_record.recovery_attempts} in {delay_seconds} seconds"
        )
    
    async def _apply_fallback_message(self, error_record: ErrorRecord) -> RecoveryResult:
        """Apply fallback message when primary message fails."""
        try:
            context = error_record.context
            
            # Get patient information
            patient = self.patient_repo.get(context.patient_id)
            if not patient:
                return RecoveryResult(
                    success=False,
                    strategy_used=RecoveryStrategy.FALLBACK_MESSAGE,
                    attempts_made=1,
                    error_resolved=False,
                    message="Patient not found for fallback message"
                )
            
            # Create fallback message
            fallback_content = self._generate_fallback_message_content(error_record, patient)
            
            # Create and send fallback message
            from app.models.message import Message, MessageType, MessageDirection
            fallback_message = Message(
                patient_id=context.patient_id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=fallback_content,
                message_metadata={
                    "fallback_message": True,
                    "original_error": error_record.error_type,
                    "error_id": error_record.id
                },
                status=MessageStatus.PENDING,
                scheduled_for=datetime.utcnow()
            )
            
            self.db.add(fallback_message)
            self.db.commit()
            
            # Send via message sender
            from app.services.message_sender import MessageSender
            message_sender = MessageSender(self.db)
            success = await message_sender.send_message(fallback_message)
            
            if success:
                error_record.resolved = True
                error_record.resolved_at = datetime.utcnow()
                
                return RecoveryResult(
                    success=True,
                    strategy_used=RecoveryStrategy.FALLBACK_MESSAGE,
                    attempts_made=1,
                    error_resolved=True,
                    fallback_applied=True,
                    message="Fallback message sent successfully"
                )
            else:
                return RecoveryResult(
                    success=False,
                    strategy_used=RecoveryStrategy.FALLBACK_MESSAGE,
                    attempts_made=1,
                    error_resolved=False,
                    message="Fallback message failed to send"
                )
                
        except Exception as e:
            logger.error(f"Fallback message failed: {e}")
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.FALLBACK_MESSAGE,
                attempts_made=1,
                error_resolved=False,
                message=f"Fallback message error: {str(e)}"
            )
    
    def _generate_fallback_message_content(self, error_record: ErrorRecord, patient: Patient) -> str:
        """Generate appropriate fallback message content."""
        patient_name = patient.name or "paciente"
        
        fallback_messages = {
            ErrorCategory.MESSAGE_DELIVERY: f"Olá {patient_name}! Estou com algumas dificuldades técnicas, mas estou aqui para você. Nossa equipe médica foi notificada e entrará em contato em breve.",
            ErrorCategory.EXTERNAL_SERVICE: f"Oi {patient_name}! Estou passando por uma atualização no sistema. Enquanto isso, se precisar de algo urgente, entre em contato diretamente com nossa equipe médica.",
            ErrorCategory.FLOW_PROCESSING: f"Olá {patient_name}! Houve um pequeno problema no processamento da sua mensagem. Nossa equipe técnica foi notificada e resolverá em breve.",
        }
        
        return fallback_messages.get(
            error_record.category,
            f"Olá {patient_name}! Estou enfrentando algumas dificuldades técnicas temporárias. Nossa equipe foi notificada e entrará em contato em breve."
        )
    
    async def _skip_and_continue(self, error_record: ErrorRecord) -> RecoveryResult:
        """Skip current operation and continue with flow."""
        try:
            context = error_record.context
            
            # Get flow state
            if context.flow_state_id:
                flow_state = self.flow_repo.get(context.flow_state_id)
                if flow_state:
                    # Mark error as resolved and continue
                    flow_state.state_data = flow_state.state_data or {}
                    flow_state.state_data["skipped_operations"] = flow_state.state_data.get("skipped_operations", [])
                    flow_state.state_data["skipped_operations"].append({
                        "operation": context.operation,
                        "error_id": error_record.id,
                        "skipped_at": datetime.utcnow().isoformat()
                    })
                    
                    self.db.commit()
            
            error_record.resolved = True
            error_record.resolved_at = datetime.utcnow()
            
            return RecoveryResult(
                success=True,
                strategy_used=RecoveryStrategy.SKIP_AND_CONTINUE,
                attempts_made=1,
                error_resolved=True,
                message="Operation skipped, flow continues"
            )
            
        except Exception as e:
            logger.error(f"Skip and continue failed: {e}")
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.SKIP_AND_CONTINUE,
                attempts_made=1,
                error_resolved=False,
                message=f"Skip operation failed: {str(e)}"
            )
    
    async def _pause_flow_for_recovery(self, error_record: ErrorRecord) -> RecoveryResult:
        """Pause flow temporarily for recovery."""
        try:
            context = error_record.context
            
            # Get flow state
            if context.flow_state_id:
                flow_state = self.flow_repo.get(context.flow_state_id)
                if flow_state:
                    # Pause flow
                    flow_state.state_data = flow_state.state_data or {}
                    flow_state.state_data["paused"] = True
                    flow_state.state_data["pause_reason"] = f"Error recovery: {error_record.error_type}"
                    flow_state.state_data["paused_at"] = datetime.utcnow().isoformat()
                    flow_state.state_data["error_id"] = error_record.id
                    
                    self.db.commit()
                    
                    # Schedule resume in 1 hour
                    resume_at = datetime.utcnow() + timedelta(hours=1)
                    await self._schedule_flow_resume(context.patient_id, resume_at)
            
            return RecoveryResult(
                success=True,
                strategy_used=RecoveryStrategy.PAUSE_FLOW,
                attempts_made=1,
                error_resolved=False,
                message="Flow paused for recovery, will resume in 1 hour"
            )
            
        except Exception as e:
            logger.error(f"Pause flow failed: {e}")
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.PAUSE_FLOW,
                attempts_made=1,
                error_resolved=False,
                message=f"Flow pause failed: {str(e)}"
            )
    
    async def _reset_flow_state(self, error_record: ErrorRecord) -> RecoveryResult:
        """Reset flow state to recover from corruption."""
        try:
            context = error_record.context
            
            # Get flow state
            if context.flow_state_id:
                flow_state = self.flow_repo.get(context.flow_state_id)
                if flow_state:
                    # Backup current state
                    backup_data = {
                        "original_state": flow_state.state_data,
                        "reset_reason": error_record.error_type,
                        "reset_at": datetime.utcnow().isoformat(),
                        "error_id": error_record.id
                    }
                    
                    # Reset to safe state
                    flow_state.state_data = {
                        "reset": True,
                        "backup": backup_data,
                        "current_step": max(1, flow_state.current_step - 1),  # Go back one step
                        "reset_recovery": True
                    }
                    
                    self.db.commit()
                    
                    error_record.resolved = True
                    error_record.resolved_at = datetime.utcnow()
            
            return RecoveryResult(
                success=True,
                strategy_used=RecoveryStrategy.RESET_FLOW,
                attempts_made=1,
                error_resolved=True,
                message="Flow state reset to safe state"
            )
            
        except Exception as e:
            logger.error(f"Flow reset failed: {e}")
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.RESET_FLOW,
                attempts_made=1,
                error_resolved=False,
                message=f"Flow reset failed: {str(e)}"
            )
    
    async def _escalate_for_manual_intervention(self, error_record: ErrorRecord) -> RecoveryResult:
        """Escalate error for manual intervention."""
        try:
            # Create escalation notification
            escalation_data = {
                "error_id": error_record.id,
                "patient_id": str(error_record.context.patient_id),
                "error_type": error_record.error_type,
                "category": error_record.category.value,
                "severity": error_record.severity.value,
                "message": error_record.message,
                "context": {
                    "operation": error_record.context.operation,
                    "timestamp": error_record.created_at.isoformat()
                },
                "requires_manual_intervention": True
            }
            
            # Publish escalation event
            await websocket_events.publish_alert_event(
                event_type=WebSocketEventType.ALERT_CREATED,
                patient_id=error_record.context.patient_id,
                alert_type="flow_error_escalation",
                priority="high" if error_record.severity == ErrorSeverity.CRITICAL else "medium",
                message=f"Flow error requires manual intervention: {error_record.error_type}",
                metadata=escalation_data
            )
            
            return RecoveryResult(
                success=True,
                strategy_used=RecoveryStrategy.ESCALATE_MANUAL,
                attempts_made=1,
                error_resolved=False,
                message="Error escalated for manual intervention"
            )
            
        except Exception as e:
            logger.error(f"Escalation failed: {e}")
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.ESCALATE_MANUAL,
                attempts_made=1,
                error_resolved=False,
                message=f"Escalation failed: {str(e)}"
            )
    
    async def _schedule_retry(self, error_record: ErrorRecord, retry_at: datetime):
        """Schedule retry operation."""
        try:
            # Store retry schedule in Redis
            retry_data = {
                "error_id": error_record.id,
                "patient_id": str(error_record.context.patient_id),
                "operation": error_record.context.operation,
                "retry_at": retry_at.isoformat(),
                "attempt": error_record.recovery_attempts
            }
            
            # Use Redis to schedule retry
            await self.memory.redis.setex(
                f"flow_retry:{error_record.id}",
                int((retry_at - datetime.utcnow()).total_seconds()) + 60,  # Add buffer
                json.dumps(retry_data)
            )
            
            logger.info(f"Scheduled retry for error {error_record.id} at {retry_at}")
            
        except Exception as e:
            logger.error(f"Failed to schedule retry: {e}")
    
    async def _schedule_flow_resume(self, patient_id: UUID, resume_at: datetime):
        """Schedule flow resume."""
        try:
            resume_data = {
                "patient_id": str(patient_id),
                "resume_at": resume_at.isoformat(),
                "reason": "error_recovery"
            }
            
            # Use Redis to schedule resume
            await self.memory.redis.setex(
                f"flow_resume:{patient_id}",
                int((resume_at - datetime.utcnow()).total_seconds()) + 60,
                json.dumps(resume_data)
            )
            
            logger.info(f"Scheduled flow resume for patient {patient_id} at {resume_at}")
            
        except Exception as e:
            logger.error(f"Failed to schedule flow resume: {e}")
    
    async def _store_error_in_redis(self, error_record: ErrorRecord):
        """Store error record in Redis for monitoring."""
        try:
            error_data = {
                "id": error_record.id,
                "error_type": error_record.error_type,
                "category": error_record.category.value,
                "severity": error_record.severity.value,
                "message": error_record.message,
                "patient_id": str(error_record.context.patient_id),
                "operation": error_record.context.operation,
                "recovery_attempts": error_record.recovery_attempts,
                "resolved": error_record.resolved,
                "created_at": error_record.created_at.isoformat()
            }
            
            # Store with 7-day expiration
            await self.memory.redis.setex(
                f"flow_error:{error_record.id}",
                604800,  # 7 days
                json.dumps(error_data)
            )
            
        except Exception as e:
            logger.error(f"Failed to store error in Redis: {e}")
    
    async def _publish_error_event(self, error_record: ErrorRecord, recovery_result: RecoveryResult):
        """Publish error event via WebSocket."""
        try:
            event_data = {
                "error_id": error_record.id,
                "error_type": error_record.error_type,
                "category": error_record.category.value,
                "severity": error_record.severity.value,
                "recovery_strategy": recovery_result.strategy_used.value,
                "recovery_success": recovery_result.success,
                "error_resolved": recovery_result.error_resolved
            }
            
            await websocket_events.publish_flow_event(
                event_type=WebSocketEventType.FLOW_ERROR,
                patient_id=error_record.context.patient_id,
                flow_id=error_record.context.flow_state_id,
                event_data=event_data
            )
            
        except Exception as e:
            logger.error(f"Failed to publish error event: {e}")
    
    async def _escalate_error(self, error_record: ErrorRecord, recovery_result: RecoveryResult):
        """Escalate error to healthcare providers."""
        try:
            if error_record.severity == ErrorSeverity.CRITICAL or not recovery_result.success:
                escalation_message = f"Critical flow error for patient {error_record.context.patient_id}: {error_record.error_type}"
                
                await websocket_events.publish_alert_event(
                    event_type=WebSocketEventType.ALERT_CREATED,
                    patient_id=error_record.context.patient_id,
                    alert_type="critical_flow_error",
                    priority="critical",
                    message=escalation_message,
                    metadata={
                        "error_id": error_record.id,
                        "recovery_failed": not recovery_result.success
                    }
                )
                
                logger.critical(f"Escalated critical error: {error_record.id}")
            
        except Exception as e:
            logger.error(f"Failed to escalate error: {e}")
    
class ErrorStatisticsCache:
    """Caches error statistics to avoid expensive Redis operations."""
    
    def __init__(self, redis_client, cache_ttl: int = 300):  # 5 minutes cache
        self.redis = redis_client
        self.cache_ttl = cache_ttl
        self._cache_key = "error_stats_cache"
    
    async def get_cached_stats(self, timeframe_hours: int) -> Optional[dict[str, Any]]:
        """Get cached statistics if available."""
        try:
            cache_key = f"{self._cache_key}:{timeframe_hours}"
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Failed to get cached stats: {e}")
        return None
    
    async def cache_stats(self, stats: dict[str, Any], timeframe_hours: int):
        """Cache statistics."""
        try:
            cache_key = f"{self._cache_key}:{timeframe_hours}"
            await self.redis.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(stats)
            )
        except Exception as e:
            logger.warning(f"Failed to cache stats: {e}")


    async def get_error_statistics(self, 
                                 timeframe_hours: int = 24,
                                 use_cache: bool = True) -> dict[str, Any]:
        """Get error statistics for monitoring with caching."""
        try:
            # Check cache first
            if use_cache:
                stats_cache = ErrorStatisticsCache(self.memory.redis)
                cached_stats = await stats_cache.get_cached_stats(timeframe_hours)
                if cached_stats:
                    return cached_stats
            
            cutoff_time = datetime.utcnow() - timedelta(hours=timeframe_hours)
            
            # Use pipeline for efficient Redis operations
            pipeline = self.memory.redis.pipeline()
            
            # Get all error keys in one operation
            error_keys = await self.memory.redis.keys("flow_error:*")
            
            # Batch get all error data
            if error_keys:
                for key in error_keys:
                    pipeline.get(key)
                error_data_list = await pipeline.execute()
            else:
                error_data_list = []
            
            stats = {
                "total_errors": 0,
                "by_category": {},
                "by_severity": {},
                "resolved_errors": 0,
                "pending_errors": 0,
                "recovery_success_rate": 0.0,
                "timeframe_hours": timeframe_hours,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            resolved_count = 0
            total_count = 0
            
            # Process error data efficiently
            for error_data in error_data_list:
                if not error_data:
                    continue
                    
                try:
                    error_info = json.loads(error_data)
                    error_time = datetime.fromisoformat(error_info["created_at"])
                    
                    if error_time >= cutoff_time:
                        total_count += 1
                        
                        # Count by category
                        category = error_info["category"]
                        stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
                        
                        # Count by severity
                        severity = error_info["severity"]
                        stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1
                        
                        # Count resolved
                        if error_info["resolved"]:
                            resolved_count += 1
                
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning(f"Failed to parse error data: {e}")
                    continue
            
            stats["total_errors"] = total_count
            stats["resolved_errors"] = resolved_count
            stats["pending_errors"] = total_count - resolved_count
            stats["recovery_success_rate"] = (resolved_count / total_count * 100) if total_count > 0 else 0.0
            
            # Cache the results
            if use_cache:
                await stats_cache.cache_stats(stats, timeframe_hours)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get error statistics: {e}")
            return {"error": str(e), "generated_at": datetime.utcnow().isoformat()}
    
    async def cleanup_old_errors(self, days_old: int = 7) -> int:
        """Clean up old error records."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days_old)
            cleaned_count = 0
            
            # Clean from memory
            to_remove = []
            for error_id, error_record in self.error_records.items():
                if error_record.created_at < cutoff_time:
                    to_remove.append(error_id)
            
            for error_id in to_remove:
                del self.error_records[error_id]
                cleaned_count += 1
            
            logger.info(f"Cleaned up {cleaned_count} old error records")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old errors: {e}")
            return 0


class FlowErrorHandlerFactory:
    """Factory for creating FlowErrorHandler instances."""
    
    @staticmethod
    def create_default(db: Session) -> FlowErrorHandler:
        """Create FlowErrorHandler with default configuration."""
        return FlowErrorHandler(db)
    
    @staticmethod
    def create_with_config(
        db: Session,
        config: ErrorHandlerConfig,
        classifier: Optional[ErrorClassifier] = None,
        strategy_selector: Optional[RecoveryStrategySelector] = None
    ) -> FlowErrorHandler:
        """Create FlowErrorHandler with custom configuration."""
        return FlowErrorHandler(
            db=db,
            config=config,
            classifier=classifier,
            strategy_selector=strategy_selector
        )
    
    @staticmethod
    def create_for_testing(
        db: Session,
        mock_memory=None,
        mock_repos=None
    ) -> FlowErrorHandler:
        """Create FlowErrorHandler for testing with mocked dependencies."""
        handler = FlowErrorHandler(db)
        
        if mock_memory:
            handler.memory = mock_memory
        
        if mock_repos:
            if 'flow_repo' in mock_repos:
                handler.flow_repo = mock_repos['flow_repo']
            if 'message_repo' in mock_repos:
                handler.message_repo = mock_repos['message_repo']
            if 'patient_repo' in mock_repos:
                handler.patient_repo = mock_repos['patient_repo']
        
        return handler


def get_flow_error_handler(db: Session) -> FlowErrorHandler:
    """Get flow error handler instance."""
    return FlowErrorHandlerFactory.create_default(db)