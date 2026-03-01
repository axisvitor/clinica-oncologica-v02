# Phase 28: Async Session Gap Closure - Research

**Researched:** 2026-02-28
**Domain:** SQLAlchemy AsyncSession adapter pattern, FastAPI dependency injection
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TEST-01 | Test fixtures support AsyncSession endpoints via `get_async_db` override in client fixtures — specifically: `SyncToAsyncSessionAdapter` must expose awaitable wrappers for `delete()`, `add()`, `scalars()`, and `get()` so that `await db.delete(obj)` does not raise TypeError | The `__getattr__` fallback on the current adapter returns the underlying sync session method directly. Sync methods return `None`, not an awaitable. Adding explicit methods that call the sync operation and return `self._awaitable()` follows the exact same pattern already used by `commit`, `flush`, `refresh`, and `rollback` in both conftest copies. |
| API-09 | Remaining routers use AsyncSession — specifically: `enhanced_reports.py` must replace `iter_db_dependency(get_db)` with direct `Depends(get_async_db)` | `enhanced_reports.py` currently imports `get_db` from `app.database` and wraps it with `iter_db_dependency`. The `EnhancedReportsService` constructor accepts `Any` for `db`, so no constructor change is needed. The migration is a straight swap of `_get_db_dep` with `Depends(get_async_db)`. |

</phase_requirements>

---

## Summary

Phase 28 closes two isolated code-level gaps discovered during the v1.4 milestone audit. Both gaps are narrow, mechanical, and do not require architectural changes.

**Gap 1 (TEST-01):** `SyncToAsyncSessionAdapter` in `tests/conftest.py` and `tests/api/critical/conftest.py` falls back to `__getattr__` for any method not explicitly defined. When a router calls `await db.delete(obj)`, the adapter's `__getattr__` returns `self._sync_session.delete`, a regular bound method that returns `None`. Python then tries to `await None`, which raises `TypeError: object NoneType can't be used in 'await' expression`. The fix is to add explicit awaitable wrappers for `delete()`, `add()`, `scalars()`, and `get()` — the same pattern as the existing `commit()`, `flush()`, `refresh()`, `rollback()`, and `close()` wrappers. Five routers currently use `await db.delete()`: `alerts.py`, `appointments.py`, `flow_templates.py`, `quiz_sessions.py`, and `quiz_templates.py`. All five use `get_async_db` directly and will hit the adapter during test execution.

**Gap 2 (API-09):** `enhanced_reports.py` is the sole remaining router using sync `get_db` via the `iter_db_dependency` adapter function. The `EnhancedReportsService` does not actually use the `db` parameter for real DB operations (it uses Redis cache exclusively), so passing either a sync Session or an AsyncSession makes no functional difference. The migration is purely a dependency injection swap: remove `_get_db_dep`, remove the `iter_db_dependency(get_db)` call, import `get_async_db`, and use `Depends(get_async_db)` directly in `get_enhanced_reports_service`.

**Primary recommendation:** Add four awaitable wrapper methods to both adapter copies, then replace the `_get_db_dep` helper in `enhanced_reports.py` with a direct `Depends(get_async_db)`. No service changes, no schema changes, no test framework changes.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy AsyncSession | 2.x (already installed) | Async DB session type used by all migrated routers | Already the project standard since Phase 21 |
| pytest + pytest-asyncio | already configured | Test infrastructure for async test functions | Project test standard throughout v1.4 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `app.core.database.async_engine.get_async_db` | project-local | FastAPI async DB dependency | All API routers — canonical import path |
| `app.database.get_db` | project-local (sync, keep for Celery) | Sync session for Celery tasks only | Do NOT use in API routers |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Explicit awaitable wrappers | `__getattr__` with coroutine wrapping | `__getattr__` approach is fragile; returns a coroutine wrapping a sync call but `delete()` return value is `None` so there is nothing to wrap; explicit wrappers are simpler and match the existing adapter style |
| Direct `Depends(get_async_db)` | Keep `iter_db_dependency` + pass `get_async_db` | `iter_db_dependency` supports async generators too, but introducing unnecessary indirection hides intent; direct `Depends` is the project standard for all other routers |

---

## Architecture Patterns

### Pattern 1: Awaitable Wrapper Method (existing adapter style)

**What:** Each method that a router may `await` is defined explicitly on the adapter. The method calls the underlying sync session operation synchronously, then returns `self._awaitable(return_value)`.

**When to use:** Any adapter method that the endpoint code prefixes with `await`.

**Example (from existing `commit` method — both conftest copies):**
```python
def commit(self):
    self._sync_session.flush()
    return self._awaitable()
```

**New methods to add, following the same pattern:**
```python
def delete(self, instance):
    self._sync_session.delete(instance)
    return self._awaitable()

def add(self, instance):
    self._sync_session.add(instance)
    return self._awaitable()

def scalars(self, statement, *args, **kwargs):
    result = self._sync_session.execute(statement, *args, **kwargs)
    return self._awaitable(result.scalars())

def get(self, entity, ident, **kwargs):
    return self._awaitable(self._sync_session.get(entity, ident, **kwargs))
```

**Key constraint:** `delete()` and `add()` return `None` from the sync session, so `self._awaitable()` with no argument (defaults to `None`) is correct. `scalars()` returns a `ScalarResult`, so it must pass the result. `get()` returns the instance or `None`.

### Pattern 2: Direct `Depends(get_async_db)` in Router

**What:** Replace the `_get_db_dep` generator helper and the `iter_db_dependency(get_db)` call with a direct FastAPI dependency on `get_async_db`.

**When to use:** Any router that previously used a wrapper around `get_db`.

**Before (`enhanced_reports.py` current state):**
```python
from app.database import get_db
from app.api.v2.db_dependency_shared import iter_db_dependency

async def _get_db_dep():
    async for db in iter_db_dependency(get_db):
        yield db

async def get_enhanced_reports_service(db=Depends(_get_db_dep)) -> EnhancedReportsService:
    return EnhancedReportsService(db)
```

**After (target state):**
```python
from app.core.database.async_engine import get_async_db

async def get_enhanced_reports_service(
    db: AsyncSession = Depends(get_async_db),
) -> EnhancedReportsService:
    return EnhancedReportsService(db)
```

Remove the `_get_db_dep` function entirely. Remove the `iter_db_dependency` import. Remove the `get_db` import from `app.database`.

### Pattern 3: Two-File Adapter Synchronization

**What:** The `SyncToAsyncSessionAdapter` class is defined in two separate files:
- `tests/conftest.py` (line 1019) — root conftest used by most tests
- `tests/api/critical/conftest.py` (line 863) — critical-path conftest

Both files are structurally identical for the adapter class. Both must receive the same four new methods.

**Verification:** After adding wrappers, both files' adapter class definitions should pass a source-level check that verifies `def delete`, `def add`, `def scalars`, and `def get` are defined.

### Anti-Patterns to Avoid

- **Relying on `__getattr__` for awaited methods:** `__getattr__` returns the underlying sync method directly. Sync methods that return `None` will cause `TypeError: object NoneType can't be used in 'await' expression` when the router does `await db.delete(obj)`.
- **Passing `AsyncSession` to a service that calls `db.query()`:** `EnhancedReportsService` uses `self.db` only for constructor storage; it does not call `db.query()` or `await db.execute()` in its current implementation. No service-level changes are needed.
- **Importing `get_db` in API routers:** The project-wide regression tests (from Phases 25-26) scan for `Depends(get_db)` in router files as a CI gate. After this phase, `enhanced_reports.py` must not import `get_db`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Making sync `None` awaitable | Custom coroutine wrapper | `self._awaitable()` (already in adapter) | The `_awaitable` static method handles this cleanly; no new abstraction needed |
| Detecting if a method is being awaited | Runtime introspection | Explicit method definitions | Python `await` checks `__await__` at call site; the cleanest solution is always an explicit definition |

---

## Common Pitfalls

### Pitfall 1: `get()` signature mismatch with SQLAlchemy 2.x
**What goes wrong:** SQLAlchemy 2.x `Session.get()` accepts keyword args like `options`, `populate_existing`. If the adapter's `get()` signature is too narrow, passing those args in router code will raise `TypeError`.
**Why it happens:** The adapter wraps a sync session; the sync `Session.get()` shares the same signature as `AsyncSession.get()`.
**How to avoid:** Use `**kwargs` in the adapter `get()` signature: `def get(self, entity, ident, **kwargs)`.

### Pitfall 2: `scalars()` vs `execute().scalars()`
**What goes wrong:** In AsyncSession, `scalars()` is a shorthand that runs the statement and returns a `ScalarResult`. In a sync session, there is no direct `session.scalars()` in older SQLAlchemy. SQLAlchemy 2.x sync Session does have `session.scalars()` as a convenience method.
**Why it happens:** Routers calling `await db.scalars(select(...))` expect the same return signature as `AsyncSession.scalars()`.
**How to avoid:** Call `self._sync_session.scalars(statement, *args, **kwargs)` if SQLAlchemy 2.x is confirmed; otherwise call `self._sync_session.execute(statement, *args, **kwargs).scalars()` as a safe fallback.
**Project context:** The project uses SQLAlchemy 2.x throughout (asyncpg driver, `async_sessionmaker`). `Session.scalars()` is available. Verify the installed version with `pip show sqlalchemy` or `requirements.txt`.

### Pitfall 3: Forgetting the critical conftest copy
**What goes wrong:** Wrappers added to `tests/conftest.py` but not `tests/api/critical/conftest.py`. Tests in `tests/api/critical/` continue to fail with TypeError.
**Why it happens:** Two independent copies of the class; easy to miss the second file.
**How to avoid:** Add wrappers to both files in the same plan task. Add a source-level regression assertion that checks both files contain `def delete`.

### Pitfall 4: `enhanced_reports.py` still imports `iter_db_dependency`
**What goes wrong:** Import line left behind after migration causes no runtime error but leaves a cosmetic violation that the Phase 25-26 regression scans may flag.
**How to avoid:** Remove the entire `_get_db_dep` function and both imports (`get_db` and `iter_db_dependency`) as part of the migration task.

### Pitfall 5: `EnhancedReportsService` type hint
**What goes wrong:** After migration, `get_enhanced_reports_service` accepts `db: AsyncSession` but `EnhancedReportsService.__init__` is typed as `def __init__(self, db: Any)`. This is intentional (service does not use the DB for real operations) but may cause a misleading static-analysis warning.
**How to avoid:** No change needed in the service. The `Any` type is correct given the service's current mock/cache-only implementation.

---

## Code Examples

### Adding `delete` wrapper to the adapter

```python
def delete(self, instance):
    self._sync_session.delete(instance)
    return self._awaitable()
```

### Adding `add` wrapper to the adapter

```python
def add(self, instance):
    self._sync_session.add(instance)
    return self._awaitable()
```

### Adding `scalars` wrapper to the adapter

```python
def scalars(self, statement, *args, **kwargs):
    return self._awaitable(self._sync_session.scalars(statement, *args, **kwargs))
```

### Adding `get` wrapper to the adapter

```python
def get(self, entity, ident, **kwargs):
    return self._awaitable(self._sync_session.get(entity, ident, **kwargs))
```

### Migrated `get_enhanced_reports_service` factory

```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database.async_engine import get_async_db

async def get_enhanced_reports_service(
    db: AsyncSession = Depends(get_async_db),
) -> EnhancedReportsService:
    return EnhancedReportsService(db)
```

### Source-level regression assertion (for plan verification task)

```python
import inspect, importlib

def test_adapter_has_awaitable_wrappers():
    import tests.conftest as root_conftest
    src = inspect.getsource(root_conftest.SyncToAsyncSessionAdapter)
    for method in ("def delete", "def add", "def scalars", "def get"):
        assert method in src, f"SyncToAsyncSessionAdapter missing {method}"

def test_enhanced_reports_no_sync_get_db():
    import importlib.util, pathlib
    path = pathlib.Path("backend-hormonia/app/api/v2/routers/enhanced_reports.py")
    src = path.read_text()
    assert "iter_db_dependency" not in src
    assert "from app.database import get_db" not in src
    assert "get_async_db" in src
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sync `get_db` in API routers | `get_async_db` (AsyncSession) for all API routers | Phase 21-26 | All router DB calls are non-blocking |
| `__getattr__` fallback for all Session methods | Explicit awaitable wrappers for write methods | Phase 24 (commit, flush, refresh) + Phase 27 (begin_nested) + Phase 28 (delete, add, scalars, get) | Tests can exercise any router endpoint that awaits these methods |
| `iter_db_dependency` adapter | Direct `Depends(get_async_db)` | Phase 26 for most routers; Phase 28 for enhanced_reports.py | Simpler, consistent, scannable |

---

## Open Questions

1. **Does `Session.scalars()` exist in the installed SQLAlchemy version?**
   - What we know: SQLAlchemy 2.0+ added `Session.scalars()` as a convenience method mirroring `AsyncSession.scalars()`.
   - What's unclear: The exact SQLAlchemy version pinned in `requirements.txt` was not checked.
   - Recommendation: If any router calls `await db.scalars(...)`, verify with `grep -rn "await db\.scalars" backend-hormonia/app/api/`. If no router currently uses it, the `scalars` wrapper can still be added as a safety measure using the `execute().scalars()` fallback pattern.

2. **Are there test files that exercise `await db.delete()` through the test client (not unit tests)?**
   - What we know: Unit tests in `tests/unit/api/v2/test_quiz_sessions_orphan_security.py` use a hand-rolled `_FakeDB` that has its own sync `delete()`. Integration tests in `tests/api/v2/test_quiz.py` and `tests/api/critical/test_quiz_session.py` exercise the delete endpoint via TestClient, which routes through the adapter.
   - What's unclear: Whether the TestClient-based tests actually hit the `await db.delete()` code path (the TestClient tests may have their own auth bypass that prevents reaching the delete call).
   - Recommendation: Add a targeted regression test that directly calls the router function with a `SyncToAsyncSessionAdapter`-backed db to confirm no TypeError.

---

## Validation Architecture

> `workflow.nyquist_validation` is not set in `.planning/config.json`. Skipping this section.

---

## File Inventory

### Files to Modify

| File | Change | Gap |
|------|--------|-----|
| `backend-hormonia/tests/conftest.py` | Add `delete`, `add`, `scalars`, `get` methods to `SyncToAsyncSessionAdapter` (class at line 1019) | TEST-01 |
| `backend-hormonia/tests/api/critical/conftest.py` | Add same four methods to `SyncToAsyncSessionAdapter` (class at line 863) | TEST-01 |
| `backend-hormonia/app/api/v2/routers/enhanced_reports.py` | Replace `_get_db_dep` + `iter_db_dependency(get_db)` with `Depends(get_async_db)`; remove `get_db` and `iter_db_dependency` imports | API-09 |

### Files to Create

| File | Purpose | Gap |
|------|---------|-----|
| `backend-hormonia/tests/test_phase28_gap_closure.py` | Source-level regression assertions: adapter has all four wrappers, enhanced_reports has no sync get_db | TEST-01 + API-09 |

### Files to NOT Modify

- `app/services/reporting/enhanced_reports_service.py` — constructor accepts `Any`; service uses Redis cache, not DB; no change needed
- `app/api/v2/db_dependency_shared.py` — utility still used by other routers in theory; do not remove
- Any Celery task files — must remain on sync `get_db`

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `tests/conftest.py` lines 1019-1124 — full `SyncToAsyncSessionAdapter` class with `__getattr__` fallback and existing awaitable wrappers
- Direct codebase inspection: `tests/api/critical/conftest.py` lines 863-962 — second copy of the same adapter class
- Direct codebase inspection: `app/api/v2/routers/enhanced_reports.py` lines 27, 57, 73-75, 269 — sync `get_db` via `iter_db_dependency`
- Direct codebase inspection: `app/core/database/async_engine.py` — canonical `get_async_db` implementation
- Direct codebase inspection: five router files (`alerts.py`, `appointments.py`, `flow_templates.py`, `quiz_sessions.py`, `quiz_templates.py`) — all confirmed to use `get_async_db` directly and call `await db.delete()`
- `.planning/v1.4-MILESTONE-AUDIT.md` — authoritative gap description with exact line numbers and affected routers

### Secondary (MEDIUM confidence)
- SQLAlchemy 2.x documentation pattern: `Session.scalars()` is a convenience method available since 2.0 — consistent with project's use of `async_sessionmaker` and `create_async_engine` which are 2.0+ APIs

---

## Metadata

**Confidence breakdown:**
- Gap identification: HIGH — both gaps are confirmed by direct code inspection and the audit document
- Fix approach: HIGH — the adapter wrapper pattern is already established by 5 existing methods in the same class
- `enhanced_reports.py` migration: HIGH — mechanical import swap with no service dependency changes
- `scalars()` sync availability: MEDIUM — SQLAlchemy 2.x but version not pinned-confirmed from requirements.txt

**Research date:** 2026-02-28
**Valid until:** 2026-03-28 (stable domain — SQLAlchemy adapter pattern, no external API dependencies)
