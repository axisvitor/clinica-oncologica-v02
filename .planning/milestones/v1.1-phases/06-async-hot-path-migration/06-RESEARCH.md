# Phase 6: Async Hot Path Migration - Research

**Researched:** 2026-02-22
**Domain:** SQLAlchemy AsyncSession migration — Python/FastAPI async hot paths
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ASYNC-01 | Migrar hot paths para `AsyncSession` — webhook handling (`sequential_message_handler.py`, 12 instancias anotadas com `TODO(async-migration)`) | AsyncSession infrastructure exists in `database.py`; `get_async_db()` dependency ready; asyncpg installed |
| ASYNC-02 | Migrar hot paths para `AsyncSession` — flow advancement (`flow_core.py`, 7 instancias anotadas) | FlowCore uses `db: Any` type hint — accepts AsyncSession; `_commit_flow_state_with_lock` is the critical sync method that needs async rewrite |
| ASYNC-03 | Migrar hot paths para `AsyncSession` — quiz response processing (`enhanced_quiz_service.py`, 8 instancias anotadas) | Router currently injects sync `get_db`; needs to switch to `get_async_db`; service constructor uses `db: Any` — type-flexible |
| ASYNC-05 | Migrar saga orchestrator para `AsyncSession` (compensation + steps — data integrity risk por timeout) | SagaOrchestrator, SagaCompensator, SagaStepExecutor all take `db: Session`; callers in `crud.py` and `saga_retry.py` are sync — partial migration is possible for compensation/steps sub-modules |
</phase_requirements>

---

## Summary

The project already has a complete, production-quality `AsyncSession` infrastructure in `app/database.py`. This includes an async engine (using asyncpg driver), an `async_sessionmaker`, a `get_async_db()` FastAPI dependency, and the `AsyncSessionLocal` proxy. The asyncpg driver (`>=0.30.0`) is listed in `requirements.txt`. There is no need to install anything new.

The core problem is that all four target services were built with sync `Session` and have `async def` methods that call synchronous SQLAlchemy operations (`self.db.query(...)`, `self.db.commit()`, `self.db.execute(text(...))`, `self.db.add(...)`, `self.db.flush()`). These block the event loop because the underlying psycopg (sync driver) performs blocking I/O on the thread. The fix for each service follows the same pattern: change `db: Session` to `db: AsyncSession`, replace `self.db.query(Model)` with `await self.db.execute(select(Model))`, replace `self.db.commit()` with `await self.db.commit()`, and replace `self.db.add(obj); self.db.commit()` with `self.db.add(obj); await self.db.flush(); await self.db.refresh(obj)` (within a session context that commits on exit) or `await self.db.commit()` directly.

The migration has two complexity tiers: (1) `sequential_message_handler.py`, `flow_core.py`, and `enhanced_quiz_service.py` are called from FastAPI routes that already use or can switch to `get_async_db` — straightforward injection change. (2) The saga orchestrator (`compensation.py`, `steps.py`) is called from both FastAPI routes (sync `get_db`) and Celery tasks (sync `get_scoped_session`) — the sub-module classes can accept `AsyncSession` once callers are updated, but Celery callers will need `asyncio.run()` wrapping.

**Primary recommendation:** For each of the four plans, the migration follows the same three-step pattern: (1) change type annotation, (2) convert queries to `select()`-based `await self.db.execute(...)`, (3) change `commit()`/`add()`/`flush()` calls to their async equivalents. Update the callers/factories to inject `AsyncSession` where they currently inject sync `Session`.

---

## Standard Stack

### Core (already installed — no new dependencies required)

| Library | Version in requirements.txt | Purpose | Why Standard |
|---------|----------------------------|---------|--------------|
| `sqlalchemy[asyncio]` | >=2.0 (inferred from asyncio imports working) | AsyncSession, async_sessionmaker, create_async_engine | Only official async SQLAlchemy path |
| `asyncpg` | `>=0.30.0,<0.31.0` | Async PostgreSQL driver used by AsyncEngine | Required by SQLAlchemy async for PostgreSQL |
| `psycopg[binary]` | `>=3.2.13,<3.3.0` | Sync driver still needed for Celery tasks | Celery workers remain sync |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sqlalchemy.ext.asyncio.AsyncSession` | — | Async session class | All async endpoint-path methods |
| `sqlalchemy.future.select` / `sqlalchemy.select` | — | Core-style queries replacing `.query()` ORM style | Required for AsyncSession — legacy query API not supported |
| `app.database.get_async_db` | — | FastAPI dependency injecting AsyncSession | Replace `Depends(get_db)` in async router factories |
| `app.utils.transaction_manager.async_transaction` | — | Context manager for auto-commit/rollback on AsyncSession | Wrap complex multi-step transactions |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Full AsyncSession | `loop.run_in_executor(None, sync_func)` | Executor approach avoids query rewrite but does NOT eliminate thread blocking — still occupies a thread pool thread, doesn't scale for high throughput hot paths |
| Direct `await session.commit()` | `async_transaction` context manager | Context manager adds safety but both are correct; direct commit is simpler for methods already managing their own error handling |

**Installation:** None required. All dependencies are already installed.

---

## Architecture Patterns

### Recommended Pattern: Async Query Replacement

The legacy sync ORM style (`self.db.query(Model).filter(...).first()`) is NOT supported by AsyncSession. Every query must be rewritten to use SQLAlchemy Core-style `select()`:

```python
# BEFORE (sync — blocks event loop)
from sqlalchemy.orm import Session
from sqlalchemy import text

def __init__(self, db: Session):
    self.db = db

async def get_flow_state(self, patient_id: UUID):
    # TODO(async-migration): sync SQLAlchemy calls block event loop
    flow_state = self.db.query(PatientFlowState)\
        .filter(PatientFlowState.patient_id == patient_id)\
        .first()
    return flow_state
```

```python
# AFTER (async — non-blocking)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

def __init__(self, db: AsyncSession):
    self.db = db

async def get_flow_state(self, patient_id: UUID):
    result = await self.db.execute(
        select(PatientFlowState)
        .filter(PatientFlowState.patient_id == patient_id)
    )
    flow_state = result.scalar_one_or_none()
    return flow_state
```

### Pattern: Commit / Add / Flush

```python
# BEFORE
self.db.add(flow_state)
self.db.commit()
self.db.refresh(flow_state)

# AFTER
self.db.add(flow_state)
await self.db.flush()
await self.db.refresh(flow_state)
# OR commit the transaction directly:
await self.db.commit()
```

### Pattern: Raw SQL with text()

```python
# BEFORE
result = self.db.execute(text("SELECT ftv.steps FROM ..."), {"kind": flow_kind}).fetchone()

# AFTER
result = await self.db.execute(text("SELECT ftv.steps FROM ..."), {"kind": flow_kind})
row = result.fetchone()
```

### Pattern: Scalar Query

```python
# BEFORE (in _commit_flow_state_with_lock)
current_version = self.db.query(PatientFlowState.version)\
    .filter(PatientFlowState.id == flow_state.id)\
    .scalar()

# AFTER
result = await self.db.execute(
    select(PatientFlowState.version)
    .filter(PatientFlowState.id == flow_state.id)
)
current_version = result.scalar_one_or_none()
```

### Pattern: Eager Loading

```python
# BEFORE
sessions = query.options(joinedload(QuizSession.quiz_template)).all()

# AFTER
result = await self.db.execute(
    select(QuizSession)
    .filter(...)
    .options(joinedload(QuizSession.quiz_template))
)
sessions = result.scalars().all()
```

### Pattern: FastAPI Dependency Injection

```python
# BEFORE (in router)
from app.database import get_db

async def get_enhanced_quiz_service(db=Depends(get_db)) -> EnhancedQuizService:
    return EnhancedQuizService(db)

# AFTER
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_async_db

async def get_enhanced_quiz_service(
    db: AsyncSession = Depends(get_async_db)
) -> EnhancedQuizService:
    return EnhancedQuizService(db)
```

### Pattern: Existing Working Example (message_service.py)

This is the canonical pattern already used in `app/integrations/whatsapp/services/message_service.py`:

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class WhatsAppMessageService:
    def __init__(self, ..., db: AsyncSession, ...):
        self.db = db

    async def some_method(self):
        stmt = select(WhatsAppInstance).where(WhatsAppInstance.name == instance_name)
        result = await self.db.execute(stmt)
        existing_instance = result.scalar_one_or_none()
```

### Anti-Patterns to Avoid

- **Mixing sync and async on the same session object:** Never call `self.db.query(...)` (sync ORM) on an `AsyncSession` — it raises `MissingGreenlet` or `greenlet_spawn` errors at runtime.
- **Calling `self.db.commit()` without await:** Silent no-op on AsyncSession, transaction never committed.
- **Using `expire_on_commit=True` (default) with AsyncSession in background tasks:** After `await session.commit()`, accessing lazy-loaded attributes raises `MissingGreenlet`. The session factory in `database.py` already sets `expire_on_commit=False` — preserve this.
- **Instantiating repositories with sync Session and passing to async methods:** Repositories (`FlowStateRepository`, `PatientRepository`) use `self.db.query(...)` — passing an `AsyncSession` to them will break silently. Each repository method accessed from async code must also be converted.

---

## File-by-File TODO Catalog

### File 1: `sequential_message_handler.py` (ASYNC-01)
**Path:** `backend-hormonia/app/services/flow/sequential_message_handler.py`
**Constructor:** `def __init__(self, db: Session, use_ai_personalization: bool = True)`
**Total TODOs:** 12

| Line | Method | Operation | Async Replacement |
|------|--------|-----------|-------------------|
| 232 | `_get_flow_day_config` | `self.db.execute(text(...)).fetchone()` | `await self.db.execute(text(...))` then `.fetchone()` |
| 268 | `_get_or_create_flow_state` | `self.flow_state_repo.get_active_flow(...)` (sync repo call) | Needs inline `select()` query OR async repo variant |
| 274 | `_get_or_create_flow_state` | `self.db.execute(text(...)).fetchone()`, `self.db.add(...)`, `self.db.commit()` | `await self.db.execute(...)`, `self.db.add(...)`, `await self.db.commit()` |
| 363 | `_send_flow_message` | `self.db.add(message)`, `self.db.commit()` | `self.db.add(message)`, `await self.db.commit()` |
| 387 | `_inject_quiz_link_if_needed` | `self.db.query(QuizTemplate).filter(...).all()` | `await self.db.execute(select(QuizTemplate).filter(...))` |
| 425 | `_inject_quiz_link_if_needed` | `self.db.query(QuizSession).filter(...).first()` | `await self.db.execute(select(QuizSession).filter(...))` |
| 450 | `_inject_quiz_link_if_needed` | `self.db.query(QuizSession).filter(...).first()` | `await self.db.execute(select(QuizSession).filter(...))` |
| 459 | `_inject_quiz_link_if_needed` | `self.db.commit()` | `await self.db.commit()` |
| 529 | `_send_all_sequential` | `self.db.commit()` | `await self.db.commit()` |
| 657 | `_send_wait_each_with_auto_advance` | `self.db.commit()` | `await self.db.commit()` |
| 846 | (send wait all remaining) | `self.db.commit()` | `await self.db.commit()` |
| 1154 | `_set_flow_progress` | `self.db.commit()` | `await self.db.commit()` |

**Sub-dependency problem:** `SequentialMessageHandler` instantiates:
- `FlowStateRepository(db)` — sync repo, methods like `get_active_flow()` use `self.db.query(...)`
- `MessageRepository(db)` — sync repo
- `UnifiedWhatsAppService(db)` — already detects `AsyncSession` (checks `isinstance(db, AsyncSession)`)

**Callers:**
- `app/services/webhook/handlers/message_handler.py` line 756: `handler = SequentialMessageHandler(self.db)` — `self.db` comes from the webhook route's session injection
- `app/services/response_processor/processor.py` line 679: `self._sequential_handler = SequentialMessageHandler(self.db)`
- `app/tasks/flow_automation.py`: uses `get_db_session()` (sync scoped session) — Celery task, stays sync

**Factory function (line 1159):**
```python
def get_sequential_message_handler(db: Session) -> SequentialMessageHandler:
    return SequentialMessageHandler(db)
```
Must be updated to accept `AsyncSession`.

---

### File 2: `flow_core.py` (ASYNC-02)
**Path:** `backend-hormonia/app/services/flow_core.py`
**Constructor:** `def __init__(self, db: Any, ...)` — already type-flexible
**Total TODOs:** 7

| Line | Method | Operation | Async Replacement |
|------|--------|-----------|-------------------|
| 175 | `enroll_patient` | `self.patient_repo.get(...)`, `self.flow_state_repo.get_active_flow(...)`, `self.db.query(FlowKind)`, add/commit | Multiple sync repo calls + direct query |
| 262 | `calculate_patient_day` | `self.flow_state_repo.get_active_flow(...)` | Sync repo call |
| 317 | `advance_patient_flow` | `self.flow_state_repo.get_active_flow(...)` | Sync repo call |
| 440 | `pause_patient_flow` | `self.flow_state_repo.get_active_flow(...)` | Sync repo call; also `_commit_flow_state_with_lock` is sync |
| 500 | `resume_patient_flow` | `self.flow_state_repo.get_active_flow(...)` | Sync repo call |
| 561 | `get_flow_state` | `self.patient_repo.get(...)`, `self.flow_state_repo.get_active_flow(...)` | Two sync repo calls |
| 792 | `health_check` | `self.db.execute("SELECT 1")` | `await self.db.execute(text("SELECT 1"))` |

**Critical sync method:** `_commit_flow_state_with_lock` (line 102) is a SYNC `def` called from multiple async methods. It contains:
- `self.db.query(PatientFlowState.version).filter(...).scalar()` — sync query
- `self.db.commit()` — sync commit

Must be converted to `async def _commit_flow_state_with_lock(...)` and called with `await`.

**Sub-dependency problem:** `PatientRepository(db)` and `FlowStateRepository(db)` are sync repos. For FlowCore, the key repo methods used are:
- `patient_repo.get(patient_id)` — single ID lookup
- `flow_state_repo.get_active_flow(patient_id)` — filter + join + first

**Recommendation:** Inline the critical repo calls as direct `await self.db.execute(select(...))` queries within FlowCore's async methods, rather than converting the entire repo classes. This is the lowest-risk approach per scope.

---

### File 3: `enhanced_quiz_service.py` (ASYNC-03)
**Path:** `backend-hormonia/app/services/enhanced_quiz_service.py`
**Constructor:** `def __init__(self, db: Any)` — already type-flexible
**Total TODOs:** 8

| Line | Method | Operation | Async Replacement |
|------|--------|-----------|-------------------|
| 158 | `get_quiz_analytics` | `self.db.query(QuizSession).join(...).filter(...).all()` | `await self.db.execute(select(...).join(...).filter(...))` |
| 283 | (analytics sub-method) | `self.db.query(QuizSession).filter(...).all()` | `await self.db.execute(...)` |
| 325 | `get_quiz_session_details` | `self.db.query(QuizSession).filter(...).first()` | `await self.db.execute(select(QuizSession).filter(...))` |
| 445 | `calculate_risk_score` | `self.db.query(QuizSession).filter(...).options(...).all()` | `await self.db.execute(select(...).options(...))` |
| 538 | (analytics) | `self.db.query(QuizSession).filter(...).options(...).all()` | `await self.db.execute(...)` |
| 617 | (bulk analytics) | `self.db.query(QuizSession).join(...).filter(...).all()` | `await self.db.execute(...)` |
| 745 | `bulk_quiz_operation` | `self.db.query(QuizSession).filter(...).first()`, `QuizSession(...)`, add/commit | Needs `await` on execute and commit |
| 854 | `export_quiz_data` | `self.db.query(QuizSession).join(...).filter(...).all()` | `await self.db.execute(...)` |

**Caller:**
- `app/api/v2/routers/enhanced_quiz.py` line 50: `async def get_enhanced_quiz_service(db=Depends(get_db))` — must change to `Depends(get_async_db)`

**Note on joinedload/selectinload:** With AsyncSession, `joinedload` and `selectinload` patterns still work when passed to `select(...).options(...)`. Lazy-loading is disabled — all relationships needed must be explicitly eager-loaded in the query.

---

### File 4: Saga Orchestrator — `compensation.py` + `steps.py` (ASYNC-05)
**Path:** `backend-hormonia/app/orchestration/saga_orchestrator/compensation.py` and `steps.py`

**compensation.py — TODOs:** 5
| Line | Method | Operation |
|------|--------|-----------|
| 90 | `_compensate_saga_internal` | `self.db.commit()`, `self.db.rollback()` after compensation steps |
| 241 | `_compensate_message` | `self.db.query(Message).filter(...).all()`, modifying messages |
| 299 | `_compensate_flow` | `self.db.query(PatientFlowState).filter(...).all()`, `self.db.delete(flow_state)` |
| 354 | (patient compensation) | `self.patient_repo` calls |
| 412 | (tracking) | `self.db` calls |

**steps.py — TODOs:** 3
| Line | Method | Operation |
|------|--------|-----------|
| 84 | `step_create_patient` | `self.patient_repo.create(...)`, `self.db.flush()` |
| 193 | (flow step) | `self.flow_service` calls |
| 315 | (whatsapp step) | Service calls, note: comment mentions "AsyncSession mismatch" was previously a known issue |

**Critical complexity for ASYNC-05:** The `SagaOrchestrator` itself (in `orchestrator.py`) takes `db: Session` and is instantiated from:
1. `app/api/v2/routers/patients/crud.py` — uses `Depends(get_db)` (sync)
2. `app/tasks/saga_retry.py` — uses `get_scoped_session()` (sync, Celery task)

The saga orchestrator is the most complex migration because:
- It has sub-components (`SagaCompensator`, `SagaStepExecutor`, `SagaPersistence`) all sharing the same `db` session
- `SagaPersistence` (query-only) and `SagaOrchestrator` itself are NOT in scope (ASYNC-05 specifies only compensation + steps)
- The Celery retry task (`saga_retry.py`) must remain sync — it calls `run_async()` wrapper for async saga execution

**Approach for ASYNC-05:** Convert `SagaCompensator` and `SagaStepExecutor` to accept `AsyncSession`, keeping `SagaOrchestrator` as the adapter that obtains and passes the async session to sub-components. The orchestrator's callers (FastAPI route and Celery) must be updated to supply `AsyncSession`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async session factory | Custom async session builder | `get_async_session_factory()` in `database.py` | Already handles SSL, pool config, `expire_on_commit=False` |
| Transaction management | Manual try/except commit/rollback | `async_transaction` context manager in `transaction_manager.py` | Project already has this utility |
| Async repository base | New `AsyncBaseRepository` class | Inline `select()`-based queries in service methods | Avoids converting all 22 repositories; scope is hot paths only |
| asyncpg installation | — | Already in `requirements.txt` | No action needed |

**Key insight:** This project already has the full infrastructure for async DB access. The work is converting query patterns, not building infrastructure. The `BaseRepository` is sync-only — do NOT attempt to generalize it for async within this phase. Inline the specific queries needed.

---

## Common Pitfalls

### Pitfall 1: Calling Sync Repo Methods on AsyncSession
**What goes wrong:** `FlowStateRepository(db).get_active_flow(patient_id)` where `db` is `AsyncSession` — raises `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await from sqlalchemy sync context`
**Why it happens:** `get_active_flow` uses `self.db.query(...)` which triggers sync I/O detection
**How to avoid:** Inline the query in the service method: `await self.db.execute(select(PatientFlowState).filter(...).join(...))` instead of using the repo
**Warning signs:** `MissingGreenlet` in traceback

### Pitfall 2: Forgetting `await` on `session.commit()`
**What goes wrong:** Data silently not committed; no error raised; subsequent reads may see stale state
**Why it happens:** `session.commit()` on `AsyncSession` returns a coroutine — without `await` it's a no-op
**How to avoid:** Always `await self.db.commit()`; enable async linting rules
**Warning signs:** Data appears not saved in integration tests

### Pitfall 3: `expire_on_commit=True` with Lazy Loading
**What goes wrong:** After `await session.commit()`, accessing `flow_state.patient` raises `MissingGreenlet` because lazy loading triggers sync I/O
**Why it happens:** AsyncSession disables implicit lazy loading by default
**How to avoid:** The existing `async_sessionmaker` already sets `expire_on_commit=False`. Never change this. Also use `selectinload()` or `joinedload()` in queries for needed relationships.
**Warning signs:** `greenlet_spawn` errors after commit when accessing model attributes

### Pitfall 4: Mixed Session Types in Same Call Chain
**What goes wrong:** A service method receives `AsyncSession` but passes it to a sub-service that holds a sync `Session` reference
**Why it happens:** `UnifiedWhatsAppService` — already handled (it detects session type). `FlowStateRepository`, `PatientRepository` — NOT handled
**How to avoid:** For each service that instantiates a repository with `self.db`, either inline the query or pass a sync session separately. Within this phase scope, inline the critical queries.
**Warning signs:** `MissingGreenlet` in repo method calls from async context

### Pitfall 5: `selectin` Loading in Async Context
**What goes wrong:** `selectinload` triggers additional SELECT queries automatically — in async context this requires the session to still be open
**Why it happens:** SQLAlchemy lazily executes `selectin` after the main query completes
**How to avoid:** Always ensure `selectinload()` is in the same `execute()` call, not added after fetching
**Warning signs:** `DetachedInstanceError` when accessing a `selectinload` relationship after session close

### Pitfall 6: `_commit_flow_state_with_lock` — Sync Method Called from Async
**What goes wrong:** `FlowCore._commit_flow_state_with_lock` is a sync `def` that calls `self.db.commit()`. When `self.db` is AsyncSession, the commit is silently not awaited.
**Why it happens:** Sync method cannot `await` inside itself; the `self.db.commit()` call returns a coroutine but does not execute it
**How to avoid:** Convert to `async def _commit_flow_state_with_lock(...)` and add `await self._commit_flow_state_with_lock(...)` at all three call sites (lines 375, 468, 530)
**Warning signs:** Flow state versions never increment; optimistic locking appears to pass when it should not

### Pitfall 7: Saga Orchestrator Celery Callers
**What goes wrong:** `saga_retry.py` uses `get_scoped_session()` (sync) and passes it to `SagaOrchestrator`. If the orchestrator's sub-components require `AsyncSession`, the Celery task will fail.
**Why it happens:** Celery workers run in sync context; `asyncio.run()` is needed to bridge async saga logic
**How to avoid:** In `saga_retry.py`, use `get_async_session_factory()` with `asyncio.run()` and an async context manager to get `AsyncSession`. Alternatively, keep saga retry calls wrapped in `run_async()` as they currently use.
**Warning signs:** `MissingGreenlet` in Celery task logs

---

## Code Examples

Verified patterns from existing codebase:

### Existing Working AsyncSession Pattern (from `routes.py`)
```python
# Source: backend-hormonia/app/integrations/whatsapp/api/routes.py lines 131-148
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_async_db

@router.get("/instances")
async def list_instances(db: AsyncSession = Depends(get_async_db)):
    stmt = select(WhatsAppInstance).where(WhatsAppInstance.name == instance_name)
    result = await db.execute(stmt)
    existing_instance = result.scalar_one_or_none()
```

### Existing get_async_db Dependency
```python
# Source: backend-hormonia/app/database.py lines 415-432
async def get_async_db() -> AsyncSession:
    async_session_factory = get_async_session_factory()
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Async database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()
```

### Async Transaction Context Manager
```python
# Source: backend-hormonia/app/utils/transaction_manager.py lines 22-60
from app.utils.transaction_manager import async_transaction

async with async_transaction(db) as session:
    session.add(new_record)
    # Auto-commits on success, auto-rolls back on exception
```

### Pattern for Replacing `self.db.query().join().filter().all()`
```python
# BEFORE (lines 172-187 in enhanced_quiz_service.py)
query = self.db.query(QuizSession).join(
    Patient, Patient.id == QuizSession.patient_id
)
if start_date:
    filters.append(QuizSession.created_at >= start_date)
sessions = query.options(joinedload(QuizSession.quiz_template)).all()

# AFTER
from sqlalchemy import select
from sqlalchemy.orm import joinedload

stmt = (
    select(QuizSession)
    .join(Patient, Patient.id == QuizSession.patient_id)
    .options(joinedload(QuizSession.quiz_template))
)
if start_date:
    stmt = stmt.where(QuizSession.created_at >= start_date)
result = await self.db.execute(stmt)
sessions = result.scalars().all()
```

### Pattern for Delete
```python
# BEFORE (compensation.py)
for flow_state in flow_states:
    self.db.delete(flow_state)

# AFTER — no change needed for delete() on individual loaded objects;
# the session.delete() method is still synchronous (marks for deletion),
# the actual DELETE executes on await self.db.flush() or await self.db.commit()
for flow_state in flow_states:
    await self.db.delete(flow_state)  # AsyncSession.delete() is a coroutine
```

**Important:** `AsyncSession.delete()` is a coroutine and must be awaited. `AsyncSession.add()` is NOT a coroutine — it is synchronous. `AsyncSession.commit()` IS a coroutine. `AsyncSession.flush()` IS a coroutine. `AsyncSession.refresh()` IS a coroutine.

---

## State of the Art

| Old Approach | Current Approach | Status |
|--------------|------------------|--------|
| `Session.query(Model).filter(...).all()` | `await session.execute(select(Model).where(...))` then `.scalars().all()` | AsyncSession does not support legacy query API |
| `Session.add(obj); Session.commit()` | `session.add(obj); await session.commit()` | `add()` is sync, `commit()` is async on AsyncSession |
| Sync `psycopg2` driver for async | `asyncpg` driver via `create_async_engine` | Already configured in `database.py` |
| `expire_on_commit=True` (default) | `expire_on_commit=False` | Already set in `get_async_session_factory()` |

---

## Open Questions

1. **Repository class conversion scope**
   - What we know: `FlowStateRepository`, `PatientRepository`, `MessageRepository` are all sync. The target services use them internally.
   - What's unclear: Should repos be converted to async (out of scope per REQUIREMENTS.md which limits to hot paths), or should the specific queries be inlined?
   - Recommendation: Inline specific queries in the service methods. Do NOT convert the repository base class — it would affect all callers. Add a comment `# Inlined from FlowStateRepository.get_active_flow() for async compat` to explain.

2. **`SequentialMessageHandler` instantiated from `ResponseProcessor`**
   - What we know: `processor.py` instantiates `SequentialMessageHandler(self.db)` at line 679. `ResponseProcessor.__init__` takes `db: Any`. The processor itself is called from both async webhook handlers and potentially sync contexts.
   - What's unclear: Does `ResponseProcessor` need to be updated to pass `AsyncSession`?
   - Recommendation: Check how `ResponseProcessor` is instantiated in the webhook route — if the route already gets `AsyncSession`, then the processor's `self.db` is already async-compatible once `SequentialMessageHandler` is migrated.

3. **Saga retry Celery task bridge**
   - What we know: `saga_retry.py` uses `get_scoped_session()` (sync) and `run_async()`. ASYNC-05 requires saga compensation to use AsyncSession.
   - What's unclear: Whether the Celery task should obtain `AsyncSession` via `asyncio.run(async_with_session())` pattern, or whether a thin wrapper maintains backward compat.
   - Recommendation: Use `asyncio.run()` with `get_async_session_factory()` in Celery tasks for saga operations. The `run_async()` helper already exists in `app/utils/async_helpers.py`.

---

## Sources

### Primary (HIGH confidence)
- Codebase direct inspection — `backend-hormonia/app/database.py` lines 319-432 — async engine, session factory, `get_async_db` dependency confirmed
- Codebase direct inspection — `backend-hormonia/requirements.txt` lines 9-11 — asyncpg `>=0.30.0` confirmed installed
- Codebase direct inspection — all four target files — TODO line numbers and operations confirmed via Grep

### Secondary (MEDIUM confidence)
- `backend-hormonia/docs/reports/debug/async-quick-reference.md` — project's own async migration guide, validates patterns
- `backend-hormonia/app/integrations/whatsapp/api/routes.py` — verified working AsyncSession usage pattern in this codebase
- `backend-hormonia/app/services/audit/audit_service.py` — verified `AsyncSession` in `__init__` pattern
- `backend-hormonia/app/utils/transaction_manager.py` — verified `async_transaction` context manager exists and is usable

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — asyncpg and SQLAlchemy async already installed and configured
- Architecture: HIGH — exact line numbers and operations found via direct grep; existing working patterns identified in same codebase
- Pitfalls: HIGH — several pitfalls documented in codebase's own async docs + confirmed by reading actual code paths
- Caller analysis: MEDIUM — found primary callers; async chain tracing is complete for FastAPI paths; Celery path has one open question

**Research date:** 2026-02-22
**Valid until:** 2026-05-22 (stable — SQLAlchemy async API is stable; asyncpg version pinned)
