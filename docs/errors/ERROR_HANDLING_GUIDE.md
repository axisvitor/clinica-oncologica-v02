# Error Handling Guide - Hormonia Oncology System

## Overview

The Hormonia oncology system implements a comprehensive, multi-layered error handling architecture designed for healthcare applications where reliability and proper error recovery are critical. This guide documents the domain error hierarchy, recovery strategies, audit logging, error flow handling, and retry mechanisms.

## Table of Contents

1. [Error Hierarchy Diagram](#error-hierarchy-diagram)
2. [Domain Error Classes](#domain-error-classes)
3. [Error Classification System](#error-classification-system)
4. [Recovery Strategy Patterns](#recovery-strategy-patterns)
5. [Retry Mechanisms](#retry-mechanisms)
6. [Audit Logging](#audit-logging)
7. [Exception Handling Examples](#exception-handling-examples)
8. [Best Practices](#best-practices)

---

## Error Hierarchy Diagram

```
Exception (Python base)
    |
    +-- HormoniaException (Application root)
    |       |
    |       +-- APIException (HTTP errors with status codes)
    |       |       |
    |       |       +-- BusinessRuleError (400)
    |       |       +-- ValidationError (422)
    |       |       +-- NotFoundError (404)
    |       |       |       +-- PatientNotFoundError
    |       |       |       +-- MessageNotFoundError
    |       |       |       +-- QuizNotFoundError
    |       |       |
    |       |       +-- ConflictError (409)
    |       |       |       +-- QuizSessionExpiredError
    |       |       |
    |       |       +-- UnauthorizedError (401)
    |       |       |       +-- AuthenticationError
    |       |       |
    |       |       +-- ForbiddenError (403)
    |       |       |       +-- AuthorizationError
    |       |       |       +-- PatientAccessDeniedError
    |       |       |
    |       |       +-- BadRequestError (400)
    |       |       +-- RateLimitError (429)
    |       |       +-- ServiceUnavailableError (503)
    |       |       +-- ExternalServiceError (503)
    |       |               +-- MessageSendError
    |       |
    |       +-- DatabaseError
    |       +-- CacheError
    |       |       +-- CacheKeyNotFoundError
    |       |
    |       +-- ProcessingError
    |       |       +-- AIProcessingError
    |       |       +-- ResponseProcessingError
    |       |       +-- FlowStateError
    |       |
    |       +-- FlowException (Flow-specific errors)
    |               +-- FlowStateNotFoundError
    |               +-- FlowValidationError
    |               +-- FlowStateConflictError
    |               +-- FlowOperationError
    |               +-- MessageDeliveryError
    |               +-- FlowStateCorruptionError
    |               +-- FlowProcessingError
    |               +-- ConcurrencyError
    |               +-- TemplateLoadError
    |
    +-- FlowException (Standalone flow errors)
            +-- ExternalServiceError
            |       +-- AIServiceError
            |       +-- RedisConnectionError
            |
            +-- DatabaseError (Flow-specific)
            +-- FlowValidationError
            +-- ConcurrencyError
```

---

## Domain Error Classes

### Base Exception Classes

#### HormoniaException

The root exception for all application-specific errors.

**Location**: `/backend-hormonia/app/core/exceptions.py`

```python
class HormoniaException(Exception):
    """Root exception for all Hormonia application errors."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        code: Optional[str] = None,
        field: Optional[str] = None,
        **kwargs
    ):
        self.message = message
        self.details = details or {}
        self.code = code
        self.field = field
```

**Key Features**:
- Consistent `message`, `details`, `code`, and `field` attributes
- `to_dict()` method for API response serialization
- Support for additional context via kwargs

#### APIException

Base exception for HTTP-related errors with status codes.

```python
class APIException(HormoniaException):
    """Base exception for HTTP API errors with status codes."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
        ...
    ):
        self.status_code = status_code
        self.error_code = error_code
```

### HTTP Exception Classes

| Exception Class | HTTP Status | Error Code | Use Case |
|-----------------|-------------|------------|----------|
| `BusinessRuleError` | 400 | BUSINESS_RULE_VIOLATION | Business logic violations |
| `ValidationError` | 422 | VALIDATION_ERROR | Input validation failures |
| `NotFoundError` | 404 | NOT_FOUND | Resource not found |
| `ConflictError` | 409 | CONFLICT | Resource conflicts (duplicates) |
| `UnauthorizedError` | 401 | UNAUTHORIZED | Authentication required |
| `ForbiddenError` | 403 | FORBIDDEN | Insufficient permissions |
| `BadRequestError` | 400 | BAD_REQUEST | Malformed requests |
| `RateLimitError` | 429 | RATE_LIMIT_EXCEEDED | Rate limit exceeded |
| `ServiceUnavailableError` | 503 | SERVICE_UNAVAILABLE | Service temporarily down |

### Flow-Specific Exceptions

**Location**: `/backend-hormonia/app/exceptions/flow_exceptions.py`

| Exception Class | Description | Key Attributes |
|-----------------|-------------|----------------|
| `FlowException` | Base for flow errors | `patient_id`, `flow_type`, `context` |
| `MessageDeliveryError` | Message delivery failure | `message_id`, `retry_count`, `last_error` |
| `FlowStateCorruptionError` | State data corruption | `flow_state_data`, `corruption_type` |
| `FlowProcessingError` | Processing operation failure | `current_day`, `operation` |
| `ExternalServiceError` | External API failure | `service_name`, `error_code`, `is_recoverable`, `retry_after` |
| `AIServiceError` | AI service failure | `ai_service`, `prompt` |
| `RedisConnectionError` | Redis connection failure | `operation`, `key` |
| `DatabaseError` | Database operation failure | `operation`, `table`, `is_recoverable` |
| `FlowValidationError` | Flow data validation failure | `validation_errors` |
| `ConcurrencyError` | Concurrent operation conflict | `conflicting_operation` |
| `TemplateLoadError` | Template loading failure | `template_path` |

---

## Error Classification System

The system uses a sophisticated error classification mechanism to automatically categorize errors and determine appropriate recovery strategies.

**Location**: `/backend-hormonia/app/domain/errors/flows/classifier.py`

### Error Categories

```python
class ErrorCategory(Enum):
    MESSAGE_DELIVERY = "message_delivery"    # WhatsApp/Evolution API errors
    FLOW_PROCESSING = "flow_processing"      # Flow state machine errors
    EXTERNAL_SERVICE = "external_service"    # Gemini, Redis, external APIs
    DATA_CORRUPTION = "data_corruption"      # Invalid state, constraint violations
    SYSTEM_ERROR = "system_error"            # Memory, disk, general system
    VALIDATION_ERROR = "validation_error"    # Input validation failures
```

### Error Severity Levels

```python
class ErrorSeverity(Enum):
    LOW = "low"           # Non-critical, can continue
    MEDIUM = "medium"     # Degraded but operational
    HIGH = "high"         # Requires attention
    CRITICAL = "critical" # Immediate intervention needed
```

### Classification Logic

The `ErrorClassifier` analyzes error messages and types to determine category and severity:

```python
class ErrorClassifier:
    def classify_error(self, error: Exception) -> tuple[ErrorCategory, ErrorSeverity]:
        error_message = str(error).lower()

        # Message delivery errors (WhatsApp, Evolution)
        if any(keyword in error_message for keyword in ["evolution", "whatsapp", "message"]):
            if "timeout" in error_message:
                return ErrorCategory.MESSAGE_DELIVERY, ErrorSeverity.MEDIUM
            elif "rate limit" in error_message:
                return ErrorCategory.MESSAGE_DELIVERY, ErrorSeverity.LOW
            else:
                return ErrorCategory.MESSAGE_DELIVERY, ErrorSeverity.MEDIUM

        # External service errors (Gemini, Redis, APIs)
        elif any(keyword in error_message for keyword in ["gemini", "redis", "api"]):
            if "timeout" in error_message:
                return ErrorCategory.EXTERNAL_SERVICE, ErrorSeverity.HIGH
            elif "rate limit" in error_message:
                return ErrorCategory.EXTERNAL_SERVICE, ErrorSeverity.MEDIUM
            else:
                return ErrorCategory.EXTERNAL_SERVICE, ErrorSeverity.MEDIUM

        # Database and data corruption
        elif isinstance(error, SQLAlchemyError):
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

        # System resource errors
        if any(keyword in error_message for keyword in ["memory", "disk"]):
            return ErrorCategory.SYSTEM_ERROR, ErrorSeverity.CRITICAL

        return ErrorCategory.SYSTEM_ERROR, ErrorSeverity.MEDIUM
```

---

## Recovery Strategy Patterns

**Location**: `/backend-hormonia/app/domain/errors/flows/recovery_strategy.py`

### Available Recovery Strategies

```python
class RecoveryStrategy(Enum):
    RETRY_EXPONENTIAL = "retry_exponential"   # Exponential backoff retry
    RETRY_LINEAR = "retry_linear"             # Linear interval retry
    FALLBACK_MESSAGE = "fallback_message"     # Send fallback message to patient
    SKIP_AND_CONTINUE = "skip_and_continue"   # Skip operation, continue flow
    PAUSE_FLOW = "pause_flow"                 # Pause flow temporarily
    ESCALATE_MANUAL = "escalate_manual"       # Escalate for manual intervention
    RESET_FLOW = "reset_flow"                 # Reset flow to safe state
```

### Strategy Selection Matrix

```python
class RecoveryStrategySelector:
    def determine_recovery_strategy(
        self, category: ErrorCategory, severity: ErrorSeverity
    ) -> RecoveryStrategy:
        # Critical errors always escalate
        if severity == ErrorSeverity.CRITICAL:
            return RecoveryStrategy.ESCALATE_MANUAL

        strategy_map = {
            ErrorCategory.MESSAGE_DELIVERY: RecoveryStrategy.RETRY_EXPONENTIAL,
            ErrorCategory.FLOW_PROCESSING: RecoveryStrategy.RETRY_LINEAR,
            ErrorCategory.EXTERNAL_SERVICE: RecoveryStrategy.RETRY_EXPONENTIAL,
            ErrorCategory.DATA_CORRUPTION: RecoveryStrategy.ESCALATE_MANUAL,
            ErrorCategory.SYSTEM_ERROR: RecoveryStrategy.RETRY_LINEAR,
            ErrorCategory.VALIDATION_ERROR: RecoveryStrategy.SKIP_AND_CONTINUE,
        }

        return strategy_map.get(category, RecoveryStrategy.RETRY_EXPONENTIAL)
```

### Recovery Action Implementations

#### 1. Exponential Backoff Retry

Delays: 1min, 5min, 15min, 30min, 1hr

```python
class ExponentialBackoffRetry(RecoveryAction):
    async def execute(self, error_record, context) -> RecoveryResult:
        if error_record.recovery_attempts >= error_record.max_recovery_attempts:
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.RETRY_EXPONENTIAL,
                message="Max retry attempts exceeded"
            )

        delays = [60, 300, 900, 1800, 3600]  # seconds
        delay_seconds = delays[min(error_record.recovery_attempts, len(delays) - 1)]
        next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)

        await context.retry_manager.schedule_retry(error_record, next_retry_at)
        error_record.recovery_attempts += 1

        return RecoveryResult(
            success=True,
            strategy_used=RecoveryStrategy.RETRY_EXPONENTIAL,
            next_retry_at=next_retry_at,
            message=f"Scheduled retry #{error_record.recovery_attempts} in {delay_seconds} seconds"
        )
```

#### 2. Fallback Message Action

Sends a graceful fallback message to the patient when primary message fails.

```python
FALLBACK_MESSAGE_TEMPLATES = {
    "message_delivery": "Ola {name}! Estou com algumas dificuldades tecnicas, mas estou aqui para voce. Nossa equipe medica foi notificada e entrara em contato em breve.",
    "external_service": "Oi {name}! Estou passando por uma atualizacao no sistema. Enquanto isso, se precisar de algo urgente, entre em contato diretamente com nossa equipe medica.",
    "flow_processing": "Ola {name}! Houve um pequeno problema no processamento da sua mensagem. Nossa equipe tecnica foi notificada e resolvera em breve.",
    "default": "Ola {name}! Estou enfrentando algumas dificuldades tecnicas temporarias. Nossa equipe foi notificada e entrara em contato em breve."
}
```

#### 3. Pause Flow Action

Pauses the flow and schedules automatic resume.

```python
class PauseFlowAction(RecoveryAction):
    async def execute(self, error_record, context) -> RecoveryResult:
        flow_state.state_data["paused"] = True
        flow_state.state_data["pause_reason"] = f"Error recovery: {error_record.error_type}"
        flow_state.state_data["paused_at"] = datetime.now(timezone.utc).isoformat()

        # Schedule resume after 1 hour
        resume_at = datetime.now(timezone.utc) + timedelta(hours=1)
        await context.retry_manager.schedule_flow_resume(patient_id, resume_at)

        return RecoveryResult(
            success=True,
            strategy_used=RecoveryStrategy.PAUSE_FLOW,
            message="Flow paused for recovery, will resume in 1 hour(s)"
        )
```

#### 4. Reset Flow Action

Resets flow state to a safe state with backup.

```python
class ResetFlowAction(RecoveryAction):
    async def execute(self, error_record, context) -> RecoveryResult:
        # Backup current state
        backup_data = {
            "original_state": flow_state.state_data,
            "reset_reason": error_record.error_type,
            "reset_at": datetime.now(timezone.utc).isoformat(),
            "error_id": error_record.id
        }

        # Reset to safe state (go back one step)
        flow_state.state_data = {
            "reset": True,
            "backup": backup_data,
            "current_step": max(1, flow_state.current_step - 1),
            "reset_recovery": True
        }

        return RecoveryResult(
            success=True,
            strategy_used=RecoveryStrategy.RESET_FLOW,
            error_resolved=True,
            message="Flow state reset to safe state"
        )
```

#### 5. Escalate Manual Action

Escalates critical errors to healthcare providers via WebSocket.

```python
class EscalateManualAction(RecoveryAction):
    async def execute(self, error_record, context) -> RecoveryResult:
        escalation_data = {
            "error_id": error_record.id,
            "patient_id": str(error_record.context.patient_id),
            "error_type": error_record.error_type,
            "category": error_record.category.value,
            "severity": error_record.severity.value,
            "message": error_record.message,
            "requires_manual_intervention": True
        }

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
            message="Error escalated for manual intervention"
        )
```

---

## Retry Mechanisms

**Location**: `/backend-hormonia/app/domain/errors/flows/retry_manager.py`

### Configuration

```python
class ErrorHandlerConstants:
    # Retry delays (in seconds)
    DEFAULT_EXPONENTIAL_DELAYS = [60, 300, 900, 1800, 3600]  # 1min, 5min, 15min, 30min, 1hr
    DEFAULT_LINEAR_DELAY = 300  # 5 minutes

    # TTL and expiration
    REDIS_ERROR_TTL = 604800  # 7 days
    REDIS_RETRY_BUFFER = 60   # 1 minute buffer
    FLOW_RESUME_DELAY_HOURS = 1
```

### Max Retry Attempts by Category

```python
max_retry_attempts = {
    ErrorCategory.MESSAGE_DELIVERY: 5,
    ErrorCategory.FLOW_PROCESSING: 3,
    ErrorCategory.EXTERNAL_SERVICE: 7,
    ErrorCategory.DATA_CORRUPTION: 1,
    ErrorCategory.SYSTEM_ERROR: 2,
    ErrorCategory.VALIDATION_ERROR: 1,
}
```

### RetryManager Class

```python
class RetryManager:
    async def schedule_retry(self, error_record: ErrorRecord, retry_at: datetime) -> bool:
        """Schedule retry operation in Redis."""
        retry_data = {
            "error_id": error_record.id,
            "patient_id": str(error_record.context.patient_id),
            "operation": error_record.context.operation,
            "retry_at": retry_at.isoformat(),
            "attempt": error_record.recovery_attempts
        }

        ttl_seconds = int((retry_at - datetime.now(timezone.utc)).total_seconds()) + 60
        await self.redis.setex(f"flow_retry:{error_record.id}", ttl_seconds, json.dumps(retry_data))
        return True

    async def schedule_flow_resume(self, patient_id: UUID, resume_at: datetime) -> bool:
        """Schedule flow resume operation."""
        resume_data = {
            "patient_id": str(patient_id),
            "resume_at": resume_at.isoformat(),
            "reason": "error_recovery"
        }
        ttl_seconds = int((resume_at - datetime.now(timezone.utc)).total_seconds()) + 60
        await self.redis.setex(f"flow_resume:{patient_id}", ttl_seconds, json.dumps(resume_data))
        return True

    async def cancel_retry(self, error_id: str) -> bool:
        """Cancel scheduled retry."""
        await self.redis.delete(f"flow_retry:{error_id}")
        return True

    def should_retry(self, error_record: ErrorRecord) -> bool:
        """Determine if error should be retried."""
        return error_record.recovery_attempts < error_record.max_recovery_attempts
```

---

## Audit Logging

**Location**: `/backend-hormonia/app/domain/errors/flows/audit_logger.py`

### Error Record Storage

Errors are stored in Redis with 7-day TTL for monitoring and analysis.

```python
class ErrorAuditLogger:
    async def store_error(self, error_record: ErrorRecord) -> bool:
        """Store error record in Redis for monitoring."""
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
        await self.redis.setex(
            f"flow_error:{error_record.id}",
            604800,  # 7 days
            json.dumps(error_data)
        )
        return True
```

### Error Event Publishing

Errors are published via WebSocket for real-time monitoring.

```python
async def publish_error_event(self, error_record, recovery_result) -> bool:
    """Publish error event via WebSocket."""
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
    return True
```

### Error Escalation

Critical errors are escalated to healthcare providers.

```python
async def escalate_error(self, error_record, recovery_result) -> bool:
    """Escalate error to healthcare providers via WebSocket."""
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
        return True
    return False
```

### Error Statistics

Statistics are calculated with caching for monitoring dashboards.

```python
async def get_error_statistics(self, timeframe_hours: int = 24, use_cache: bool = True) -> dict:
    """Get error statistics for monitoring with caching."""
    stats = {
        "total_errors": 0,
        "by_category": {},
        "by_severity": {},
        "resolved_errors": 0,
        "pending_errors": 0,
        "recovery_success_rate": 0.0,
        "timeframe_hours": timeframe_hours,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
    # ... aggregation logic
    return stats
```

### Audit Log Format

```json
{
  "id": "12345678_9876_1703548800",
  "error_type": "FlowStateError",
  "category": "flow_processing",
  "severity": "medium",
  "message": "Flow state not found for patient",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "operation": "process_message",
  "recovery_attempts": 1,
  "resolved": false,
  "created_at": "2025-12-26T10:00:00.000Z"
}
```

---

## Exception Handling Examples

### Basic Error Handling

```python
from app.core.exceptions import NotFoundError, ValidationError

# Raise not found error
def get_patient(patient_id: str):
    patient = patient_repo.get(patient_id)
    if not patient:
        raise NotFoundError("Patient", patient_id)
    return patient

# Raise validation error
def validate_cpf(cpf: str):
    if not is_valid_cpf(cpf):
        raise ValidationError(
            "Invalid CPF format",
            errors={"cpf": "CPF must have 11 digits"},
            field="cpf",
            code="invalid_cpf"
        )
```

### Flow Error Handling

```python
from app.domain.errors.flows import (
    FlowErrorHandler,
    ErrorContext,
    get_flow_error_handler
)

async def process_patient_message(db: Session, patient_id: UUID, message: str):
    handler = get_flow_error_handler(db)

    try:
        # Process message
        result = await flow_engine.process(patient_id, message)
        return result
    except Exception as e:
        # Create error context
        context = ErrorContext(
            patient_id=patient_id,
            flow_state_id=flow_state_id,
            message_id=message_id,
            operation="process_message"
        )

        # Handle error with automatic recovery
        recovery_result = await handler.handle_error(e, context)

        if recovery_result.error_resolved:
            logger.info(f"Error recovered: {recovery_result.message}")
        else:
            logger.warning(f"Error requires attention: {recovery_result.message}")

        return recovery_result
```

### Custom Recovery Strategy

```python
from app.domain.errors.flows import FlowErrorHandler, RecoveryStrategy

async def handle_with_custom_strategy(db, error, context):
    handler = FlowErrorHandler(db)

    # Force specific recovery strategy
    result = await handler.handle_error(
        error=error,
        context=context,
        recovery_strategy=RecoveryStrategy.FALLBACK_MESSAGE
    )
    return result
```

### Middleware Exception Handling

```python
# In app/middleware/exception_handler.py

async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """Handle all APIException instances."""
    logger.warning(
        f"API Exception: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method
        }
    )
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())
```

### Graceful Error Handling

```python
from app.core.graceful_error_handler import graceful_error_handler

async def handle_database_operation():
    try:
        result = await db.execute(query)
        return result
    except Exception as e:
        error_response = await graceful_error_handler.handle_database_error(
            error=e,
            operation="query_patients",
            table_name="patients"
        )
        return error_response.to_json_response()
```

---

## Best Practices

### 1. Exception Selection

| Scenario | Exception to Use |
|----------|------------------|
| Resource not found | `NotFoundError`, `PatientNotFoundError` |
| Input validation failed | `ValidationError` |
| Business rule violation | `BusinessRuleError` |
| Duplicate resource | `ConflictError` |
| Authentication failed | `UnauthorizedError`, `AuthenticationError` |
| Permission denied | `ForbiddenError`, `AuthorizationError` |
| External API failure | `ExternalServiceError`, `AIServiceError` |
| Database operation failed | `DatabaseError` |
| Flow state issues | `FlowException`, `FlowStateError` |

### 2. Error Context Best Practices

Always provide rich context for debugging:

```python
# Good - Rich context
raise ValidationError(
    "Patient age validation failed",
    errors={"birth_date": "Patient must be at least 18 years old"},
    field="birth_date",
    code="invalid_age",
    patient_id=str(patient_id),
    provided_date=str(birth_date)
)

# Bad - Missing context
raise ValidationError("Validation failed")
```

### 3. Error Handling Hierarchy

```python
try:
    # Operation
    pass
except ValidationError as e:
    # Handle validation specifically
    return handle_validation_error(e)
except APIException as e:
    # Handle other API exceptions
    return handle_api_error(e)
except HormoniaException as e:
    # Handle application exceptions
    return handle_app_error(e)
except Exception as e:
    # Catch-all for unexpected errors
    return handle_unexpected_error(e)
```

### 4. Recovery Strategy Selection

| Error Category | Recommended Strategy | Max Retries |
|----------------|---------------------|-------------|
| Message Delivery | Exponential Backoff | 5 |
| External Service | Exponential Backoff | 7 |
| Flow Processing | Linear Backoff | 3 |
| System Error | Linear Backoff | 2 |
| Data Corruption | Escalate Manual | 1 |
| Validation Error | Skip and Continue | 1 |

### 5. Logging Guidelines

```python
# Error levels based on severity
logger.debug("...")    # LOW severity, non-critical
logger.info("...")     # Informational
logger.warning("...")  # MEDIUM severity, degraded
logger.error("...")    # HIGH severity, requires attention
logger.critical("...")  # CRITICAL severity, immediate action
```

### 6. Testing Error Handlers

```python
from app.domain.errors.flows import FlowErrorHandlerFactory

def test_error_handling():
    # Create handler with mocked dependencies
    handler = FlowErrorHandlerFactory.create_for_testing(
        db=mock_db,
        mock_memory=mock_memory,
        mock_repos={"flow_repo": mock_flow_repo}
    )

    # Test error handling
    result = await handler.handle_error(test_error, test_context)
    assert result.success
```

### 7. Cleanup and Maintenance

```python
# Periodic cleanup of old error records
async def cleanup_errors():
    handler = get_flow_error_handler(db)
    cleaned_count = await handler.cleanup_old_errors(days_old=7)
    logger.info(f"Cleaned {cleaned_count} old error records")
```

---

## Related Files

- `/backend-hormonia/app/core/exceptions.py` - Core exception definitions
- `/backend-hormonia/app/exceptions/__init__.py` - Exception package
- `/backend-hormonia/app/exceptions/flow_exceptions.py` - Flow-specific exceptions
- `/backend-hormonia/app/exceptions/response_processing.py` - Response processing exceptions
- `/backend-hormonia/app/domain/errors/flows/` - Flow error handling module
  - `classifier.py` - Error classification
  - `recovery_strategy.py` - Recovery actions
  - `retry_manager.py` - Retry scheduling
  - `audit_logger.py` - Error logging
  - `error_handler.py` - Main orchestrator
- `/backend-hormonia/app/middleware/exception_handler.py` - FastAPI middleware
- `/backend-hormonia/app/core/exception_handlers.py` - Core exception handlers
- `/backend-hormonia/app/core/graceful_error_handler.py` - Graceful degradation

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-26 | Initial documentation |
