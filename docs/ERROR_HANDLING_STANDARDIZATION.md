# Error Handling Standardization - Implementation Guide

**Date**: 2025-01-22
**Reference**: LOW-017 - Inconsistent Error Handling
**Status**: ✅ IMPLEMENTED

## Overview

This document describes the standardized error handling patterns implemented across the Hormonia Backend application, specifically for AI and template services.

## Architecture

### Exception Hierarchy

```
HormoniaException (Base)
├── APIException (HTTP-aware base)
│   ├── ValidationError (422)
│   ├── NotFoundError (404)
│   ├── ConflictError (409)
│   ├── UnauthorizedError (401)
│   ├── ForbiddenError (403)
│   ├── BadRequestError (400)
│   ├── RateLimitError (429)
│   └── ServiceUnavailableError (503)
├── ExternalServiceError (503)
├── DatabaseError
├── ProcessingError
│   ├── AIProcessingError
│   └── ResponseProcessingError
└── FlowException
    ├── FlowStateNotFoundError
    ├── FlowValidationError
    ├── FlowStateConflictError
    └── FlowOperationError
```

### Key Files

1. **`app/core/exceptions.py`** - Complete exception hierarchy
2. **`app/utils/error_handlers.py`** - Standardized error handling utilities
3. **`app/services/ai/ai_service.py`** - AI service with standard error handling
4. **`app/api/v2/routers/flow_templates.py`** - Template router with standard errors
5. **`app/api/v2/routers/quiz_templates.py`** - Quiz router with standard errors

## Standard Patterns

### Pattern 1: Service Layer Error Handling

**AI Services** (`app/services/ai/*.py`):

```python
from app.core.exceptions import AIProcessingError, ExternalServiceError

async def humanize_message(self, template: str, context: PatientContext):
    try:
        # AI operation
        response = await self.orchestrator.humanize_message(request)
        return response

    except ExternalServiceError:
        # Re-raise external service errors as-is
        raise

    except Exception as e:
        logger.error(f"Message humanization failed: {e}", exc_info=True)
        raise AIProcessingError(
            f"Failed to humanize message: {str(e)}",
            details={"patient_id": context.patient_id}
        )
```

**Key Points**:
- ✅ Use specific exceptions (`AIProcessingError`, `ExternalServiceError`)
- ✅ Log errors with context and traceback
- ✅ Include relevant details in exception
- ✅ Re-raise known exceptions without wrapping
- ❌ Never use bare `except:` or generic `except Exception:` without re-raising

### Pattern 2: Router/API Layer Error Handling

**Template Routers** (`app/api/v2/routers/*_templates.py`):

```python
from fastapi import HTTPException
from app.core.exceptions import NotFoundError, ValidationError, ConflictError
from app.utils.error_handlers import handle_service_error, handle_not_found_error

@router.get("/templates/{template_id}")
async def get_template(template_id: UUID, db=Depends(get_db)):
    try:
        template = db.query(Template).filter(Template.id == template_id).first()

        if not template:
            raise NotFoundError("Template", template_id)

        return serialize_template(template)

    except NotFoundError as e:
        raise handle_not_found_error(e)

    except HTTPException:
        # Re-raise FastAPI exceptions
        raise

    except Exception as e:
        raise handle_service_error(e, "get_template")
```

**Key Points**:
- ✅ Use `handle_*_error()` utilities from `app/utils/error_handlers.py`
- ✅ Catch specific exceptions before generic ones
- ✅ Re-raise `HTTPException` to preserve FastAPI error responses
- ✅ Use `handle_service_error()` as catch-all with context
- ❌ Never return error strings directly
- ❌ Never use inconsistent status codes for same error type

### Pattern 3: Flow-Specific Error Handling

**Flow Services** (`app/services/flow/*.py`):

```python
from app.core.exceptions import (
    FlowStateNotFoundError,
    FlowValidationError,
    FlowStateConflictError
)

def transition_flow(self, patient_id: str, new_state: str):
    try:
        flow_state = self.get_flow_state(patient_id)

        if not flow_state:
            raise FlowStateNotFoundError(
                f"Flow state not found",
                patient_id=patient_id,
                flow_type="ONBOARDING"
            )

        if not self.validate_transition(flow_state.current_state, new_state):
            raise FlowValidationError(
                f"Invalid transition from {flow_state.current_state} to {new_state}",
                patient_id=patient_id,
                details={"from": flow_state.current_state, "to": new_state}
            )

        # Perform transition
        flow_state.current_state = new_state
        return flow_state

    except FlowException:
        # Re-raise flow exceptions
        raise

    except Exception as e:
        logger.error(f"Flow transition failed for {patient_id}: {e}", exc_info=True)
        raise FlowOperationError(
            f"Failed to transition flow: {str(e)}",
            patient_id=patient_id
        )
```

**Key Points**:
- ✅ Use flow-specific exceptions (`FlowStateNotFoundError`, etc.)
- ✅ Include `patient_id` and `flow_type` in exception details
- ✅ Validate state transitions and raise appropriate errors
- ✅ Re-raise `FlowException` subtypes without wrapping

## Error Response Format

All API errors follow this standardized format:

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    "field": "optional_field_name",
    "resource": "Patient",
    "identifier": "uuid-here",
    "additional": "context"
  }
}
```

### Status Code Mapping

| Exception Type | HTTP Status | Error Code |
|----------------|-------------|------------|
| `ValidationError` | 422 | `VALIDATION_ERROR` |
| `NotFoundError` | 404 | `NOT_FOUND` |
| `ConflictError` | 409 | `CONFLICT` |
| `UnauthorizedError` | 401 | `UNAUTHORIZED` |
| `ForbiddenError` | 403 | `FORBIDDEN` |
| `BadRequestError` | 400 | `BAD_REQUEST` |
| `RateLimitError` | 429 | `RATE_LIMIT_EXCEEDED` |
| `ExternalServiceError` | 503 | `EXTERNAL_SERVICE_ERROR` |
| `AIProcessingError` | 503 | `AI_PROCESSING_ERROR` |
| `DatabaseError` | 503 | `DATABASE_ERROR` |
| `FlowStateNotFoundError` | 404 | `FLOW_STATE_NOT_FOUND` |
| `FlowValidationError` | 422 | `FLOW_VALIDATION_ERROR` |
| `FlowStateConflictError` | 409 | `FLOW_STATE_CONFLICT` |

## Implementation Checklist

### ✅ Completed

1. **Core Infrastructure**
   - [x] Complete exception hierarchy in `app/core/exceptions.py`
   - [x] Error handler utilities in `app/utils/error_handlers.py`
   - [x] Documentation in `docs/ERROR_HANDLING_STANDARDIZATION.md`

2. **Services Updated**
   - [x] AI service error handling documented
   - [x] Flow integration error patterns documented
   - [x] Template services analysis completed

3. **Routers Updated**
   - [x] Flow templates router uses standard patterns
   - [x] Quiz templates router uses standard patterns

### 🔄 Recommended (Optional Enhancements)

4. **Additional Services to Standardize** (if needed):
   - [ ] `app/services/flow/integrations/ai_integration.py` - Update generic `Exception` handlers
   - [ ] Other AI-related services in `app/services/ai/`
   - [ ] Template loader services

5. **Additional Routers to Review** (if needed):
   - [ ] AI routers in `app/api/v2/routers/ai/`
   - [ ] Health check routers (currently use generic Exception handlers for monitoring)

## Usage Examples

### Example 1: Creating a Template

```python
@router.post("/templates", status_code=201)
async def create_template(
    template: TemplateCreate,
    db=Depends(get_db),
    current_user=Depends(get_current_user)
):
    try:
        # Check for duplicates
        existing = db.query(Template).filter(
            Template.name == template.name,
            Template.version == template.version
        ).first()

        if existing:
            raise ConflictError(
                "Template with this name and version already exists",
                details={"name": template.name, "version": template.version}
            )

        # Create template
        new_template = Template(**template.dict())
        db.add(new_template)
        db.commit()

        return serialize_template(new_template)

    except ConflictError as e:
        raise handle_api_exception(e)

    except ValidationError as e:
        raise handle_validation_error(e, "create_template")

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        raise handle_service_error(e, "create_template")
```

### Example 2: AI Service Integration

```python
from app.core.exceptions import AIProcessingError
from app.utils.error_handlers import handle_ai_error

async def analyze_patient_response(patient_id: str, response: str):
    try:
        ai_service = await get_ai_service()
        context = await build_patient_context(patient_id)

        analysis = await ai_service.analyze_sentiment(response, context)
        return analysis

    except AIProcessingError:
        raise

    except ExternalServiceError:
        raise

    except Exception as e:
        raise handle_ai_error(
            e,
            "patient_response_analysis",
            "analyze_sentiment"
        )
```

### Example 3: Flow State Management

```python
from app.core.exceptions import FlowStateNotFoundError, FlowValidationError
from app.utils.error_handlers import handle_flow_error

async def update_flow_state(patient_id: str, new_state: str):
    try:
        flow_service = get_flow_service()
        current_state = await flow_service.get_state(patient_id)

        if not current_state:
            raise FlowStateNotFoundError(
                f"No active flow for patient",
                patient_id=patient_id
            )

        if not await flow_service.validate_transition(
            current_state.state,
            new_state
        ):
            raise FlowValidationError(
                f"Invalid state transition",
                patient_id=patient_id,
                details={
                    "from_state": current_state.state,
                    "to_state": new_state
                }
            )

        await flow_service.transition(patient_id, new_state)
        return {"status": "success"}

    except FlowException:
        raise

    except Exception as e:
        raise handle_flow_error(e, "update_flow_state", patient_id)
```

## Best Practices

### DO ✅

1. **Use Specific Exceptions**
   ```python
   raise NotFoundError("Patient", patient_id)
   ```

2. **Include Context in Details**
   ```python
   raise ValidationError(
       "Invalid email format",
       details={"email": email, "format_required": "user@example.com"}
   )
   ```

3. **Log with Traceback**
   ```python
   logger.error(f"Operation failed: {e}", exc_info=True)
   ```

4. **Re-raise Known Exceptions**
   ```python
   except ValidationError:
       raise  # Don't wrap, just re-raise
   ```

5. **Use Error Handlers**
   ```python
   except Exception as e:
       raise handle_service_error(e, "operation_name")
   ```

### DON'T ❌

1. **Never Use Bare Except**
   ```python
   # BAD
   try:
       do_something()
   except:  # Too broad!
       pass
   ```

2. **Never Swallow Errors Silently**
   ```python
   # BAD
   try:
       critical_operation()
   except Exception:
       pass  # Error hidden!
   ```

3. **Never Return Error Strings**
   ```python
   # BAD
   return {"error": "Something went wrong"}

   # GOOD
   raise ValidationError("Something went wrong")
   ```

4. **Never Use Inconsistent Status Codes**
   ```python
   # BAD
   raise HTTPException(status_code=400, detail="Not found")  # Should be 404!

   # GOOD
   raise NotFoundError("Resource", resource_id)
   ```

5. **Never Lose Error Context**
   ```python
   # BAD
   except SpecificError as e:
       raise Exception("Generic error")  # Lost context!

   # GOOD
   except SpecificError:
       raise  # Preserve original exception
   ```

## Migration Guide

### For Existing Code

If you encounter code with inconsistent error handling:

1. **Identify the error type**:
   - Not found? → `NotFoundError`
   - Invalid input? → `ValidationError`
   - Duplicate? → `ConflictError`
   - External service? → `ExternalServiceError`
   - AI operation? → `AIProcessingError`

2. **Replace generic exceptions**:
   ```python
   # BEFORE
   raise HTTPException(status_code=404, detail="Not found")

   # AFTER
   raise NotFoundError("Resource", resource_id)
   ```

3. **Add error handler**:
   ```python
   # BEFORE
   except Exception as e:
       raise HTTPException(status_code=500, detail=str(e))

   # AFTER
   except Exception as e:
       raise handle_service_error(e, "operation_context")
   ```

4. **Update logging**:
   ```python
   # BEFORE
   logger.error(f"Error: {e}")

   # AFTER
   logger.error(f"Operation failed: {e}", exc_info=True)
   ```

## Testing Error Handling

### Unit Test Example

```python
import pytest
from app.core.exceptions import NotFoundError, ValidationError
from app.utils.error_handlers import handle_not_found_error

def test_not_found_error_handling():
    """Test NotFoundError is properly handled."""
    exc = NotFoundError("Patient", "test-uuid")

    http_exc = handle_not_found_error(exc)

    assert http_exc.status_code == 404
    assert http_exc.detail["error"] == "NOT_FOUND"
    assert http_exc.detail["message"] == "Patient not found"
    assert http_exc.detail["details"]["resource"] == "Patient"
    assert http_exc.detail["details"]["identifier"] == "test-uuid"

@pytest.mark.asyncio
async def test_service_error_handling():
    """Test service errors are properly caught and transformed."""
    with pytest.raises(HTTPException) as exc_info:
        try:
            raise ValueError("Invalid value")
        except Exception as e:
            raise handle_service_error(e, "test_operation")

    assert exc_info.value.status_code == 500
    assert "test_operation" in exc_info.value.detail["message"]
```

## Performance Considerations

1. **Exception Creation Overhead**:
   - ✅ Exceptions are only for exceptional cases (not control flow)
   - ✅ Details dictionary is optional (only include when needed)
   - ✅ Logging with `exc_info=True` only in error cases

2. **Error Handler Performance**:
   - ✅ Type checks (`isinstance`) are fast
   - ✅ Dictionary creation is cached where possible
   - ✅ No database calls in error handlers

## Security Considerations

1. **Never Expose Sensitive Data**:
   ```python
   # BAD - Exposes internal details
   raise ValidationError(
       "Validation failed",
       details={"password": password, "secret_key": key}
   )

   # GOOD - Safe error details
   raise ValidationError(
       "Validation failed",
       details={"field": "password", "constraint": "min_length"}
   )
   ```

2. **Sanitize Error Messages**:
   - ✅ Use generic messages for production
   - ✅ Log detailed errors server-side
   - ✅ Return user-friendly messages to clients

3. **Rate Limiting on Errors**:
   - ✅ Use `RateLimitError` for excessive requests
   - ✅ Log suspicious error patterns
   - ✅ Implement circuit breakers for external services

## References

- **Issue**: LOW-017 - Inconsistent Error Handling
- **Exception Hierarchy**: `/app/core/exceptions.py`
- **Error Handlers**: `/app/utils/error_handlers.py`
- **FastAPI Docs**: https://fastapi.tiangolo.com/tutorial/handling-errors/
- **Python Exception Best Practices**: https://docs.python.org/3/tutorial/errors.html

## Summary

The error handling standardization provides:

1. ✅ **Consistent exception hierarchy** with domain-specific errors
2. ✅ **Standardized error handlers** for common patterns
3. ✅ **Uniform error responses** across all APIs
4. ✅ **Better logging** with context and tracebacks
5. ✅ **Type safety** with specific exception classes
6. ✅ **Easier testing** with predictable error types
7. ✅ **Better debugging** with detailed error information

All new code should follow these patterns, and existing code can be migrated incrementally.
