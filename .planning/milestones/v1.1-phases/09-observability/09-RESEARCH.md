# Phase 9: Observability - Research

**Researched:** 2026-02-23
**Domain:** Celery metrics instrumentation, physician scheduling, WebSocket pub/sub multi-instance
**Confidence:** HIGH (all findings verified directly from codebase)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| OBS-01 | Remove hardcoded `avg_task_duration_seconds = 2.5` and instrument Celery task completion times with rolling average in Redis | Celery signal hooks already exist in `celery_metrics.py`; `task_postrun_handler` records duration to Prometheus Histogram. Need Redis-backed rolling average read by `check_worker_health()`. |
| OBS-02 | Implement `get_available_slots()` with real slot generation logic based on physician working hours | `get_available_slots()` returns empty list. No physician schedule/working-hours model exists — must define working hours inline as a simple configurable default (e.g., 08:00–17:00 weekdays) and generate slots by subtracting booked appointments. |
| OBS-03 | Verify and fix WebSocket scaling with Redis pub/sub for multi-instance | `RedisPubSubManager` exists and is initialized in lifespan, but calls `connection_manager.broadcast()` and `connection_manager.broadcast_to_room()` which do NOT exist on `UnifiedWebSocketConnectionManager`. API name mismatch breaks cross-instance delivery silently. |
</phase_requirements>

---

## Summary

Phase 9 addresses three independent observability gaps. Each gap requires targeted surgical changes to existing modules — no new architectural components are needed.

**OBS-01** is the simplest: a hardcoded float `2.5` in `check_worker_health()` inside `service_health.py` must be replaced by a Redis rolling average. The Celery signal infrastructure (`celery_metrics.py`) already captures per-task durations via `task_postrun_handler`, but stores them only in a Prometheus Histogram. A parallel Redis LPUSH/LTRIM rolling-list pattern must be added to the `task_postrun_handler`, and `check_worker_health()` must read from that list.

**OBS-02** is the most complex from a domain perspective: `get_available_slots()` fetches booked appointments correctly but then discards the result and returns an empty list (`available_slots = []`). There is no `PhysicianSchedule` or `WorkingHours` model in the database — the physician user model has no schedule fields. The implementation must define a default working-hours configuration (hardcoded or settings-driven) and generate time slots for each day in the requested range, filtering out any slots that overlap with existing appointments.

**OBS-03** has a clear structural bug: `RedisPubSubManager._handle_broadcast()` calls `self.connection_manager.broadcast()` and `_handle_room_message()` calls `self.connection_manager.broadcast_to_room()`, but `UnifiedWebSocketConnectionManager` exposes `broadcast_to_all_authenticated()` and `broadcast_to_patient_room()` respectively. Additionally, `_handle_user_message()` calls `self.connection_manager.send_personal_message()` which also does not exist (the actual method is `send_message()`). These three method name mismatches mean cross-instance WebSocket delivery silently fails with `AttributeError` at runtime.

**Primary recommendation:** Implement OBS-01 and OBS-03 first (both are narrow bug fixes), then OBS-02 (requires domain judgment on slot generation).

---

## Standard Stack

### Core (all already in project dependencies — no new installs needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `redis.asyncio` | project version | Redis LPUSH/LTRIM/LRANGE for rolling average | Already used throughout via `RedisManager` |
| `celery.signals` | project version | `task_postrun` hook to capture duration | Already connected in `celery_metrics.py` |
| `app.core.redis_manager` | internal | Canonical Redis client accessor | Established pattern: `from app.core.redis_manager import redis_manager` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `datetime` (stdlib) | — | Day iteration, time arithmetic for slot generation | OBS-02 slot generation |
| `time` (stdlib) | — | `time.time()` for duration measurement | Already used in `celery_metrics.py` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Redis LPUSH/LTRIM rolling list | Prometheus Histogram (existing) | Prometheus Histogram already captures distributions but cannot be read back as a simple average float without exposing a metrics scrape endpoint; Redis rolling list gives a cheap scalar read in `check_worker_health()` |
| Default working hours in code | New `physician_schedules` DB table | DB migration is heavy for a field that doesn't exist; `JSONB` column on User model is cleaner but also requires migration; simplest correct approach is configurable defaults with hardcoded fallback for v1.1 |

**Installation:** None required — all dependencies already present.

---

## Architecture Patterns

### OBS-01: Rolling Average Pattern (Redis LPUSH/LTRIM/LRANGE)

**What:** On every `task_postrun`, push duration to a Redis list capped at N entries. `check_worker_health()` reads the list and computes mean.

**Key:** `celery:metrics:task_duration_samples` (global across all task names, for a single average scalar). Alternatively keyed per task name, but the health endpoint wants one number.

**Redis DB:** Use DB 0 (broker) or DB 1 (cache). Given this is an observability metric (not a task), DB 1 (cache) is appropriate per project convention.

**Pattern:**
```python
# In task_postrun_handler (celery_metrics.py) — after existing Prometheus observe:
async def _push_duration_to_redis(duration: float) -> None:
    """Push task duration to Redis rolling list (fire-and-forget)."""
    try:
        client = await redis_manager.get_async_client()
        key = "celery:metrics:avg_task_duration"
        pipe = client.pipeline()
        pipe.lpush(key, duration)
        pipe.ltrim(key, 0, 99)   # Keep last 100 samples
        pipe.expire(key, 86400)  # 24h TTL
        await pipe.execute()
    except Exception:
        pass  # Metrics must never crash task execution

# In check_worker_health() (service_health.py) — replace hardcoded 2.5:
async def _read_avg_task_duration() -> float:
    """Read rolling average task duration from Redis."""
    try:
        client = await redis_manager.get_async_client()
        samples = await client.lrange("celery:metrics:avg_task_duration", 0, -1)
        if not samples:
            return 0.0
        durations = [float(s) for s in samples]
        return round(sum(durations) / len(durations), 3)
    except Exception:
        return 0.0
```

**Note:** `task_postrun_handler` is a synchronous Celery signal handler. Redis push must be done via `asyncio.run()` or better via the sync Redis client. Use `redis_manager.get_sync_client()` (if available) or create a dedicated sync call. Alternatively, call the async function from a background thread-safe wrapper. The simplest approach: use the sync Redis client from `redis_manager`.

**Sync-in-signal constraint:** Celery signal handlers (`@task_postrun.connect`) run in the worker process synchronously. The project uses `redis-py` which has both sync and async clients. Use `redis_manager.get_sync_client()` or a new sync Redis client using `redis.Redis` with connection pool — NOT `await`. The existing `celery_metrics.py` is already fully synchronous; stay consistent.

### OBS-02: Slot Generation Pattern

**What:** Generate all possible time slots for each date in `[start_date, end_date]`, subtract booked appointments, return remaining slots.

**Working hours:** No database model exists. Use a hardcoded default: Monday–Friday, 08:00–17:00, 30-minute slots. This is explicitly a simplification for v1.1 — the TODO comment in the code acknowledges this.

**Pattern:**
```python
def get_available_slots(
    self,
    physician_id: UUID,
    start_date: date,
    end_date: date,
    slot_duration_minutes: int = 30,
) -> List[Dict[str, Any]]:
    # 1. Fetch booked appointments (already implemented — remove the _ = discard)
    booked = self.db.query(Appointment).filter(...).all()
    booked_times = {appt.scheduled_at for appt in booked}

    # 2. Define working hours (default, no DB needed for v1.1)
    WORK_START = time(8, 0)
    WORK_END = time(17, 0)
    WORK_DAYS = {0, 1, 2, 3, 4}  # Mon–Fri (weekday() values)

    # 3. Iterate each day in range
    available_slots = []
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() in WORK_DAYS:
            current_slot = datetime.combine(current_date, WORK_START, tzinfo=timezone.utc)
            end_of_day = datetime.combine(current_date, WORK_END, tzinfo=timezone.utc)
            while current_slot + timedelta(minutes=slot_duration_minutes) <= end_of_day:
                # Check if slot overlaps any booked appointment
                if not _overlaps_any(current_slot, slot_duration_minutes, booked):
                    available_slots.append({
                        "start": current_slot.isoformat(),
                        "end": (current_slot + timedelta(minutes=slot_duration_minutes)).isoformat(),
                        "duration_minutes": slot_duration_minutes,
                    })
                current_slot += timedelta(minutes=slot_duration_minutes)
        current_date += timedelta(days=1)

    return available_slots
```

**Timezone:** Use `now_sao_paulo()` / `timezone.utc` consistently with the rest of the codebase. The appointment model stores `scheduled_at` as `DateTime(timezone=True)`. Combine `date` + `time` with the same timezone for correct overlap comparison.

### OBS-03: WebSocket API Method Name Fixes

**What:** Three method calls in `RedisPubSubManager` reference methods that do not exist on `UnifiedWebSocketConnectionManager`.

**Exact mismatches:**

| RedisPubSubManager calls | Actual method on UnifiedWebSocketConnectionManager |
|--------------------------|---------------------------------------------------|
| `self.connection_manager.broadcast(payload)` | `await self.connection_manager.broadcast_to_all_authenticated(payload)` |
| `self.connection_manager.broadcast_to_room(room_id, payload)` | `await self.connection_manager.broadcast_to_patient_room(room_id, payload)` |
| `self.connection_manager.send_personal_message(payload, conn_id)` | `await self.connection_manager.send_message(conn_id, payload)` (note: argument order reversed) |

**Fix location:** `backend-hormonia/app/services/redis_pubsub_manager.py` — three handler methods:
- `_handle_broadcast()` line ~309
- `_handle_room_message()` line ~320
- `_handle_user_message()` lines ~333–342

**The `_handle_user_message` method also has a logic gap:** it iterates `self.connection_manager.connections.items()` expecting `conn_data.get("user_id")` but `connections` now contains `ConnectionInfo` dataclass objects, not raw dicts. The lookup must use `conn_data.user_id` (attribute access) instead of `conn_data.get("user_id")`.

**After fix, `_handle_user_message` pattern:**
```python
async def _handle_user_message(self, user_id: str, data: Dict[str, Any]):
    payload = data.get("payload", {})
    # Use the manager's dedicated broadcast method directly
    await self.connection_manager.broadcast_to_user(user_id, payload)
```

**Note:** `broadcast_to_user` already exists and handles the user_id → connection_ids lookup correctly.

### Anti-Patterns to Avoid

- **Do not call `redis.keys()` pattern-match** — use `scan_iter()` or direct key access. Project rule: never use `redis.keys()`.
- **Do not add async code to synchronous Celery signal handlers** without a sync Redis client. Celery workers run in their own event loop context; mixing `asyncio.run()` is fragile.
- **Do not create a new Redis client in `celery_metrics.py`** — use `redis_manager` (canonical module per project patterns).
- **Do not add a DB migration for physician working hours** in v1.1 — hardcoded defaults are explicitly acceptable per requirement scope.
- **Do not change the public API of `UnifiedWebSocketConnectionManager`** — only fix the callers in `redis_pubsub_manager.py`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rolling average storage | Custom circular buffer class | Redis LPUSH + LTRIM | Redis natively handles bounded list with O(1) push+trim |
| Task duration capture | New Celery task wrapper | Existing `task_postrun` signal handler | Signal handler already fires for all tasks |
| Slot overlap detection | Interval tree / segment tree | Simple `for` loop over booked list | Date ranges are small (≤ 90 days × ~18 slots/day = ≤ 1620 slots) |

**Key insight:** All three OBS requirements are fixes to existing code, not new systems. The infrastructure (Celery signals, Redis manager, RedisPubSubManager, connection manager) already exists — the gaps are: a missing Redis write, a missing slot generation loop, and three wrong method names.

---

## Common Pitfalls

### Pitfall 1: Sync vs Async in Celery Signal Handler (OBS-01)
**What goes wrong:** Calling `await` inside `@task_postrun.connect` handler causes `RuntimeError: no current event loop`.
**Why it happens:** Celery workers run their own event loop; signal handlers are sync callbacks.
**How to avoid:** Use the sync Redis client. Pattern: `redis_manager.get_sync_client()` if available, otherwise instantiate `redis.Redis(...)` with the same URL and use it synchronously. Alternatively, use `asyncio.run()` in a thread-safe way — but this is fragile. Simplest: sync Redis call.
**Warning signs:** `RuntimeError: no running event loop` in Celery worker logs.

### Pitfall 2: Redis DB Selection (OBS-01)
**What goes wrong:** Writing to DB 0 (broker) contaminates the broker namespace; writing without TTL leaks memory.
**Why it happens:** Multiple Redis databases have different semantics in the project.
**How to avoid:** Write to DB 1 (cache) with explicit `expire(key, 86400)`. Key: `celery:metrics:avg_task_duration`.
**Warning signs:** Key appears in broker namespace and confuses Celery inspect.

### Pitfall 3: Timezone-naive vs timezone-aware datetime comparison (OBS-02)
**What goes wrong:** `datetime.combine(date, time)` produces timezone-naive datetimes; comparing with `appointment.scheduled_at` (stored as timezone-aware) raises `TypeError`.
**Why it happens:** PostgreSQL `DateTime(timezone=True)` returns timezone-aware objects; Python `datetime.combine()` defaults to naive.
**How to avoid:** Use `datetime.combine(current_date, WORK_START).replace(tzinfo=timezone.utc)` or use `now_sao_paulo()` timezone pattern. Check how `availability_service.py` already does this — it uses `time.min` and `time.max` for query boundaries; do the same for generated slots.
**Warning signs:** `TypeError: can't compare offset-naive and offset-aware datetimes` in slot generation.

### Pitfall 4: ConnectionInfo is a dataclass, not a dict (OBS-03)
**What goes wrong:** `conn_data.get("user_id")` raises `AttributeError` because `ConnectionInfo` is a dataclass.
**Why it happens:** `RedisPubSubManager._handle_user_message` was written against the old dict-based connection storage; `UnifiedWebSocketConnectionManager` stores `ConnectionInfo` objects.
**How to avoid:** Use `broadcast_to_user(user_id, payload)` directly — it handles the lookup internally. Do not iterate `connections` dict manually.
**Warning signs:** `AttributeError: 'ConnectionInfo' object has no attribute 'get'` in logs when user-targeted pub/sub messages arrive.

### Pitfall 5: Echo prevention in pub/sub (OBS-03)
**What goes wrong:** Instance publishes a message to Redis, then receives its own message and re-broadcasts locally, causing duplicate delivery.
**Why it happens:** All instances subscribe to the same channels.
**How to avoid:** The existing `_handle_pubsub_message()` already implements echo prevention via `if data.get("instance_id") == self.instance_id: return`. This is CORRECT — do not remove it when fixing method names.
**Warning signs:** Clients receive every broadcast event twice.

---

## Code Examples

Verified patterns from codebase:

### Existing Celery signal handler pattern (celery_metrics.py lines 359–387)
```python
# Source: backend-hormonia/app/tasks/celery_metrics.py
@task_postrun.connect
def task_postrun_handler(
    sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, **extra
):
    try:
        task_name = _resolve_task_name(sender=sender, task=task)
        _finalize_task_metadata(
            task_id=task_id,
            fallback_task_name=task_name,
            observe_duration=True,  # <-- This observes Prometheus Histogram
        )
    except Exception as e:
        logger.error(f"Error in task_postrun_handler: {e}", exc_info=True)
```

**For OBS-01:** After `_finalize_task_metadata`, add synchronous Redis LPUSH to record duration.

### Canonical Redis client access pattern
```python
# Source: project MEMORY.md canonical pattern
# Sync pattern (for use in Celery signal handlers):
from app.core.redis_manager import redis_manager
client = redis_manager.get_client()  # sync client

# Async pattern (for use in FastAPI route handlers):
client = await redis_manager.get_async_client()
```

### Appointment query pattern already in get_available_slots
```python
# Source: backend-hormonia/app/api/v2/routers/physicians/services/availability_service.py:59-71
booked = self.db.query(Appointment).filter(
    Appointment.practitioner_id == physician_id,
    Appointment.scheduled_at >= datetime.combine(start_date, time.min),
    Appointment.scheduled_at <= datetime.combine(end_date, time.max),
    Appointment.status.in_([
        AppointmentStatus.SCHEDULED.value,
        AppointmentStatus.CONFIRMED.value,
        AppointmentStatus.IN_PROGRESS.value,
    ]),
).order_by(Appointment.scheduled_at).all()
# NOTE: Result is currently discarded (not assigned to variable). Must fix.
```

### Correct UnifiedWebSocketConnectionManager broadcast methods
```python
# Source: backend-hormonia/app/services/websocket/connection_manager.py
# These are the ACTUAL method signatures:
await manager.broadcast_to_all_authenticated(message: Dict[str, Any]) -> int
await manager.broadcast_to_patient_room(patient_id: str, message: Dict[str, Any]) -> int
await manager.broadcast_to_user(user_id: str, message: Dict[str, Any]) -> int
await manager.send_message(connection_id: str, message: Dict[str, Any]) -> bool
```

### RedisPubSubManager broken calls (lines to fix)
```python
# Source: backend-hormonia/app/services/redis_pubsub_manager.py

# BROKEN (line ~309):
await self.connection_manager.broadcast(payload)
# FIX:
await self.connection_manager.broadcast_to_all_authenticated(payload)

# BROKEN (line ~320):
await self.connection_manager.broadcast_to_room(room_id, payload)
# FIX:
await self.connection_manager.broadcast_to_patient_room(room_id, payload)

# BROKEN (lines ~333-342) — also uses dict-access on ConnectionInfo:
user_connections = [
    conn_id
    for conn_id, conn_data in self.connection_manager.connections.items()
    if conn_data.get("user_id") == user_id
]
for conn_id in user_connections:
    await self.connection_manager.send_personal_message(payload, conn_id)
# FIX (use existing broadcast_to_user which handles lookup correctly):
await self.connection_manager.broadcast_to_user(user_id, payload)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded metric `avg_task_duration_seconds = 2.5` | Redis rolling average from real task executions | OBS-01 | Health endpoint returns real data |
| `get_available_slots()` returns `[]` silently | Real slot list minus booked appointments | OBS-02 | Scheduler can actually query availability |
| Pub/sub messages routed to non-existent methods | Correct method names matched to API | OBS-03 | Multi-instance WebSocket delivery works |

**No deprecated libraries involved.** All changes are within existing Python/Redis/FastAPI/Celery stack.

---

## Open Questions

1. **Redis sync client availability for Celery workers (OBS-01)**
   - What we know: `redis_manager` has `get_async_client()`. The `app/core/redis_manager/manager.py` is the canonical client.
   - What's unclear: Whether `redis_manager` exposes a synchronous `.get_client()` or `.get_sync_client()` method, or only async.
   - Recommendation: Read `app/core/redis_manager/manager.py` before writing the plan for OBS-01. If only async is available, the rolling-average write from `task_postrun_handler` must use `redis.Redis` directly (sync) with the same `REDIS_URL` env var. Document this in the plan as a known implementation detail.

2. **Physician working hours scope for OBS-02**
   - What we know: No `working_hours` field exists on `User` model or any related model. The requirement says "based on physician configured working hours" but there is nothing to configure.
   - What's unclear: Whether the v1.1 requirement means (a) implement slot generation with a hardcoded default schedule, or (b) also add some configuration mechanism.
   - Recommendation: Implement with a hardcoded default (Mon–Fri 08:00–17:00, 30-min slots) controlled by module-level constants. The original TODO comment in the code says "this would typically come from physician preferences/settings" — interpret this as out of scope for v1.1. Add a comment explaining where per-physician config would plug in.

3. **WebSocket pub/sub test strategy for OBS-03**
   - What we know: The `_handle_user_message` fix is straightforward; unit tests exist for `connection_manager` (not for `redis_pubsub_manager`).
   - What's unclear: Whether there are integration tests that simulate two-instance pub/sub.
   - Recommendation: Unit-test the three handler methods with a mock `connection_manager` that verifies the correct methods are called with correct arguments. No actual two-instance test needed for v1.1 — that's an integration/infra concern.

---

## Sources

### Primary (HIGH confidence — all verified from direct codebase reading)

- `backend-hormonia/app/api/v2/routers/health/service_health.py:129` — hardcoded `avg_task_duration_seconds=2.5` exact location
- `backend-hormonia/app/schemas/v2/health.py:173,184` — `WorkerHealth` schema with hardcoded example
- `backend-hormonia/app/tasks/celery_metrics.py:359-387` — existing `task_postrun_handler` signal infrastructure
- `backend-hormonia/app/api/v2/routers/physicians/services/availability_service.py:38-77` — `get_available_slots()` full implementation showing empty-return bug
- `backend-hormonia/app/models/user.py` — `User` model has no working-hours fields
- `backend-hormonia/app/models/appointment.py` — `Appointment` model structure
- `backend-hormonia/app/services/websocket/connection_manager.py` — `UnifiedWebSocketConnectionManager` actual method names
- `backend-hormonia/app/services/redis_pubsub_manager.py:301-342` — broken method calls in three handlers
- `backend-hormonia/app/core/lifespan.py:492-541` — pub/sub manager IS initialized in lifespan (startup path exists)
- `backend-hormonia/app/services/websocket_events.py` — `WebSocketEventService` uses local `connection_manager` only (does not go through pub/sub)
- Project MEMORY.md — canonical patterns for Redis client, Redis key naming

### Secondary (MEDIUM confidence — from project documentation)

- `backend-hormonia/docs/reports/performance/redis-performance-compendium.md:32` — documents `RedisPubSubManager` as "Risk: Bypasses RedisManager to create own client"
- `.planning/STATE.md:52-53` — confirms the two research flags that motivated this investigation

---

## Key Findings Summary

1. **OBS-01 hardcode location:** `service_health.py` line 129, function `check_worker_health()`. The Celery signal infrastructure in `celery_metrics.py` already measures task durations for Prometheus — a Redis write must be added to `task_postrun_handler` and a Redis read added to `check_worker_health()`.

2. **OBS-02 root cause:** `get_available_slots()` fetches appointments correctly but discards the query result (`_ = slot_duration_minutes` discards the slot duration param, and the query result is not assigned). No physician schedule model exists — implement with hardcoded Mon–Fri 08:00–17:00 defaults.

3. **OBS-03 root cause:** Three method names in `redis_pubsub_manager.py` do not match `UnifiedWebSocketConnectionManager`'s API. The pub/sub manager IS started in lifespan correctly, but all cross-instance message delivery silently fails with `AttributeError`. Fix requires changing 3 method call sites.

4. **No new dependencies, no DB migrations required** for any of the three requirements.

5. **Sync/async boundary** is the main implementation risk for OBS-01: Celery signal handlers are synchronous; Redis writes must use sync client.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project, verified from imports
- Architecture patterns: HIGH — verified from actual code reading, method signatures confirmed
- Pitfalls: HIGH — timezone, sync/async, and method name issues all directly observed in source

**Research date:** 2026-02-23
**Valid until:** 2026-03-23 (stable codebase, no fast-moving dependencies)
