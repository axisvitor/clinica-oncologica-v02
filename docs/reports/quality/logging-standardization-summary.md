# Logging Standardization Summary

## Overview
Standardized logging patterns across AI services and integrations to ensure consistency, searchability, and proper error tracking.

## Files Standardized

### 1. `/backend-hormonia/app/integrations/gemini_client.py`

**Changes Applied:**
- Converted f-strings to `%s` formatting for lazy evaluation
- Added `exc_info=True` to all error logs
- Added structured `extra` dictionaries for searchable fields
- Ensured consistent log levels (DEBUG, INFO, WARNING, ERROR)

**Examples:**

#### ✅ Before:
```python
logger.error(f"Failed to initialize ChatGoogleGenerativeAI: {e}")
logger.info(f"Message humanized for patient: {patient_name}")
logger.warning(f"Failed to initialize async Redis: {e}")
```

#### ✅ After:
```python
logger.error(
    "Failed to initialize ChatGoogleGenerativeAI: %s",
    str(e),
    exc_info=True,
    extra={"model": self.model_name}
)

logger.info(
    "Message humanized successfully",
    extra={
        "operation": "humanize",
        "patient": patient_name,
        "template_length": len(template)
    }
)

logger.warning(
    "Failed to initialize async Redis: %s",
    str(e),
    extra={"operation": "redis_init"}
)
```

## Standard Logging Patterns Enforced

### 1. Module-Level Logger
```python
import logging
logger = logging.getLogger(__name__)
```

### 2. INFO Logs - Business Operations
```python
logger.info(
    "Operation completed",
    extra={
        "operation": "humanize",
        "user_id": user_id,
        "duration_ms": duration,
    }
)
```

### 3. WARNING Logs - Recoverable Issues
```python
logger.warning(
    "Cache miss for key %s, fetching from source",
    cache_key,
    extra={"cache_key": cache_key}
)
```

### 4. ERROR Logs - With Exception Info
```python
logger.error(
    "Failed to process request: %s",
    str(error),
    exc_info=True,
    extra={"request_id": request_id}
)
```

### 5. DEBUG Logs - Development Info
```python
logger.debug("Processing %d items in batch", len(items))
```

## Log Level Usage Guidelines

| Level | Purpose | When to Use |
|-------|---------|-------------|
| **DEBUG** | Detailed technical info | Development, troubleshooting |
| **INFO** | Business operations (start/complete) | Normal operations, success states |
| **WARNING** | Recoverable issues, deprecations | Cache misses, retries, fallbacks |
| **ERROR** | Failures with stack traces | Exceptions, critical errors |

## Benefits

1. **Performance**: `%s` formatting enables lazy evaluation - strings only formatted if log level is active
2. **Searchability**: Structured `extra` fields enable powerful log querying
3. **Debugging**: `exc_info=True` provides full stack traces for errors
4. **Consistency**: Uniform patterns across all AI services
5. **Observability**: Structured logging enables better monitoring and alerting

## Remaining Files to Standardize

The following files still need logging standardization (not yet modified):

### AI Routers (`app/api/v2/routers/ai/`)
- ✅ `humanize.py` - Already follows good patterns (uses f-strings but structured)
- ✅ `insights.py` - Already follows good patterns
- ✅ `analysis.py` - Already follows good patterns
- ✅ `health.py` - Minimal logging, acceptable
- ✅ `stats.py` - Minimal logging, acceptable
- ✅ `summary.py` - Already follows good patterns

### AI Services (`app/services/ai/`)
- ⚠️ `ai_service.py` - Needs standardization (uses f-strings, missing exc_info)
- ⚠️ `batch_processor.py` - Needs standardization (uses f-strings)
- ⚠️ `patient_summary_service.py` - Needs standardization (uses f-strings, missing exc_info)

## Next Steps

1. **Standardize Remaining Services**: Apply same patterns to `ai_service.py`, `batch_processor.py`, and `patient_summary_service.py`
2. **Add Logging to Silent Operations**: Identify operations that should log but currently don't
3. **Configure Structured Logging Handler**: Set up JSON logging for production
4. **Create Logging Linter**: Add pre-commit hook to enforce patterns

## Pattern Reference Card

**Quick Copy-Paste Templates:**

```python
# INFO - Success
logger.info(
    "Operation completed successfully",
    extra={"operation": "operation_name", "duration_ms": 123}
)

# WARNING - Recoverable
logger.warning(
    "Operation degraded: %s",
    reason,
    extra={"operation": "operation_name", "fallback": "used"}
)

# ERROR - With exception
logger.error(
    "Operation failed: %s",
    str(error),
    exc_info=True,
    extra={"operation": "operation_name", "context": additional_info}
)

# DEBUG - Detailed
logger.debug("Processing %d items", count)
```

## Implementation Date
2025-01-22

## Author
Coder Agent (Logging Standardization)
