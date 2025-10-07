# P1-2: Circuit Breaker Fix for Async Code

## Problem Description

**Severity**: P1 (Critical)
**Location**: `backend-hormonia/app/utils/db_retry.py:63-128`

The `DatabaseCircuitBreaker.call()` method was executing async coroutines but never awaiting them. This caused exceptions to be raised AFTER the coroutine was awaited in the wrapper function, so the circuit breaker never:
- Incremented failure counts
- Opened after threshold failures
- Protected the database from transient errors

This meant transient DB errors would hammer the database unchecked, potentially causing cascade failures.

## Root Cause

```python
# OLD CODE (BROKEN)
def call(self, func: Callable, *args, **kwargs) -> Any:
    try:
        result = func(*args, **kwargs)  # Returns coroutine object, doesn't execute
        # ...
    except Exception as e:  # Never catches async exceptions
        self.failure_count += 1
```

When `func` is an async function, `func(*args, **kwargs)` returns a coroutine object immediately without executing. The actual execution (and exception raising) happens when the coroutine is awaited in the wrapper, which is outside the circuit breaker's try/except block.

## Solution Implemented

### 1. Split Circuit Breaker into Sync and Async Variants

Created two methods:
- `call()` - For synchronous functions
- `acall()` - For asynchronous functions (properly awaits coroutines)

### 2. Refactored Common Logic

Extracted shared logic into helper methods:
- `_check_circuit_state()` - Validates circuit state before operation
- `_record_success()` - Updates state on successful operation
- `_record_failure()` - Increments failure count and opens circuit if needed

### 3. Updated Decorator

Modified `with_db_retry` decorator to use the correct circuit breaker method:
- `async_wrapper` now calls `await db_circuit_breaker.acall(func, ...)`
- `sync_wrapper` continues to call `db_circuit_breaker.call(func, ...)`

## Code Changes

### File: `backend-hormonia/app/utils/db_retry.py`

```python
# NEW CODE (FIXED)
async def acall(self, func: Callable, *args, **kwargs) -> Any:
    """Execute asynchronous function through circuit breaker"""
    self._check_circuit_state()

    try:
        # Properly await the coroutine
        result = await func(*args, **kwargs)
        self._record_success()
        return result

    except Exception as e:
        self._record_failure()
        raise
```

## Testing

Created comprehensive test suite covering:

### Test File 1: `tests/unit/utils/test_db_circuit_breaker.py`

Tests circuit breaker functionality:
- ✅ Sync operations track failures correctly
- ✅ Async operations track failures correctly
- ✅ Circuit opens after threshold failures
- ✅ Circuit transitions to HALF_OPEN after timeout
- ✅ Circuit closes on successful recovery
- ✅ Mixed sync/async operations share state
- ✅ Coroutines are properly awaited

### Test File 2: `tests/unit/utils/test_db_retry_decorator.py`

Tests retry decorator integration:
- ✅ Retry logic with exponential backoff
- ✅ Circuit breaker integration
- ✅ Session rollback on failures
- ✅ IntegrityErrors bypass retry logic
- ✅ Circuit prevents retry attempts when open
- ✅ Function type detection (sync vs async)

## Running the Tests

```bash
# Run circuit breaker tests only
python run_tests.py --quick

# Or run specific test files
python -m pytest tests/unit/utils/test_db_circuit_breaker.py -v
python -m pytest tests/unit/utils/test_db_retry_decorator.py -v
```

## Impact and Benefits

### Before Fix
- ❌ Circuit breaker never tracked async failures
- ❌ Transient DB errors hammered database
- ❌ No protection from cascade failures
- ❌ Circuit always stayed CLOSED for async code

### After Fix
- ✅ Circuit breaker properly tracks async failures
- ✅ Database protected from repeated transient errors
- ✅ Circuit opens after threshold, preventing cascade failures
- ✅ Automatic recovery with HALF_OPEN state
- ✅ Maintains backward compatibility with sync code

## Backward Compatibility

The fix maintains 100% backward compatibility:
- Existing sync code continues to work unchanged
- Existing async code now works correctly (was broken before)
- No API changes required
- Same decorator usage pattern

## Performance Considerations

- Minimal overhead added (helper method calls)
- No additional async/await overhead (was already async)
- Circuit breaker state checks are fast (simple comparisons)
- Memory usage unchanged

## Future Improvements

Potential enhancements (not required for fix):
1. Per-operation circuit breakers (instead of global)
2. Configurable circuit breaker policies per service
3. Circuit breaker metrics export to monitoring
4. Automatic threshold tuning based on error patterns

## Related Files

**Modified:**
- `backend-hormonia/app/utils/db_retry.py`

**Created:**
- `backend-hormonia/tests/unit/utils/test_db_circuit_breaker.py`
- `backend-hormonia/tests/unit/utils/test_db_retry_decorator.py`
- `docs/deployment/P1-2_CIRCUIT_BREAKER_FIX.md` (this file)

## Verification Checklist

- [x] Circuit breaker increments failure counts on async errors
- [x] Circuit breaker opens after threshold failures
- [x] Circuit breaker properly awaits coroutines
- [x] Backward compatibility with sync code maintained
- [x] Comprehensive test coverage added
- [x] Tests pass for both sync and async operations
- [x] Circuit state transitions work correctly
- [x] Session rollback still works
- [x] Documentation created

## Deployment Notes

This fix can be deployed immediately as it:
- Fixes a critical bug (P1)
- Has comprehensive test coverage
- Maintains backward compatibility
- Has no database migrations
- Has no environment variable changes

## Author

Generated by Claude Code - Senior Software Engineer Agent
Date: 2025-10-07
