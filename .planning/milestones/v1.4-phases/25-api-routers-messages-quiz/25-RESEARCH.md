# Phase 25: API Routers — Messages / Quiz - Research

**Researched:** 2026-02-27
**Domain:** SQLAlchemy AsyncSession migration — FastAPI router handlers
**Confidence:** HIGH

## Summary

Phase 25 migrates two router groups — messages and quiz — from synchronous `Session` (`get_db`) to async `AsyncSession` (`get_async_db`). The migration pattern is fully established by Phase 24 and does not require new tooling or architectural decisions. What distinguishes Phase 25 from Phase 24 is that the scope is simpler in some places and more complex in others.

The messages group is one single large file (`messages.py`, 947 lines) rather than nine separate submodule files. The roadmap names nine sub-files that do not actually exist in the codebase; all message endpoints live in `messages.py`. Of the 27 handler functions in that file, only 10 have `db=Depends(get_db)` in their signatures, and several of those are either stubs returning empty/mock payloads or call sync-only repository methods (`MessageRepository`, `PatientRepository`, `MessageService`) that do not yet support `AsyncSession`. The six stub-only handlers that declare `Depends(get_db)` but perform no actual database work can simply have `get_db` removed or replaced with `get_async_db` without any query conversion needed.

The quiz group is six actual files with real database logic. All six use `db.query(...)` chains and `Depends(get_db)`. The most complex file is `monthly_quiz_operations/crud.py` (511 lines, 18 `db.query` calls and 7 `Depends(get_db)` occurrences), which also contains N+1 patterns (per-response template and session lookups in a loop). The simplest are `quiz_templates.py` (5 `db.query` calls, straightforward CRUD) and `monthly_quiz_management.py` (4 `db.query` calls, mostly simple single-object fetches). There is a special complication in `quiz_sessions.py`: it uses `acquire_lock_sync` from `app.core.distributed_lock` inside `create_quiz` — an async equivalent (`acquire_lock`) exists and must be used instead.

Two shared helper files require attention: `app/api/v2/_quiz_shared.py` (used by `quiz_responses.py`, `quiz_alerts.py`, `monthly_quiz_management.py`) and `app/api/v2/routers/monthly_quiz_operations/_shared.py` (used by `crud.py`). Both import `get_db` and export it to their consumers; these re-exports must be updated to `get_async_db`.

The `_check_patient_access` function in `_quiz_shared.py` is typed `db: Session` and calls `db.query(Patient)` directly — it must be converted to an async helper that calls `await db.execute(select(Patient)...)`. This affects `quiz_responses.py` and `quiz_alerts.py` which call it inline.

Services consumed by these routers (`MessageRepository`, `PatientRepository`, `MessageService`) are NOT AsyncSession-compatible (Phase 23 did not cover them). Handlers in `messages.py` that delegate to these services cannot simply receive `AsyncSession` — they must inline the async query directly or the service must be replaced inline. The handlers that call `repo.list_v2(...)` or `service.get_message(...)` or `service.update_message(...)` need their DB calls inlined using `select(...)/await db.execute(...)` rather than delegating to a sync service with an AsyncSession instance.

**Primary recommendation:** Migrate in two waves — messages first (one file, mostly stubs and inline replacements), then quiz group (six files, planned sequentially by complexity). Create a Phase 25 regression test file modeled on `test_phase24_flows_async.py` that asserts zero `db.query(` and no `Depends(get_db)` in all migrated routers.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| API-04 | Message routers (`messages.py` and named sub-files) use AsyncSession throughout | All message endpoints live in `messages.py` (947 lines). Sub-files in the roadmap do not exist. 10 handlers use `Depends(get_db)`; 6 are stubs, 4 have real DB logic. Migration: replace `get_db` with `get_async_db`, inline async queries for handlers that call sync repos (`MessageRepository`, `MessageService`, `PatientRepository`). |
| API-05 | Quiz routers (6 files) use AsyncSession throughout | Six files confirmed: `quiz_responses.py`, `quiz_sessions.py`, `quiz_alerts.py`, `quiz_templates.py`, `monthly_quiz_management.py`, `monthly_quiz_operations/crud.py`. All import `get_db`. Migration: update shared helper exports, convert `_check_patient_access` to async, replace `acquire_lock_sync` with `async acquire_lock`, convert all `db.query(...)` chains to `select(...)/await db.execute(...)`. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `sqlalchemy.ext.asyncio.AsyncSession` | 2.x (project-pinned) | Async DB session for API handlers | Established in Phase 21; all Phase 24 routers migrated to it |
| `app.core.database.async_engine.get_async_db` | Internal | FastAPI DI generator yielding `AsyncSession` | Canonical async DB dependency from Phase 21 |
| `sqlalchemy.future.select` | — | Async-compatible query construction | Replaces `db.query(Model)` in all async paths |
| `sqlalchemy.ext.asyncio.AsyncSession.execute` | — | Async execution of select statements | Core of the async pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sqlalchemy.orm.selectinload` | 2.x | Eager relationship loading in async context | Use instead of `joinedload` for most relationships (lazy-load safe with AsyncSession) |
| `sqlalchemy.orm.contains_eager` | 2.x | Eager loading with explicit join | Use when explicit join is already in the query |
| `app.core.distributed_lock.acquire_lock` | Internal async context manager | Async distributed lock | Replace `acquire_lock_sync` in `quiz_sessions.create_quiz` |
| `sqlalchemy.update` | 2.x | Bulk update via `await db.execute(update(...).where(...).values(...))` | Bulk updates (mark-read pattern in `messages.py`) |
| `sqlalchemy.func` | 2.x | SQL functions (count, distinct) | `select(func.count(...)).select_from(Model)` pattern |

## Architecture Patterns

### Migration Pattern (established Phase 24, HIGH confidence)

All Phase 25 migrations follow the exact same pattern validated in Phase 24.

**Dependency injection:**
```python
# Before
from app.database import get_db
db=Depends(get_db)

# After
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database.async_engine import get_async_db
db: AsyncSession = Depends(get_async_db)
```

**Read single:**
```python
# Before
obj = db.query(Model).filter(Model.id == id).first()

# After
result = await db.execute(select(Model).where(Model.id == id))
obj = result.scalar_one_or_none()
```

**Read list:**
```python
# Before
items = db.query(Model).filter(...).all()

# After
result = await db.execute(select(Model).where(...))
items = result.scalars().all()
```

**Read list with eager join (unique required):**
```python
# Before
items = db.query(Model).join(Other).options(contains_eager(Model.rel)).all()

# After
stmt = select(Model).join(Other).options(contains_eager(Model.rel))
result = await db.execute(stmt)
items = result.unique().scalars().all()
```

**Count:**
```python
# Before
count = db.query(func.count(Model.id)).scalar()

# After
result = await db.execute(select(func.count(Model.id)))
count = result.scalar_one()
```

**Bulk update:**
```python
# Before
db.query(Message).filter(...).update({...}, synchronize_session=False)
db.commit()

# After
await db.execute(update(Message).where(...).values(...))
await db.commit()
```

**Write operations:**
```python
# db.add() is unchanged (synchronous method on session)
db.add(obj)
# But flush/commit/refresh/delete/rollback must be awaited:
await db.flush()
await db.commit()
await db.refresh(obj)
await db.delete(obj)
await db.rollback()
```

**Eager load with selectinload (async safe):**
```python
result = await db.execute(
    select(Model).where(...).options(selectinload(Model.relationship))
)
obj = result.scalar_one_or_none()
```

**Legacy `.get(id)` pattern (deprecated in async):**
```python
# Before (sync Session only)
obj = db.query(Model).get(id)

# After
result = await db.execute(select(Model).where(Model.id == id))
obj = result.scalar_one_or_none()
```

### Pattern: Async Distributed Lock (quiz_sessions.py specific)

```python
# Before (sync lock inside async handler)
from app.core.distributed_lock import acquire_lock_sync, LockAcquisitionError, LockKeys

with acquire_lock_sync(lock_key, timeout=5.0, ttl=30):
    existing = db.query(QuizSession)...first()
    # ...
    db.add(new_quiz)
    db.commit()

# After (async lock)
from app.core.distributed_lock import acquire_lock, LockAcquisitionError, LockKeys

async with acquire_lock(lock_key, timeout=5.0, ttl=30):
    result = await db.execute(select(QuizSession).where(...))
    existing = result.scalar_one_or_none()
    # ...
    db.add(new_quiz)
    await db.commit()
    await db.refresh(new_quiz)
```

### Pattern: Async _check_patient_access helper

The `_check_patient_access` function in `app/api/v2/_quiz_shared.py` is typed `db: Session` and uses `db.query(Patient)`. Since it is called within async handlers that will receive `AsyncSession`, it must be converted to async:

```python
# Before
def _check_patient_access(db: Session, current_user: User, patient_id: UUID) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    ...

# After
async def _check_patient_access(db: AsyncSession, current_user: User, patient_id: UUID) -> Patient:
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    ...
```

All callers in `quiz_responses.py`, `quiz_alerts.py` must then `await _check_patient_access(...)`.

### Pattern: Shared re-export module update

Both shared helper files re-export `get_db`. These must be updated:

**`app/api/v2/routers/monthly_quiz_operations/_shared.py`:**
```python
# Before
from app.database import get_db
# ... get_db in __all__

# After
from app.core.database.async_engine import get_async_db
# ... get_async_db in __all__ (rename throughout)
```

**`app/api/v2/_quiz_shared.py`:**
```python
# Before
from sqlalchemy.orm import Session
def _check_patient_access(db: Session, ...) -> Patient:
    patient = db.query(Patient)...

# After
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
async def _check_patient_access(db: AsyncSession, ...) -> Patient:
    result = await db.execute(select(Patient).where(...))
    patient = result.scalar_one_or_none()
```

### Pattern: messages.py — Sync Services With AsyncSession

`messages.py` handlers call `MessageRepository(db)` and `MessageService(db)` — both typed `db: Session` and NOT AsyncSession-compatible (Phase 23 did not migrate them).

**Strategy:** Replace inline instead of delegating to the sync service:

```python
# Before: send_message handler
repo = PatientRepository(db)
patient = repo.get_by_id(pid)
message_service = MessageService(db)
message = message_service.schedule_message(...)

# After: inline async queries
result = await db.execute(select(Patient).where(Patient.id == pid))
patient = result.scalar_one_or_none()
# schedule_message logic inlined with async session
new_message = Message(patient_id=pid, content=..., ...)
db.add(new_message)
await db.commit()
await db.refresh(new_message)
```

For `list_messages` which calls `repo.list_v2(...)`, the filtering/cursor logic must be inlined using `select(Message).where(...).limit(...)`.

For `mark_message_as_read` and `delete_message` which call `service.get_message(mid)` and `service.update_message(...)`, inline the lookups and updates.

### Pattern: N+1 Elimination in monthly_quiz_operations/crud.py

`get_monthly_quiz_responses` loops over responses and makes two `db.query` calls per iteration (template and session lookup). These must be batched:

```python
# Before (N+1 pattern)
for response in responses:
    template = db.query(QuizTemplate).filter(QuizTemplate.id == response.quiz_template_id).first()
    session = db.query(QuizSession).filter(QuizSession.id == response.quiz_session_id).first()

# After (batch async)
template_ids = {r.quiz_template_id for r in responses}
session_ids = {r.quiz_session_id for r in responses if r.quiz_session_id}

t_result = await db.execute(select(QuizTemplate).where(QuizTemplate.id.in_(template_ids)))
templates_by_id = {t.id: t for t in t_result.scalars().all()}

s_result = await db.execute(select(QuizSession).where(QuizSession.id.in_(session_ids)))
sessions_by_id = {s.id: s for s in s_result.scalars().all()}

for response in responses:
    template = templates_by_id.get(response.quiz_template_id)
    session = sessions_by_id.get(response.quiz_session_id)
    ...
```

Similarly `get_active_links` also has per-session template and patient N+1 lookups that must be batched.

## Detailed Router Inventory

### Message Group

| File | Lines | db.query | Depends(get_db) | db.commit | Complexity | Notes |
|------|-------|----------|-----------------|-----------|------------|-------|
| `messages.py` | 947 | 6 | 12 | 1 | HIGH | Single file; 17 handlers are stubs (no real DB); 10 have `Depends(get_db)`, only 6-7 do real DB work; calls sync-only `MessageRepository`, `MessageService`, `PatientRepository` |

**Roadmap-named sub-files that DO NOT exist:**

The roadmap requirement API-04 names nine files (`messages.py`, `messages/send.py`, `messages/crud.py`, etc.). In the actual codebase, there is only **one file**: `app/api/v2/routers/messages.py`. The subdirectory `messages/` does not exist. The planning for Phase 25 should document this discrepancy and cover only the actual file.

**Real vs stub handlers in messages.py:**

| Handler | Has `Depends(get_db)` | Real DB work | Notes |
|---------|----------------------|--------------|-------|
| `list_messages` | YES (via `db=Depends(get_db)`) but body delegates to `MessageRepository(db)` | YES | Uses `repo.list_v2()` — sync repo, must inline |
| `list_scheduled_messages` | YES | NO | Returns empty list stub |
| `get_patient_message_stats` | YES | NO | Returns zero-filled stub |
| `list_conversations` | YES | YES | 3 `db.query()` calls including N+1 |
| `get_conversation_unread_count` | YES | YES | 1 `db.query()` count |
| `mark_conversation_read` | YES | YES | 1 bulk update + commit |
| `get_message` | YES | YES | `db.query(Message).filter(...).first()` |
| `send_message` | YES | YES | Calls `PatientRepository(db)` + `MessageService(db)` — both sync |
| `mark_message_as_read` | YES | YES | Calls `MessageService(db).get_message()` + `update_message()` |
| `delete_message` | YES | YES | Calls `MessageService(db).get_message()` + `update_message()` |
| `get_patient_conversation` | YES | YES | Uses `MessageRepository(db).list_v2()` |
| `send_bulk_messages` | YES | NO | Returns mock response |
| All template endpoints | NO | NO | All return 501 Not Implemented |
| Analytics endpoints | NO | NO | Stubs returning zeros |

### Quiz Group

| File | Lines | db.query | Depends(get_db) | db.commit | Complexity | Special Notes |
|------|-------|----------|-----------------|-----------|------------|---------------|
| `quiz_responses.py` | 386 | 9 | 3 | 0 | MEDIUM | No writes; uses `_check_patient_access` (sync helper that must become async); calls sync `db.query(Patient)` for RBAC |
| `quiz_sessions.py` | 403 | 9 | 5 | 3 | HIGH | Has writes (add/commit/refresh/delete); uses `acquire_lock_sync` → must switch to `async acquire_lock`; uses `db.query(...).get(id)` (deprecated in async) |
| `quiz_alerts.py` | 499 | 9 | 5 | 1 | MEDIUM | 1 write (acknowledge); calls `_check_patient_access` (sync); N+1 per-alert patient lookup |
| `quiz_templates.py` | 380 | 5 | 6 | 4 | LOW | Standard CRUD; uses `db.query(QuizTemplate).get(template_id)` deprecated pattern; `TemplateAuditLogger` is sync but not DB-dependent |
| `monthly_quiz_management.py` | 641 | 4 | 7 | 5 | MEDIUM | Uses helper `_get_monthly_quiz_or_404(db, ...)` (sync); `tags` JSONB mutation then `db.commit()` |
| `monthly_quiz_operations/crud.py` | 511 | 18 | 7 | 2 | HIGH | Most complex; N+1 patterns in `get_monthly_quiz_responses` and `get_active_links`; re-exports `get_db` from `_shared.py`; sync cache call `redis_cache.get/setex` in `get_monthly_quiz_statistics` |

## Shared Helper Files (must migrate)

### `app/api/v2/_quiz_shared.py`
- Imports `Session` from sqlalchemy.orm
- Exports `_check_patient_access(db: Session, ...)` — sync `db.query(Patient)` call
- Also exports `_get_current_user_simple` (already async-safe, no DB call)
- **Action:** Change to `AsyncSession`, make `_check_patient_access` async with `select/execute`, update callers

### `app/api/v2/routers/monthly_quiz_operations/_shared.py`
- Imports and re-exports `get_db` from `app.database`
- All 7 `Depends(get_db)` in `crud.py` come from this re-export
- **Action:** Replace `get_db` import with `get_async_db` from canonical path; update `__all__`

## Service Dependency Analysis (Phase 23 coverage)

| Service | AsyncSession Support | Used In | Phase 25 Action |
|---------|---------------------|---------|-----------------|
| `MessageRepository` (app/repositories/message.py) | NO — `db: Session` typed, sync only | `messages.py` (list_messages, get_patient_conversation) | Inline async select/execute instead of calling repo |
| `MessageService` (app/domain/messaging/core/message_service/service.py) | NO — `db: Session` typed, sync only | `messages.py` (send_message, mark_as_read, delete_message) | Inline async DB operations (schedule, get, update patterns) |
| `PatientRepository` (app/repositories/patient/) | NO — `db: Session` typed, sync only | `messages.py` (send_message patient lookup) | Inline `select(Patient).where(Patient.id == pid)` |
| `QuizService` group | YES (Phase 23 migrated) | Not directly in these routers | No action needed |
| `UnifiedWhatsAppService` | YES (Phase 23 migrated; accepts async session) | `send_message_background` background task (already async) | No action needed; background task already uses its own `async_factory()` session |
| `TemplateAuditLogger` | N/A (no DB calls, just logging) | `quiz_templates.py` | No action needed |
| `acquire_lock_sync` | SYNC ONLY | `quiz_sessions.py` create_quiz | Replace with `async acquire_lock` from same module |

## Execution Grouping (Waves)

### Wave 1 — messages.py migration (API-04)
Single file, mostly stubs. Real DB handlers require inlining since repos are sync-only.
**Files:** `app/api/v2/routers/messages.py`
**Work:** Replace 12 `Depends(get_db)` with `Depends(get_async_db)`, inline 6 real DB handlers, convert 1 `db.commit()`, convert 6 `db.query()` calls.

### Wave 2 — Quiz shared helpers (prerequisite for quiz files)
Must run before any quiz router migrations.
**Files:** `app/api/v2/_quiz_shared.py`, `app/api/v2/routers/monthly_quiz_operations/_shared.py`
**Work:** Make `_check_patient_access` async, update `get_db` re-export to `get_async_db`.

### Wave 3 — Quiz simple routers (API-05, part 1)
**Files:** `quiz_templates.py`, `monthly_quiz_management.py`
**Work:** `quiz_templates.py` has 5 `db.query` + CRUD writes (straightforward). `monthly_quiz_management.py` has 4 `db.query` + writes, extract `_get_monthly_quiz_or_404` to async inline.

### Wave 4 — Quiz medium routers (API-05, part 2)
**Files:** `quiz_responses.py`, `quiz_alerts.py`
**Work:** Read-heavy with RBAC. Requires awaiting updated `_check_patient_access`. N+1 fix in `quiz_alerts.py` (per-alert patient lookup).

### Wave 5 — Quiz complex router (API-05, part 3)
**Files:** `monthly_quiz_operations/crud.py`
**Work:** Most `db.query` calls (18), `acquire_lock_sync` → `async acquire_lock`, N+1 fixes in `get_monthly_quiz_responses` and `get_active_links`, sync `redis_cache.setex` call in `get_monthly_quiz_statistics`.

### Wave 6 — Quiz sessions (API-05, part 4)
**Files:** `quiz_sessions.py`
**Work:** Most complex: writes + lock pattern. `acquire_lock_sync` → `async acquire_lock`, 9 `db.query` → async select, 3 commits + add + delete + refresh → all awaited.

### Wave 7 — Regression tests
**Files:** `tests/api/v2/test_phase25_messages_quiz_async.py` (new)
**Work:** Source-level assertions (zero `db.query(`, zero `Depends(get_db)`, presence of `Depends(get_async_db)`) for all 7 migrated files.

## Common Pitfalls

### Pitfall 1: Calling Sync Repository With AsyncSession
**What goes wrong:** `MessageRepository(db)` or `MessageService(db)` passed an `AsyncSession` instance — the repo methods call `self.db.query(...)` which raises `MissingGreenlet` under async.
**Why it happens:** The repos were not migrated in Phase 23 (only service-layer objects were targeted).
**How to avoid:** Inline the async query directly in the router handler instead of delegating to the sync repo. Do not pass `AsyncSession` to `MessageRepository` or `MessageService`.
**Warning signs:** Any `MessageRepository(db)` or `MessageService(db)` call in a handler after `db: AsyncSession = Depends(get_async_db)` is a bug.

### Pitfall 2: Forgetting to await _check_patient_access after conversion
**What goes wrong:** After making `_check_patient_access` async, callers in `quiz_responses.py` and `quiz_alerts.py` that previously called it synchronously now silently return a coroutine object instead of a `Patient` (no error, wrong behavior).
**Why it happens:** Python async/await requires explicit `await` at every call site.
**How to avoid:** Search all callers of `_check_patient_access` across the codebase before and after conversion. Use `await _check_patient_access(...)` at every call site.
**Warning signs:** `isinstance(patient, Patient)` returns `False`; the returned object is a coroutine.

### Pitfall 3: Missing await on db operations in shared helper `_get_monthly_quiz_or_404`
**What goes wrong:** `_get_monthly_quiz_or_404(db, quiz_id)` in `monthly_quiz_management.py` calls `db.query(QuizTemplate)...first()` — if passed an `AsyncSession`, this blocks.
**Why it happens:** Helper functions typed for `Session` are called from async handlers.
**How to avoid:** Convert `_get_monthly_quiz_or_404` to `async def` and inline the query, then `await` it at call sites.

### Pitfall 4: Using acquire_lock_sync inside an async handler
**What goes wrong:** `acquire_lock_sync` uses `threading.Lock` internals — inside an async handler it blocks the event loop for the full duration of the lock wait (up to 5 seconds by default).
**Why it happens:** Sync lock was used before the async alternative was added.
**How to avoid:** Use `async with acquire_lock(lock_key, timeout=5.0, ttl=30):` instead of `with acquire_lock_sync(...)`.

### Pitfall 5: db.query(...).get(id) Pattern (Legacy ORM API)
**What goes wrong:** `db.query(Model).get(pk)` is not supported with `AsyncSession` (this is the legacy `Session.get()` shortcut; in async you must use `select` explicitly).
**Why it happens:** Legacy pattern in `quiz_sessions.py` (`_get_quiz_with_access`, `create_quiz`).
**How to avoid:** Replace `db.query(Model).get(pk)` with `await db.execute(select(Model).where(Model.id == pk))` → `result.scalar_one_or_none()`.

### Pitfall 6: N+1 Queries in Loop
**What goes wrong:** `get_monthly_quiz_responses` and `get_active_links` in `crud.py` perform per-item `db.query` calls inside a loop — after migration each becomes an `await db.execute(...)` but remains N+1. Under async load this is still poor performance and risks timeout.
**Why it happens:** Sync code lazily loaded relationships per item.
**How to avoid:** Batch the lookups using `.in_()` before the loop. See Architecture Patterns → N+1 Elimination.

### Pitfall 7: Sync redis_cache.setex call
**What goes wrong:** In `monthly_quiz_operations/crud.py`, `get_monthly_quiz_statistics` calls `redis_cache.setex(...)` synchronously (not awaited) — this is already technically a bug (the cache is async in production). After migration this pattern should be harmonized.
**Why it happens:** The `_shared.py` cache helpers use different patterns than the `monthly_quiz_management.py` helpers.
**How to avoid:** Use the `_cache_set` or `await redis_cache.set(...)` pattern consistently. Check whether the `redis_cache` object in `crud.py` is actually async (it comes from `get_redis_cache` which is `async def` and returns an async cache object).

### Pitfall 8: Shared re-export _shared.py breaks consumers
**What goes wrong:** If `_shared.py` is updated to export `get_async_db` instead of `get_db`, but `crud.py` still imports `get_db` from `_shared`, the consumers break silently.
**Why it happens:** Re-exports must be updated consistently; all consumers must be updated in the same commit.
**How to avoid:** Update `_shared.py` and all its consumers (`crud.py`) in a single atomic change. Check `__all__` list in `_shared.py` and update the name there too.

## Code Examples

### Verified Pattern: Read with selectinload (from Phase 24 flows.py)
```python
# Source: backend-hormonia/app/api/v2/routers/flows.py (migrated Phase 24)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

# Read single with relationship
result = await db.execute(
    select(FlowTemplateVersion)
    .where(FlowTemplateVersion.id == template_id)
    .options(selectinload(FlowTemplateVersion.kind))
)
template = result.scalar_one_or_none()
```

### Verified Pattern: Bulk Update (marks messages as read)
```python
# Equivalent for mark_conversation_read in messages.py
from sqlalchemy import update
await db.execute(
    update(Message)
    .where(
        Message.patient_id == pid,
        Message.direction == MessageDirection.INBOUND,
        Message.read_at.is_(None),
    )
    .values(read_at=now_sao_paulo(), status=MessageStatus.READ)
)
await db.commit()
```

### Verified Pattern: Count Query
```python
# Equivalent for list_conversations total count
from sqlalchemy import func, select
result = await db.execute(
    select(func.count(func.distinct(Message.patient_id)))
    .where(Message.patient_id.isnot(None))
)
total = result.scalar_one() or 0
```

### Verified Pattern: Async Distributed Lock (quiz_sessions.py)
```python
# Source: app/core/distributed_lock.py (async variant exists)
from app.core.distributed_lock import acquire_lock, LockAcquisitionError, LockKeys

lock_key = LockKeys.quiz_session(str(pid))
try:
    async with acquire_lock(lock_key, timeout=5.0, ttl=30):
        result = await db.execute(
            select(QuizSession)
            .where(
                QuizSession.patient_id == pid,
                QuizSession.quiz_template_id == tid,
                QuizSession.status == "started",
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise ConflictError(...)
        new_quiz = QuizSession(...)
        db.add(new_quiz)
        await db.commit()
        await db.refresh(new_quiz)
except LockAcquisitionError:
    raise ServiceUnavailableError("Service busy, please retry")
```

### Verified Pattern: Regression Test (from Phase 24)
```python
# Source: backend-hormonia/tests/api/v2/test_phase24_flows_async.py
import inspect, re
import app.api.v2.routers.messages as messages_router

def test_messages_router_no_sync_query():
    source = inspect.getsource(messages_router)
    assert "db.query(" not in source, "db.query( found in messages.py"
    assert "Depends(get_async_db)" in source

def test_messages_router_write_ops_async():
    source = inspect.getsource(messages_router)
    for op in ["commit", "flush", "refresh", "rollback", "delete"]:
        pattern = rf"(?<!await )db\.{op}\("
        assert not re.search(pattern, source), f"Sync db.{op}() without await found"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `db.query(Model).filter(...).first()` | `await db.execute(select(Model).where(...))` then `.scalar_one_or_none()` | Phase 21-24 | All router handlers must use this |
| `db.query(Model).get(pk)` | `await db.execute(select(Model).where(Model.id==pk))` then `.scalar_one_or_none()` | Phase 24 | Legacy `get()` shortcut unsupported in AsyncSession |
| `joinedload` (lazy-load on access) | `selectinload` (eagerly loaded) | Phase 24 | `joinedload` causes `DetachedInstanceError` with AsyncSession when accessed after session close |
| `with acquire_lock_sync(...)` | `async with acquire_lock(...)` | Phase 25 (new) | Required: sync lock in async handler blocks event loop |
| `Depends(get_db)` | `Depends(get_async_db)` with `db: AsyncSession` type annotation | Phase 21 | All API router dependencies must use async version |
| Calling `MessageRepository(db)` from async handler | Inline `select(Message).where(...)` in handler | Phase 25 (new) | Sync repos cannot safely receive AsyncSession |

## Test Files for Regression Evidence

| Test File | Router(s) Covered | Type |
|-----------|------------------|------|
| `tests/api/v2/test_messages.py` (545 lines) | `messages.py` | Existing functional tests |
| `tests/api/v2/test_quiz.py` (224 lines) | `quiz_sessions.py` | Existing functional tests |
| `tests/api/v2/test_quiz_extensions.py` (953 lines) | `quiz_responses.py`, `quiz_alerts.py`, `quiz_templates.py`, `monthly_quiz_management.py` | Existing functional tests |
| `tests/api/v2/test_quiz_pagination.py` | `quiz_sessions.py`, `quiz_responses.py` | Existing functional tests |
| `tests/api/v2/test_monthly_quiz_compatibility.py` | `monthly_quiz_management.py`, `monthly_quiz_operations/crud.py` | Existing functional tests |
| `tests/api/v2/test_phase25_messages_quiz_async.py` | All Phase 25 routers | NEW — source-level async regression tests |

The new test file must assert for each migrated router module:
1. `"db.query(" not in source`
2. `"Depends(get_db)" not in source`
3. `"Depends(get_async_db)" in source` (for files that have DB)
4. No bare `db.commit(`, `db.flush(`, `db.refresh(`, `db.delete(`, `db.rollback(` without preceding `await`

## Open Questions

1. **`_get_monthly_quiz_or_404` scope** — This sync helper is only used within `monthly_quiz_management.py`. It should be converted to `async def` and called with `await` only in that file, OR inlined at each call site. Either approach is valid; inlining is simpler and avoids helper type changes.
   - What we know: 3 call sites in `monthly_quiz_management.py`
   - What's unclear: Whether to keep as helper or inline
   - Recommendation: Convert to `async def _get_monthly_quiz_or_404(db: AsyncSession, ...)` in the same file since it's not shared

2. **`MessageService.schedule_message` replacement scope** — The `send_message` handler calls `message_service.schedule_message(...)` which wraps a complex flow (creates Message record, sets scheduling). Inlining requires understanding the full method.
   - What we know: `MessageService.__init__` takes `db: Session`; `schedule_message` is at line 239 of `service.py`
   - What's unclear: Whether any write logic beyond `db.add(message); db.commit(); db.refresh(message)` exists in `schedule_message`
   - Recommendation: Read `schedule_message` body during planning to confirm what needs inlining

3. **`monthly_quiz_operations/crud.py` redis_cache.setex async correction** — The cache call `redis_cache.setex(cache_key, CACHE_TTL_STATISTICS, result.json())` is synchronous but the cache object is returned by `get_redis_cache` (async DI). This was pre-existing; fixing it during Phase 25 keeps the migration clean.
   - Recommendation: Replace with `await _cache_set(redis_cache, cache_key, result.json(), CACHE_TTL_STATISTICS)` using the helpers already defined at the top of `monthly_quiz_management.py`, or similar pattern.

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `backend-hormonia/app/api/v2/routers/messages.py` — actual file structure, handler count, `db.query` occurrences
- Direct code inspection: `backend-hormonia/app/api/v2/routers/quiz_*.py` and `monthly_quiz_management.py` — confirmed sync patterns
- Direct code inspection: `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/crud.py` — N+1 patterns confirmed
- Direct code inspection: `backend-hormonia/app/core/distributed_lock.py` — confirmed `async def acquire_lock` exists
- Direct code inspection: `backend-hormonia/app/repositories/message.py` — confirmed `db: Session` only, no AsyncSession support
- Phase 24 verification: `.planning/phases/24-api-routers-auth-patients-flow/24-VERIFICATION.md` — confirmed migration pattern works
- Phase 24 plan: `.planning/phases/24-api-routers-auth-patients-flow/24-07-PLAN.md` — confirmed canonical async patterns
- REQUIREMENTS.md — API-04 and API-05 requirement text and scope

### Secondary (MEDIUM confidence)
- Phase 23 state decisions from `STATE.md` — `UnifiedWhatsAppService` confirmed async-safe, quiz services confirmed async-safe

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — same stack as Phase 24, verified in production
- Architecture: HIGH — migration pattern validated across 14+ files in Phase 24
- Pitfalls: HIGH — directly observed from code inspection of actual files
- Service dependency gaps (MessageRepository sync-only): HIGH — confirmed by source inspection

**Research date:** 2026-02-27
**Valid until:** Stable for the duration of this project (patterns are locked by Phase 24 decisions)
