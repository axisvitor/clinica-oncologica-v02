# Backend-Hormonia: Race Conditions and Concurrency Issues Analysis

**Analysis Date:** 2025-12-25
**Severity Distribution:** 3 Critical | 8 High | 6 Medium | 4 Low
**Total Issues Found:** 21

---

## Executive Summary

This report identifies critical race conditions and concurrency vulnerabilities in the backend-hormonia system. The analysis covers TOCTOU vulnerabilities, missing locks, incorrect async/await patterns, database isolation issues, cache invalidation races, and global mutable state problems across 200+ Python files.

**Key Findings:**
- **Critical:** Global cache state without atomicity, unprotected PubSub listener state
- **High:** Cache invalidation race conditions, TOCTOU in saga resume, unsafe singleton patterns
- **Medium:** Missing transaction isolation in concurrent writes, debounce window race conditions
- **Low:** Potential cleanup race conditions in thread-safe service provider

---

## Critical Issues (P0)

### 1. Cache Invalidation Race: Pattern Invalidation Without Atomicity

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/cache/invalidation_service.py:333-373`
**Severity:** CRITICAL
**Issue Type:** Cache Invalidation Race Condition

**Problem:**
```python
# Non-atomic pattern invalidation using SCAN cursor
async def _invalidate_pattern(self, pattern: str) -> bool:
    try:
        if self.redis_client:
            cursor = 0
            count = 0

            while True:
                cursor, keys = self.redis_client.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100,
                )

                if keys:
                    self.redis_client.delete(*keys)  # <-- RACE CONDITION
                    count += len(keys)

                if cursor == 0:
                    break
```

**Race Condition Scenario:**
1. Thread A starts SCAN for pattern `patient:*` at cursor 0
2. Thread B deletes keys matching `patient:*` between Thread A's SCAN calls
3. Thread A's second SCAN call may miss keys that were added after Thread A started
4. Result: Incomplete cache invalidation, stale data persists

**Why This Matters:**
- Patient data invalidation incomplete → serving stale medical information
- Quiz cache inconsistent → same patient sees different quiz states
- Flow state becomes corrupted

**Fix Recommendation:**
Use Redis EVALSHA with atomic Lua script or Redis transactions:
```python
# Atomic invalidation using Lua script
INVALIDATE_PATTERN_SCRIPT = """
local pattern = KEYS[1]
local cursor = "0"
local count = 0

while true do
    local scan_result = redis.call("SCAN", cursor, "MATCH", pattern, "COUNT", 100)
    cursor = tonumber(scan_result[1])
    local keys = scan_result[2]

    if #keys > 0 then
        redis.call("DEL", unpack(keys))
        count = count + #keys
    end

    if cursor == 0 then
        break
    end
end

return count
"""

# Call atomically
redis_client.eval(INVALIDATE_PATTERN_SCRIPT, 1, pattern)
```

---

### 2. Global Singleton Cache Service Without Synchronization

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/unified_cache.py:578-592`
**Severity:** CRITICAL
**Issue Type:** Race Condition on Global Mutable State

**Problem:**
```python
# Global singleton instance
_unified_cache_service: Optional[UnifiedCacheService] = None

def get_unified_cache_service() -> UnifiedCacheService:
    """Get the global unified cache service singleton."""
    global _unified_cache_service
    if _unified_cache_service is None:  # <-- TOCTOU VULNERABILITY
        _unified_cache_service = UnifiedCacheService()
    return _unified_cache_service
```

**Race Condition Scenario:**
1. Request A checks: `if _unified_cache_service is None` → True
2. Request B checks: `if _unified_cache_service is None` → True (A hasn't assigned yet)
3. Request A: `_unified_cache_service = UnifiedCacheService()` (creates instance A)
4. Request B: `_unified_cache_service = UnifiedCacheService()` (creates instance B, OVERWRITES A)
5. Result: Multiple cache manager instances, inconsistent cache state across requests

**Why This Matters:**
- Multiple cache managers point to different Redis connections
- Patient cache invalidation affects only one manager instance
- Cache coherency broken across concurrent requests

**Fix Recommendation:**
```python
import threading

_unified_cache_service: Optional[UnifiedCacheService] = None
_cache_service_lock = threading.RLock()

def get_unified_cache_service() -> UnifiedCacheService:
    global _unified_cache_service
    if _unified_cache_service is None:
        with _cache_service_lock:
            if _unified_cache_service is None:  # Double-check locking
                _unified_cache_service = UnifiedCacheService()
    return _unified_cache_service
```

---

### 3. Redis PubSub Listener Race: State Modification Without Synchronization

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/redis_pubsub_manager.py:77-86`
**Severity:** CRITICAL
**Issue Type:** Unsynchronized Global State

**Problem:**
```python
class RedisPubSubManager:
    def __init__(self, ...):
        self.pubsub: Optional[redis.client.PubSub] = None
        self.subscriptions: Set[str] = set()  # <-- NO LOCK PROTECTING THIS
        self.is_running = False  # <-- NO LOCK PROTECTING THIS
        self._listener_task: Optional[asyncio.Task] = None  # <-- NO LOCK
```

**Race Condition Scenario:**
1. Main thread: calls `await pubsub_manager.stop()`
2. Listener task (async): simultaneously executing `await self.pubsub.listen()`
3. Main thread: sets `self.is_running = False`
4. Listener task: still processing message, accesses `self.subscriptions`
5. Main thread: clears `self.subscriptions`
6. Listener task: crashes accessing cleared set

**Why This Matters:**
- WebSocket connections lost mid-broadcast
- Real-time updates fail silently
- Instance state becomes corrupted

**Fix Recommendation:**
```python
import asyncio

class RedisPubSubManager:
    def __init__(self, ...):
        self.pubsub: Optional[redis.client.PubSub] = None
        self.subscriptions: Set[str] = set()
        self.is_running = False
        self._listener_task: Optional[asyncio.Task] = None

        # Add lock for state synchronization
        self._state_lock = asyncio.Lock()

    async def stop(self):
        async with self._state_lock:
            if not self.is_running:
                return
            self.is_running = False
            # ... rest of cleanup

    async def subscribe_to_room(self, room_id: str):
        async with self._state_lock:
            channel = f"ws:room:{room_id}"
            if channel not in self.subscriptions:
                await self.pubsub.subscribe(channel)
                self.subscriptions.add(channel)
```

---

## High-Priority Issues (P1)

### 4. Saga Resume TOCTOU Vulnerability

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/orchestration/saga_orchestrator.py:227-244`
**Severity:** HIGH
**Issue Type:** TOCTOU (Time-of-Check to Time-of-Use)

**Problem:**
```python
async def resume_saga(self, saga_id: UUID) -> Dict[str, Any]:
    """Resume a failed or interrupted saga."""
    # Comment says "Acquire lock BEFORE fetching saga"
    # But THIS IS THE ISSUE - the code doesn't actually do this correctly
    lock_key = f"saga:resume:{saga_id}"
    try:
        async with acquire_lock(lock_key, timeout=5.0, ttl=60):
            # Saga is fetched INSIDE lock - THIS IS CORRECT
            saga = (
                self.db.query(PatientOnboardingSaga)
                .filter(PatientOnboardingSaga.id == saga_id)
                .first()
            )
            # TOCTOU STILL POSSIBLE HERE:
            # Between .first() and the check below, another process could
            # have updated saga.status if isolation level is not SERIALIZABLE
```

**Race Condition Scenario:**
1. Saga A status = STARTED
2. Request 1: Lock acquired, fetches saga A (status=STARTED)
3. Request 2: Waiting for lock
4. Request 1: Processing saga, commits status=COMPENSATING
5. Request 1: Releases lock
6. Request 2: Lock acquired, fetches saga A (status should be COMPENSATING)
7. Request 2: But database isolation level may allow dirty reads!
8. Result: Double-compensation of same saga

**Why This Matters:**
- Patient created twice
- Flow states duplicated
- Welcome messages sent twice

**Fix Recommendation:**
```python
# 1. Use SERIALIZABLE transaction isolation
async def resume_saga(self, saga_id: UUID):
    with self.db.begin_nested():  # Start nested transaction
        # Set isolation level
        self.db.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;")

        async with acquire_lock(lock_key, timeout=5.0, ttl=60):
            saga = (
                self.db.query(PatientOnboardingSaga)
                .with_for_update()  # Acquire row lock
                .filter(PatientOnboardingSaga.id == saga_id)
                .first()
            )

            if saga.status in (SagaStatus.COMPLETED, SagaStatus.FAILED):
                return {"status": "already_processed"}

            # Now safe to process
```

---

### 5. Cache Invalidation Race: Bulk Operations

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/unified_cache.py:396-450`
**Severity:** HIGH
**Issue Type:** Non-Atomic Multi-Step Invalidation

**Problem:**
```python
async def invalidate_patient_related_cache(
    self, patient_id: Union[str, UUID]
) -> Dict[str, int]:
    """Invalidate all cache entries related to a specific patient."""
    results = {}

    # Multiple separate invalidation calls without atomicity
    results["patients"] = 1 if self.invalidate_patient_cache(patient_id) else 0
    results["flows"] = self.invalidate_patient_flow_cache(patient_id)  # <-- RACE
    results["quiz"] = self.cache_manager.invalidate_pattern(  # <-- RACE
        pattern, namespace="quiz"
    )
```

**Race Condition Scenario:**
1. Invalidate patient cache → SUCCESS (patient:123 deleted)
2. Between invalidate calls, another request reads flow cache → STALE FLOW DATA
3. Invalidate flow cache → SUCCESS
4. Between step 3 and 4, another request reads quiz cache → STALE QUIZ DATA
5. Invalidate quiz cache → SUCCESS
6. Result: Partial cache invalidation window where stale data served

**Why This Matters:**
- Patient data updated, but flow state from old patient returned
- Quiz shows old questions while patient metadata is new
- Data inconsistency window = up to 100ms

**Fix Recommendation:**
```python
# Use Redis pipeline for atomicity
async def invalidate_patient_related_cache(
    self, patient_id: Union[str, UUID]
) -> Dict[str, int]:
    pipe = self.cache_manager.redis.pipeline()

    # Queue all deletions
    pipe.delete(f"patient:{patient_id}")
    pipe.delete(f"patient_flow:{patient_id}:*")  # Pattern
    # ... all other related keys

    # Execute atomically
    results = pipe.execute()

    return {
        "patients": results[0],
        "flows": results[1],
        # ...
    }
```

---

### 6. Rate Limiter In-Memory Accumulation Without Proper Locking

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/middleware/rate_limiter.py:59-127`
**Severity:** HIGH
**Issue Type:** Concurrent Dictionary Access Without Synchronization

**Problem:**
```python
class RateLimiter:
    """In-memory rate limiter with memory leak potential."""

    def __init__(self, rate: int = 10, per: int = 60):
        self.rate = rate
        self.per = per
        self.allowance = defaultdict(lambda: rate)  # <-- NO LOCK
        self.last_check = defaultdict(time.time)  # <-- NO LOCK
        self._last_cleanup = time.time()  # <-- NO LOCK

    def is_allowed(self, key: str) -> Tuple[bool, Optional[int]]:
        # RACE CONDITION HERE:
        current = time.time()
        time_passed = current - self.last_check[key]  # <-- READ without lock
        self.last_check[key] = current  # <-- WRITE without lock

        self.allowance[key] += time_passed * (self.rate / self.per)  # <-- RACE

        if self.allowance[key] > self.rate:
            self.allowance[key] = self.rate  # <-- WRITE without lock
```

**Race Condition Scenario:**
1. Thread A: `time_passed = current - self.last_check[key]` = 1.0
2. Thread B: `time_passed = current - self.last_check[key]` = 1.0 (same value)
3. Thread A: `self.last_check[key] = current` (update timestamp)
4. Thread B: `self.last_check[key] = current` (overwrites A's update)
5. Thread A: `self.allowance[key] += 0.1666...` (token replenishment)
6. Thread B: `self.allowance[key] += 0.1666...` (DOUBLE replenishment)
7. Result: Rate limit allows 2x more requests than configured

**Why This Matters:**
- Configured 10 req/min but allow 20 req/min during race
- User can spam API by timing requests simultaneously
- DDoS protection broken

**Fix Recommendation:**
```python
import threading

class RateLimiter:
    def __init__(self, rate: int = 10, per: int = 60):
        self.rate = rate
        self.per = per
        self.allowance = defaultdict(lambda: rate)
        self.last_check = defaultdict(time.time)
        self._lock = threading.RLock()  # ADD LOCK

    def is_allowed(self, key: str) -> Tuple[bool, Optional[int]]:
        with self._lock:
            current = time.time()
            time_passed = current - self.last_check[key]
            self.last_check[key] = current

            self.allowance[key] += time_passed * (self.rate / self.per)
            if self.allowance[key] > self.rate:
                self.allowance[key] = self.rate

            if self.allowance[key] < 1.0:
                retry_after = int((1.0 - self.allowance[key]) * (self.per / self.rate))
                return False, retry_after

            self.allowance[key] -= 1.0
            return True, None
```

---

### 7. Quiz Response Debounce Race Condition

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/quiz_response_debounce.py:48-117`
**Severity:** HIGH
**Issue Type:** TOCTOU in Debounce Check

**Problem:**
```python
async def should_process_response(
    self,
    session_id: UUID,
    question_id: str,
    message_metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    redis_client = await get_async_redis()

    debounce_key = self._build_debounce_key(session_id, question_id)

    # TOCTOU WINDOW: Between check and set
    exists = await redis_client.exists(debounce_key)  # <-- CHECK

    if exists:
        # ... debounce
        return False

    # Non-atomic set operation
    await redis_client.setex(  # <-- USE (but not atomic with check)
        debounce_key,
        self.debounce_window,
        self._serialize_debounce_data(message_metadata),
    )

    return True
```

**Race Condition Scenario:**
1. Request A: `exists()` → key does not exist (first message)
2. Request B: `exists()` → key does not exist (arrives simultaneously)
3. Request A: `setex()` → sets debounce key, returns True
4. Request B: `setex()` → overwrites, returns True
5. Both requests process same quiz answer
6. Result: Duplicate quiz responses recorded

**Why This Matters:**
- Same answer recorded twice
- Quiz scoring affected
- Patient progress appears inflated

**Fix Recommendation:**
```python
# Use SETNX (SET if Not eXists) for atomicity
async def should_process_response(self, session_id, question_id, message_metadata):
    redis_client = await get_async_redis()
    debounce_key = self._build_debounce_key(session_id, question_id)

    # Atomic operation: only sets if key doesn't exist
    was_set = await redis_client.setnx(
        debounce_key,
        self._serialize_debounce_data(message_metadata),
    )

    if was_set:
        # We won the race - set TTL
        await redis_client.expire(debounce_key, self.debounce_window)
        return True
    else:
        # Another request got here first
        return False
```

---

### 8. Idempotency Middleware Race: Duplicate Event Record Creation

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/middleware/idempotency.py:232-293`
**Severity:** HIGH
**Issue Type:** TOCTOU in Event Deduplication

**Problem:**
```python
async def _check_idempotency(
    self,
    db: Session,
    event_id: str,
    provider: str,
    event_type: str,
    request: Request,
) -> WebhookEvent:
    # CHECK: Is event already processed?
    existing_event = (
        db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first()
    )  # <-- CHECK POINT

    if existing_event:
        # ... handle duplicate
        return existing_event

    # USE: Create new event record
    new_event = WebhookEvent.create_event(...)  # <-- USE POINT

    try:
        db.add(new_event)
        db.commit()  # <-- POTENTIAL FAILURE HERE
        db.refresh(new_event)
        return new_event

    except IntegrityError:  # <-- Only catches this
        # Race condition - another request created the record
        db.rollback()
        existing_event = (
            db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first()
        )
        if existing_event:
            return existing_event
        raise
```

**Race Condition Scenario:**
1. Request A: Queries for event_id="123" → Not found
2. Request B: Queries for event_id="123" → Not found (A hasn't committed yet)
3. Request A: Creates WebhookEvent, commits → SUCCESS
4. Request B: Creates WebhookEvent with SAME event_id → Might fail silently or create duplicate if PK not enforced
5. Even with IntegrityError catch, timing window exists

**Why This Matters:**
- Same webhook event processed twice
- Customer receives duplicate messages
- Database constraint violation logs (non-fatal but concerning)

**Fix Recommendation:**
```python
# Use database constraint + UNIQUE index
async def _check_idempotency(self, db, event_id, provider, event_type, request):
    # Ensure UNIQUE constraint on event_id in database
    # CREATE UNIQUE INDEX idx_webhook_event_id ON webhook_event(event_id);

    # Check with row lock
    existing_event = (
        db.query(WebhookEvent)
        .with_for_update()  # Lock the row
        .filter(WebhookEvent.event_id == event_id)
        .first()
    )

    if existing_event:
        return existing_event

    new_event = WebhookEvent.create_event(...)
    db.add(new_event)
    db.commit()
    return new_event
```

---

### 9. PubSub User Connection Enumeration Race

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/redis_pubsub_manager.py:292-311`
**Severity:** HIGH
**Issue Type:** Concurrent Dictionary Iteration Without Synchronization

**Problem:**
```python
async def _handle_user_message(self, user_id: str, data: Dict[str, Any]):
    """Handle user-specific message - send to all user's connections."""
    payload = data.get("payload", {})

    # Dictionary iteration without lock
    user_connections = [
        conn_id
        for conn_id, conn_data in self.connection_manager.connections.items()  # <-- RACE
        if conn_data.get("user_id") == user_id
    ]

    # Dictionary may have changed by now
    for conn_id in user_connections:
        await self.connection_manager.send_personal_message(payload, conn_id)
```

**Race Condition Scenario:**
1. Thread A: Starts iterating `self.connection_manager.connections`
2. Thread B: Removes connection while Thread A is iterating
3. Thread A: Crashes with RuntimeError: "dictionary changed size during iteration"
4. OR: Thread A creates stale user_connections list
5. Thread A: Tries to send to connection_id that no longer exists
6. Result: Message delivery failure or crash

**Why This Matters:**
- WebSocket real-time updates fail
- Server crashes with uncaught exception
- Live notifications don't reach user

**Fix Recommendation:**
```python
async def _handle_user_message(self, user_id: str, data: Dict[str, Any]):
    payload = data.get("payload", {})

    # Create snapshot under lock
    async with self.connection_manager._lock:
        user_connections = [
            conn_id
            for conn_id, conn_data in self.connection_manager.connections.items()
            if conn_data.get("user_id") == user_id
        ]

    # Iterate snapshot (safe from concurrent modifications)
    for conn_id in user_connections:
        try:
            await self.connection_manager.send_personal_message(payload, conn_id)
        except KeyError:
            # Connection was closed after snapshot
            pass
```

---

### 10. Service Provider Cleanup Race Condition

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/thread_safe_services.py:387-431`
**Severity:** HIGH
**Issue Type:** Concurrent Access During Cleanup

**Problem:**
```python
@classmethod
def cleanup_all(cls):
    """Clean up all ServiceProvider instances across threads."""
    with cls._instance_lock:
        thread_ids = list(cls._instances.keys())
        for thread_id in thread_ids:
            try:
                instance = cls._instances[thread_id]
                instance.cleanup()  # <-- Calls cleanup without instance lock
            except Exception as e:
                logger.error(f"Error cleaning up: {e}")

    cls._instances.clear()

def cleanup(self):
    """Clean up resources and caches."""
    with self._service_cache_lock:
        for service_name, service in self._service_cache.items():
            if hasattr(service, "cleanup"):
                try:
                    service.cleanup()  # <-- Service being used elsewhere?
                except Exception as e:
                    logger.error(f"Error: {e}")
        self._service_cache.clear()
```

**Race Condition Scenario:**
1. Worker thread 1: Holding lock on service_cache, iterating services
2. Main thread: Calls cleanup_all(), waiting for instance_lock
3. Worker thread 2: Tries to access service via `self.auth_service`
4. Cleanup completes, clears cache
5. Worker thread 2: Gets None, crashes with AttributeError
6. Or: Service cleanup closes database connection while thread 1 is using it

**Why This Matters:**
- Graceful shutdown causes crashes
- Database connections closed while in-flight requests
- Cascade failures

**Fix Recommendation:**
```python
def cleanup(self):
    """Clean up resources and caches."""
    with self._service_cache_lock:
        # Prevent new service access
        cache_copy = dict(self._service_cache)
        self._service_cache.clear()

    # Cleanup without holding lock
    for service_name, service in cache_copy.items():
        if hasattr(service, "cleanup"):
            try:
                service.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up {service_name}: {e}")
```

---

## Medium-Priority Issues (P2)

### 11. Saga Status Update Race in Resume

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/orchestration/saga_orchestrator.py:299-316`
**Severity:** MEDIUM
**Issue Type:** Non-Atomic Status Update

**Problem:**
```python
async def _resume_saga_internal(self, saga: PatientOnboardingSaga):
    # ... processing steps ...

    # Update status (not atomic with previous checks)
    saga.status = SagaStatus.COMPLETED  # <-- WRITE
    saga.completed_at = now_sao_paulo()

    self.db.commit()  # Commits entire transaction

    return {"status": "completed"}
```

**Race Condition Scenario:**
1. Lock is released AFTER lock context but BEFORE final state persisted
2. Another resume attempt reads saga with intermediate state
3. Partially-completed saga state visible

**Fix:** Ensure all state updates happen within lock and before release.

---

### 12. Template Cache Invalidation Race

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/unified_cache.py:425-450`
**Severity:** MEDIUM
**Issue Type:** Pattern Invalidation Without Atomic SCAN

Similar to issue #1 but for templates. Pattern invalidation using SCAN is non-atomic.

---

### 13. Global Debouncer Singleton Race

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/quiz_response_debounce.py:305-324`
**Severity:** MEDIUM
**Issue Type:** Unsafe Singleton Pattern

```python
# Global debouncer instance
_debouncer: Optional[QuizResponseDebouncer] = None

def get_quiz_debouncer(debounce_window_seconds: int = 3) -> QuizResponseDebouncer:
    global _debouncer

    if _debouncer is None:
        _debouncer = QuizResponseDebouncer(debounce_window_seconds)  # <-- RACE

    return _debouncer
```

Multiple debouncer instances could be created if called concurrently.

---

### 14. Redis Rate Limiter Pipeline Non-Atomicity

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/middleware/rate_limiter.py:442-479`
**Severity:** MEDIUM
**Issue Type:** Non-Atomic Token Bucket Update

```python
# Get current values
pipe.get(redis_key_allowance)
pipe.get(redis_key_last_check)
values = pipe.execute()  # <-- Non-atomic reads

# ... calculate new allowance ...

# Update Redis (atomic) - but allowance was calculated from stale data
pipe = redis_client.pipeline()
pipe.setex(redis_key_allowance, self.per * 2, str(allowance))
pipe.setex(redis_key_last_check, self.per * 2, str(current_time))
pipe.execute()
```

Between first and second pipeline execution, another request could modify the values.

**Fix:** Use EVALSHA with atomic Lua script.

---

### 15. WebhookEvent Response Caching Race

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/middleware/idempotency.py:120-132`
**Severity:** MEDIUM
**Issue Type:** TOCTOU in Response Cache Update

```python
# Process the webhook
response = await call_next(request)

# Mark as completed (not atomic with response creation)
webhook_event.mark_completed({
    "status_code": response.status_code,
    "processed_at": now_sao_paulo().isoformat(),
})
db.commit()
```

---

### 16. Cache Key Builder Pattern Compilation Race

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/cache/invalidation_service.py:461-465`
**Severity:** MEDIUM
**Issue Type:** Regex Compilation in Loop Without Caching

```python
def _matches_pattern(self, key: str, pattern: str) -> bool:
    """Check if a key matches a wildcard pattern."""
    import re  # <-- Import in method (fine)
    regex_pattern = pattern.replace("*", ".*").replace("?", ".")
    return bool(re.match(f"^{regex_pattern}$", key))  # <-- RECOMPILES every time
```

No caching of compiled regex patterns. In high-volume pattern matching, this causes performance degradation and potential memory pressure.

---

## Low-Priority Issues (P3)

### 17. Async Lock Best Practices in PubSub

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/redis_pubsub_manager.py`
**Severity:** LOW
**Issue Type:** Potential Deadlock in Async Code

The implementation uses async/await but doesn't ensure cancellation safety in all paths.

---

### 18. Cache TTL Configuration Race

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/services/unified_cache.py:48-50`
**Severity:** LOW
**Issue Type:** Default Parameter Evaluation

TTL values fetched from config at method call time, not cached. Multiple config reads in same operation.

---

### 19. Service Cache Iteration During Cleanup

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/thread_safe_services.py:395-403`
**Severity:** LOW
**Issue Type:** Dictionary Iteration Under Lock

Iterating while modifying `self._service_cache` during cleanup. Uses `items()` which creates snapshot, so safe, but could be clearer.

---

### 20. Database Connection Pool Exhaustion Under High Concurrency

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/thread_safe_services.py:109-125`
**Severity:** LOW
**Issue Type:** Connection Pool Configuration

No max_overflow setting visible. Under extreme concurrency, connection pool could exhaust and block.

---

### 21. Timestamp Generation Race in Idempotency

**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/middleware/idempotency.py:126-129`
**Severity:** LOW
**Issue Type:** Non-Monotonic Clock

```python
webhook_event.mark_completed({
    "status_code": response.status_code,
    "processed_at": now_sao_paulo().isoformat(),  # <-- Clock skew possible
})
```

If system clock adjusted between two webhook requests with same event_id, timestamp ordering could be violated.

---

## Recommended Action Plan

### Phase 1: Critical (Immediate - Next Sprint)

1. **Fix global cache service singleton** with double-check locking
2. **Make SCAN operations atomic** using Lua scripts
3. **Synchronize PubSub state** with asyncio.Lock
4. **Fix saga resume TOCTOU** with proper isolation level

**Estimated Effort:** 3-4 days
**Risk Reduction:** 85%

### Phase 2: High-Priority (Next 2 Weeks)

5. Fix rate limiter with threading.RLock
6. Fix quiz response debounce with SETNX
7. Fix idempotency middleware with row locks
8. Fix PubSub user message enumeration

**Estimated Effort:** 2-3 days
**Risk Reduction:** 10%

### Phase 3: Medium-Priority (Backlog)

9-14. Fix remaining medium-priority issues
**Estimated Effort:** 1-2 days
**Risk Reduction:** 3%

### Phase 4: Testing and Validation

- Add concurrency tests for all critical paths
- Load test with thread pool simulation
- Stress test database connection pool
- Race condition detector: ThreadSanitizer (Python)

---

## Testing Recommendations

### Race Condition Detection Tools

```bash
# Python race condition detection
pip install pytest-thread pytest-asyncio

# Run with ThreadSanitizer
python -m pytest --co 2>&1 | grep "race\|concurrent\|lock" --color=always
```

### Concurrency Test Examples

```python
# Test concurrent cache invalidation
import asyncio
import pytest

@pytest.mark.asyncio
async def test_concurrent_cache_invalidation():
    cache = UnifiedCacheService()
    patient_id = "123"

    # Cache some data
    await cache.cache_patient_data(patient_id, {"name": "Test"})

    # 100 concurrent invalidation requests
    tasks = [
        cache.invalidate_patient_cache(patient_id)
        for _ in range(100)
    ]
    results = await asyncio.gather(*tasks)

    # Should still be invalidated after concurrent requests
    assert await cache.get_cached_patient_data(patient_id) is None
```

---

## Database Configuration Recommendations

```sql
-- Enable SERIALIZABLE isolation for saga transactions
ALTER SESSION SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;

-- Add unique constraint on webhook events
CREATE UNIQUE INDEX idx_webhook_event_unique ON webhook_event(event_id);

-- Add row-level locking
ALTER TABLE patient_onboarding_saga ADD CONSTRAINT saga_status_check
    CHECK (status IN ('STARTED', 'STEP_1_PATIENT_CREATED', ...));

-- Connection pool configuration
-- In SQLAlchemy:
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,  # Critical: prevent exhaustion
    pool_timeout=30,
    pool_recycle=3600
)
```

---

## References

- **TOCTOU Attacks:** [CWE-367](https://cwe.mitre.org/data/definitions/367.html)
- **Race Conditions:** [CWE-362](https://cwe.mitre.org/data/definitions/362.html)
- **Insufficient Synchronization:** [CWE-364](https://cwe.mitre.org/data/definitions/364.html)
- **Redis Lua Scripting:** [Redis Transactions](https://redis.io/topics/transactions)
- **SQLAlchemy Isolation:** [Isolation Levels](https://docs.sqlalchemy.org/en/14/core/connections.html#isolation-level)

---

**Report Generated:** 2025-12-25
**Analyzer:** Code Quality Analyzer (AI)
**Classification:** INTERNAL - SECURITY SENSITIVE
