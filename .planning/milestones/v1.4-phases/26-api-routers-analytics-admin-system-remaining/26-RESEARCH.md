# Phase 26: API Routers — Analytics / Admin / System / Remaining - Research

**Researched:** 2026-02-27
**Domain:** FastAPI AsyncSession migration — remaining router groups
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| API-06 | Analytics and reporting routers (`analytics/dashboard_analytics.py`, `analytics/patient_analytics.py`, `analytics/quiz_analytics.py`, `dashboard.py`, `reports.py`) use AsyncSession | Code audit shows all five files still use `get_db` / sync `db.query()` with one partial exception; migration pattern identical to Phases 24–25 |
| API-07 | Admin routers (`admin/compensation.py`, `admin/activity.py`, `admin/users.py`, `admin/stats.py`, `admin_extensions/audit.py`, `admin_extensions/dlq.py`) use AsyncSession | `compensation.py` is partially migrated (two mixed endpoints); the other five are fully sync; same migration pattern applies |
| API-08 | System routers (`health/service_health.py`, `health/database_health.py`, `health/monitoring.py`, `platforms_sync.py`, `upload/handlers.py`) use AsyncSession | All five files still use `get_db`; some (platforms_sync.py) barely touch the DB; migration straightforward |
| API-09 | Remaining domain routers (`appointments.py`, `medications.py`, `treatments.py`, `notifications.py`, `alerts.py`, `template_versions.py`, `template_admin.py`) use AsyncSession | All seven files use `get_db` / sync `db.query()`; same select/execute migration pattern as Phases 24–25 |
</phase_requirements>

---

## Summary

Phase 26 completes the API-layer AsyncSession migration across four router groups (analytics, admin, system/health, and remaining domain routers) that were deferred from Phases 24–25. The total scope is 20 router files. Every migration task follows a single, well-proven pattern established over Phases 21–25: replace `Depends(get_db)` with `Depends(get_async_db)`, convert `db.query(...)` chains to `await db.execute(select(...))`, and await all write operations (`commit`, `flush`, `refresh`, `rollback`). No new patterns are required — the codebase already has all infrastructure in place.

The main complexity in this phase comes from **three special cases**: (1) `admin/compensation.py` is half-migrated with two endpoints using different session types, requiring a consistency fix; (2) `health/database_health.py` accesses the sync engine pool directly (`engine.pool`) and uses `db.execute(text(...))` without `await` — this endpoint must be handled carefully to preserve health-check semantics; (3) several admin and DLQ routers pass the session directly into sync service constructors (`DLQService(db)`, `UserRepository(db)`) whose internals are sync — these need to use the inline async pattern (inlining `select`/`execute` in the router instead of delegating to a sync service) as established in Phase 25 for messages.

The success criterion is zero `Depends(get_db)` and zero `db.query(` in all 20 target router files. Source-level regression tests (same style as `test_phase25_messages_quiz_async.py`) lock in the migration.

**Primary recommendation:** Migrate each router group as a separate plan file; use `await db.execute(select(...))` inline for all reads, and `await db.commit()` / `await db.refresh()` for writes. Where existing sync services are passed the session, either inline async SQL or create thin async wrappers — do NOT rewrite services in this phase.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `sqlalchemy.ext.asyncio.AsyncSession` | 2.x (already installed) | Async DB session type for request handlers | Already in use across Phases 21–25; all ORM models compatible |
| `sqlalchemy.future.select` / `sqlalchemy.select` | 2.x | Async-compatible SELECT construction | Required for `await db.execute(select(...))` pattern |
| `app.core.database.async_engine.get_async_db` | internal | FastAPI dependency yielding AsyncSession | Canonical import path established in Phase 21 |
| `app.database.get_async_db` | internal shim | Backward-compatible re-export | `app.database` is a shim; both import paths work |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sqlalchemy.text` | 2.x | Raw SQL for health checks | Only for `health/database_health.py` — must use `await db.execute(text(...))` |
| `sqlalchemy.func` | 2.x | Aggregate functions (count, sum, etc.) | In analytics routers — same API, works with async execute |
| `sqlalchemy.orm.selectinload` / `joinedload` | 2.x | Eager loading in async context | Needed for DLQ/audit routers that use `joinedload` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Inline async SQL in router | Async service wrapper | Service wrappers are cleaner but require touching service layer — out of scope per project constraints |
| `selectinload` for eager loads | `joinedload` | Both work in async; `selectinload` is preferred for async because it avoids lazy loading issues; `joinedload` still works with `execute` |

---

## Architecture Patterns

### Recommended Project Structure (unchanged — migration only)
No new files are created. Every change is a surgical replacement inside the 20 target router files.

### Pattern 1: Standard Async SELECT (read endpoints)
**What:** Replace `db.query(Model).filter(...).all()` with `await db.execute(select(Model).where(...))`.
**When to use:** All read endpoints in all 20 target routers.

```python
# BEFORE (sync)
from app.database import get_db
async def endpoint(db=Depends(get_db)):
    results = db.query(Patient).filter(Patient.doctor_id == user_id).all()

# AFTER (async)
from app.core.database import get_async_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.patient import Patient

async def endpoint(db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(select(Patient).where(Patient.doctor_id == user_id))
    results = result.scalars().all()
```

### Pattern 2: Async Scalar / Count
**What:** Replace `db.query(func.count(Model.id)).scalar()` with `await db.scalar(select(func.count(Model.id)))`.
**When to use:** `admin/stats.py`, `analytics/dashboard_analytics.py`, `analytics/quiz_analytics.py`.

```python
# BEFORE (sync)
total = db.query(func.count(User.id)).scalar() or 0

# AFTER (async)
from sqlalchemy import select, func
result = await db.execute(select(func.count(User.id)))
total = result.scalar() or 0
# Alternatively:
total = await db.scalar(select(func.count(User.id))) or 0
```

### Pattern 3: Async Write Operations
**What:** Await `commit`, `refresh`, `flush`, `rollback`, `delete`.
**When to use:** Any endpoint that modifies data — all create/update/delete endpoints.

```python
# BEFORE (sync)
db.add(alert)
db.commit()
db.refresh(alert)

# AFTER (async)
db.add(alert)
await db.commit()
await db.refresh(alert)
```

### Pattern 4: First-or-None (single record fetch)
**What:** Replace `db.query(Model).filter(...).first()` with scalar_one_or_none.
**When to use:** Any endpoint fetching a single record.

```python
# BEFORE (sync)
user = db.query(User).filter(User.id == user_id).first()

# AFTER (async)
result = await db.execute(select(User).where(User.id == user_id))
user = result.scalar_one_or_none()
```

### Pattern 5: Eager Loading in Async
**What:** Use `options(selectinload(...))` or `options(joinedload(...))` inside `select()`.
**When to use:** DLQ routers (`dlq.py`) and any router that uses `joinedload`.

```python
# BEFORE (sync)
item = (
    db.query(FailedMessage)
    .options(joinedload(FailedMessage.patient))
    .filter(FailedMessage.id == dlq_id)
    .first()
)

# AFTER (async)
from sqlalchemy.orm import joinedload
result = await db.execute(
    select(FailedMessage)
    .options(joinedload(FailedMessage.patient))
    .where(FailedMessage.id == dlq_id)
)
item = result.scalar_one_or_none()
```

### Pattern 6: Health Check Raw SQL
**What:** Use `await db.execute(text(...))` for raw SQL pings.
**When to use:** `health/database_health.py` — must `await` the execute call.

```python
# BEFORE (sync)
result = db.execute(text("SELECT 1 as health_check")).fetchone()

# AFTER (async)
from sqlalchemy import text
result = await db.execute(text("SELECT 1 as health_check"))
row = result.fetchone()
```

**Note for database_health.py:** The sync engine pool access (`engine.pool`) is independent of the session. The fix only needs to make the session parameter `AsyncSession` and await the text execute. The `engine` import refers to the sync engine and its pool stats can be read without changes.

### Pattern 7: Group-By Queries (analytics)
**What:** All GROUP BY + aggregate queries in analytics routers.
**When to use:** `analytics/dashboard_analytics.py`, `analytics/quiz_analytics.py`.

```python
# BEFORE (sync)
results = (
    db.query(
        func.extract("year", QuizSession.created_at).label("year"),
        func.count(QuizSession.id).label("total"),
    )
    .group_by(...)
    .all()
)

# AFTER (async)
stmt = (
    select(
        func.extract("year", QuizSession.created_at).label("year"),
        func.count(QuizSession.id).label("total"),
    )
    .group_by(...)
)
result = await db.execute(stmt)
results = result.all()
# Unpack as: for year, total in results: ...
```

### Pattern 8: Inline SQL for Sync-Service Callers
**What:** When a router passes `db` to a sync service that cannot be easily converted (e.g., `DLQService(db)`, `UserRepository(db)`) — inline the SQL directly in the router using async patterns.
**When to use:** `admin_extensions/dlq.py`, `admin/activity.py`, `admin/users.py` where service constructors are sync.

This was established in Phase 25 for `MessageRepository` / `PatientRepository` — do not pass AsyncSession to sync services; inline async SQL instead.

```python
# BEFORE (sync service delegation)
dlq_service = DLQService(db)
success, error_message = dlq_service.retry_message(dlq_id, manual=True)

# AFTER (inline async, preserving behavior)
# Option A: Keep sync service but pass a sync-compatible session proxy (risky)
# Option B: Inline the minimal DB operations the service needs (preferred for this phase)
# The DLQ retry only marks FailedMessage status — inline that:
result = await db.execute(select(FailedMessage).where(FailedMessage.id == dlq_id))
item = result.scalar_one_or_none()
if item:
    item.status = "retrying"
    await db.commit()
```

> **Decision note (carried from Phase 25 pattern):** Do not pass AsyncSession into sync-service constructors. Either inline async SQL for the operations the router needs, or create a thin async wrapper method in the service. The service internals are NOT migrated in this phase.

### Anti-Patterns to Avoid
- **`db.query(...)`:** Never use in async handlers — causes `MissingGreenlet` errors.
- **`db.commit()` without await:** Silent data loss / greenlet errors.
- **Passing AsyncSession to sync services:** Runtime `MissingGreenlet` when the service calls sync ORM methods.
- **Using `engine` (sync) pool info directly in async endpoint:** The pool stats are fine to read via `engine.pool`; just don't use the sync `engine` to execute queries.
- **`db.execute(text(...))` without await:** Sync execute on async session raises an error.

---

## Per-Router Migration Inventory

This section documents the exact current state of each target file and what must change.

### API-06: Analytics Routers

#### `analytics/dashboard_analytics.py`
- **Current state:** Imports `get_db`, all 3 handlers use `db=Depends(get_db)`, all queries use `db.query(...)`.
- **Handlers:** `get_analytics_overview`, `get_treatment_distribution`, `get_patient_status_distribution`
- **Queries:** COUNT, GROUP BY (treatment_type, week_start), COUNT DISTINCT — all must become `select` + `await db.execute`.
- **Write ops:** None — read-only router. Simple migration.

#### `analytics/patient_analytics.py`
- **Current state:** Mixed. `get_patient_engagement` already uses `AsyncSession = Depends(get_async_db)` but still uses `db.query(...)` inside the handler (sync ORM on async session — broken). `get_risk_assessment` uses `db=Depends(get_db)` and `db.query(...)`.
- **Handlers:** `get_patient_engagement` (partially migrated but wrong), `get_risk_assessment`
- **Fix needed:** `get_patient_engagement` must convert its inner `db.query(...)` to `await db.execute(select(...))`. `get_risk_assessment` must switch to `get_async_db` and convert query.

#### `analytics/quiz_analytics.py`
- **Current state:** Imports `get_db`, 2 handlers use `db=Depends(get_db)`, all queries use `db.query(...)`.
- **Handlers:** `get_quiz_status_distribution`, `get_completion_trend`
- **Queries:** GROUP BY status, year/month with case() expressions — all convert to select + await.

#### `dashboard.py`
- **Current state:** Local `get_dashboard_service(db=Depends(get_db))` factory + 5 handlers all use `db=Depends(get_db)`. `DashboardService` is initialized with the sync session and all its methods are sync.
- **Handlers:** `get_main_dashboard`, `get_patient_dashboard`, `get_physician_dashboard`, `get_admin_dashboard`, `get_custom_dashboard`, `update_custom_dashboard_layout`
- **Special case:** `DashboardService` is a sync service — do not convert it. Instead, inline async SQL for any DB queries currently done in-router (e.g., `db.query(Patient.id).filter(...)`) and pass `None` or skip `db` for the service's internal queries (the service operates on whatever db it received at construction time).
- **Strategy:** Convert all in-router `db.query(...)` calls to `await db.execute(select(...))`. The `DashboardService` receives `db` at construction — provide AsyncSession. Service methods that call `db.query()` internally will fail. Workaround: inline the service's DB-needing methods directly in the router (the few in-router DB calls are simple: fetching patient_ids for a doctor).
- **Write ops:** None — read-only. Moderate complexity due to `DashboardService`.

#### `reports.py`
- **Current state:** `_get_db_dep()` wrapper delegates to `iter_db_dependency(get_db)` — a sync session wrapped as async generator. 4 handlers use `db=Depends(_get_db_dep)`.
- **Fix:** Replace `_get_db_dep` with direct `Depends(get_async_db)`. The `_check_patient_access` sync helper uses `db.query(...)` — inline that with async select.
- **Write ops:** None — reports are Redis-backed. The only DB touch is in `_check_patient_access`.

### API-07: Admin Routers

#### `admin/compensation.py`
- **Current state:** MIXED. `list_compensation_failures` uses `db: Session = Depends(get_db)` + sync `db.query(...)`. `retry_compensation` already uses `db: AsyncSession = Depends(get_async_db)` + `await db.execute(select(...))`. `cleanup_compensation` uses `db: Session = Depends(get_db)` + sync `db.query(...)`.
- **Fix:** Migrate `list_compensation_failures` and `cleanup_compensation` to AsyncSession. Simple pagination query + soft delete.

#### `admin/activity.py`
- **Current state:** All 3 handlers use `db=Depends(get_db)` + `db.query(AuditLog)` and `UserRepository(db)`.
- **Special case:** `UserRepository` is sync. Options: (A) inline `select(User).where(User.id == user_id)` for the `user_repo.get(user_id)` calls; (B) keep `UserRepository` call with AsyncSession (will fail — it uses `db.query` internally). **Use option A: inline async SQL.**
- **Write ops:** None — read-only audit log queries.

#### `admin/users.py`
- **Current state:** 11 handlers all use `db=Depends(get_db)`, `UserRepository(db)`, and `db.query(User)`.
- **Special case:** `UserRepository` is sync. For each handler, inline `select(User)` for reads; for writes (create/update/delete), use `db.add(...)`, `await db.commit()`, `await db.refresh(...)`.
- **Complexity:** HIGH — largest router in the phase (11 endpoints). Pattern is repetitive once established.
- **Write ops:** `db.commit()`, `db.refresh()`, `db.rollback()` — all must be awaited.

#### `admin/stats.py`
- **Current state:** 3 handlers use `db=Depends(get_db)` + extensive `db.query(func.count(...))` and `db.query(AuditLog).all()`.
- **Fix:** Replace counts with `await db.scalar(select(func.count(...)))`. Replace `db.query(AuditLog).all()` with `await db.execute(select(AuditLog))` + `.scalars().all()`.
- **Write ops:** None — read-only.

#### `admin_extensions/audit.py`
- **Current state:** 3 handlers type-hint `db: Session = Depends(get_db)` + `db.query(AuditLog)` and `AuditService(db)`.
- **Special case:** `AuditService` is already async-safe per Phase 23 MEMORY (it uses `await execute/commit/refresh`). Passing AsyncSession to it should work.
- **Fix:** Switch to `db: AsyncSession = Depends(get_async_db)`, convert `db.query(AuditLog)` to async select, pass AsyncSession to `AuditService` (safe per Phase 23).

#### `admin_extensions/dlq.py`
- **Current state:** 7 handlers type-hint `db: Session = Depends(get_db)` + `db.query(FailedMessage)` and `DLQService(db)`.
- **Special case:** `DLQService` is sync (Phase 23 context does not mention it was migrated). Methods like `retry_message`, `discard_message`, `get_stats` use sync DB internally.
- **Strategy:** Inline async SQL for the router's own DB queries (`db.query(FailedMessage)`). For `DLQService` calls, the service only receives `db` at construction but may use sync ORM — **do not pass AsyncSession to DLQService**. Instead, use the service only for non-DB operations (e.g., business logic like `retry_message` that might use its own connection), or inline the DB mutation directly.
- **Practical decision:** The DLQ router's own queries (list, get single item) must go async. The `DLQService.retry_message`, `.discard_message`, `.get_stats` calls are behavioral wrappers — inline their minimal DB ops if they touch the session directly, or keep the service call by creating an async version. Given the phase constraint (do not rewrite services), the safest path is to inline the DLQ state mutation (a simple status update) directly in the router.

### API-08: System Routers

#### `health/service_health.py`
- **Current state:** `worker_health_check` uses `db: Session = Depends(get_db)` + `db.query(Message)`. `redis_health_check` and `external_services_health_check` do NOT use `db`.
- **Fix:** Migrate `worker_health_check` to AsyncSession. Convert `db.query(Message).filter(...).count()` calls to `await db.scalar(select(func.count(Message.id)).where(...))`.
- **Write ops:** None.

#### `health/database_health.py`
- **Current state:** `check_database_health(db)` and `database_health_check` use `db: Session = Depends(get_db)` + `db.execute(text("SELECT 1"))` (sync execute, no await) + `engine.pool` access.
- **Fix:** Switch session to `AsyncSession = Depends(get_async_db)`. Change `db.execute(text("SELECT 1 as health_check")).fetchone()` to `result = await db.execute(text("SELECT 1 as health_check"))` + `row = result.fetchone()`. Keep `engine.pool` access unchanged — the sync engine pool stats are read-only and don't need async.
- **Special note:** The `engine` import from `app.database` is the SYNC engine — this is intentional for pool stats. Do NOT change it to the async engine (different pool object).

#### `health/monitoring.py`
- **Current state:** 3 handlers use `db: Session = Depends(get_db)` + `db.query(SystemHealthSnapshot)`, `db.query(SystemIncident)`.
- **Fix:** Standard migration — switch to AsyncSession, convert all queries to `await db.execute(select(...))`.
- **Write ops:** None — read-only monitoring.

#### `platform_sync.py` (named `platform_sync.py` in the file tree)
- **Current state:** Most handlers do NOT use `db` at all (stub/Redis-backed implementation). `list_sync_jobs`, `get_sync_job`, `trigger_sync`, etc. all have `db=Depends(get_db)` in signature but immediately defer to Redis or raise 404. The `test_platform_connection` handler does not use `db`.
- **Fix:** Switch all `db=Depends(get_db)` to `db: AsyncSession = Depends(get_async_db)`. Since the current implementation does not actually execute DB queries (it's a stub), no query conversion is needed — just change the dependency annotation.
- **Write ops:** None in current stub.

#### `upload/handlers.py`
- **Current state:** `upload_file_handler` and other handler functions use `db=Depends(get_db)` + `db.query(Upload)` + `db.add(...)`, `db.commit()`, `db.rollback()`.
- **Fix:** Switch to AsyncSession. Convert `db.query(Upload).filter(...)` to `await db.execute(select(Upload).where(...))`. Await `db.commit()`, `db.rollback()`.
- **Note:** `handlers.py` contains handler functions (not routes) called from the router. The `db` parameter flows in via Depends. The migration is inside the handler functions.

### API-09: Remaining Domain Routers

#### `appointments.py`
- **Current state:** All handlers use `db=Depends(get_db)` + `db.query(Appointment)` + sync `AppointmentService(db)` / `AppointmentRepository(db)`.
- **Special case:** `AppointmentService` and `AppointmentRepository` are sync. Same strategy as admin/users.py — inline async SQL for in-router queries; pass AsyncSession to service (if service uses `db.query()` it will fail).
- **Write ops:** `db.commit()` in `cancel_appointment`, `complete_appointment`.
- **Strategy:** For the simple PATCH endpoints (`cancel`, `complete`), inline the fetch + update + `await db.commit()`. For `list_appointments`, `get_appointment`, convert `db.query` to `await db.execute(select(...))`. For `create_appointment`/`update_appointment` that delegate to `AppointmentService`, the service will need to work with AsyncSession or have its DB calls inlined.

#### `medications.py`
- **Current state:** Same pattern — `db=Depends(get_db)` + `db.query(Medication)`.
- **Write ops:** Create/update/delete endpoints will have sync `db.commit()`, `db.rollback()`.
- **Fix:** Standard migration.

#### `treatments.py`
- **Current state:** Same pattern as medications.py.
- **Fix:** Standard migration.

#### `notifications.py`
- **Current state:** `db=Depends(get_db)` + `db.query(Notification)`.
- **Fix:** Standard migration.

#### `alerts.py`
- **Current state:** `db=Depends(get_db)` in all handlers + `db.query(Alert)`, `db.query(Patient)`, `db.add(alert)`, `db.commit()`, `db.refresh(alert)`, `db.delete(alert)`.
- **Write ops:** All write paths (create, update, delete, mark-as-read, mark-all-read) must await commit/refresh/rollback.
- **Fix:** Standard migration — moderate complexity due to many write endpoints.

#### `template_versions.py`
- **Current state:** `db=Depends(get_db)` + `db.query(FlowTemplateVersion)`.
- **Fix:** Standard migration.

#### `template_admin.py`
- **Current state:** `db=Depends(get_db)` + `db.query(FlowTemplateVersion)`, `db.query(QuizTemplate)`.
- **Fix:** Standard migration.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async DB session | Custom session factory | `get_async_db` from `app.core.database` | Already established in Phase 21; has fail-fast guard |
| Passing AsyncSession to sync services | Compatibility shim | Inline async SQL in the router | Shims cause hidden errors; inline is explicit and testable |
| New DB pooling logic | Custom pool wrapper | Existing `engine.pool` (sync engine) for stats | Pool stats are read-only; no session needed |
| Async task locks | Custom asyncio locks | Existing `acquire_lock` async helper (established Phase 25) | Already in use for quiz sessions |

---

## Common Pitfalls

### Pitfall 1: Sync ORM on AsyncSession (`MissingGreenlet`)
**What goes wrong:** Calling `db.query(Model)` or `db.execute(text(...))` (without `await`) on an `AsyncSession` raises `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called`.
**Why it happens:** `AsyncSession` routes all I/O through the async event loop; synchronous SQLAlchemy ORM calls attempt to spawn a greenlet which doesn't exist.
**How to avoid:** Always prefix DB calls with `await`. Use `select()` not `db.query()`.
**Warning signs:** `MissingGreenlet` in stack traces; any `db.query(` in source after migration.

### Pitfall 2: Awaiting Non-Awaitable (double-await)
**What goes wrong:** `await db.query(...)` raises `TypeError: object Query is not awaitable`.
**Why it happens:** `db.query(...)` returns a synchronous `Query` object, not a coroutine. Adding `await` doesn't fix it — the call must be rewritten with `select()`.
**How to avoid:** `await db.execute(select(...))` is the correct form.

### Pitfall 3: Forgetting to Await Write Operations
**What goes wrong:** Data appears to commit but silently doesn't; or the session is closed before the async commit runs.
**Why it happens:** `db.commit()` on AsyncSession is a coroutine — calling without `await` schedules it but doesn't block.
**How to avoid:** Audit every `db.commit()`, `db.refresh()`, `db.rollback()` and add `await`.
**Warning signs:** Test-level write ops don't persist; regression test `_assert_write_ops_awaited` catches this.

### Pitfall 4: `admin/compensation.py` Mixed Session Types
**What goes wrong:** Two endpoints use AsyncSession (already migrated) and two use sync Session — the router as a whole is inconsistent.
**How to avoid:** Migrate the remaining two sync endpoints to AsyncSession in the same plan. Do not leave a mixed router.

### Pitfall 5: `health/database_health.py` Engine Pool vs Session
**What goes wrong:** Changing `engine` to `async_engine` breaks pool size stats because the async engine's pool behaves differently.
**How to avoid:** Keep `from app.database import engine` (sync engine) for pool stats. Only change the `db` dependency from `get_db` to `get_async_db`.

### Pitfall 6: `DashboardService` Sync Methods with AsyncSession
**What goes wrong:** `DashboardService.__init__(db)` stores the session; its methods (`get_patient_metrics`, etc.) call `db.query(...)` internally with the AsyncSession, causing `MissingGreenlet`.
**How to avoid:** The in-router DB calls (`db.query(Patient.id).filter(...)`) must be inlined as async. The `DashboardService` method calls that do NOT use `db` directly (e.g., date range calculation) are safe. Check each method carefully.

### Pitfall 7: `iter_db_dependency` Wrapper in `reports.py`
**What goes wrong:** `_get_db_dep()` wraps `get_db` via `iter_db_dependency` — replacing `get_db` inside it with `get_async_db` doesn't make the session truly async.
**How to avoid:** Remove `_get_db_dep` entirely. Use `db: AsyncSession = Depends(get_async_db)` directly in each handler.

---

## Code Examples

### Read: Analytics COUNT (verified pattern)
```python
# Source pattern: Phase 24/25 router migrations
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_db

async def get_analytics_overview(
    db: AsyncSession = Depends(get_async_db),
    ...
):
    result = await db.execute(
        select(func.count(Patient.id)).where(Patient.flow_state != FlowState.CANCELLED)
    )
    total_patients = result.scalar() or 0
```

### Read: JOIN with GROUP BY (analytics trend)
```python
from sqlalchemy import select, func, case

stmt = (
    select(
        func.extract("year", QuizSession.created_at).label("year"),
        func.extract("month", QuizSession.created_at).label("month"),
        func.count(QuizSession.id).label("total"),
        func.sum(case((QuizSession.status == "completed", 1), else_=0)).label("completed"),
    )
    .join(Patient, Patient.id == QuizSession.patient_id)
    .where(QuizSession.created_at >= start_date)
    .group_by(
        func.extract("year", QuizSession.created_at),
        func.extract("month", QuizSession.created_at),
    )
    .order_by(...)
)
result = await db.execute(stmt)
rows = result.all()
for year, month, total, completed in rows:
    ...
```

### Write: Create + Commit + Refresh
```python
# Source pattern: Phase 25 quiz_responses
alert = Alert(patient_id=..., alert_type=..., ...)
db.add(alert)
await db.commit()
await db.refresh(alert)
return _serialize_alert(alert)
```

### Write: Rollback on Error
```python
try:
    db.add(record)
    await db.commit()
except Exception as e:
    await db.rollback()
    raise HTTPException(...)
```

### Health Check: Raw SQL (async)
```python
from sqlalchemy import text

result = await db.execute(text("SELECT 1 as health_check"))
row = result.fetchone()
# Continue reading engine.pool for sync pool metrics (unchanged)
pool = engine.pool
pool_size = pool.size()
```

### Eager Loading (DLQ router)
```python
from sqlalchemy.orm import joinedload

result = await db.execute(
    select(FailedMessage)
    .options(joinedload(FailedMessage.patient), joinedload(FailedMessage.reviewer))
    .where(FailedMessage.id == dlq_id)
)
item = result.scalar_one_or_none()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `db.query(Model).filter(...).all()` | `await db.execute(select(Model).where(...))` | Phase 21 | Required for async context |
| `db=Depends(get_db)` in API handlers | `db: AsyncSession = Depends(get_async_db)` | Phase 21 | Non-blocking DB access |
| Sync service factories for API | Async DI factories in `app/dependencies/` | Phase 21–23 | Proper DI for both API and Celery |
| `db.commit()` | `await db.commit()` | Phase 22+ | Prevents silent data loss |

**Deprecated/outdated:**
- `get_db` in API request handlers: Deprecated for all API routers after Phase 26 is done. Still valid for Celery tasks.
- `db.query(...)`: Forbidden in all API handler code after Phase 26.

---

## Regression Test Design

All 20 routers must be locked by source-level regression tests modeled after `test_phase25_messages_quiz_async.py`. The test file for this phase should be `tests/api/v2/test_phase26_analytics_admin_system_async.py`.

### Test structure (source-inspection approach — verified to work in Phases 24/25)

```python
import importlib
import inspect
import re
import pytest

ROUTER_MODULES = [
    # API-06
    "app.api.v2.routers.analytics.dashboard_analytics",
    "app.api.v2.routers.analytics.patient_analytics",
    "app.api.v2.routers.analytics.quiz_analytics",
    "app.api.v2.routers.dashboard",
    "app.api.v2.routers.reports",
    # API-07
    "app.api.v2.routers.admin.compensation",
    "app.api.v2.routers.admin.activity",
    "app.api.v2.routers.admin.users",
    "app.api.v2.routers.admin.stats",
    "app.api.v2.routers.admin_extensions.audit",
    "app.api.v2.routers.admin_extensions.dlq",
    # API-08
    "app.api.v2.routers.health.service_health",
    "app.api.v2.routers.health.database_health",
    "app.api.v2.routers.health.monitoring",
    "app.api.v2.routers.platform_sync",
    "app.api.v2.routers.upload.handlers",
    # API-09
    "app.api.v2.routers.appointments",
    "app.api.v2.routers.medications",
    "app.api.v2.routers.treatments",
    "app.api.v2.routers.notifications",
    "app.api.v2.routers.alerts",
    "app.api.v2.routers.template_versions",
    "app.api.v2.routers.template_admin",
]

WRITE_OPS = ["commit", "flush", "refresh", "rollback", "delete"]

def _get_source(module_path: str) -> str:
    mod = importlib.import_module(module_path)
    return inspect.getsource(mod)

@pytest.mark.parametrize("module_path", ROUTER_MODULES)
def test_no_sync_db_query(module_path):
    source = _get_source(module_path)
    assert "db.query(" not in source, f"db.query( found in {module_path}"

@pytest.mark.parametrize("module_path", ROUTER_MODULES)
def test_no_depends_get_db(module_path):
    source = _get_source(module_path)
    assert "Depends(get_db)" not in source, f"Depends(get_db) found in {module_path}"

@pytest.mark.parametrize("module_path", ROUTER_MODULES)
def test_write_ops_awaited(module_path):
    source = _get_source(module_path)
    for op in WRITE_OPS:
        pattern = rf"(?<!await )db\.{op}\("
        assert not re.search(pattern, source), (
            f"Sync db.{op}() without await found in {module_path}"
        )
```

---

## Validation Architecture

> `workflow.nyquist_validation` is not set in `.planning/config.json` (field absent). Skipping formal Validation Architecture section.

### Test Infrastructure Available

| Property | Value |
|----------|-------|
| Framework | pytest (confirmed — `conftest.py` present at multiple levels) |
| Config file | `backend-hormonia/pytest.ini` or via `pyproject.toml` |
| Quick run command | `pytest tests/api/v2/test_phase26_analytics_admin_system_async.py -x` |
| Full suite command | `pytest tests/ -x --ignore=tests/middleware/test_distributed_rate_limiter.py` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| API-06 | Analytics routers use `get_async_db`, no `db.query` | source-inspection | `pytest tests/api/v2/test_phase26_analytics_admin_system_async.py::test_no_sync_db_query -k analytics -x` | ❌ Wave 0 |
| API-07 | Admin routers use `get_async_db`, no `db.query` | source-inspection | `pytest tests/api/v2/test_phase26_analytics_admin_system_async.py::test_no_sync_db_query -k admin -x` | ❌ Wave 0 |
| API-08 | System routers use `get_async_db`, no `db.query` | source-inspection | `pytest tests/api/v2/test_phase26_analytics_admin_system_async.py::test_no_sync_db_query -k health -x` | ❌ Wave 0 |
| API-09 | Domain routers use `get_async_db`, no `db.query` | source-inspection | `pytest tests/api/v2/test_phase26_analytics_admin_system_async.py -k "appointments or alerts or medications" -x` | ❌ Wave 0 |

### Wave 0 Gaps

- [ ] `tests/api/v2/test_phase26_analytics_admin_system_async.py` — covers all API-06 through API-09 via source inspection (no live DB required)

---

## Open Questions

1. **DashboardService async compatibility**
   - What we know: `DashboardService` receives `db` in `__init__` and calls sync methods (`get_patient_metrics`, etc.) internally. The service is not in the target files list.
   - What's unclear: Do the service methods touch `db` directly, or do they use their own session? Need to verify `app/services/dashboard_service.py` content.
   - Recommendation: Read `dashboard_service.py` during planning. If methods use `db.query(...)`, inline the in-router DB calls (patient_ids lookup) and pass `None` for the service db parameter since service metrics don't need live DB in the current stub pattern.

2. **DLQService async compatibility**
   - What we know: `DLQService(db)` is called in 6 places in `dlq.py`. The Phase 23 memory does not mention DLQService as migrated.
   - What's unclear: Whether `DLQService.retry_message`, `.discard_message`, `.get_stats` use `db.query()` or a separate session.
   - Recommendation: Read `app/services/dlq/` during planning. If sync, inline the minimal state mutations (a status update on FailedMessage) directly in the router.

3. **UserRepository async compatibility**
   - What we know: `UserRepository(db)` is called in `admin/users.py` and `admin/activity.py` with sync Session.
   - What's unclear: Whether there's an async variant already.
   - Recommendation: Inline `select(User)` queries in the router. UserRepository's sync methods (`get`, `get_by_email`, `create`, `update`) map trivially to SQLAlchemy Core select/insert/update.

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection of all 20 target router files — verified 2026-02-27
- Phase 24/25 migration pattern files (`test_phase24_auth_users_roles_async.py`, `test_phase25_messages_quiz_async.py`) — verified source inspection approach
- `app/api/v2/routers/patients/crud.py` — confirmed canonical async pattern (`await db.execute(select(...))`, `get_async_db`)
- `.planning/REQUIREMENTS.md` — confirmed API-06 through API-09 are pending
- `.planning/STATE.md` — confirmed Phase 25 completed, Phase 26 not started
- Project MEMORY.md — confirmed DualSessionMixin, PIISafeAgent, async migration decisions

### Secondary (MEDIUM confidence)
- SQLAlchemy 2.x async docs (training knowledge, consistent with observed code patterns in Phases 21–25)
- FastAPI dependency injection behavior (training knowledge, consistent with patterns in Phases 21–25)

### Tertiary (LOW confidence)
- DashboardService and DLQService internal behavior — not read during research; flagged as open questions

---

## Metadata

**Confidence breakdown:**
- Per-router migration inventory: HIGH — based on direct file read
- Migration patterns (select/execute): HIGH — established across 5 prior phases, verified in code
- Regression test design: HIGH — direct model from test_phase25_messages_quiz_async.py
- DashboardService / DLQService internals: LOW — not read; flagged as open questions

**Research date:** 2026-02-27
**Valid until:** 2026-03-13 (stable code, 14-day window)
