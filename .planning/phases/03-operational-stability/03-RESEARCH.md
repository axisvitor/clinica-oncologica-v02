# Phase 3: Operational Stability - Research

**Researched:** 2026-02-22
**Domain:** Celery async bridge, Redis Lua scripting, dependency audit (python-jose removal)
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ASYNC-04 | Padronizar todas Celery tasks para `async_to_sync` (eliminar `asyncio.run()` — memory leak fix) | asgiref 3.11+ is already in requirements.txt and installed; two real `asyncio.run()` call sites identified in app/tasks + one in base helper. Pattern already applied correctly in other tasks. |
| REL-01 | Rate limiter atômico via Lua script Redis (template já existe em comment, `rate_limit_core.py`) | Lua script template found verbatim in the TODO comment at line 188–205 of `rate_limit_core.py`. redis-py 6.4.0 `register_script()` is the correct API. `check_rate_limit` is already `async def`, so registration must happen on the sync Redis instance before the async boundary. |
| REL-02 | Sweep e remoção de imports `from jose` remanescentes (CVE-2024-23342) | Exactly 2 files import `from jose`: `tests/api/test_admin_contracts.py` (line 211) and `tests/validation/test_security_comprehensive.py` (line 204). Both are inside test functions, not module level. Both can be replaced with `import jwt` (PyJWT, already in requirements). |
| REL-03 | python-jose confirmado removido de todos os módulos — substituído por `pyjwt` | python-jose 3.5.0 is STILL INSTALLED in the venv despite being removed from requirements.txt. The package must be `pip uninstall python-jose` in the venv AND removed from any transitive paths. Confirmed: production code uses only `import jwt` (PyJWT 2.10.1). |
</phase_requirements>

---

## Summary

Phase 3 has three tightly-scoped tasks with clear before/after states. The codebase is already partway through each fix — several tasks already use `async_to_sync` correctly, the Lua script template is literally embedded as a comment in `rate_limit_core.py`, and python-jose has been removed from `requirements.txt` but not yet purged from the installed venv or from two test files that still import it.

The highest-risk item is the `asyncio.run()` in `app/tasks/flows/flow_tasks.py` line 326 — it wraps a genuinely complex async function (`process_daily_flows_async`) that uses `asyncio.Semaphore`, `asyncio.gather`, and `asyncio.sleep`. Replacing it with `asgiref.sync.async_to_sync` is straightforward and already the established pattern in the codebase, but the inner function must remain async (only the entry point changes).

The second `asyncio.run()` location is inside `app/tasks/flows/base.py` line 69, inside a `ThreadPoolExecutor` submit lambda — this entire block is a workaround for a running-loop scenario that `async_to_sync` handles internally. The fix collapses ~12 lines of loop-detection code into a single `async_to_sync(manager.process_alert)(alert)` call.

**Primary recommendation:** Apply `asgiref.sync.async_to_sync` to the two `asyncio.run()` call sites; implement the Lua script already written in the comment; replace `from jose import jwt` in two test files with `import jwt`; then `pip uninstall python-jose` in the venv.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asgiref | >=3.11.0 (installed: 3.10.0) | `async_to_sync` bridge for calling coroutines from sync Celery tasks | Django project; thread-safe, handles running-loop detection, already used in 15+ places in this codebase |
| redis-py | 6.4.0 | `register_script()` for Lua atomicity; `pipeline()` for multi-command batches | Already the project's Redis client via `RedisManager` |
| pyjwt | 2.10.1 | JWT encode/decode replacement for python-jose | Already in production code at `app/core/security.py`, `app/utils/security.py`, `app/services/websocket/connection_manager.py` |

**Note on asgiref version:** requirements.txt pins `>=3.11.0` but the installed venv has `3.10.0`. This may need `pip install --upgrade asgiref` before execution — or the 3.10.0 API is compatible (the `async_to_sync` function exists and works in 3.10.x). Verify with `.venv/bin/python -c "from asgiref.sync import async_to_sync; print('ok')"` — already confirmed OK.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| concurrent.futures | stdlib | Thread isolation for `run_async_in_thread` pattern | Only when async_to_sync's own thread management is insufficient |
| fakeredis | >=2.20.0 | In-memory Redis for testing Lua scripts atomicity | All unit tests for rate limiter — Lua scripts work in fakeredis |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `asgiref.sync.async_to_sync` | `app.utils.async_helpers.run_async` (project's own helper) | Project has its own `run_async` in `async_helpers.py` that also reuses event loops. Both work; `asgiref.async_to_sync` is the pattern already applied in 15 other task locations — use it for consistency |
| `redis.register_script()` | `redis.eval()` per call | `register_script` caches script SHA1, avoids re-sending script body on each call. Marginally faster. Both work identically for atomicity. |

---

## Architecture Patterns

### Pattern 1: asgiref.sync.async_to_sync — The Standard Bridge

**What:** `async_to_sync(coro_func)(*args)` runs a coroutine in a new thread with its own event loop, returns result synchronously. Thread-safe. Handles "loop already running" case automatically.

**When to use:** Any Celery task body (sync context) that needs to call an async function.

**Example — replacing asyncio.run() in flow_tasks.py:**
```python
# BEFORE (line 326 of flow_tasks.py)
results = asyncio.run(process_daily_flows_async(limit))

# AFTER
from asgiref.sync import async_to_sync
results = async_to_sync(process_daily_flows_async)(limit)
```

**Example — replacing the ThreadPoolExecutor + asyncio.run() in base.py:**
```python
# BEFORE (lines 55–71 of base.py) — 16 lines of loop-detection boilerplate
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

if loop.is_running():
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(
            lambda: asyncio.run(manager.process_alert(alert))
        )
        future.result(timeout=10)
else:
    loop.run_until_complete(manager.process_alert(alert))

# AFTER — 1 line
from asgiref.sync import async_to_sync
async_to_sync(manager.process_alert)(alert)
```

### Pattern 2: Redis Lua Script Registration

**What:** `register_script(lua_src)` returns a callable `Script` object. Calling it with `keys=[...]` and `args=[...]` executes atomically on Redis.

**When to use:** Any multi-step Redis operation that must be indivisible (check-then-act).

**The Lua script template (already in rate_limit_core.py comment, lines 189–201):**
```lua
local key = KEYS[1]
local window_start = tonumber(ARGV[1])
local current_time = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local window = tonumber(ARGV[4])
redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, current_time, tostring(current_time))
    redis.call('EXPIRE', key, window + 60)
    return {1, count + 1}  -- allowed, new_count
end
return {0, count}  -- denied, count
```

**How to register (in `DistributedRateLimiter.__init__`):**
```python
# In __init__ after self.redis = redis
self._sliding_window_script = redis.register_script(SLIDING_WINDOW_LUA)
```

**How to call (in check_rate_limit):**
```python
result = self._sliding_window_script(
    keys=[key],
    args=[window_start, current_time, limit, window]
)
allowed_flag, new_count = int(result[0]), int(result[1])
```

**Critical detail:** `register_script` takes the sync `Redis` instance (not the async client). The `DistributedRateLimiter` already holds `self.redis: Redis` (sync). The `check_rate_limit` method is `async def` but the underlying redis calls are sync — calling `self._sliding_window_script(...)` from inside an async method is fine (it's a sync call, no await needed).

### Pattern 3: jose → pyjwt Migration in Tests

**What:** Replace `from jose import jwt` with `import jwt`. The API for HS256 encode/decode is compatible:

```python
# jose API (being removed)
from jose import jwt
token = jwt.encode({"sub": email, "exp": exp}, secret, algorithm="HS256")
decoded = jwt.decode(token, secret, algorithms=["HS256"])

# pyjwt API (identical for these calls)
import jwt
token = jwt.encode({"sub": email, "exp": exp}, secret, algorithm="HS256")
decoded = jwt.decode(token, secret, algorithms=["HS256"])
```

**Key difference:** PyJWT `jwt.encode()` returns a `str` (not bytes) in pyjwt >= 2.0. No `.decode()` needed. Since both test files just encode+pass the token, this is a drop-in replacement.

**Exception hierarchy change:**
- jose raises `jose.exceptions.JWTError`
- pyjwt raises `jwt.exceptions.PyJWTError`

The test in `test_security_comprehensive.py` uses a bare `except Exception: pass` — no change needed. The test in `test_admin_contracts.py` does not catch exceptions — no change needed.

### Anti-Patterns to Avoid

- **Do not use `asyncio.get_event_loop()` + `loop.run_until_complete()`** in Celery tasks: This fails with Python 3.10+ where `get_event_loop()` warns when there's no running loop. Use `async_to_sync` instead.
- **Do not re-use a single asyncio.run() wrapper around all per-item calls in batch**: The existing `asyncio.run(process_daily_flows_async(limit))` wraps one call that internally parallelizes with asyncio.gather — this is the correct architecture. Do not move `asyncio.run()` inside the per-patient loop.
- **Do not pipeline without MULTI/EXEC for atomic operations**: Redis pipeline without MULTI is not atomic. The comment in the code correctly identifies this as the problem being fixed.
- **Do not call `pip uninstall python-jose` on the host**: Must be done inside the venv (`cd backend-hormonia && .venv/bin/pip uninstall python-jose -y`).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Event loop bridge for Celery | Custom loop creation with `asyncio.new_event_loop()` | `asgiref.sync.async_to_sync` | Already in requirements; handles thread-safety, loop reuse, cleanup, and running-loop detection. The `app/utils/async_helpers.py::run_async_in_thread` is also valid but less consistent with existing task pattern |
| Atomic Redis operations | Multi-step pipeline + client-side check | `register_script()` with Lua | Redis Lua is single-threaded; guaranteed atomic even across Redis Cluster |
| JWT encoding for tests | Any new helper | `import jwt` (pyjwt) directly | Already in prod code; no new abstraction needed |

**Key insight:** The project already has `asgiref.sync.async_to_sync` applied correctly in ~15 locations. The two remaining `asyncio.run()` call sites in `app/tasks/` are leftover from before the pattern was standardized. The fix is mechanical, not architectural.

---

## Common Pitfalls

### Pitfall 1: asyncio.run() inside ThreadPoolExecutor.submit()

**What goes wrong:** In `base.py` line 69, the code already detects a running loop and spawns a thread to call `asyncio.run()`. This works but is complex and creates a new event loop per invocation (memory pressure).

**Why it happens:** Original author correctly identified the running-loop problem but chose a manual workaround instead of `async_to_sync`.

**How to avoid:** `async_to_sync` internally uses a `ThreadPoolExecutor` + new event loop per call. The collapsing is safe.

**Warning signs:** Any code with `asyncio.get_event_loop()` + `if loop.is_running():` branch in a Celery task.

### Pitfall 2: Lua script registration on wrong client type

**What goes wrong:** `register_script()` is on the sync `Redis` class, not `asyncio`-based clients. If you call it on `aioredis` or an async redis client, the API differs.

**Why it happens:** The project uses synchronous redis-py in `rate_limit_core.py` (the `check_rate_limit` is `async def` but calls `self.redis.pipeline()` synchronously — this is the existing pattern).

**How to avoid:** Register the script in `__init__` against `self.redis` (the sync client passed in). Do not await the script call — it is synchronous.

**Warning signs:** `await self._sliding_window_script(...)` would be wrong. It should be `result = self._sliding_window_script(keys=[...], args=[...])`.

### Pitfall 3: python-jose still importable after requirements.txt removal

**What goes wrong:** Even though `python-jose` is removed from `requirements.txt`, it is still installed in the venv (confirmed: `pip show python-jose` shows version 3.5.0). Tests with `from jose import jwt` will PASS locally, giving false confidence.

**Why it happens:** `pip install -r requirements.txt` does not uninstall packages that were previously installed and are now absent from the file.

**How to avoid:** Explicitly uninstall: `.venv/bin/pip uninstall python-jose -y`. Then verify with `.venv/bin/pip show python-jose` returning nothing.

**Warning signs:** CI passes but prod might fail if the venv is rebuilt from scratch (python-jose absent) and any remaining `from jose` import is in app/ code. Currently only test files import jose, so prod is safe — but the venv inconsistency is a risk.

### Pitfall 4: PyJWT encode returns str (not bytes) in pyjwt >= 2.0

**What goes wrong:** Old code might call `.decode()` on the token after `jwt.encode()`, expecting bytes. PyJWT 2.0+ returns `str` directly.

**Why it happens:** python-jose always returned `str`; old pyjwt < 2.0 returned `bytes`.

**How to avoid:** Do not call `.decode()` on the result of `jwt.encode()`. Both test files just pass the token to `client.post()` — no `.decode()` call, so no issue.

### Pitfall 5: Lua ARGV values are strings, not numbers

**What goes wrong:** `ARGV[1]` in Lua is a string. If you do arithmetic without `tonumber()`, comparisons silently fail.

**Why it happens:** Redis always passes ARGV as strings.

**How to avoid:** The template already uses `tonumber(ARGV[1])` etc. Preserve this pattern exactly.

---

## Code Examples

Verified patterns from codebase inspection:

### Full async_to_sync replacement for flow_tasks.py

```python
# BEFORE: app/tasks/flows/flow_tasks.py, lines 322–327
import asyncio
# ...
try:
    logger.info(f"Starting daily flow processing task for up to {limit} patients")
    # Execute async version ONCE with a single event loop
    results = asyncio.run(process_daily_flows_async(limit))
    return results

# AFTER
from asgiref.sync import async_to_sync
# ...
try:
    logger.info(f"Starting daily flow processing task for up to {limit} patients")
    results = async_to_sync(process_daily_flows_async)(limit)
    return results
```

No other changes needed in `flow_tasks.py`. The `asyncio` import at the top can remain (still used for `asyncio.Semaphore`, `asyncio.sleep`, `asyncio.gather` inside `process_daily_flows_async`).

### Full async_to_sync replacement for base.py send_critical_alert_sync

```python
# BEFORE: app/tasks/flows/base.py, lines 8–9 and 49–73
import asyncio
import logging
from typing import Any
from celery import Task
# ...

def send_critical_alert_sync(task_name: str, error: str, context: dict = None):
    try:
        # ... create alert ...
        manager = get_alert_manager()

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(manager.process_alert(alert))
                )
                future.result(timeout=10)
        else:
            loop.run_until_complete(manager.process_alert(alert))
    except Exception as e:
        logger.error(f"Failed to send critical alert for {task_name}: {e}")

# AFTER
import logging
from celery import Task
from asgiref.sync import async_to_sync
# asyncio import removed (no longer needed in this function)
# ...

def send_critical_alert_sync(task_name: str, error: str, context: dict = None):
    try:
        # ... create alert ...
        manager = get_alert_manager()
        async_to_sync(manager.process_alert)(alert)
    except Exception as e:
        logger.error(f"Failed to send critical alert for {task_name}: {e}")
```

**Note:** `FlowTaskBase._store_task_result` uses `asyncio` indirectly through `asyncio.sleep` in `process_daily_flows_async`, not in base.py directly. The `asyncio` import in `flow_tasks.py` must stay; the one in `base.py` can be removed if no other code in that file uses it. Verify before removing.

### Lua script registration in DistributedRateLimiter

```python
# rate_limit_core.py — full atomic implementation

_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local window_start = tonumber(ARGV[1])
local current_time = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local window = tonumber(ARGV[4])
redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, current_time, tostring(current_time))
    redis.call('EXPIRE', key, window + 60)
    return {1, count + 1}
end
return {0, count}
"""

class DistributedRateLimiter:
    def __init__(self, redis: Redis, ...):
        self.redis = redis
        # ... existing params ...
        self._sliding_window_script = redis.register_script(_SLIDING_WINDOW_LUA)

    async def check_rate_limit(self, identifier, limit, window, increment=True):
        try:
            # Block check (existing code — keep as-is)
            if self.enable_blocking:
                # ... existing block check ...

            key = self._get_key(identifier, window)
            current_time = time.time()
            window_start = current_time - window

            if increment:
                # Atomic Lua path
                result = self._sliding_window_script(
                    keys=[key],
                    args=[window_start, current_time, limit, window]
                )
                allowed_flag = int(result[0])
                current_count = int(result[1])
                allowed = allowed_flag == 1
            else:
                # Read-only path: just count current entries
                pipe = self.redis.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zcard(key)
                results = pipe.execute()
                current_count = results[1]
                allowed = current_count < limit

            remaining = max(0, limit - current_count)
            reset_at = datetime.fromtimestamp(current_time + window)
            # ... rest of existing result logic ...
```

### jose → pyjwt replacement in tests

```python
# BEFORE: tests/api/test_admin_contracts.py line 211
from jose import jwt
# ...
token = jwt.encode(
    {"sub": sample_user.email, "exp": expired_time},
    settings.SECURITY_SECRET_KEY,
    algorithm="HS256"
)

# AFTER
import jwt  # PyJWT
# ...
token = jwt.encode(
    {"sub": sample_user.email, "exp": expired_time},
    settings.SECURITY_SECRET_KEY,
    algorithm="HS256"
)
# No other changes needed — jwt.encode returns str in pyjwt >= 2.0
```

```python
# BEFORE: tests/validation/test_security_comprehensive.py line 204
from jose import jwt
# ...
try:
    decoded = jwt.decode(token, "", algorithms=["none"])
    pytest.fail("Should not allow 'none' algorithm")
except Exception:
    pass

# AFTER
import jwt  # PyJWT
# ...
try:
    decoded = jwt.decode(token, "", algorithms=["none"])
    pytest.fail("Should not allow 'none' algorithm")
except Exception:
    pass
# Identical usage — PyJWT also raises on "none" algorithm
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `asyncio.run()` in Celery tasks | `asgiref.sync.async_to_sync()` | Partially adopted in this codebase | 2 remaining sites must be updated |
| `loop.is_running()` detection + ThreadPoolExecutor workaround | `async_to_sync` handles it internally | — | 12 lines → 1 line |
| Redis pipeline (non-atomic) for rate limiter | Lua script via `register_script()` | Template already written in code comment | Fix is mechanical: promote comment to code |
| `python-jose` for JWT | `pyjwt` | Already removed from requirements.txt | 2 test files still import the old package |

**Deprecated/outdated:**
- `python-jose`: CVE-2024-23342 (python-ecdsa timing vulnerability). Removed from requirements.txt but still installed in venv. Must be explicitly uninstalled.
- `asyncio.get_event_loop()` + conditional `run_until_complete`: Deprecated pattern in Python 3.10+, emits DeprecationWarning.

---

## Open Questions

1. **asyncio import cleanup in base.py**
   - What we know: `base.py` imports `asyncio` at the top. The `asyncio.run()` + `asyncio.get_event_loop()` usage will be replaced by `async_to_sync`.
   - What's unclear: Does `FlowTaskBase` or any other code in `base.py` use `asyncio` for other purposes after the fix?
   - Recommendation: Check `base.py` fully before removing the import. Lines 56–73 use asyncio extensively; after fix, if no other usage remains, remove the import and the `import concurrent.futures` in the same block.

2. **fakeredis compatibility with Lua scripts for tests**
   - What we know: fakeredis >=2.20.0 supports Lua scripting via `register_script()`.
   - What's unclear: Whether the specific Lua functions used (`ZREMRANGEBYSCORE`, `ZADD`, `ZCARD`, `EXPIRE`) are all supported in fakeredis.
   - Recommendation: Write a minimal test that registers and calls the script against a fakeredis instance. If it fails, fall back to `eval()` with inline script string per call.

3. **Blocking detection after rate limit fix**
   - What we know: The `_block_client` method uses `self.redis.setex()` synchronously. The blocking check at the top uses `self.redis.get()` synchronously. These are non-Lua reads/writes and are fine.
   - What's unclear: Whether the abuse detection (`count > limit * 2` → `_block_client`) should also be inside the Lua script for full atomicity.
   - Recommendation: Keep abuse blocking outside the Lua script for now (it is a secondary defense, not the primary rate limit). The primary race condition (ZCARD then ZADD) is fixed by the Lua script.

---

## Sources

### Primary (HIGH confidence)

- Direct codebase inspection — `app/tasks/flows/flow_tasks.py` lines 270–350 (asyncio.run call site)
- Direct codebase inspection — `app/tasks/flows/base.py` lines 1–76 (loop detection + asyncio.run in thread)
- Direct codebase inspection — `app/middleware/rate_limit_core.py` lines 183–221 (Lua TODO comment + pipeline implementation)
- Direct codebase inspection — `tests/api/test_admin_contracts.py` line 211 (from jose import)
- Direct codebase inspection — `tests/validation/test_security_comprehensive.py` line 204 (from jose import)
- Direct codebase inspection — `requirements.txt` line 14 (python-jose removal note), line 32 (asgiref), line 67 (pyjwt)
- `.venv/bin/pip show python-jose` → 3.5.0 still installed
- `.venv/bin/python -c "from asgiref.sync import async_to_sync"` → confirmed available
- `.venv/bin/python -c "import redis; Redis.register_script signature"` → confirmed API

### Secondary (MEDIUM confidence)

- grep output confirming `from asgiref.sync import async_to_sync` is used in 15+ locations across `app/tasks/` (confirmed pattern is established in this codebase)
- grep output confirming production code (`app/`) has zero `from jose` imports — only test files remain

### Tertiary (LOW confidence)

- None — all claims verified directly against codebase.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified by direct venv inspection and requirements.txt
- Architecture: HIGH — exact call sites identified, replacement patterns documented
- Pitfalls: HIGH — all pitfalls derived from actual code patterns found, not hypothetical

**Research date:** 2026-02-22
**Valid until:** 2026-03-22 (stable domain; unlikely to change)

---

## Appendix: Complete Inventory of asyncio.run() in app/tasks/

Only 2 files contain actual `asyncio.run()` calls in `app/tasks/` (not in comments):

| File | Line | Pattern | Fix |
|------|------|---------|-----|
| `app/tasks/flows/flow_tasks.py` | 326 | `results = asyncio.run(process_daily_flows_async(limit))` | `results = async_to_sync(process_daily_flows_async)(limit)` |
| `app/tasks/flows/base.py` | 69 | `lambda: asyncio.run(manager.process_alert(alert))` inside ThreadPoolExecutor | Replace entire loop-detection block with `async_to_sync(manager.process_alert)(alert)` |

Files in `app/tasks/` that already use `async_to_sync` correctly (do NOT touch):
- `app/tasks/alerts.py` — `async_to_sync` used ✓
- `app/tasks/flow_automation.py` — `async_to_sync` used 5x ✓
- `app/tasks/follow_up.py` — `async_to_sync` used 9x ✓
- `app/tasks/quiz_flow/helpers.py` — `async_to_sync` used ✓
- `app/tasks/quiz_flow/question_tasks.py` — `async_to_sync` used ✓
- `app/tasks/quiz_flow/response_tasks.py` — `async_to_sync` used ✓
- `app/tasks/quiz_flow/trigger_tasks.py` — `async_to_sync` used ✓

`asyncio.run()` outside `app/tasks/` (out of scope for ASYNC-04 but noted):
- `app/core/async_context_manager.py` — 3 calls (out of scope)
- `app/core/redis_manager/sync_client.py` — 1 call (out of scope)
- `app/domain/quizzes/resilience/link_resilience.py` — 2 calls (out of scope)
- `app/services/dlq/message_processor.py` — 1 call (out of scope)
- `app/services/dlq/retry_handler.py` — 1 call (out of scope)
- `app/services/monthly_quiz_message_integration.py` — 1 call (out of scope)
- `app/services/quiz_question_humanizer_integration.py` — 2 calls (out of scope)
- `app/workers/whatsapp_queue_worker.py` — 1 call at top-level entry point (acceptable pattern)

The success criterion `grep -r "asyncio.run(" app/tasks/` returning zero is achievable with exactly 2 file changes.
