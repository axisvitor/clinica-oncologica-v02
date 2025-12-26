# Async/Await Quick Reference Card

## The Golden Rules

1. **NEVER call `asyncio.run()` from async context**
   - Will raise: `RuntimeError: asyncio.run() cannot be called from a running event loop`

2. **NEVER use `time.sleep()` in async functions**
   - Blocks entire event loop
   - Use: `await asyncio.sleep()` instead

3. **ALWAYS `await` coroutines**
   - Forgetting `await` returns unawaited coroutine (memory leak)

4. **ALWAYS close threads/executors properly**
   - Use shutdown() or context managers

---

## Quick Diagnosis Table

| Symptom | Cause | Fix |
|---------|-------|-----|
| `RuntimeError: asyncio.run()` | Called from async context | Use `await` or `create_task()` |
| Event loop freezes/hangs | `time.sleep()` in async | Use `await asyncio.sleep()` |
| Unawaited coroutine warning | Missing `await` keyword | Add `await` before coroutine call |
| Tasks not completing | `ensure_future()` not tracked | Use `create_task()` with tracking |
| Threads never finish | No executor.shutdown() | Add shutdown on app cleanup |
| Database slow in async | Sync Session blocks loop | Use AsyncSession with await |
| Resource leak on shutdown | Fire-and-forget tasks | Track and await all tasks |

---

## Pattern Recognition

### Pattern 1: asyncio.run() Error
```python
# WRONG
async def send_message(self, msg):
    return asyncio.run(self.service.send(msg))
    # RuntimeError! ❌

# RIGHT
async def send_message(self, msg):
    return await self.service.send(msg)  # ✓
```

### Pattern 2: Blocking Sleep
```python
# WRONG
async def retry_logic(self):
    for attempt in range(3):
        try:
            await self.do_work()
        except:
            time.sleep(2)  # Blocks! ❌

# RIGHT
async def retry_logic(self):
    for attempt in range(3):
        try:
            await self.do_work()
        except:
            await asyncio.sleep(2)  # ✓
```

### Pattern 3: Missing Await
```python
# WRONG
result = self.async_function()  # Returns unawaited coroutine! ❌

# RIGHT
result = await self.async_function()  # ✓
```

### Pattern 4: Sync Database
```python
# WRONG
async def get_patient(self, patient_id):
    return self.db.query(Patient).filter(...).first()  # Blocks! ❌

# RIGHT (with AsyncSession)
async def get_patient(self, patient_id):
    result = await self.db.execute(
        select(Patient).filter(...)
    )
    return result.scalar_one_or_none()  # ✓

# RIGHT (without AsyncSession)
async def get_patient(self, patient_id):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: self.db.query(Patient).filter(...).first()
    )  # ✓
```

### Pattern 5: Context Detection
```python
# WRONG
try:
    asyncio.run(coro)
except RuntimeError:
    pass  # Silently fails! ❌

# RIGHT
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    # No running loop - safe for asyncio.run()
    return asyncio.run(coro)  # ✓
else:
    # Already in async context
    return await coro  # ✓
```

---

## Decision Tree

```
Is your code async or sync?

├─ ASYNC (async def)
│  ├─ Need to call async function?
│  │  └─ USE: await function()  ✓
│  ├─ Need to wait (sleep)?
│  │  └─ USE: await asyncio.sleep(seconds)  ✓
│  ├─ Need to call sync function that takes time?
│  │  └─ USE: await loop.run_in_executor(None, func)  ✓
│  └─ Calling from FastAPI/aiohttp?
│     └─ NO asyncio.run()! Use await instead  ✓
│
├─ SYNC (regular def)
│  ├─ Need to call async function?
│  │  ├─ From Celery worker?
│  │  │  └─ USE: asyncio.run(async_func())  ✓
│  │  ├─ From Flask/sync endpoint?
│  │  │  └─ USE: asyncio.run(async_func())  ✓
│  │  └─ Unsure of context?
│  │     └─ USE: safe_run_coroutine(coro, timeout=30)  ✓
│  ├─ Need to wait (sleep)?
│  │  └─ USE: time.sleep(seconds)  ✓
│  └─ Need background task?
│     └─ USE: threading.Thread() or ThreadPoolExecutor  ✓
│
└─ MIXED (call sync from async or vice versa)
   ├─ Sync function to async function?
   │  └─ Check context + use safe wrapper  ✓
   ├─ Async function to sync function?
   │  └─ Call sync directly (no special handling needed)  ✓
   └─ Run in thread pool?
      └─ USE: loop.run_in_executor(executor, func)  ✓
```

---

## Common Errors and Fixes

### Error 1: RuntimeError: asyncio.run() cannot be called
```python
# Context: Calling from async endpoint
# File: app/services/monthly_quiz_message_integration.py:207

# BEFORE (causes error)
def send_quiz_link_message(self, patient_id, link_url):
    success = asyncio.run(self.message_sender.send_message(message))
    # If called from FastAPI async endpoint: RuntimeError!

# AFTER (fixed)
async def send_quiz_link_message(self, patient_id, link_url):
    success = await self.message_sender.send_message(message)
    # Correct async pattern
```

### Error 2: Task is not awaited (memory leak)
```python
# Context: Forgot await on async call
# File: app/services/...

# BEFORE (causes warning)
task = coro_function()  # Returns unawaited coroutine

# AFTER (fixed)
task = await coro_function()
# OR explicitly create task:
task = asyncio.create_task(coro_function())
```

### Error 3: Event loop blocked (hangs/freezes)
```python
# Context: time.sleep() in async function
# File: app/resilience/retry/backoff.py:173

# BEFORE (blocks loop)
async def process_with_backoff(self, attempt):
    time.sleep(2 ** attempt)  # Entire loop frozen!
    return await self.do_work()

# AFTER (fixed)
async def process_with_backoff(self, attempt):
    await asyncio.sleep(2 ** attempt)  # Non-blocking
    return await self.do_work()
```

---

## Checklist Before Committing

- [ ] No `asyncio.run()` in async functions
- [ ] No `time.sleep()` in async functions
- [ ] All `await` keywords present on coroutine calls
- [ ] All background tasks tracked/awaited on shutdown
- [ ] All executors have `shutdown()` call
- [ ] Database operations use AsyncSession or loop.run_in_executor()
- [ ] Context properly detected (try get_running_loop)
- [ ] Timeouts added to blocking operations
- [ ] Test added for async context
- [ ] Test added for sync context

---

## File Locations of Issues

| Priority | File | Line | Issue |
|----------|------|------|-------|
| CRITICAL | link_resilience.py | 176-207 | asyncio.run() calls |
| CRITICAL | backoff.py | 173 | time.sleep() |
| CRITICAL | monthly_quiz_message_integration.py | 207 | asyncio.run() in method |
| HIGH | dead_letter.py | 193 | time.sleep() + thread |
| HIGH | quiz_question_humanizer_integration.py | 140-144 | Nested asyncio.run() |
| HIGH | cache_layer/__init__.py | 447, 457 | ensure_future() orphan |
| MEDIUM | monthly_quiz_message_integration.py | 70 | Sync DB in async |
| MEDIUM | celery_app.py | 423-425 | Context not checked |
| MEDIUM | docs/data_providers.py | 236, 288 | Examples misleading |
| LOW | crud_service.py | 38-119 | Executor leak |
| LOW | async_context_manager.py | 177 | Complex pattern |

---

## One-Liner Fixes

```python
# Sync method calling async - use safe wrapper
from app.core.async_context_manager import safe_run_coroutine
return safe_run_coroutine(async_func(), timeout=30)

# Async method calling sync that blocks - use executor
return await asyncio.get_running_loop().run_in_executor(None, sync_func)

# Need to wait - always check context
try:
    loop = asyncio.get_running_loop()
    return await async_func()
except RuntimeError:
    return asyncio.run(async_func())

# Track background tasks
task = asyncio.create_task(background_work())
pending_tasks.add(task)
task.add_done_callback(pending_tasks.discard)

# Proper cleanup
for task in pending_tasks:
    await asyncio.wait_for(task, timeout=5)
executor.shutdown(wait=True)
```

---

## Testing Template

```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await service.async_method()
    assert result == expected

def test_sync_operation():
    # Use asyncio.run() for testing async functions from sync test
    result = asyncio.run(service.async_method())
    assert result == expected

@pytest.mark.asyncio
async def test_no_asyncio_run_from_async():
    # Verify error when asyncio.run() called in async
    with pytest.raises(RuntimeError):
        asyncio.run(some_coro())

@pytest.mark.asyncio
async def test_no_blocking_sleep():
    # Verify time.sleep() blocks but await doesn't
    import time

    async def other_task():
        await asyncio.sleep(0.01)
        return True

    # This should show blocking behavior
    # If fixed, both tasks run concurrently
```

---

## Emergency Debug Steps

1. **Got RuntimeError?**
   - Check if calling `asyncio.run()` from async function
   - Use `await` instead or move to sync function

2. **Event loop frozen/hanging?**
   - Search for `time.sleep()` in async functions
   - Replace with `await asyncio.sleep()`

3. **Unawaited coroutine warning?**
   - Add `await` keyword before function call
   - Or use `asyncio.create_task()` to explicitly create task

4. **App won't shutdown?**
   - Check for threads without shutdown()
   - Check for tasks without await on cleanup
   - Implement proper lifespan events

5. **Slow database queries?**
   - Check if sync Session used in async function
   - Migrate to AsyncSession with await
   - Or use `loop.run_in_executor()` as temporary fix

---

## Fast Links

- Analysis Report: `/docs/ASYNC_AWAIT_ANALYSIS_REPORT.md`
- Implementation Guide: `/docs/ASYNC_AWAIT_FIX_GUIDE.md`
- Python Docs: https://docs.python.org/3/library/asyncio.html
- FastAPI Async: https://fastapi.tiangolo.com/async/

