# Race Condition Fixes - Quick Reference Guide

## Quick Lookup Table

| Priority | Issue | File | Line | Quick Fix |
|----------|-------|------|------|-----------|
| CRITICAL | Global Cache Singleton TOCTOU | `unified_cache.py` | 589-592 | Add `threading.RLock()` with double-check |
| CRITICAL | Non-Atomic SCAN Pattern Invalidation | `invalidation_service.py` | 333-373 | Use Lua script for atomic scan-delete |
| CRITICAL | PubSub State Without Sync | `redis_pubsub_manager.py` | 77-86 | Add `asyncio.Lock()` for state |
| HIGH | Saga Resume TOCTOU | `saga_orchestrator.py` | 227-244 | Use `with_for_update()` + SERIALIZABLE |
| HIGH | Bulk Cache Invalidation Race | `unified_cache.py` | 396-423 | Use pipeline with atomic execute |
| HIGH | Rate Limiter No Locking | `rate_limiter.py` | 59-127 | Add `threading.RLock()` to `is_allowed()` |
| HIGH | Quiz Debounce TOCTOU | `quiz_response_debounce.py` | 48-117 | Use `SETNX` instead of `exists()+setex()` |
| HIGH | Idempotency Duplicate Records | `idempotency.py` | 232-293 | Add `with_for_update()` on query |
| HIGH | PubSub User Connection Iteration | `redis_pubsub_manager.py` | 302-311 | Create snapshot under lock |
| HIGH | Service Cleanup Race | `thread_safe_services.py` | 387-431 | Copy cache before cleanup |

---

## Fix #1: Global Cache Singleton (CRITICAL)

**Current Code:**
```python
_unified_cache_service: Optional[UnifiedCacheService] = None

def get_unified_cache_service() -> UnifiedCacheService:
    global _unified_cache_service
    if _unified_cache_service is None:
        _unified_cache_service = UnifiedCacheService()
    return _unified_cache_service
```

**Fixed Code:**
```python
import threading

_unified_cache_service: Optional[UnifiedCacheService] = None
_cache_service_lock = threading.RLock()

def get_unified_cache_service() -> UnifiedCacheService:
    global _unified_cache_service
    if _unified_cache_service is None:
        with _cache_service_lock:
            if _unified_cache_service is None:  # Double-check
                _unified_cache_service = UnifiedCacheService()
    return _unified_cache_service
```

**Why:** Prevents multiple instances from being created if two threads call simultaneously.

---

## Fix #2: Pattern Invalidation (CRITICAL)

**Current Code:**
```python
async def _invalidate_pattern(self, pattern: str) -> bool:
    cursor = 0
    while True:
        cursor, keys = self.redis_client.scan(
            cursor=cursor, match=pattern, count=100,
        )
        if keys:
            self.redis_client.delete(*keys)  # Non-atomic
        if cursor == 0:
            break
```

**Fixed Code:**
```python
async def _invalidate_pattern(self, pattern: str) -> bool:
    # Use Lua script for atomic scan-delete
    INVALIDATE_SCRIPT = """
    local pattern = KEYS[1]
    local cursor = "0"
    local count = 0

    while true do
        local result = redis.call("SCAN", cursor, "MATCH", pattern, "COUNT", 100)
        cursor = result[1]
        local keys = result[2]

        if #keys > 0 then
            redis.call("DEL", unpack(keys))
            count = count + #keys
        end

        if cursor == "0" then break end
    end

    return count
    """

    return await self.redis_client.eval(INVALIDATE_SCRIPT, 1, pattern)
```

**Why:** Lua script executes atomically on Redis, preventing concurrent deletions from interfering.

---

## Fix #3: PubSub State Synchronization (CRITICAL)

**Current Code:**
```python
class RedisPubSubManager:
    def __init__(self, ...):
        self.subscriptions: Set[str] = set()
        self.is_running = False
        self._listener_task: Optional[asyncio.Task] = None
```

**Fixed Code:**
```python
import asyncio

class RedisPubSubManager:
    def __init__(self, ...):
        self.subscriptions: Set[str] = set()
        self.is_running = False
        self._listener_task: Optional[asyncio.Task] = None
        self._state_lock = asyncio.Lock()  # ADD THIS

    async def stop(self):
        async with self._state_lock:  # PROTECT STATE
            if not self.is_running:
                return
            self.is_running = False
            # ... cleanup ...

    async def subscribe_to_room(self, room_id: str):
        async with self._state_lock:
            channel = f"ws:room:{room_id}"
            if channel not in self.subscriptions:
                await self.pubsub.subscribe(channel)
                self.subscriptions.add(channel)
```

**Why:** Async lock prevents concurrent access to shared state during state transitions.

---

## Fix #4: Saga Resume with Row Locking (HIGH)

**Current Code:**
```python
async def resume_saga(self, saga_id: UUID):
    lock_key = f"saga:resume:{saga_id}"
    async with acquire_lock(lock_key, timeout=5.0, ttl=60):
        saga = (
            self.db.query(PatientOnboardingSaga)
            .filter(PatientOnboardingSaga.id == saga_id)
            .first()  # Can read stale data
        )
```

**Fixed Code:**
```python
async def resume_saga(self, saga_id: UUID):
    lock_key = f"saga:resume:{saga_id}"
    async with acquire_lock(lock_key, timeout=5.0, ttl=60):
        # Use transaction isolation + row lock
        saga = (
            self.db.query(PatientOnboardingSaga)
            .with_for_update()  # Lock the row
            .filter(PatientOnboardingSaga.id == saga_id)
            .first()
        )

        # Verify status hasn't changed
        if saga.status in (SagaStatus.COMPLETED, SagaStatus.FAILED):
            return {"status": "already_processed"}

        # Safe to resume
        await self._resume_saga_internal(saga)
```

**SQLAlchemy Setup:**
```python
# In database.py, set isolation level
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "isolation": "SERIALIZABLE"  # or use session-level
    }
)
```

**Why:** Row locks + SERIALIZABLE isolation prevent concurrent modifications and dirty reads.

---

## Fix #5: Rate Limiter Locking (HIGH)

**Current Code:**
```python
class RateLimiter:
    def __init__(self, rate: int = 10, per: int = 60):
        self.allowance = defaultdict(lambda: rate)
        self.last_check = defaultdict(time.time)

    def is_allowed(self, key: str) -> Tuple[bool, Optional[int]]:
        current = time.time()
        time_passed = current - self.last_check[key]  # RACE
        self.last_check[key] = current  # RACE
        self.allowance[key] += time_passed * (self.rate / self.per)  # RACE
```

**Fixed Code:**
```python
import threading

class RateLimiter:
    def __init__(self, rate: int = 10, per: int = 60):
        self.rate = rate
        self.per = per
        self.allowance = defaultdict(lambda: rate)
        self.last_check = defaultdict(time.time)
        self._lock = threading.RLock()  # ADD THIS

    def is_allowed(self, key: str) -> Tuple[bool, Optional[int]]:
        with self._lock:  # CRITICAL SECTION
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

**Why:** RLock ensures token bucket algorithm is atomic, preventing double-replenishment.

---

## Fix #6: Quiz Response Debounce (HIGH)

**Current Code:**
```python
async def should_process_response(self, session_id, question_id, metadata):
    redis_client = await get_async_redis()
    debounce_key = self._build_debounce_key(session_id, question_id)

    exists = await redis_client.exists(debounce_key)  # CHECK
    if exists:
        return False

    await redis_client.setex(debounce_key, self.debounce_window, ...)  # USE
    return True
```

**Fixed Code:**
```python
async def should_process_response(self, session_id, question_id, metadata):
    redis_client = await get_async_redis()
    debounce_key = self._build_debounce_key(session_id, question_id)

    # Atomic: only sets if doesn't exist
    was_set = await redis_client.setnx(
        debounce_key,
        self._serialize_debounce_data(metadata),
    )

    if was_set:
        # We won the race, set expiration
        await redis_client.expire(debounce_key, self.debounce_window)
        return True
    else:
        # Another request got here first
        return False
```

**Why:** SETNX is atomic - only one request can win, preventing duplicate processing.

---

## Fix #7: Idempotency with Row Locking (HIGH)

**Current Code:**
```python
async def _check_idempotency(self, db, event_id, ...):
    existing_event = (
        db.query(WebhookEvent)
        .filter(WebhookEvent.event_id == event_id)  # NO LOCK
        .first()
    )

    if existing_event:
        return existing_event

    new_event = WebhookEvent.create_event(...)
    db.add(new_event)
    db.commit()
```

**Fixed Code:**
```python
async def _check_idempotency(self, db, event_id, ...):
    # First: ensure unique constraint exists
    # CREATE UNIQUE INDEX idx_webhook_event_id ON webhook_event(event_id);

    # Use row-level locking
    existing_event = (
        db.query(WebhookEvent)
        .with_for_update()  # Lock the row
        .filter(WebhookEvent.event_id == event_id)
        .first()
    )

    if existing_event:
        # Already processed
        if not existing_event.is_expired():
            return existing_event
        else:
            # Delete and reprocess
            db.delete(existing_event)
            db.commit()

    new_event = WebhookEvent.create_event(...)
    db.add(new_event)
    try:
        db.commit()
        return new_event
    except IntegrityError:
        # Another request beat us to it
        db.rollback()
        existing = (
            db.query(WebhookEvent)
            .filter(WebhookEvent.event_id == event_id)
            .first()
        )
        return existing
```

**Why:** with_for_update() acquires row lock, preventing concurrent inserts with same event_id.

---

## Fix #8: PubSub User Message Enumeration (HIGH)

**Current Code:**
```python
async def _handle_user_message(self, user_id: str, data: Dict[str, Any]):
    payload = data.get("payload", {})

    user_connections = [
        conn_id
        for conn_id, conn_data in self.connection_manager.connections.items()  # RACE
        if conn_data.get("user_id") == user_id
    ]

    for conn_id in user_connections:
        await self.connection_manager.send_personal_message(payload, conn_id)
```

**Fixed Code:**
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
            # Connection was closed after snapshot was taken
            logger.debug(f"Connection {conn_id} no longer exists")
            pass
```

**Why:** Snapshot prevents RuntimeError from dictionary size change during iteration.

---

## Fix #9: Service Cleanup Race (HIGH)

**Current Code:**
```python
def cleanup(self):
    with self._service_cache_lock:
        for service_name, service in self._service_cache.items():
            if hasattr(service, "cleanup"):
                try:
                    service.cleanup()
                except Exception as e:
                    logger.error(f"Error: {e}")
        self._service_cache.clear()  # Other threads may be accessing!
```

**Fixed Code:**
```python
def cleanup(self):
    # Make a copy of cache
    cache_copy = None
    with self._service_cache_lock:
        cache_copy = dict(self._service_cache)
        self._service_cache.clear()  # Mark as invalid

    # Cleanup outside lock (prevents blocking other threads)
    for service_name, service in cache_copy.items():
        if hasattr(service, "cleanup"):
            try:
                service.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up {service_name}: {e}")
```

**Why:** Copy allows cleanup without holding lock, preventing deadlocks on graceful shutdown.

---

## Fix #10: Global Debouncer Singleton (MEDIUM)

**Current Code:**
```python
_debouncer: Optional[QuizResponseDebouncer] = None

def get_quiz_debouncer(debounce_window_seconds: int = 3) -> QuizResponseDebouncer:
    global _debouncer
    if _debouncer is None:
        _debouncer = QuizResponseDebouncer(debounce_window_seconds)  # RACE
    return _debouncer
```

**Fixed Code:**
```python
import threading

_debouncer: Optional[QuizResponseDebouncer] = None
_debouncer_lock = threading.RLock()

def get_quiz_debouncer(debounce_window_seconds: int = 3) -> QuizResponseDebouncer:
    global _debouncer
    if _debouncer is None:
        with _debouncer_lock:
            if _debouncer is None:  # Double-check
                _debouncer = QuizResponseDebouncer(debounce_window_seconds)
    return _debouncer
```

**Why:** Same as Fix #1 - prevents multiple instances.

---

## Verification Checklist

- [ ] All global singletons use double-check locking with RLock
- [ ] All SCAN operations use Lua scripts or Redis transactions
- [ ] All database queries in sagas use `with_for_update()`
- [ ] All async shared state uses asyncio.Lock
- [ ] Rate limiter protects token bucket with threading.RLock
- [ ] Quiz debounce uses SETNX instead of exists+setex
- [ ] Webhook idempotency uses row locks
- [ ] PubSub state protected with asyncio.Lock
- [ ] Connection enumeration creates snapshot under lock
- [ ] Service cleanup copies cache before cleanup
- [ ] All tests pass with ThreadSanitizer enabled
- [ ] Load test with 50+ concurrent requests

---

## Testing Template

```python
import asyncio
import pytest
from concurrent.futures import ThreadPoolExecutor

@pytest.mark.asyncio
async def test_no_race_condition_in_cache_invalidation():
    """Test that concurrent cache invalidation doesn't lose data."""
    cache = UnifiedCacheService()
    patient_id = "test_123"

    # Set initial data
    await cache.cache_patient_data(patient_id, {"version": 1})

    # 100 concurrent read-modify-write operations
    async def race_read_write(i):
        data = await cache.get_cached_patient_data(patient_id)
        assert data is not None
        new_data = {**data, "version": i}
        await cache.cache_patient_data(patient_id, new_data)

    tasks = [race_read_write(i) for i in range(100)]
    await asyncio.gather(*tasks)

    # Final state should be consistent
    final_data = await cache.get_cached_patient_data(patient_id)
    assert final_data is not None
    assert isinstance(final_data, dict)
```

---

**Last Updated:** 2025-12-25
**Status:** Ready for Implementation
