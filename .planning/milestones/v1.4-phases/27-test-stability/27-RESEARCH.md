# Phase 27: Test Stability - Research

**Researched:** 2026-02-27
**Domain:** pytest fixtures, AsyncSession test infrastructure, SQLAlchemy async testing, annotation cleanup
**Confidence:** HIGH

## Summary

Phase 27 is the closing phase of the v1.4 AsyncSession & Test Stability milestone. Phases 20-26 migrated
all API routers, services, and critical code paths to AsyncSession. Phase 27 now focuses on three
orthogonal tasks: (1) ensuring the existing `SyncToAsyncSessionAdapter` fixture correctly covers all
`get_async_db` override scenarios, (2) running the full test suite to confirm zero `MissingGreenlet` and
`UndefinedColumn` errors remain, and (3) removing the one remaining `TODO(async-migration)` annotation.

The key discovery from codebase analysis is that the annotation count is dramatically lower than the
MEMORY.md estimate of 42+. A full grep confirms **only 1 instance** of `TODO(async-migration)` remains
in `app/services/patient/sync_service.py` (line 102), and it is already a correct no-op comment marking a
completed migration. The main work is: (a) verify and harden the fixture infrastructure, (b) fix the
`test_bulk_delete_success` regression noted in STATE.md, and (c) execute a clean full-suite run to
confirm all success criteria.

There are also **unregistered dead-code modules** (`app/api/v2/messages/` sub-package and
`app/api/v2/flows/advanced.py`, `state.py`, `templates.py`, `analytics.py`) that still use
`Depends(get_db)` and `db.query()`. These are NOT imported by `router.py` (the canonical registered
routers all live under `app/api/v2/routers/` and are confirmed clean). These dead-code files are out of
scope per the requirements definition.

**Primary recommendation:** Three-plan execution — (1) remove the single remaining annotation, verify
fixture coverage, and fix the bulk-delete test; (2) run full suite and fix any remaining errors; (3) lock
regression gate.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TEST-01 | Test fixtures support AsyncSession endpoints via `get_async_db` override in client fixtures | `SyncToAsyncSessionAdapter` already exists in `tests/conftest.py` and is wired via `client` fixture's `_override_get_async_db`. Gap: `seed_flow_templates` in `tests/api/v2/conftest.py` still calls `db_session.query(FlowKind)` — needs review for whether it runs in async context. Main adapter covers execute/commit/flush/refresh/rollback/close. |
| TEST-02 | Full `pytest` suite runs without `MissingGreenlet` or `UndefinedColumn` errors | All API routers under `app/api/v2/routers/` confirmed zero `Depends(get_db)` and zero `db.query()`. Dead-code modules (`app/api/v2/messages/`, `app/api/v2/flows/`) still have sync calls but are not registered in `router.py`. `auth_session_shared.py` has one `db.query()` in a nested function — needs assessment for whether it can be called from async context. |
| TEST-03 | No sync-in-async blocking regressions — all `TODO(async-migration)` annotations removed | Only 1 annotation remains: `app/services/patient/sync_service.py:102` — already correct code, just needs the comment removed. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 7.0+ (pyproject.toml: minversion="7.0") | Test runner | Configured in pyproject.toml; asyncio_mode="auto" |
| pytest-asyncio | current | Async test support | asyncio_mode="auto" in pyproject.toml |
| sqlalchemy | 2.x | ORM + async engine | AsyncSession, select(), execute() |
| httpx | current | ASGI test transport | Used in AsyncTestClient |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `SyncToAsyncSessionAdapter` | project-local | Wraps sync session to satisfy AsyncSession interface in tests | All endpoints using `get_async_db` |
| `AsyncTestClient` | project-local (`tests/utils/async_test_client.py`) | Sync-API wrapper over httpx.AsyncClient + ASGITransport | All API endpoint tests |
| `StaticPool` | sqlalchemy | Shared in-memory SQLite for test isolation | Default test mode (non-Postgres) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `SyncToAsyncSessionAdapter` | `pytest-anyio` + real `AsyncSession` over `aiosqlite` | Real async engine would be more faithful but requires full async test infra migration; adapter is already in place |

## Architecture Patterns

### Existing Test Infrastructure

```
tests/
├── conftest.py            # Root: test_engine, db_session, SyncToAsyncSessionAdapter, client
├── api/
│   ├── conftest.py        # API-level: admin_user, user_token, auto_csrf_headers
│   └── v2/
│       ├── conftest.py    # v2-level: test_admin_user, test_doctor_user, test_patient, auth_headers_*
│       └── test_*.py      # Test files use `client` fixture from root conftest
├── utils/
│   ├── async_test_client.py  # AsyncTestClient (httpx.AsyncClient + ASGITransport)
│   └── sync_executor.py
└── integration/
    └── test_phase22_async_load_missinggreenlet.py  # Existing load tests
```

### Pattern 1: SyncToAsyncSessionAdapter (already implemented)

The `client` fixture in `tests/conftest.py` overrides both `get_db` and `get_async_db`:

```python
# Source: backend-hormonia/tests/conftest.py lines 1091-1101
async def _override_get_db():
    return db_session

app.dependency_overrides[get_db] = _override_get_db

async def _override_get_async_db():
    yield SyncToAsyncSessionAdapter(db_session)

app.dependency_overrides[get_async_db] = _override_get_async_db
```

The `SyncToAsyncSessionAdapter` wraps every method to return awaitable proxies:
- `execute()` → returns `_AwaitableResultProxy` that proxies all Result methods
- `commit()` → calls `flush()` on sync session, returns awaitable
- `flush()` → calls sync flush, returns awaitable
- `refresh()` → calls sync refresh, returns awaitable
- `rollback()` / `close()` → no-op awaitable
- `__getattr__` → delegates to sync session for anything else

**Gap to verify:** The adapter does NOT have an `add()` method. The `__getattr__` delegation handles this by
falling through to `self._sync_session.add()` — but `add()` is a synchronous non-awaited call, which is
correct because `session.add()` in SQLAlchemy does not need to be awaited even in async sessions.

### Pattern 2: Dead-code modules with get_db (OUT OF SCOPE)

The following are NOT registered in `app/api/v2/router.py` and are confirmed dead code:
- `app/api/v2/messages/` (analytics, bulk, conversations, crud, helpers, retry, send, stats, templates)
- `app/api/v2/flows/advanced.py`, `state.py`, `templates.py`, `analytics.py`
- `app/api/v2/auth_session_shared.py` (utility module, not a router)
- `app/api/v2/monitoring/whatsapp.py`
- `app/api/v2/patients_utils.py`
- `app/api/v2/templates_shared.py`

Per requirements, TEST-02 only applies to the registered API surface. The Phase 25 note explicitly
states the `messages/` sub-package is "dead code from an incomplete refactor; not imported by `router.py`
and is out of scope."

### Pattern 3: Test client fixture auth patterns

Tests in `tests/api/v2/test_admin.py` rely on `get_admin_user` dependency fallback for unauthenticated
tests — the dependency checks `_is_test_environment()` and `TESTING=1` and falls back to querying the DB
for the first active admin. This fallback finds `admin_user` because `admin_user` is created in the same
`db_session` that `SyncToAsyncSessionAdapter` wraps.

### Anti-Patterns to Avoid

- **Replacing SyncToAsyncSessionAdapter with real aiosqlite:** Would require rewriting all
  transaction-scoped fixtures and likely introduce greenlet context issues with SQLite async drivers.
- **Wrapping db.query() calls in dead-code modules:** These are out of scope; do not migrate them.
- **Deleting the TODO comment without verifying the code is correct:** The code at line 102 of
  `sync_service.py` already uses `select()` correctly — only remove the comment, not the logic.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async-compatible sync session | Custom async session wrapper from scratch | Existing `SyncToAsyncSessionAdapter` in `tests/conftest.py` | Already handles execute/commit/flush/refresh; extending it is safer than replacing |
| Test async detection | Custom is_async_context check | `asyncio_mode="auto"` from pyproject.toml handles this | pytest-asyncio's auto mode already lifts all test functions |
| MissingGreenlet detection | Custom log scanning | Existing log-based checks in `test_phase22_async_load_missinggreenlet.py` | Pattern already established for asserting zero MissingGreenlet logs |

**Key insight:** The test infrastructure is already 90% correct. Phase 27 is a verification and cleanup
phase, not a build phase.

## Common Pitfalls

### Pitfall 1: SyncToAsyncSessionAdapter missing scalar_one_or_none

**What goes wrong:** When an endpoint calls `result = await db.execute(...)` then `result.scalar_one_or_none()`,
the `_AwaitableResultProxy.__getattr__` delegates to the underlying sync `Result` — this should work
correctly. However if the proxy returns itself when awaited but the code does `scalar = await db.execute(stmt)`
then `scalar.scalars()`, we could have an issue if the Result proxy does not faithfully delegate all chained calls.

**Why it happens:** `_AwaitableResultProxy` uses `__getattr__` delegation, so `result.scalars().all()` should
work. But `result.scalar_one_or_none()` calls `scalar_one_or_none` on the underlying sync result, which is correct.

**How to avoid:** Before declaring TEST-01 complete, execute a representative set of endpoint tests that
exercise scalar_one_or_none, scalars().all(), and scalar() patterns.

**Warning signs:** Tests return unexpected None or raise AttributeError on Result methods.

### Pitfall 2: seed_flow_templates fixture uses db.query() in async context

**What goes wrong:** `tests/api/v2/conftest.py` has an `autouse=True` fixture `seed_flow_templates` that
calls `db_session.query(FlowKind).filter(...)`. This runs inside the function-scoped `db_session` (sync),
which is fine — but if a future test runs the fixture during an async ASGI request via AsyncTestClient, the
sync query on the adapter could fail.

**Why it happens:** `seed_flow_templates` is a pytest fixture that runs before the test body, outside any
async request context. It uses `db_session: Session` directly, not the adapter. This is safe as long as it
never gets called inside an async request handler.

**How to avoid:** Leave as-is; document that fixture-level setup uses sync db_session directly.

### Pitfall 3: test_bulk_delete_success returning HTTP 400

**What goes wrong:** STATE.md documents that `tests/api/v2/test_admin.py::TestBulkDelete::test_bulk_delete_success`
returns HTTP 400 instead of 200.

**Root cause analysis:** The test creates `multiple_users` (25 users) and sends `user_ids = [str(u.id) for u in multiple_users[:3]]`. The bulk-delete endpoint checks `if admin_user.id in bulk_data.user_ids`. The `admin_user` local fixture in `test_admin.py` creates a user with email `admin@test.com`. The `get_admin_user` dependency in test-mode queries for any active ADMIN user in the DB. The `multiple_users` fixture creates users with role ADMIN for odd indices (role=UserRole.ADMIN when i%2==1), and `multiple_users[:3]` includes index 1 (ADMIN, inactive). The fallback `get_admin_user` picks the FIRST active admin from DB — in the shared in-memory SQLite, the first admin found could be `user1` from `multiple_users` (index 1, but `is_active = i%3 != 0 = 1%3 != 0 = True`, wait: `is_active = 1%3 != 0 = True`). So `user1` is ADMIN and active, and it's in `user_ids`, triggering the "Cannot delete your own account" 400 error.

**How to fix:** The test must explicitly exclude the `admin_user` from the user IDs being deleted, or
the auth override must use the explicitly created `admin_user` fixture instead of the DB fallback. The
correct fix is to set a proper dependency override for `get_admin_user` in the test, similar to how
`auth_headers_admin` works in `tests/api/v2/conftest.py`.

**Warning signs:** 400 BAD REQUEST with "Cannot delete your own account" message.

### Pitfall 4: auth_session_shared.py db.query in nested async function

**What goes wrong:** `app/api/v2/auth_session_shared.py` line 65 defines `async def _fetch_user_by_uid`
that calls `db.query(User)`. This function is a callback passed to `get_or_cache_user_data`. If `db` here
is an `AsyncSession`, calling `db.query()` raises `MissingGreenlet`.

**Why it matters:** `auth_session_shared.py` is a utility module used by some auth flows. If any registered
router calls `get_user_data_from_session`, this becomes a live issue. Requires investigation.

**How to avoid:** Replace `db.query(User).filter(...)` with `await db.execute(select(User).where(...))` and
convert the nested function to async. Or verify it is only called from paths that never receive AsyncSession.

## Code Examples

### Removing a TODO(async-migration) comment

```python
# Source: app/services/patient/sync_service.py:102
# BEFORE (with annotation):
# TODO(async-migration): converted from .query() to select() for AsyncSession compat
stmt = select(Patient).filter(
    patient_field == field_hash, Patient.deleted_at.is_(None)
)

# AFTER (comment removed, code unchanged):
stmt = select(Patient).filter(
    patient_field == field_hash, Patient.deleted_at.is_(None)
)
```

### Fixing the bulk-delete test auth

```python
# Source: tests/api/v2/test_admin.py — add explicit admin override
@pytest.fixture
def admin_override(admin_user: User):
    from app.main import app
    from app.api.v2.routers.admin.dependencies import get_admin_user
    app.dependency_overrides[get_admin_user] = lambda: admin_user
    yield admin_user
    app.dependency_overrides.pop(get_admin_user, None)
```

### Verifying zero remaining annotations (TEST-03 gate check)

```bash
# Run from backend-hormonia/
grep -r "TODO(async-migration)" app/ --include="*.py" | wc -l
# Must return 0
```

### Running the full test suite for TEST-02

```bash
cd backend-hormonia
python -m pytest tests/ -x -q 2>&1 | tee /tmp/suite-run.txt
grep -i "missinggreenlet\|undefinedcolumn" /tmp/suite-run.txt
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `db.query()` in async handlers | `await db.execute(select(...))` | Phases 21-26 | All registered routers clean |
| Sync `Session` in all test fixtures | `SyncToAsyncSessionAdapter` wrapping sync session | Phase 21-24 | AsyncSession-facing endpoints testable without real async engine |
| 42+ `TODO(async-migration)` annotations | 1 remaining (comment-only, no code change needed) | Phases 21-26 | TEST-03 scope is trivially small |
| `test_engine` scope=session, sync SQLite | Unchanged — still sync SQLite with `StaticPool` | Phase 20 | Postgres-compat schema guards exist for alertstype, notifications, sessions, audit_logs |

**Deprecated/outdated:**
- `TODO(async-migration)` annotation: 41 of 42 already removed. 1 remaining in `sync_service.py:102`.
- The MEMORY.md "42+ methods annotated" figure is stale — most annotations were cleared during Phases 21-26 execution.

## Open Questions

1. **auth_session_shared.py db.query in async path**
   - What we know: `auth_session_shared.py:65` calls `db.query(User)` inside a nested async callback
   - What's unclear: Which registered router (if any) calls `get_user_data_from_session` with an AsyncSession `db` argument?
   - Recommendation: Grep for `get_user_data_from_session` callers. If none of the registered routers call it, it is dead utility code and out of scope. If called from registered paths, convert to `await db.execute(select(User).where(...))`.

2. **test_bulk_delete_success root cause confirmation**
   - What we know: STATE.md notes HTTP 400 instead of 200
   - What's unclear: Whether the failure is self-deletion detection or something else entirely
   - Recommendation: Run the test in isolation with `-s` to see the 400 response body, then apply targeted fix.

3. **seed_flow_templates fixture using db.query()**
   - What we know: `tests/api/v2/conftest.py` uses `db_session.query(FlowKind)` in autouse fixture
   - What's unclear: Does this cause any test failure post-migration?
   - Recommendation: Low priority. Since the fixture runs in pytest fixture scope (outside ASGI), `db_session` is the raw sync session and this is correct. Only investigate if tests using seed_flow_templates fail.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis — `tests/conftest.py` full read (lines 1-1298): SyncToAsyncSessionAdapter implementation
- Direct codebase analysis — `tests/api/v2/conftest.py` full read: auth fixtures, seed_flow_templates
- Direct codebase analysis — `tests/api/v2/test_admin.py`: TestBulkDelete and admin fixture patterns
- Direct codebase analysis — `app/api/v2/routers/admin/users.py`: bulk-delete endpoint logic
- Direct codebase analysis — `app/api/v2/routers/admin/dependencies.py`: get_admin_user fallback logic
- Direct codebase analysis — `pyproject.toml`: asyncio_mode="auto", pytest config
- Grep scan: `TODO(async-migration)` across entire app/ — confirmed 1 instance only
- Grep scan: `Depends(get_db)` in `app/api/v2/routers/` — confirmed 0 instances

### Secondary (MEDIUM confidence)
- `.planning/STATE.md` — documents `test_bulk_delete_success` blocker (HTTP 400)
- `.planning/REQUIREMENTS.md` — TEST-01/02/03 requirement definitions
- `.planning/ROADMAP.md` — Phase 27 success criteria

### Tertiary (LOW confidence)
- MEMORY.md statement "42+ methods annotated" — stale; actual count is 1 as of 2026-02-27

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pyproject.toml and conftest.py confirm all infrastructure details
- Architecture: HIGH — full conftest.py read, all fixture patterns verified directly from source
- Pitfalls: HIGH — TestBulkDelete failure is documented in STATE.md and root cause is traceable from code; annotation count confirmed by grep; auth_session_shared issue confirmed by direct read

**Research date:** 2026-02-27
**Valid until:** 2026-03-27 (stable internal codebase, no external dependencies changing)
