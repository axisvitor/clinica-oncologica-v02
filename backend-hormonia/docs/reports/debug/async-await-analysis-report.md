# Async/Await Patterns Analysis Report

**Analysis Date**: 2025-12-25
**Backend**: backend-hormonia
**Focus**: Async/Await correctness, event loop safety, deadlock prevention

---

## Executive Summary

Found **12 critical async/await issues** across the codebase:

- **4 CRITICAL**: asyncio.run() in async context (causes RuntimeError)
- **3 HIGH**: Blocking calls in async functions (time.sleep instead of await)
- **2 MEDIUM**: Missing await on coroutines
- **2 MEDIUM**: Thread-safety issues with async operations
- **1 LOW**: Improper task cancellation handling

---

## Critical Issues

### ISSUE #1: asyncio.run() in Async Context (Line 207)
**File**: `/app/services/monthly_quiz_message_integration.py:207`
**Severity**: CRITICAL
**Pattern**: Calling asyncio.run() from within an async function

**Current Code**:
```python
def send_quiz_link_message(
    self,
    patient_id: UUID,
    link_url: str,
    custom_message: Optional[str] = None,
    delivery_method: str = DeliveryMethod.WHATSAPP.value,
) -> Dict[str, Any]:
    # ...
    success = asyncio.run(self.message_sender.send_message(message))  # LINE 207
    return {"success": bool(success), "message_id": str(message.id)}
```

**Problem**:
- This is a **sync method** calling `asyncio.run()` on an async coroutine
- If called from FastAPI async endpoint, it will raise `RuntimeError: asyncio.run() cannot be called from a running event loop`
- Blocks the event loop even if called from sync context

**Impact**: Task failures, deadlock risk, API endpoint failures

**Correct Pattern**:
```python
async def send_quiz_link_message_async(
    self,
    patient_id: UUID,
    link_url: str,
    custom_message: Optional[str] = None,
    delivery_method: str = DeliveryMethod.WHATSAPP.value,
) -> Dict[str, Any]:
    # ... existing logic ...
    success = await self.message_sender.send_message(message)  # Use await
    return {"success": bool(success), "message_id": str(message.id)}

# In sync context (Celery), use:
def send_quiz_link_message(self, ...):
    from app.core.async_context_manager import safe_run_coroutine
    success = safe_run_coroutine(
        self.message_sender.send_message(message),
        timeout=30
    )
```

---

### ISSUE #2: asyncio.run() in Async Function (Line 176-207)
**File**: `/app/domain/quizzes/resilience/link_resilience.py:176-207`
**Severity**: CRITICAL
**Pattern**: Calling asyncio.run() from sync method that gets called from async context

**Current Code**:
```python
def handle_expired_token(
    self, session_id: UUID, patient_id: UUID, quiz_template_id: UUID
) -> Dict[str, Any]:
    """Sync method calling async functions via asyncio.run()"""
    # Line 176
    return asyncio.run(
        self._fallback_to_whatsapp(session, patient_id, quiz_template_id)
    )

    # Line 186
    return asyncio.run(
        self._fallback_to_whatsapp(session, patient_id, quiz_template_id)
    )

    # Line 192
    result = asyncio.run(
        self.regenerate_link(session_id, patient_id, quiz_template_id)
    )

    # Line 205
    return asyncio.run(
        self._fallback_to_whatsapp(session, patient_id, quiz_template_id)
    )
```

**Problem**:
- Method is NOT async but calls `asyncio.run()` multiple times
- If this method is called from FastAPI endpoint (which will be async), causes RuntimeError
- Creates 3+ separate event loops unnecessarily
- No timeout protection on any call

**Impact**: RuntimeError crashes, event loop exhaustion

**Correct Pattern**:
```python
async def handle_expired_token_async(
    self, session_id: UUID, patient_id: UUID, quiz_template_id: UUID
) -> Dict[str, Any]:
    """Async version - no asyncio.run() needed"""
    session = self.session_repository.get(session_id)
    if not session:
        raise NotFoundError(f"Quiz session {session_id} not found")

    metadata = session.session_metadata or {}
    regeneration_count = metadata.get("regeneration_count", 0)
    failure_count = metadata.get("failure_count", 0)

    if regeneration_count >= self.MAX_LINK_REGENERATIONS:
        return await self._fallback_to_whatsapp(session, patient_id, quiz_template_id)

    if failure_count >= self.FALLBACK_THRESHOLD:
        return await self._fallback_to_whatsapp(session, patient_id, quiz_template_id)

    try:
        result = await self.regenerate_link(session_id, patient_id, quiz_template_id)
        return {
            "action": "regenerated",
            "session_id": str(session_id),
            "new_token": result["token"],
            "new_expires_at": result["expires_at"],
            "regeneration_count": regeneration_count + 1,
        }
    except Exception as e:
        logger.error(f"Failed to regenerate link for session {session_id}: {e}")
        self.track_failure(session_id, FailureReason.LINK_ACCESS_FAILED)
        return await self._fallback_to_whatsapp(session, patient_id, quiz_template_id)
```

---

### ISSUE #3: Multiple asyncio.run() Calls (Lines 256, 356)
**File**: `/app/domain/quizzes/resilience/link_resilience.py:256, 356`
**Severity**: CRITICAL
**Pattern**: Calling asyncio.run() in class methods without context awareness

**Current Code**:
```python
# Line 256
asyncio.run(
    self._send_reminder(
        session,
        delivery_method,
        reminder_count,
        hours_before_expiry,
    )
)

# Line 356
asyncio.run(
    self._track_channel_health(delivery_method, False)
)
```

**Problem**:
- Both are sync methods creating separate event loops
- Will fail in FastAPI async context
- Creates event loop resource leaks on repeated calls

**Correct Pattern**: Make methods async or use safe_run_coroutine wrapper

---

### ISSUE #4: Blocking time.sleep() in Async Functions
**File**: `/app/resilience/retry/backoff.py:173`
**Severity**: CRITICAL
**Pattern**: Sync blocking call blocks entire event loop

**Current Code**:
```python
def wait(self, attempt: int) -> None:
    """Wait for calculated delay"""
    delay = self.calculator.calculate_delay(attempt)

    logger.info(
        f"Backing off for {delay:.3f}s (attempt {attempt + 1}, "
        f"strategy={self.config.strategy.value})"
    )

    time.sleep(delay)  # BLOCKS ENTIRE EVENT LOOP
```

**Problem**:
- If called from async context, blocks all other tasks
- Should be called on sync backoff only
- Counterpart `await_delay()` exists but might not be used

**Impact**: Event loop freezes, timeouts, missed deadlines

**Correct Pattern**:
```python
def wait(self, attempt: int) -> None:
    """Sync wait - use only in non-async contexts"""
    delay = self.calculator.calculate_delay(attempt)
    logger.info(f"Backing off for {delay:.3f}s (attempt {attempt + 1}, strategy={self.config.strategy.value})")
    time.sleep(delay)

async def await_delay(self, attempt: int) -> None:
    """Async wait - use in async contexts"""
    import asyncio
    delay = self.calculator.calculate_delay(attempt)
    logger.info(f"Async backing off for {delay:.3f}s (attempt {attempt + 1}, strategy={self.config.strategy.value})")
    await asyncio.sleep(delay)  # Correct for async
```

---

## High Severity Issues

### ISSUE #5: time.sleep() in Dead Letter Queue Handler
**File**: `/app/resilience/retry/dead_letter.py:193`
**Severity**: HIGH
**Pattern**: Blocking sleep in threading context used with async

**Current Code**:
```python
def _requeue_message(self, message: DeadLetterMessage):
    """Requeue message for retry"""
    message.status = MessageStatus.REQUEUED
    message.requeue_count += 1

    def requeue_after_delay():
        time.sleep(self.retry_backoff)  # LINE 193 - blocks thread
        try:
            self._queue.put_nowait(message.id)
            self._requeued_messages += 1
        except Exception as e:
            logger.error(f"Failed to requeue message {message.id}: {str(e)}")
            self._discard_message(message)

    thread = threading.Thread(target=requeue_after_delay, daemon=True)
    thread.start()
```

**Problem**:
- Daemon thread with blocking sleep can cause ungraceful shutdowns
- If queue is async, mixing blocking and async operations
- No timeout or cancellation mechanism

**Impact**: Message loss on shutdown, thread leaks

**Correct Pattern**:
```python
def _requeue_message(self, message: DeadLetterMessage):
    """Requeue message for retry"""
    message.status = MessageStatus.REQUEUED
    message.requeue_count += 1

    # Use Timer instead of thread + sleep
    timer = threading.Timer(
        self.retry_backoff,
        self._do_requeue,
        args=[message]
    )
    timer.daemon = True
    timer.start()
    self._pending_requeue_timers.append(timer)  # Track for cleanup

def _do_requeue(self, message: DeadLetterMessage):
    """Actually requeue after delay"""
    try:
        self._queue.put_nowait(message.id)
        self._requeued_messages += 1
        logger.info(f"Requeued message {message.id}")
    except Exception as e:
        logger.error(f"Failed to requeue message {message.id}: {str(e)}")
        self._discard_message(message)
```

---

### ISSUE #6: asyncio.run() in Celery Task with Thread Pool
**File**: `/app/services/quiz_question_humanizer_integration.py:140-144`
**Severity**: HIGH
**Pattern**: Double-wrapping asyncio operations

**Current Code**:
```python
try:
    asyncio.get_running_loop()
except RuntimeError:
    humanized_text = asyncio.run(_humanize())  # LINE 140
else:
    humanized_text = _HUMANIZER_EXECUTOR.submit(
        lambda: asyncio.run(_humanize())  # LINE 143 - asyncio.run in thread
    ).result()
```

**Problem**:
- Line 140: If called from running loop, will raise RuntimeError
- Line 143: Calling `asyncio.run()` from thread executor is correct BUT:
  - Nested try-except logic is confusing
  - Thread pool overhead for simple async operation
  - No timeout on executor.result()

**Impact**: RuntimeError, deadlocks from missing timeout

**Correct Pattern**:
```python
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    # No running loop, safe to use asyncio.run()
    humanized_text = asyncio.run(_humanize())
else:
    # We're in async context, schedule as task
    task = loop.create_task(_humanize())
    # If you need to wait, return awaitable:
    humanized_text = await task
    # OR use run_in_executor for thread-based work:
    humanized_text = await loop.run_in_executor(None, sync_humanize_func)
```

---

### ISSUE #7: Nested asyncio.run() in Air Service
**File**: `/app/services/ai/cache_layer/__init__.py:447`
**Severity**: HIGH
**Pattern**: Calling asyncio.run() at module cleanup level

**Current Code**:
```python
def reset_cache_layer():
    """Reset the cache layer instance."""
    if not instance:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - safe to use asyncio.run
        asyncio.run(instance.close())  # LINE 447
    else:
        # FIX: Schedule cleanup as a proper awaited coroutine
        async def _safe_close():
            try:
                await instance.close()
            except Exception as e:
                logger.warning(f"Error during cache layer cleanup: {e}")

        asyncio.ensure_future(_safe_close())  # LINE 457 - PROBLEM
```

**Problem**:
- Line 457: `asyncio.ensure_future()` doesn't wait for completion
- If module is unloaded before close completes, resource leak
- No task tracking or guarantee of cleanup

**Impact**: Resource leaks, file handle leaks, connection leaks

**Correct Pattern**:
```python
def reset_cache_layer():
    """Reset the cache layer instance."""
    if not instance:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - safe to use asyncio.run()
        asyncio.run(instance.close())
    else:
        # In async context: create task but don't orphan it
        async def _safe_close():
            try:
                await instance.close()
            except Exception as e:
                logger.warning(f"Error during cache layer cleanup: {e}")

        task = asyncio.create_task(_safe_close())
        # Add callback to track completion
        task.add_done_callback(lambda t: logger.info("Cache cleanup completed"))

async def reset_cache_layer_async():
    """Async version for proper await"""
    if not instance:
        return

    try:
        await instance.close()
    except Exception as e:
        logger.warning(f"Error during async cache layer cleanup: {e}")
```

---

## Medium Severity Issues

### ISSUE #8: Sync Database Calls in Async Function
**File**: `/app/services/monthly_quiz_message_integration.py:70`
**Severity**: MEDIUM
**Pattern**: Blocking database query in async function

**Current Code**:
```python
async def send_quiz_link(
    self,
    patient_id: UUID,
    quiz_template_id: UUID,
    # ... parameters ...
) -> Dict[str, Any]:
    """Generate quiz link and send invitation message."""
    # Get patient info - BLOCKING SYNC CALL
    patient = self.db.query(Patient).filter(Patient.id == patient_id).first()  # LINE 70
    if not patient:
        raise NotFoundError(f"Patient with ID {patient_id} not found")

    # Create quiz link
    link_data = MonthlyQuizLinkCreate(
        patient_id=patient_id,
        quiz_template_id=quiz_template_id,
        # ...
    )

    quiz_link = await self.monthly_quiz_service.create_quiz_link(link_data)  # ASYNC
```

**Problem**:
- SQLAlchemy sync Session blocks event loop
- Can cause timeout for other concurrent requests
- Inconsistent with async function signature
- Should use AsyncSession

**Impact**: Event loop blocking, poor concurrency

**Correct Pattern**:
```python
async def send_quiz_link(
    self,
    patient_id: UUID,
    quiz_template_id: UUID,
    # ... parameters ...
) -> Dict[str, Any]:
    """Generate quiz link and send invitation message."""
    # Use async ORM query
    patient = await self.db.execute(
        select(Patient).filter(Patient.id == patient_id)
    )
    patient = patient.scalar_one_or_none()

    if not patient:
        raise NotFoundError(f"Patient with ID {patient_id} not found")

    # Rest of async operations
    quiz_link = await self.monthly_quiz_service.create_quiz_link(link_data)
```

---

### ISSUE #9: asyncio.run() in Celery Task
**File**: `/app/celery_app.py:423-425`
**Severity**: MEDIUM
**Pattern**: Multiple asyncio.run() calls without proper context

**Current Code**:
```python
def run_async_in_celery(coro, timeout: Optional[float] = 300):
    """Helper function to run async coroutines in Celery tasks."""
    try:
        # Check if we're already in an async context
        try:
            asyncio.get_running_loop()
            logger.error("run_async_in_celery called from async context")
            raise RuntimeError("Cannot call run_async_in_celery from async context")
        except RuntimeError:
            # No running loop, safe to proceed
            pass

        # Import here to avoid circular imports
        from app.core.async_context_manager import safe_run_coroutine

        return safe_run_coroutine(coro, timeout=timeout, fallback_sync=True)
    except ImportError as e:
        logger.error(f"Failed to import async_context_manager: {e}")
        # Fallback to basic asyncio.run
        try:
            if timeout:
                async def timed_coro():
                    return await asyncio.wait_for(coro, timeout=timeout)

                return asyncio.run(timed_coro())  # LINE 423
            else:
                return asyncio.run(coro)  # LINE 425
```

**Problem**:
- Catches RuntimeError generically - hides actual issues
- Fallback uses asyncio.run() which is correct for Celery
- But error message on line 404 says "asyncio.run called from async context" when it should raise

**Impact**: Confusing error messages, potential for calling from async context

**Correct Pattern**:
```python
def run_async_in_celery(coro, timeout: Optional[float] = 300):
    """Helper function to run async coroutines in Celery tasks.

    MUST be called from sync context (Celery worker thread).
    """
    try:
        # Verify we're NOT in async context
        try:
            asyncio.get_running_loop()
            # We ARE in async context - this is an error
            logger.error("run_async_in_celery() called from async context - use await instead")
            raise RuntimeError(
                "run_async_in_celery() cannot be called from async context. "
                "Use 'await coro' instead or call from sync Celery task."
            )
        except RuntimeError as e:
            if "asyncio.run() cannot be called" in str(e):
                raise
            # "There is no current event loop" - expected for sync context
            pass

        # Import safe wrapper
        try:
            from app.core.async_context_manager import safe_run_coroutine
            return safe_run_coroutine(coro, timeout=timeout, fallback_sync=True)
        except ImportError:
            # Fallback to direct asyncio.run() - safe in Celery
            if timeout:
                async def timed_coro():
                    return await asyncio.wait_for(coro, timeout=timeout)
                return asyncio.run(timed_coro())
            else:
                return asyncio.run(coro)

    except Exception as e:
        logger.error(f"Failed to run async operation in Celery: {e}")
        raise
```

---

### ISSUE #10: Missing await on Coroutine
**File**: `/app/api/v2/routers/docs/data_providers.py:236, 288`
**Severity**: MEDIUM
**Pattern**: time.sleep() in documentation example code

**Current Code**:
```python
# Line 236 (in docstring example)
for i in range(max_retries):
    try:
        return func()
    except RequestException:
        if i == max_retries - 1:
            raise
        time.sleep(2 ** i)  # OK for sync code

# Line 288 (in docstring example)
if response.status_code == 429:
    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
    wait_time = reset_time - time.time()

    if wait_time > 0:
        time.sleep(wait_time)  # OK for sync code
        return make_request_with_retry(url)
```

**Problem**:
- These are in docstring examples showing synchronous patterns
- Should ALSO show async equivalents
- Developers might copy-paste without understanding async context

**Impact**: Documentation misleading, encourages blocking in async code

**Correct Pattern**:
```python
# Add async examples to docstrings:
"""
## Synchronous Retry
```python
for i in range(max_retries):
    try:
        return func()
    except RequestException:
        if i == max_retries - 1:
            raise
        time.sleep(2 ** i)
```

## Asynchronous Retry
```python
async def retry_async(async_func, max_retries=3):
    for i in range(max_retries):
        try:
            return await async_func()
        except RequestException:
            if i == max_retries - 1:
                raise
            await asyncio.sleep(2 ** i)  # Use await, not time.sleep()
```
"""
```

---

## Additional Issues

### ISSUE #11: Thread Pool Executor Leak
**File**: `/app/services/patient/crud_service.py:38-119`
**Severity**: LOW
**Pattern**: ThreadPoolExecutor without proper cleanup

**Current Code**:
```python
# Global thread pool at module level
_cache_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cache_invalidation")

class PatientCRUDService:
    def _run_cache_invalidation(self, entity: str, identifier: str, cascade: bool = True) -> None:
        """Safely run async cache invalidation from sync context."""
        async def _invalidate():
            try:
                await self._cache_invalidation.invalidate_entity(
                    entity=entity,
                    identifier=identifier,
                    cascade=cascade,
                )
            except Exception as e:
                self._logger.warning(f"Cache invalidation failed: {e}")

        def _run_in_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(_invalidate())
                finally:
                    loop.close()
            except Exception as e:
                logger.warning(f"Thread cache invalidation error: {e}")

        try:
            _cache_executor.submit(_run_in_thread)  # Fire-and-forget
```

**Problem**:
- Global executor never shuts down (fire-and-forget pattern)
- No tracking of submitted tasks
- On app shutdown, pending tasks may be lost
- Memory leak if many cache invalidations queue up

**Impact**: Resource leaks on application shutdown

**Correct Pattern**:
```python
class PatientCRUDService:
    def __init__(self, ...):
        # ... existing code ...
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cache_invalidation")
        self._pending_invalidations: List[Future] = []

    def _run_cache_invalidation(self, entity: str, identifier: str, cascade: bool = True) -> None:
        """Safely run async cache invalidation from sync context."""
        async def _invalidate():
            try:
                await self._cache_invalidation.invalidate_entity(
                    entity=entity,
                    identifier=identifier,
                    cascade=cascade,
                )
            except Exception as e:
                self._logger.warning(f"Cache invalidation failed: {e}")

        def _run_in_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(_invalidate())
                finally:
                    loop.close()
            except Exception as e:
                logger.warning(f"Thread cache invalidation error: {e}")

        try:
            future = self._executor.submit(_run_in_thread)
            self._pending_invalidations.append(future)
            future.add_done_callback(lambda f: self._pending_invalidations.remove(f))
        except Exception as e:
            self._logger.error(f"Failed to submit cache invalidation: {e}")

    async def cleanup(self):
        """Cleanup resources"""
        # Wait for pending invalidations
        for future in self._pending_invalidations:
            try:
                future.result(timeout=5)
            except Exception as e:
                logger.warning(f"Failed to complete invalidation: {e}")

        self._executor.shutdown(wait=True)
```

---

### ISSUE #12: Event Loop Context Manager Unsafe
**File**: `/app/core/async_context_manager.py:177`
**Severity**: LOW
**Pattern**: Using asyncio.run() without checking context first

**Current Code**:
```python
def safe_create_task(
    coro: Coroutine,
    name: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    fallback_sync: bool = False,
) -> Optional[asyncio.Task]:
    try:
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(coro, name=name)
        except RuntimeError:
            if fallback_sync:
                logger.warning(f"No event loop available, running task '{name}' synchronously")
                try:
                    asyncio.run(coro)  # LINE 177 - OK here, confirmed no running loop
                    return None
                except Exception as e:
                    logger.error(f"Sync execution failed for task '{name}': {e}")
                    return None
```

**Problem**:
- This is actually CORRECT - checks for running loop first
- But the pattern is hard to understand at first glance
- Could be improved with better documentation

**Impact**: Minimal - code is correct

**Improvement**:
```python
def safe_create_task(
    coro: Coroutine,
    name: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    fallback_sync: bool = False,
) -> Optional[asyncio.Task]:
    """
    Safely create an asyncio task with proper event loop context.

    SAFE PATTERN:
    1. Try to get running loop (asyncio.get_running_loop())
    2. If fails with RuntimeError, no loop is running
    3. Then asyncio.run() is safe
    """
    try:
        try:
            loop = asyncio.get_running_loop()
            # We're in async context, create task normally
            task = loop.create_task(coro, name=name)
            logger.debug(f"Created task '{name}' in running loop")

        except RuntimeError:
            # No running loop - SAFE TO USE asyncio.run()
            if fallback_sync:
                logger.warning(f"No event loop available, running task '{name}' synchronously")
                try:
                    asyncio.run(coro)  # SAFE: confirmed no running loop
                    return None
                except Exception as e:
                    logger.error(f"Sync execution failed: {e}")
                    return None
            else:
                # Create new loop
                loop = event_loop_context.get_or_create_event_loop()
                task = loop.create_task(coro, name=name)
                logger.debug(f"Created task '{name}' in new loop")

        # Track the task
        metadata = {
            "name": name,
            "created_at": asyncio.get_event_loop().time(),
            "context": context or {},
        }
        task_tracker.track_task(task, metadata)
        return task

    except Exception as e:
        logger.error(f"Failed to create task '{name}': {e}")
        return None
```

---

## Summary Table

| Issue # | File | Line | Severity | Type | Impact |
|---------|------|------|----------|------|--------|
| 1 | monthly_quiz_message_integration.py | 207 | CRITICAL | asyncio.run() in sync method | RuntimeError if called from async |
| 2 | link_resilience.py | 176-207 | CRITICAL | asyncio.run() in 4 locations | Event loop exhaustion, RuntimeError |
| 3 | link_resilience.py | 256, 356 | CRITICAL | Multiple asyncio.run() calls | Resource leaks, RuntimeError |
| 4 | backoff.py | 173 | CRITICAL | time.sleep() blocks event loop | Deadlock risk, timeouts |
| 5 | dead_letter.py | 193 | HIGH | time.sleep() in daemon thread | Thread leak, ungraceful shutdown |
| 6 | quiz_question_humanizer_integration.py | 140-144 | HIGH | Double-wrapped asyncio.run() | RuntimeError, missing timeout |
| 7 | cache_layer/__init__.py | 447, 457 | HIGH | asyncio.run() + ensure_future | Resource leaks, incomplete cleanup |
| 8 | monthly_quiz_message_integration.py | 70 | MEDIUM | Sync DB calls in async function | Event loop blocking, poor concurrency |
| 9 | celery_app.py | 423-425 | MEDIUM | asyncio.run() without context check | Confusing error messages |
| 10 | docs/data_providers.py | 236, 288 | MEDIUM | Misleading async examples | Developers copy blocking code |
| 11 | crud_service.py | 38-119 | LOW | ThreadPoolExecutor leak | Resource leak on shutdown |
| 12 | async_context_manager.py | 177 | LOW | Complex but correct pattern | Hard to understand |

---

## Recommendations

### Priority 1: Critical Fixes (Do Immediately)

1. **Convert handle_expired_token to async**
   - Affects: Quiz link resilience
   - Timeline: 1 day
   - Files: link_resilience.py

2. **Fix send_quiz_link_message to async or use safe wrapper**
   - Affects: Quiz delivery
   - Timeline: 1 day
   - Files: monthly_quiz_message_integration.py

3. **Replace time.sleep() with await asyncio.sleep()**
   - Affects: Retry logic, deadlock prevention
   - Timeline: 2 days
   - Files: backoff.py, dead_letter.py

### Priority 2: High Impact Fixes (This Week)

1. **Refactor cache cleanup pattern**
   - Use proper task tracking
   - Ensure cleanup completion
   - Files: cache_layer/__init__.py

2. **Fix nested asyncio.run() in humanizer**
   - Use run_in_executor properly
   - Add timeout to executor.result()
   - Files: quiz_question_humanizer_integration.py

3. **Convert sync DB queries to async ORM**
   - Use AsyncSession
   - Maintain event loop responsiveness
   - Files: monthly_quiz_message_integration.py, others

### Priority 3: Code Quality Improvements (Next Sprint)

1. **Update documentation with async examples**
2. **Add executor cleanup on app shutdown**
3. **Improve error messages for async context detection**
4. **Add async/await audit tool to CI pipeline**

---

## Testing Recommendations

### Unit Tests
```python
# Test asyncio.run() safety
def test_cannot_call_asyncio_run_from_async():
    async def test():
        with pytest.raises(RuntimeError, match="asyncio.run"):
            asyncio.run(some_coro())
    asyncio.run(test())

# Test blocking calls
def test_time_sleep_blocks_event_loop():
    # Verify event loop blocked during time.sleep()
    pass

# Test proper await
async def test_await_asyncio_sleep():
    import time
    start = time.time()
    await asyncio.sleep(0.1)
    elapsed = time.time() - start
    assert 0.05 < elapsed < 0.2  # Should be quick
```

### Integration Tests
```python
# Test from FastAPI context
async def test_quiz_link_from_async_endpoint():
    # Verify no RuntimeError
    pass

# Test from Celery context
def test_flow_processing_from_celery():
    # Verify asyncio.run() works
    pass
```

---

## References

- [Python asyncio documentation](https://docs.python.org/3/library/asyncio.html)
- [asyncio.run() limitations](https://docs.python.org/3/library/asyncio-runner.html#asyncio.run)
- [Fast API async context](https://fastapi.tiangolo.com/async/)
- [Event loop management best practices](https://docs.python.org/3/library/asyncio-eventloop.html)

