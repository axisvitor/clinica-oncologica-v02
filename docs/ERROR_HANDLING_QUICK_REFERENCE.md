# Error Handling Quick Reference Guide

**Quick lookup for common error handling patterns**

## Quick Decision Tree

```
Need to raise an error?
│
├─ Resource not found? → NotFoundError("Resource", id)
├─ Invalid input? → ValidationError("message", details={})
├─ Duplicate/conflict? → ConflictError("message", details={})
├─ No permission? → ForbiddenError("message")
├─ Not authenticated? → UnauthorizedError("message")
├─ External API failed? → ExternalServiceError("service", "error")
├─ AI operation failed? → AIProcessingError("message", details={})
├─ Flow error? → FlowStateNotFoundError/FlowValidationError/etc.
└─ Unknown error? → Use handle_service_error(e, "context")
```

## Common Patterns

### 1. Not Found (404)

```python
from app.core.exceptions import NotFoundError

# Resource not found
if not patient:
    raise NotFoundError("Patient", patient_id)

# Template not found
if not template:
    raise NotFoundError("Template", template_id)
```

### 2. Validation Error (422)

```python
from app.core.exceptions import ValidationError

# Single field
raise ValidationError(
    "Invalid email format",
    details={"field": "email", "value": email}
)

# Multiple fields
raise ValidationError(
    "Input validation failed",
    errors={
        "email": "Invalid format",
        "age": "Must be at least 18"
    }
)
```

### 3. Conflict/Duplicate (409)

```python
from app.core.exceptions import ConflictError

if existing:
    raise ConflictError(
        "Template already exists",
        details={"name": name, "version": version}
    )
```

### 4. External Service Error (503)

```python
from app.core.exceptions import ExternalServiceError

# WhatsApp API failed
raise ExternalServiceError("WhatsApp", "Connection timeout")

# Firebase failed
raise ExternalServiceError("Firebase", error_message)
```

### 5. AI Processing Error (503)

```python
from app.core.exceptions import AIProcessingError

raise AIProcessingError(
    "Failed to analyze sentiment",
    details={"patient_id": patient_id, "operation": "sentiment_analysis"}
)
```

## Router Pattern (FastAPI)

```python
from fastapi import HTTPException
from app.core.exceptions import NotFoundError, ValidationError
from app.utils.error_handlers import handle_service_error

@router.get("/resource/{resource_id}")
async def get_resource(resource_id: UUID, db=Depends(get_db)):
    try:
        # Your logic here
        resource = db.query(Resource).get(resource_id)

        if not resource:
            raise NotFoundError("Resource", resource_id)

        return resource

    except HTTPException:
        raise  # Re-raise FastAPI exceptions

    except Exception as e:
        raise handle_service_error(e, "get_resource")
```

## Service Pattern

```python
from app.core.exceptions import ValidationError, NotFoundError

class MyService:
    async def update_item(self, item_id: str, data: dict):
        try:
            # Validate
            if not self.validate(data):
                raise ValidationError("Invalid data", details=data)

            # Find
            item = await self.find(item_id)
            if not item:
                raise NotFoundError("Item", item_id)

            # Update
            return await self.save(item, data)

        except (ValidationError, NotFoundError):
            raise  # Re-raise domain exceptions

        except Exception as e:
            logger.error(f"Update failed: {e}", exc_info=True)
            raise ProcessingError(f"Failed to update: {e}")
```

## Error Handler Quick Reference

```python
from app.utils.error_handlers import (
    handle_api_exception,      # APIException → HTTPException
    handle_validation_error,   # Validation errors
    handle_not_found_error,    # 404 errors
    handle_service_error,      # Generic catch-all
    handle_flow_error,         # Flow-specific
    handle_ai_error,           # AI service errors
)

# Use in try/except:
try:
    result = operation()
except NotFoundError as e:
    raise handle_not_found_error(e)
except Exception as e:
    raise handle_service_error(e, "operation_name")
```

## Status Code Reference

| Exception | Status | Error Code |
|-----------|--------|------------|
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

## Import Quick Reference

```python
# Core exceptions
from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    ConflictError,
    UnauthorizedError,
    ForbiddenError,
    BadRequestError,
    ExternalServiceError,
    AIProcessingError,
    FlowStateNotFoundError,
    FlowValidationError,
)

# Error handlers
from app.utils.error_handlers import (
    handle_service_error,
    handle_validation_error,
    handle_not_found_error,
    handle_flow_error,
    handle_ai_error,
)
```

## Common Mistakes to Avoid

```python
# ❌ DON'T: Bare except
try:
    do_something()
except:
    pass

# ✅ DO: Specific exception
try:
    do_something()
except ValueError as e:
    raise ValidationError(str(e))

# ❌ DON'T: Wrong status code
raise HTTPException(status_code=400, detail="Not found")

# ✅ DO: Correct exception type
raise NotFoundError("Resource", resource_id)

# ❌ DON'T: Silent failure
try:
    critical_operation()
except Exception:
    pass

# ✅ DO: Log and re-raise
try:
    critical_operation()
except Exception as e:
    logger.error(f"Failed: {e}", exc_info=True)
    raise

# ❌ DON'T: Lose context
except SpecificError:
    raise Exception("Generic error")

# ✅ DO: Preserve or enhance
except SpecificError:
    raise  # or wrap with more context
```

## Logging Best Practices

```python
import logging

logger = logging.getLogger(__name__)

# ✅ Include context
logger.error(f"Operation failed for patient {patient_id}: {e}", exc_info=True)

# ✅ Use appropriate level
logger.info("Resource not found")  # Expected, not critical
logger.warning("Validation failed")  # User error, not system
logger.error("Database error", exc_info=True)  # System error

# ❌ Don't log sensitive data
logger.error(f"Auth failed: {password}")  # NEVER!

# ✅ Log safely
logger.error(f"Auth failed for user {user_id}")  # Safe
```

## Quick Templates

### Generic CRUD Endpoint

```python
@router.get("/{item_id}")
async def get_item(item_id: UUID, db=Depends(get_db)):
    try:
        item = db.query(Model).get(item_id)
        if not item:
            raise NotFoundError("Item", item_id)
        return item
    except HTTPException:
        raise
    except Exception as e:
        raise handle_service_error(e, "get_item")

@router.post("/")
async def create_item(data: Schema, db=Depends(get_db)):
    try:
        if not validate(data):
            raise ValidationError("Invalid data", details=data.dict())

        existing = db.query(Model).filter_by(name=data.name).first()
        if existing:
            raise ConflictError("Item exists", details={"name": data.name})

        item = Model(**data.dict())
        db.add(item)
        db.commit()
        return item
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_service_error(e, "create_item")
```

### AI Service Call

```python
async def process_with_ai(patient_id: str, message: str):
    try:
        ai_service = await get_ai_service()
        context = await build_context(patient_id)

        result = await ai_service.process(message, context)
        return result

    except AIProcessingError:
        raise

    except ExternalServiceError:
        raise

    except Exception as e:
        raise handle_ai_error(e, "message_processing", "process")
```

### Flow Operation

```python
async def update_flow(patient_id: str, new_state: str):
    try:
        state = await get_flow_state(patient_id)

        if not state:
            raise FlowStateNotFoundError(
                "No active flow",
                patient_id=patient_id
            )

        if not validate_transition(state.current, new_state):
            raise FlowValidationError(
                "Invalid transition",
                patient_id=patient_id,
                details={"from": state.current, "to": new_state}
            )

        await transition(patient_id, new_state)
        return {"status": "success"}

    except FlowException:
        raise

    except Exception as e:
        raise handle_flow_error(e, "update_flow", patient_id)
```

## Need More Details?

- **Full Documentation**: `/docs/ERROR_HANDLING_STANDARDIZATION.md`
- **Implementation Summary**: `/docs/ERROR_HANDLING_IMPLEMENTATION_SUMMARY.md`
- **Exception Hierarchy**: `/app/core/exceptions.py`
- **Error Handlers**: `/app/utils/error_handlers.py`
