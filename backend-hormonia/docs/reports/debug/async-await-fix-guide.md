# Async/Await Fix Implementation Guide

**Quick Reference for Fixing All 12 Issues**

---

## Pattern 1: Converting asyncio.run() Calls (Issues #1, #2, #3)

### Problem
```python
# WRONG: Calling asyncio.run() from sync method
def handle_expired_token(self, session_id, patient_id, quiz_template_id):
    return asyncio.run(self._fallback_to_whatsapp(session, patient_id, quiz_template_id))
    # ^ RuntimeError if called from FastAPI async endpoint
```

### Solution A: Make it Async
```python
# RIGHT: Make the entire method async
async def handle_expired_token(self, session_id, patient_id, quiz_template_id):
    # No asyncio.run() needed
    return await self._fallback_to_whatsapp(session, patient_id, quiz_template_id)

# Usage
result = await resilience_service.handle_expired_token(...)
```

### Solution B: Use Safe Wrapper (For Sync Methods)
```python
# RIGHT: Use safe wrapper for sync methods that need async
def handle_expired_token(self, session_id, patient_id, quiz_template_id):
    from app.core.async_context_manager import safe_run_coroutine

    return safe_run_coroutine(
        self._fallback_to_whatsapp(session, patient_id, quiz_template_id),
        timeout=30
    )

# This handles both sync and async contexts correctly
```

### Solution C: Context-Aware Pattern
```python
# RIGHT: Check context and handle appropriately
def handle_expired_token(self, session_id, patient_id, quiz_template_id):
    try:
        loop = asyncio.get_running_loop()
        # We're in async context - can't use asyncio.run()
        # Instead, create a task
        task = loop.create_task(
            self._fallback_to_whatsapp(session, patient_id, quiz_template_id)
        )
        # Return a way for caller to await it
        return task
    except RuntimeError:
        # No running loop - safe to use asyncio.run()
        return asyncio.run(
            self._fallback_to_whatsapp(session, patient_id, quiz_template_id)
        )
```

---

## Pattern 2: Fixing Blocking Sleep (Issues #4, #5)

### Problem
```python
# WRONG: time.sleep() blocks entire event loop
async def process_with_retry(self):
    for attempt in range(3):
        try:
            return await self.do_work()
        except Exception:
            time.sleep(2 ** attempt)  # BLOCKS ENTIRE LOOP!
```

### Solution: Use await asyncio.sleep()
```python
# RIGHT: Use await asyncio.sleep() in async context
async def process_with_retry(self):
    for attempt in range(3):
        try:
            return await self.do_work()
        except Exception:
            await asyncio.sleep(2 ** attempt)  # Non-blocking
            # Other tasks can run now

# For sync context, time.sleep() is OK:
def process_with_retry_sync(self):
    for attempt in range(3):
        try:
            return self.do_work()
        except Exception:
            time.sleep(2 ** attempt)  # OK in sync context
```

### Pattern for Both Sync and Async
```python
# RIGHT: Provide both versions
async def process_with_retry_async(self):
    for attempt in range(3):
        try:
            return await self.do_work()
        except Exception:
            await asyncio.sleep(2 ** attempt)

def process_with_retry_sync(self):
    for attempt in range(3):
        try:
            return self.do_work()
        except Exception:
            time.sleep(2 ** attempt)

# Or make it smart:
async def process_with_retry(self):
    for attempt in range(3):
        try:
            return await self.do_work()
        except Exception:
            delay = 2 ** attempt
            try:
                loop = asyncio.get_running_loop()
                await asyncio.sleep(delay)  # Async context
            except RuntimeError:
                time.sleep(delay)  # Sync context
```

---

## Pattern 3: Fixing Database Operations (Issue #8)

### Problem
```python
# WRONG: Sync DB query in async function
async def send_quiz_link(self, patient_id):
    patient = self.db.query(Patient).filter(...).first()  # BLOCKS!
    # Other async operations paused while database query runs
    quiz_link = await self.monthly_quiz_service.create_quiz_link(...)
```

### Solution: Use AsyncSession
```python
# RIGHT: Use async ORM query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def send_quiz_link(self, patient_id):
    # Use async ORM
    result = await self.db.execute(
        select(Patient).filter(Patient.id == patient_id)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise NotFoundError(f"Patient {patient_id} not found")

    quiz_link = await self.monthly_quiz_service.create_quiz_link(...)
```

### If You Must Use Sync DB
```python
# If you must use sync database:
async def send_quiz_link(self, patient_id):
    loop = asyncio.get_running_loop()

    # Run sync DB operation in thread pool
    patient = await loop.run_in_executor(
        None,  # Use default executor (ThreadPoolExecutor)
        lambda: self.db.query(Patient).filter(...).first()
    )

    # Now continue with async operations
    quiz_link = await self.monthly_quiz_service.create_quiz_link(...)
```

---

## Pattern 4: Fixing Thread Pool Management (Issue #11)

### Problem
```python
# WRONG: Global executor without cleanup
_cache_executor = ThreadPoolExecutor(max_workers=2)

def _run_cache_invalidation(self):
    _cache_executor.submit(_run_in_thread)  # Fire-and-forget - never cleaned up!
```

### Solution: Proper Lifecycle
```python
# RIGHT: Manage lifecycle properly
from contextlib import asynccontextmanager

class PatientCRUDService:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._pending_tasks = set()

    def _run_cache_invalidation(self):
        future = self._executor.submit(self._run_in_thread)

        # Track and remove when done
        def cleanup(f):
            self._pending_tasks.discard(f)

        self._pending_tasks.add(future)
        future.add_done_callback(cleanup)

    async def shutdown(self):
        """Call on app shutdown"""
        # Wait for pending tasks
        for future in list(self._pending_tasks):
            try:
                await asyncio.wait_for(
                    asyncio.wrap_future(future),
                    timeout=5
                )
            except asyncio.TimeoutError:
                logger.warning("Pending task timeout during shutdown")

        # Shutdown executor
        self._executor.shutdown(wait=True)

# Usage in FastAPI lifespan:
@app.on_event("shutdown")
async def shutdown():
    await crud_service.shutdown()
```

---

## Pattern 5: Fixing Cleanup Operations (Issue #7)

### Problem
```python
# WRONG: ensure_future() without waiting
if loop_running:
    async def _safe_close():
        await instance.close()

    asyncio.ensure_future(_safe_close())  # Fires and forgets!
    # Function returns immediately, instance may not be closed yet
```

### Solution: Proper Task Management
```python
# RIGHT: Track task completion
_cleanup_tasks = set()

def reset_cache_layer():
    if not instance:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - safe to use asyncio.run()
        asyncio.run(instance.close())
    else:
        # In async context - create tracked task
        async def _safe_close():
            try:
                await instance.close()
            except Exception as e:
                logger.warning(f"Error during cleanup: {e}")

        task = asyncio.create_task(_safe_close())
        _cleanup_tasks.add(task)
        task.add_done_callback(_cleanup_tasks.discard)

# Ensure cleanup during shutdown:
async def wait_for_cleanup():
    if _cleanup_tasks:
        await asyncio.gather(*_cleanup_tasks, return_exceptions=True)
```

---

## Pattern 6: Fixing Context Detection (Issue #9)

### Problem
```python
# WRONG: Generic except catches the error we're checking for
try:
    asyncio.get_running_loop()
    raise RuntimeError("...")
except RuntimeError:  # Catches the raise above!
    asyncio.run(coro)  # Wrong!
```

### Solution: Specific Error Handling
```python
# RIGHT: Detect if loop is already running
try:
    loop = asyncio.get_running_loop()
    # We ARE in async context
    logger.error("Cannot call asyncio.run() from async context")
    raise RuntimeError(
        "asyncio.run() cannot be used from async context. "
        "Use 'await coro' instead."
    )
except RuntimeError as e:
    if "There is no current event loop" in str(e):
        # Safe to use asyncio.run()
        return asyncio.run(coro)
    elif "asyncio.run() cannot be called" in str(e):
        # Already in async context - re-raise
        raise
    else:
        # Some other error
        raise

# Better approach using try-except asymmetry:
try:
    loop = asyncio.get_running_loop()
    # If we get here, we're in async context
    # Don't call asyncio.run()
    task = loop.create_task(coro)
    return task
except RuntimeError:
    # No running loop - safe for asyncio.run()
    return asyncio.run(coro)
```

---

## Checklist for Fixing Each Issue

### Issue #1: monthly_quiz_message_integration.py:207
- [ ] Make method async: `async def send_quiz_link_message()`
- [ ] Change `asyncio.run()` to `await`
- [ ] Update all callers to await the result
- [ ] Add integration test from async context

### Issue #2-3: link_resilience.py:176-207, 256, 356
- [ ] Convert `handle_expired_token` to async
- [ ] Convert all async methods it calls to be properly awaited
- [ ] Remove all `asyncio.run()` calls
- [ ] Add tests for async/sync context

### Issue #4: backoff.py:173
- [ ] Change `time.sleep()` to be in separate sync method
- [ ] Ensure `await_delay()` is used in async contexts
- [ ] Add docstring clarifying sync vs async usage
- [ ] Add test ensuring no blocking in async code

### Issue #5: dead_letter.py:193
- [ ] Replace thread + sleep with Timer
- [ ] Add cleanup tracking
- [ ] Test graceful shutdown
- [ ] Verify no daemon thread leaks

### Issue #6: quiz_question_humanizer_integration.py:140-144
- [ ] Simplify context detection
- [ ] Add timeout to executor.result()
- [ ] Add error handling for timeout
- [ ] Test from both sync and async contexts

### Issue #7: cache_layer/__init__.py:447, 457
- [ ] Replace `ensure_future()` with `create_task()`
- [ ] Add task tracking
- [ ] Add callback for completion logging
- [ ] Test shutdown cleanup

### Issue #8: monthly_quiz_message_integration.py:70
- [ ] Migrate to AsyncSession
- [ ] Use `select()` for queries
- [ ] Add integration test with real DB
- [ ] Benchmark performance improvement

### Issue #9: celery_app.py:423-425
- [ ] Improve error messages
- [ ] Add specific error type checking
- [ ] Add documentation
- [ ] Test from Celery worker

### Issue #10: docs/data_providers.py:236, 288
- [ ] Add async code examples
- [ ] Mark sync examples clearly
- [ ] Add "correct async pattern" section
- [ ] Add warning about blocking in async

### Issue #11: crud_service.py:38-119
- [ ] Move executor to instance variable
- [ ] Add task tracking
- [ ] Implement cleanup method
- [ ] Call cleanup on app shutdown

### Issue #12: async_context_manager.py:177
- [ ] Add documentation comments
- [ ] Consider renaming for clarity
- [ ] Add type hints
- [ ] Add tests

---

## Testing Each Fix

### Test Template
```python
import asyncio
import pytest
from unittest.mock import AsyncMock, Mock

class TestAsyncAwaitFix:
    """Test async/await fixes"""

    @pytest.mark.asyncio
    async def test_no_asyncio_run_in_async_context(self):
        """Verify asyncio.run() raises when called from async"""
        async def test_func():
            # This should raise RuntimeError
            with pytest.raises(RuntimeError, match="asyncio.run"):
                asyncio.run(asyncio.sleep(0))

        await test_func()

    @pytest.mark.asyncio
    async def test_blocking_sleep_detected(self):
        """Verify time.sleep() blocks event loop"""
        import time

        async def other_task():
            await asyncio.sleep(0.05)
            return "completed"

        # If blocking sleep is used, other_task will be delayed
        async def blocking_func():
            time.sleep(0.1)  # Should be detected

        start = asyncio.get_event_loop().time()
        await asyncio.gather(
            blocking_func(),
            other_task()
        )
        elapsed = asyncio.get_event_loop().time() - start

        # Should be ~0.15s (sequential due to blocking)
        # Not ~0.05s (parallel)
        assert elapsed > 0.1

    def test_asyncio_run_safe_in_sync(self):
        """Verify asyncio.run() works in sync context"""
        async def async_func():
            return "result"

        result = asyncio.run(async_func())
        assert result == "result"

    @pytest.mark.asyncio
    async def test_await_asyncio_sleep_nonblocking(self):
        """Verify await asyncio.sleep() doesn't block other tasks"""
        import time

        async def sleeper():
            await asyncio.sleep(0.1)
            return "done"

        async def fast_task():
            await asyncio.sleep(0.01)
            return "quick"

        start = asyncio.get_event_loop().time()
        results = await asyncio.gather(sleeper(), fast_task())
        elapsed = asyncio.get_event_loop().time() - start

        assert results == ["done", "quick"]
        # Both run concurrently, should be ~0.1s not ~0.11s
        assert elapsed < 0.12
```

---

## Gradual Implementation Plan

### Phase 1: Critical Path (Week 1)
1. Fix Issue #2 (link_resilience.py - affects quiz delivery)
2. Fix Issue #4 (backoff.py - deadlock prevention)
3. Fix Issue #5 (dead_letter.py - thread safety)

### Phase 2: High Impact (Week 2)
1. Fix Issue #1 (quiz message integration)
2. Fix Issue #6 (humanizer integration)
3. Fix Issue #8 (database operations)

### Phase 3: Code Quality (Week 3)
1. Fix Issue #7 (cleanup operations)
2. Fix Issue #11 (thread pool lifecycle)
3. Fix Issue #9 (error messages)

### Phase 4: Documentation (Week 4)
1. Fix Issue #10 (documentation examples)
2. Fix Issue #12 (pattern clarity)
3. Add async/await audit to CI

---

## Verification Commands

```bash
# Check for asyncio.run() in async functions
grep -r "async def" --include="*.py" app/ | \
  while read line; do
    file=$(echo "$line" | cut -d: -f1)
    grep -q "asyncio\.run" "$file" && echo "$file has asyncio.run()"
  done

# Check for time.sleep() in async functions
grep -B5 "time\.sleep" --include="*.py" app/ | grep -B5 "async def"

# Check for missing await on coroutines
grep -r "\.result()\|\.done()\|\.cancelled()" --include="*.py" app/ | grep -v "# " | grep -v test

# Verify ThreadPoolExecutor cleanup
grep -r "ThreadPoolExecutor" --include="*.py" app/ | grep -v "shutdown"
```

---

## References

- [asyncio best practices](https://docs.python.org/3/library/asyncio-dev.html)
- [Event loop management](https://docs.python.org/3/library/asyncio-eventloop.html)
- [SQLAlchemy async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [FastAPI async docs](https://fastapi.tiangolo.com/async/)

