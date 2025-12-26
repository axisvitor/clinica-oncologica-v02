# Error Handling Fixes - Quick Reference Guide

## Critical Fixes (Do First!)

### FIX-001: Remove `str(e)` from HTTP Responses

**Files to Fix**:
- `app/api/v2/flows/advanced.py` - Lines 115, 212, 268, 386, 637, 689 (7 instances)
- `app/api/v2/flows/state.py` - Lines 160, 215, 263 (3 instances)
- `app/services/firebase_auth_service.py` - Line 200 (1 instance)

**Total**: 11 occurrences

**Pattern - BEFORE**:
```python
except FlowOperationError as e:
    raise flow_operation_exception("advance_flow", str(e))
    # ^^ SECURITY ISSUE: Exception message exposed to client
```

**Pattern - AFTER**:
```python
except FlowOperationError as e:
    logger.error(f"Flow operation failed: {str(e)}", exc_info=True)
    # Log the detailed error
    raise flow_operation_exception("advance_flow", "Operation failed")
    # Return generic message to client
```

**Impact**:
- Eliminates potential information leak (stack traces, internal paths, etc.)
- Maintains detailed error logging for debugging
- Improves security posture

**Effort**: 15 minutes (global find/replace + manual review)

---

### FIX-002: Replace Bare Exception Handlers

**File**: `app/middleware/enhanced_error_handler.py:308`

**BEFORE**:
```python
def _get_system_state(self) -> Dict[str, Any]:
    try:
        return {
            "cpu_percent": round(psutil.cpu_percent(interval=0.1), 2),
            # ...
        }
    except Exception:  # ❌ BARE EXCEPT
        return {"error": "Could not retrieve system state"}
```

**AFTER**:
```python
def _get_system_state(self) -> Dict[str, Any]:
    try:
        return {
            "cpu_percent": round(psutil.cpu_percent(interval=0.1), 2),
            # ...
        }
    except (OSError, RuntimeError) as e:  # ✅ SPECIFIC EXCEPTIONS
        logger.debug(f"Could not retrieve system state: {str(e)}")
        return {"error": "Could not retrieve system state"}
```

**Impact**:
- Improves exception specificity
- Easier to debug unexpected errors
- Better error categorization

**Effort**: 5 minutes

---

## Major Fixes (This Sprint)

### FIX-003: Handle Swallowed Exceptions Properly

**File**: `app/services/error_recovery.py:336`

**BEFORE**:
```python
try:
    error_key = f"flow_errors:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    await self.redis.lpush(error_key, json.dumps(error_data))
    await self.redis.expire(error_key, 86400 * 7)
except Exception:  # ❌ SWALLOWED
    pass  # Don't fail if Redis is unavailable
```

**AFTER**:
```python
try:
    error_key = f"flow_errors:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    await self.redis.lpush(error_key, json.dumps(error_data))
    await self.redis.expire(error_key, 86400 * 7)
except redis.ConnectionError as e:
    # ✅ SPECIFIC EXCEPTION WITH FALLBACK
    logger.warning(
        f"Failed to store error in Redis (non-critical): {str(e)}",
        exc_info=True
    )
    # TODO: Implement in-memory buffer fallback
except Exception as e:
    logger.error(f"Unexpected error storing flow error: {str(e)}", exc_info=True)
```

**Impact**:
- Improves observability
- Enables graceful degradation
- Facilitates root cause analysis

**Effort**: 10 minutes

---

### FIX-004: Improve Generic Exception Handlers

**File**: `app/api/v2/routers/auth.py:138`

**BEFORE**:
```python
try:
    user, created = await sync_service.sync_firebase_user(
        firebase_uid=firebase_uid,
        firebase_data=user_data,
        auto_create=True
    )
except ValueError as e:  # ❌ TOO GENERIC
    logger.warning(f"Firebase sync validation failed: {str(e)}")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied: Invalid user configuration"
    )
```

**AFTER**:
```python
try:
    user, created = await sync_service.sync_firebase_user(
        firebase_uid=firebase_uid,
        firebase_data=user_data,
        auto_create=True
    )
except ValueError as e:  # ✅ WITH CONTEXT
    error_message = str(e)
    if "unauthorized" in error_message.lower():
        logger.warning(
            f"Firebase user domain not authorized: {error_message}",
            extra={"user_email": email, "firebase_uid": firebase_uid}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User domain not authorized"
        )
    elif "claims" in error_message.lower():
        logger.warning(
            f"Invalid Firebase claims: {error_message}",
            extra={"user_email": email}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user configuration"
        )
    else:
        logger.error(f"Firebase sync validation failed: {error_message}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
```

**Impact**:
- Better error categorization
- Improved debugging capability
- More specific error messages to clients

**Effort**: 20 minutes

---

### FIX-005: Add Exception Chaining

**Pattern** (applies to multiple files):

**BEFORE**:
```python
except Exception as e:
    logger.error(f"Error getting user: {str(e)}")
    return None  # ❌ LOST CONTEXT
```

**AFTER**:
```python
except auth.UserNotFoundError:
    logger.warning(f"User not found: {uid}")
    return None

except Exception as e:
    # ✅ PRESERVE EXCEPTION CHAIN
    logger.error(f"Error getting user: {str(e)}", exc_info=True)
    raise FirebaseServiceError(f"Failed to retrieve user {uid}") from e
```

**Key Points**:
- Use `from e` to preserve original exception
- Use `exc_info=True` in logging to capture full traceback
- Define custom exceptions in `app/exceptions/__init__.py`

**Impact**:
- Preserves full error context for debugging
- Better stack trace in logs
- Easier root cause analysis

**Effort**: 25 minutes (multiple files)

---

## Minor Improvements (Backlog)

### FIX-006: Standardize HTTP Error Response Format

**Goal**: All error responses follow consistent structure

```python
# Standardized error response schema
{
    "detail": str,           # Human-readable message
    "error_code": str,       # Machine-readable code (e.g., "FLOW_NOT_FOUND")
    "status_code": int,      # HTTP status code
    "timestamp": str,        # ISO 8601 format
    "request_id": str,       # For request tracing
    "error_type": str        # Category: validation, auth, resource, etc.
}
```

**File to Create**: `app/schemas/error_response.py`

```python
from pydantic import BaseModel
from typing import Optional

class ErrorResponse(BaseModel):
    detail: str
    error_code: str
    status_code: int
    timestamp: str
    request_id: str
    error_type: str

    class Config:
        schema_extra = {
            "example": {
                "detail": "Patient not found",
                "error_code": "PATIENT_NOT_FOUND",
                "status_code": 404,
                "timestamp": "2025-12-25T10:30:00Z",
                "request_id": "req_abc123def456",
                "error_type": "resource"
            }
        }
```

**Effort**: 30 minutes

---

### FIX-007: Replace Exception Returns with Raises

**File**: `app/services/error_recovery.py` (multiple locations)

**BEFORE**:
```python
async def handle_error(self, error: Exception, context: dict) -> bool:
    try:
        recovery_func = self._get_recovery_strategy(error)
        if not recovery_func:
            logger.error(f"No recovery strategy for error type: {type(error)}")
            return False  # ❌ AMBIGUOUS
        # ...
        return recovery_result
    except Exception as recovery_error:
        logger.error(f"Error during recovery process: {recovery_error}")
        return False  # ❌ SWALLOWED
```

**AFTER**:
```python
async def handle_error(self, error: Exception, context: dict) -> bool:
    """
    Handle flow operation errors with appropriate recovery strategy.

    Returns:
        True if error was successfully recovered

    Raises:
        UnrecoverableError: If error cannot be recovered
    """
    try:
        recovery_func = self._get_recovery_strategy(error)
        if not recovery_func:
            # ✅ RAISE instead of return False
            raise UnrecoverableError(
                f"No recovery strategy for error type: {type(error).__name__}",
                original_error=error
            )

        recovery_result = await recovery_func(error, context)
        if recovery_result:
            logger.info(f"Successfully recovered from error: {error}")
            return True
        else:
            # ✅ Distinguish between "recovered" and "unrecoverable"
            raise UnrecoverableError(
                f"Recovery strategy failed for {type(error).__name__}",
                original_error=error
            )
    except (UnrecoverableError, UnhandledError):
        raise  # Re-raise known exceptions
    except Exception as recovery_error:
        # ✅ CHAIN EXCEPTIONS
        raise UnrecoverableError(
            f"Error during recovery process: {str(recovery_error)}",
            original_error=recovery_error
        ) from recovery_error
```

**First, Create the Custom Exception**:
```python
# In app/exceptions/__init__.py

class UnrecoverableError(Exception):
    """Raised when an error cannot be automatically recovered."""

    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        error_code: str = "UNRECOVERABLE_ERROR"
    ):
        self.message = message
        self.original_error = original_error
        self.error_code = error_code
        super().__init__(self.message)
```

**Effort**: 35 minutes

---

### FIX-008: Add Resource Cleanup in Exception Paths

**File**: `app/integrations/whatsapp/api/webhooks.py` (and similar patterns)

**BEFORE**:
```python
async def _legacy_is_event_processed(event_id: str) -> bool:
    try:
        redis_client = await get_redis()
        key = f"webhook:processed:{event_id}"
        result = await redis_client.set(key, "1", nx=True, ex=86400)
        if result:
            return False
        else:
            return True
    except Exception as e:
        logger.error(f"Legacy idempotency also failed: {e}")
        return False
```

**AFTER**:
```python
async def _legacy_is_event_processed(event_id: str) -> bool:
    redis_client = None
    try:
        redis_client = await get_redis()
        key = f"webhook:processed:{event_id}"
        result = await redis_client.set(key, "1", nx=True, ex=86400)
        return not result  # True if new, False if exists
    except Exception as e:
        logger.error(f"Legacy idempotency check failed: {e}", exc_info=True)
        return False
    finally:
        # ✅ Cleanup happens regardless of success/failure
        # Note: redis.asyncio client doesn't need explicit close
        # but this documents cleanup intent
        pass
```

**Better Approach** (Using context manager):
```python
async def _legacy_is_event_processed(event_id: str) -> bool:
    """Check if webhook event was already processed (legacy fallback)."""
    try:
        # redis.asyncio handles connection pooling automatically
        redis_client = await get_redis()
        key = f"webhook:processed:{event_id}"
        result = await redis_client.set(key, "1", nx=True, ex=86400)
        return not result
    except redis.ConnectionError as e:
        logger.error(f"Redis connection failed: {e}", exc_info=True)
        return False  # Fail-open to not drop events
    except Exception as e:
        logger.error(f"Idempotency check failed: {e}", exc_info=True)
        return False
```

**Effort**: 15 minutes

---

## Implementation Priority Matrix

```
         Low Effort    Medium Effort    High Effort
Impact
High     FIX-001      FIX-004           FIX-005
         FIX-002      FIX-006           FIX-007
         FIX-003
         FIX-008

Medium   (none)       (none)            (none)

Low      (none)       (none)            (none)
```

---

## Testing Checklist

### Before Submitting Each Fix

- [ ] Run pytest on modified file(s)
- [ ] Check logging output for error messages
- [ ] Verify exception details don't leak in HTTP responses
- [ ] Confirm exception chain is preserved in logs
- [ ] Test error paths (not just happy path)

### Example Test Cases

```python
# Test that error messages don't leak
async def test_flow_operation_error_generic():
    response = client.post("/flows/123/advance")
    assert response.status_code == 500
    # Should NOT contain original exception message
    assert str(error) not in response.json()["detail"]

# Test that detailed errors are in logs
async def test_flow_operation_error_logged():
    with caplog.at_level(logging.ERROR):
        await flow_service.advance_flow(patient_id)
    # Logs SHOULD contain detailed error
    assert "detailed error message" in caplog.text
```

---

## Rollout Plan

### Phase 1: Critical Fixes (This Week)
- [ ] FIX-001: Remove `str(e)` from responses (11 occurrences)
- [ ] FIX-002: Replace bare exceptions (1 occurrence)
- [ ] Create PR, get review, merge
- [ ] Deploy to staging
- [ ] Test in staging environment

### Phase 2: Major Fixes (Next Sprint)
- [ ] FIX-003: Handle swallowed exceptions
- [ ] FIX-004: Improve generic handlers
- [ ] FIX-005: Add exception chaining
- [ ] Create PR, review, merge
- [ ] Deploy to staging + production

### Phase 3: Minor Improvements (Backlog)
- [ ] FIX-006: Standardize response format
- [ ] FIX-007: Replace returns with raises
- [ ] FIX-008: Add resource cleanup
- [ ] Plan for next sprint

---

## Questions & Answers

**Q: Why remove `str(e)` from error responses?**
A: Exception messages can contain sensitive information (file paths, stack traces, configuration details). Detailed errors should be logged server-side, not sent to clients.

**Q: What about users needing detailed error information?**
A: Use the `request_id` field in error response. Log the detailed error server-side and provide API that admin users can query with request_id.

**Q: Should I always use exception chaining?**
A: Yes, when you catch an exception and raise a different one. It preserves the original stack trace for debugging.

**Q: What's the difference between `exc_info=True` and `from e`?**
A:
- `exc_info=True` in logger calls includes full traceback in logs
- `from e` in raise statements preserves exception chain in the exception object itself

Use both together for maximum debugging information.

---

## Contact & Questions

- Code Quality: Review with team lead
- Security: Escalate information leak fixes
- Testing: QA team should validate error scenarios
- Deployment: Follow standard release process

---

**Document Version**: 1.0
**Created**: 2025-12-25
**Last Updated**: 2025-12-25
