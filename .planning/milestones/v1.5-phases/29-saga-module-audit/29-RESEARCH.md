# Phase 29: Saga Module Audit - Research

**Researched:** 2026-02-28
**Domain:** Python static audit — saga orchestration package correctness after v1.3 split
**Confidence:** HIGH

---

## Summary

Phase 29 is a correctness audit, not a feature or refactor. The `app/orchestration/saga_orchestrator/` package was produced by SPLIT-08 and SPLIT-09 during v1.3 (Phase 19). The phase 19 verifier confirmed the structural split was wired correctly (19/19 truths), but did not audit the _behavioral correctness_ of each module post-split — that is this phase's job.

The package contains 10 files (excluding `__pycache__`): `__init__.py`, `orchestrator.py` (482 LOC), `steps.py` (518 LOC), `compensation.py` (239 LOC), `compensation_handlers.py` (344 LOC), `persistence.py` (202 LOC), `metrics.py` (98 LOC), `query_helpers.py` (23 LOC), `types.py` (63 LOC), `exceptions.py` (77 LOC). The `__init__.py` (94 LOC) re-exports from 6 of these sub-modules (orchestrator, steps, compensation, persistence, exceptions, types) — these are the "6 shim re-exports" in AUDIT-02.

Critical correctness finding from pre-reading code: `orchestrator.py` uses **sync** `Session` (`self.db.query()`, `self.db.add()`, `self.db.commit()`, `self.db.flush()`) while `compensation.py`, `steps.py`, and `compensation_handlers.py` all use **async** `AsyncSession` (`await db.execute()`, `await db.delete()`, `await db.flush()`). Both `SagaStepExecutor` and `SagaCompensator` document their `db` parameter as "typed as Any for backward compat with orchestrator". `SagaPersistence` uses sync `Session` explicitly. This dual-session design is intentional (v1.4 decision: API routers use AsyncSession; Celery tasks use sync Session) but must be verified to be correctly wired in all call paths.

**Primary recommendation:** Read each module top-to-bottom, document every issue found (type annotation gaps, session-mode mismatches, missing `__all__` entries, inconsistent behavior), apply fixes, then verify the `__init__.py` `__all__` list against the union of all module public APIs.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AUDIT-01 | All saga orchestrator modules (orchestrator.py, compensation.py, steps.py, persistence.py, compensation_handlers.py) reviewed for correctness after v1.3 split | All 5 files read in full; issues pre-identified below |
| AUDIT-02 | All 6 shim re-exports verified to expose the complete public API matching their canonical packages | `__init__.py` re-exports from 6 sub-modules; `__all__` comparison is mechanical |
| AUDIT-03 | Saga support modules (metrics.py, query_helpers.py, types.py, exceptions.py) verified for correct type definitions and usage | All 4 files read; issues pre-identified below |
| AUDIT-04 | Saga `__init__.py` exports verified against all module public APIs | `__init__.py` `__all__` = 16 symbols; all 6 re-exporting sub-modules need cross-checked |
</phase_requirements>

---

## Standard Stack

### Core

| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| Python | 3.12 | Runtime | Project baseline |
| SQLAlchemy | existing | ORM (sync Session + AsyncSession) | Both used in saga package |
| pytest + pytest-asyncio | 8.3.4 | Test framework | pyproject.toml: `asyncio_mode = "auto"` |
| prometheus_client | existing | Metrics (guarded import) | Already in metrics.py with ImportError fallback |

### Supporting

| Component | Version | Purpose | When to Use |
|-----------|---------|---------|-------------|
| `from __future__ import annotations` | stdlib | Deferred annotation evaluation | Already used in compensation_handlers.py; needed for TYPE_CHECKING patterns |
| `typing.TypedDict` | stdlib | Structured return types | Already used in types.py |
| `asyncio` | stdlib | Async primitives | Already used in compensation.py retry loop |

### No New Dependencies

This is a read-and-fix audit phase. No new packages are needed or should be introduced.

---

## Architecture Patterns

### The Saga Package After v1.3 (Phase 19)

```
app/orchestration/saga_orchestrator/
├── __init__.py              # 94 LOC  — Public API (re-exports from 6 modules)
├── orchestrator.py          # 482 LOC — SagaOrchestrator class; sync Session
├── steps.py                 # 518 LOC — SagaStepExecutor class; AsyncSession
├── compensation.py          # 239 LOC — SagaCompensator class; AsyncSession
├── compensation_handlers.py # 344 LOC — 4 standalone async functions; AsyncSession
├── persistence.py           # 202 LOC — SagaPersistence class; sync Session
├── metrics.py               # 98 LOC  — Prometheus metrics + phone format helper
├── query_helpers.py         # 23 LOC  — metadata_key_equals() helper
├── types.py                 # 63 LOC  — 5 TypedDict classes
└── exceptions.py            # 77 LOC  — 6 exception classes
```

### The 6 Shim Re-Exports (AUDIT-02)

The `__init__.py` re-exports from these 6 sub-modules only:

| Sub-module | Symbols Re-exported |
|------------|---------------------|
| `orchestrator` | `SagaOrchestrator` |
| `steps` | `SagaStepExecutor` |
| `compensation` | `SagaCompensator` |
| `persistence` | `SagaPersistence` |
| `exceptions` | `SagaError`, `SagaCompensationError`, `SagaStepError`, `SagaLockError`, `SagaNotFoundError`, `SagaAlreadyCompletedError` |
| `types` | `SagaLogEntry`, `SagaStatusInfo`, `FailedSagaSummary`, `CompensationResult`, `ResumeResult` |

`metrics`, `query_helpers`, and `compensation_handlers` are **internal sub-modules** — intentionally not re-exported from `__init__.py`.

### Dual-Session Design (v1.4 Decision — Intentional)

| Module | Session Type | Reason |
|--------|-------------|--------|
| `orchestrator.py` | sync `Session` | Called from Celery tasks (saga_retry.py) which use sync session |
| `persistence.py` | sync `Session` | Same Celery task context |
| `steps.py` | `AsyncSession` | Called from async saga execution path |
| `compensation.py` | `AsyncSession` | Async compensation loop |
| `compensation_handlers.py` | `AsyncSession` | Called by SagaCompensator |

The `SagaOrchestrator.__init__` accepts `db: Any` and passes it to both sync sub-components (`SagaPersistence`) and async sub-components (`SagaStepExecutor`, `SagaCompensator`). In the async execution path (`execute_patient_onboarding_saga`), the orchestrator calls `self.db.commit()` and `self.db.rollback()` synchronously but also calls `await self.step_executor.step_*()` which internally calls `await self.db.flush()`. This means the _same `db` object_ is used both synchronously and asynchronously — this is valid ONLY if the `db` passed is an `AsyncSession` that supports sync attribute access for `.add()` and `.flush()`.

### Anti-Patterns to Watch For

- **Missing `__all__` entry**: A public class/function defined in a module but not in `__all__` will not be exported from `__init__.py` even if the module is re-exported there.
- **Deprecated `.dict()` call**: `steps.py:124` calls `patient_data.dict(exclude_unset=True)` — this is Pydantic v1 API; Pydantic v2 uses `.model_dump()`. The orchestrator already uses `.model_dump()` (line 132). This is a correctness issue in steps.py.
- **Sync `self.db.add()` in async steps**: `steps.py:160` has comment `"self.db.add() is NOT a coroutine"` — this is correct for AsyncSession but must be verified per SQLAlchemy 2.x async docs.
- **TypedDict vs dataclass mismatch**: `types.py` uses `TypedDict`; callers that instantiate these types using keyword args (`SagaStatusInfo(id=..., status=...)`) work correctly because TypedDict classes accept kwargs at construction time. No issue found.
- **SagaLogEntry missing `error` key**: `types.py` defines `SagaLogEntry` with `error: Optional[str]` but `PatientOnboardingSaga.add_log_entry()` generates log entries with key `"message"` (not `"error"`). This key mismatch means the TypedDict does not match the actual log entry schema.

---

## Pre-Identified Issues by Module

### orchestrator.py (482 LOC)

| Line | Issue | Severity |
|------|-------|----------|
| 54 | `db: Any` type hint hides session type — no documentation of which session type is expected at runtime | LOW (doc gap) |
| 139 | `self.db.add(saga)` then `self.db.flush()` — sync calls in what may be async context | MEDIUM — needs verification |
| 204 | `self.db.commit()` — sync call in async method | MEDIUM — needs verification |
| 232 | `self.db.rollback()` — sync call in async method | MEDIUM — needs verification |
| 244-252 | Re-creates saga after rollback using `self.db.query(Patient.id)` — sync query in async method | MEDIUM |
| 358-370 | `self.db.query(PatientFlowState)` — sync query inside `_resume_saga_internal` | MEDIUM |
| 401-403 | `saga.status = ...` then `self.db.commit()` sync in async method | MEDIUM |
| 414-415 | `self.db.rollback()` then `self.db.commit()` in async except block | MEDIUM |

**Root cause**: The orchestrator was originally synchronous. The async methods were added when the caller path became async. The sub-components (steps, compensation) were made AsyncSession-native during v1.3. But the orchestrator's direct DB calls were NOT converted.

**Assessment**: If the `db` passed at runtime is an `AsyncSession`, SQLAlchemy 2.x AsyncSession does NOT support `db.query()`, `db.commit()` (sync), or `db.rollback()` (sync) — these must be `await db.commit()`, `await db.rollback()`, `await db.execute(select(...))`. If the orchestrator is always called with a sync `Session` from Celery tasks (saga_retry.py), then these sync calls are correct. But if called from API path (patients/crud.py) which uses AsyncSession, there is a real bug.

**Verification needed**: Check what session type `patients/crud.py` passes when instantiating `SagaOrchestrator`.

### steps.py (518 LOC)

| Line | Issue | Severity |
|------|-------|----------|
| 124 | `patient_data.dict(exclude_unset=True)` — Pydantic v1 `.dict()` is deprecated in v2, `.model_dump()` is correct | MEDIUM (Pydantic v2 compat) |
| 518 | File is 518 LOC — 18 lines over the 500-line project budget | LOW (pre-existing, documented) |

**Assessment**: The `.dict()` call is a correctness issue. Pydantic v2 still supports `.dict()` as deprecated alias, so it works but generates deprecation warnings. Should be changed to `.model_dump()`.

### compensation.py (239 LOC)

| Issue | Severity |
|-------|----------|
| `SagaCompensator.__init__` accepts `patient_repo` but never uses it (marked "Kept for backward compat") | LOW — dead parameter |
| `_compensate_saga_internal` checks `saga.current_step >= 4` for message compensation but step 4 is `STEP_4_MESSAGE_SENT`; compensation order is 4→3→1 (skipping step 2) — step 2 was Firebase user creation, now deprecated | MEDIUM — needs explicit doc comment |
| `await self.db.commit()` in compensation — consistent with AsyncSession expectation | OK |

### compensation_handlers.py (344 LOC)

| Issue | Severity |
|-------|----------|
| `from __future__ import annotations` is present — good for TYPE_CHECKING forward refs | OK |
| Uses `db: AsyncSession` parameter correctly — explicit type, not Any | OK |
| `redis.setex()` is a sync call — correct since redis client from `get_sync_redis_client` is sync | OK |
| No issues with `__all__` — all 4 public functions are listed | OK |

### persistence.py (202 LOC)

| Issue | Severity |
|-------|----------|
| Uses sync `Session` consistently — `self.db.query(...)` everywhere | OK (correct for Celery context) |
| `get_saga_statistics()` loads all sagas into memory with `query.all()` — no pagination | LOW (performance concern for large deployments) |
| `list_pending_sagas` checks `STEP_4_MESSAGE_SENT` but does NOT include it in the status filter | VERIFY — `STEP_4_MESSAGE_SENT` is not in the filter for pending sagas, but a saga could legitimately be in that status if it got stuck |

### metrics.py (98 LOC)

| Issue | Severity |
|-------|----------|
| `_detect_phone_format` private name (underscore prefix) is exported in `__all__` and used by orchestrator.py | LOW — inconsistency between private name and explicit export |
| All metric objects exposed in `__all__` | OK |
| `METRICS_AVAILABLE` flag used consistently in orchestrator | OK |

### query_helpers.py (23 LOC)

| Issue | Severity |
|-------|----------|
| No `__all__` defined | LOW — minor; only one exported function |
| Uses `cast(metadata_column, String)` — dialect-agnostic; tested for SQLite/PostgreSQL | OK |

### types.py (63 LOC)

| Issue | Severity |
|-------|----------|
| `SagaLogEntry` has field `error: Optional[str]` but `add_log_entry()` in the model uses key `"message"` | MEDIUM — TypedDict does not match runtime schema |
| `FailedSagaSummary` includes `retry_count: int` — matches `SagaPersistence.list_failed_sagas` which accesses `s.retry_count` | OK |
| `CompensationResult` TypedDict is defined but NEVER imported or used anywhere in the codebase | LOW — dead type |

### exceptions.py (77 LOC)

| Issue | Severity |
|-------|----------|
| All 6 exceptions are in `__init__.py` `__all__` | OK |
| `SagaStepError` adds `step_number` and `step_name` attributes — these are useful for debugging but never surfaced in `execute_patient_onboarding_saga` error handling | LOW |
| `SagaLockError` and `SagaNotFoundError` and `SagaAlreadyCompletedError` are defined but never raised in the codebase | LOW — dead exceptions |

### __init__.py (94 LOC)

| Issue | Severity |
|-------|----------|
| `__all__` has 16 symbols; does not include `CompensationHandlers` functions (correct — internal) | OK |
| `__all__` does not include `SagaCompensationHandlers` sub-module functions | OK (intentional) |
| `query_helpers` is not in `__all__` — correct (internal utility) | OK |
| `metrics` is not in `__all__` — correct (internal) | OK |
| `__version__ = "2.0.0"` defined at bottom | OK |

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Finding all public names in a module | Custom AST parser | Python `dir()` or inspect the `__all__` list directly | Already established pattern in contract tests |
| Verifying export identity | Custom comparison script | `assert ModuleA.X is ModuleB.X` as used in existing contract tests | Already the project standard |
| Pydantic v2 migration | Large-scale replacement | Single `.dict()` → `.model_dump()` call change | One-line fix |

---

## Common Pitfalls

### Pitfall 1: AsyncSession vs sync Session in SagaOrchestrator

**What goes wrong:** `execute_patient_onboarding_saga` is `async def` and calls `await self.step_executor.step_create_patient()` which internally calls `await self.db.flush()`. But `orchestrator.py` also calls `self.db.commit()`, `self.db.rollback()`, `self.db.query()` synchronously. If `db` is an AsyncSession, sync calls will raise `InvalidRequestError` or `AttributeError`.

**Why it happens:** The orchestrator predates the AsyncSession migration. Sub-components were made async but the orchestrator's direct DB calls were not.

**How to avoid:** Verify the concrete session type passed by each caller. If `patients/crud.py` passes AsyncSession, the sync direct calls in the orchestrator must be awaited.

**Warning signs:** Runtime `AttributeError: 'AsyncSession' object has no attribute 'query'` or `asyncpg.exceptions.InterfaceError: cannot perform operation: another operation is in progress`.

### Pitfall 2: SagaLogEntry TypedDict field name mismatch

**What goes wrong:** `types.py:SagaLogEntry` declares `error: Optional[str]` but `PatientOnboardingSaga.add_log_entry()` generates entries with key `"message"`. Code that reads `entry["error"]` expecting a TypedDict will get a KeyError.

**Why it happens:** TypedDict in Python is purely a type hint — it does not enforce the schema at runtime. The mismatch only surfaces when code tries to read from a log entry as if it were a `SagaLogEntry`.

**How to avoid:** The fix is to rename the TypedDict field from `error` to `message` OR rename the `add_log_entry` parameter from `message` to `error`. Check all callers before deciding direction.

**Warning signs:** `KeyError: 'error'` when accessing `SagaLogEntry`-typed entries from `execution_log`.

### Pitfall 3: __all__ Drift After Audit Fixes

**What goes wrong:** Adding or renaming a public symbol during the audit (e.g., renaming `_detect_phone_format` to `detect_phone_format`) breaks callers that import the old name.

**Why it happens:** `orchestrator.py` imports `_detect_phone_format` from `metrics.py` — changing the name in `metrics.py` without updating the import in `orchestrator.py` and the contract test breaks both the module and the test.

**How to avoid:** For any rename, use search-and-replace across the full codebase before committing.

**Warning signs:** `ImportError: cannot import name '_detect_phone_format' from 'app.orchestration.saga_orchestrator.metrics'`.

### Pitfall 4: CompensationResult TypedDict is Dead Code

**What goes wrong:** `CompensationResult` is defined in `types.py` and re-exported from `__init__.py` (it IS in `__all__`) but no production code instantiates or uses it.

**Why it happens:** It was defined prophylactically during the split but no module uses it as a return type.

**How to avoid:** Do not remove it during this phase (AUDIT-01 through AUDIT-04 scope is correctness, not dead code removal — that belongs in a separate cleanup). Document it as unused in the SUMMARY.

---

## Code Examples

### Verifying Export Identity (AUDIT-02 pattern)

```python
# Pattern already used in contract tests
from app.orchestration.saga_orchestrator import SagaOrchestrator
from app.orchestration.saga_orchestrator.orchestrator import SagaOrchestrator as _Direct

assert SagaOrchestrator is _Direct  # identity check — same object, not just same name
```

### Verifying __all__ Completeness (AUDIT-04 pattern)

```python
import app.orchestration.saga_orchestrator as pkg

# Every symbol in __all__ must be importable
for name in pkg.__all__:
    assert hasattr(pkg, name), f"Missing: {name}"

# Every symbol exported via __all__ must resolve to the same object as direct sub-module import
from app.orchestration.saga_orchestrator.exceptions import SagaError
assert pkg.SagaError is SagaError
```

### Checking for Pydantic v2 .dict() calls

```bash
grep -rn "\.dict(" backend-hormonia/app/orchestration/saga_orchestrator/
# Expected: steps.py:124 — should be .model_dump()
```

### AsyncSession call audit pattern

```python
# In orchestrator.py async methods, any of these patterns is WRONG if db is AsyncSession:
self.db.commit()        # must be: await self.db.commit()
self.db.rollback()      # must be: await self.db.rollback()
self.db.flush()         # must be: await self.db.flush()
self.db.query(Model)    # must be: await self.db.execute(select(Model))
```

---

## Validation Architecture

> `workflow.nyquist_validation` is not present in `.planning/config.json` — validation section included because existing test infrastructure covers this phase.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 + pytest-asyncio |
| Config file | `backend-hormonia/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `cd backend-hormonia && python -m pytest tests/unit/orchestration/ tests/orchestration/test_saga_orchestrator.py tests/services/test_saga_compensation.py -x -q` |
| Full suite command | `cd backend-hormonia && python -m pytest -x --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUDIT-01 | Core modules read; correctness issues documented and fixed | read + fix | `cd backend-hormonia && python -m pytest tests/orchestration/test_saga_orchestrator.py tests/services/test_saga_compensation.py -x -q` | ✅ |
| AUDIT-02 | All 6 shim re-exports match canonical package symbols | unit (identity) | `cd backend-hormonia && python -m pytest tests/unit/orchestration/ -x -q` | ✅ (contract tests exist) |
| AUDIT-03 | Support module types verified against callers | read + verify | `cd backend-hormonia && python -m pytest tests/unit/orchestration/ -x -q` | ✅ |
| AUDIT-04 | `__init__.py` `__all__` verified against all module public APIs | unit | `cd backend-hormonia && python -c "import app.orchestration.saga_orchestrator as p; [getattr(p,n) for n in p.__all__]; print('All __all__ symbols resolve OK')"` | needs smoke test |

### Sampling Rate

- **Per task commit:** `cd backend-hormonia && python -m pytest tests/unit/orchestration/ -x -q`
- **Per plan merge:** `cd backend-hormonia && python -m pytest tests/orchestration/ tests/services/test_saga_compensation.py tests/unit/orchestration/ -x -q`
- **Phase gate:** Full suite green before verify-work

### Wave 0 Gaps

- [ ] `tests/unit/orchestration/test_saga_module_audit.py` — new test file to cover AUDIT-03/04: verifies `types.py` field names match `add_log_entry()` output schema, verifies `CompensationResult` is importable, verifies all `__all__` symbols resolve
- [ ] Smoke test for `__init__.py` completeness: `python -c "import app.orchestration.saga_orchestrator as p; [getattr(p,n) for n in p.__all__]"`

---

## Key Facts for Planning

### File Inventory with Line Counts

| File | LOC | Session Type | Status |
|------|-----|-------------|--------|
| `orchestrator.py` | 482 | sync Session (direct calls) + delegates to async components | AUDIT-01 target |
| `compensation.py` | 239 | AsyncSession | AUDIT-01 target |
| `steps.py` | 518 | AsyncSession | AUDIT-01 target; pre-existing 18 LOC over budget |
| `persistence.py` | 202 | sync Session | AUDIT-01 target |
| `compensation_handlers.py` | 344 | AsyncSession | AUDIT-01 target |
| `metrics.py` | 98 | N/A | AUDIT-03 target |
| `query_helpers.py` | 23 | N/A | AUDIT-03 target |
| `types.py` | 63 | N/A | AUDIT-03 target; field name mismatch found |
| `exceptions.py` | 77 | N/A | AUDIT-03 target |
| `__init__.py` | 94 | N/A | AUDIT-04 target |

### Confirmed Issues to Fix

| Issue | File | Severity | Fix |
|-------|------|----------|-----|
| `.dict(exclude_unset=True)` — Pydantic v1 API | steps.py:124 | MEDIUM | Change to `.model_dump(exclude_unset=True)` |
| `SagaLogEntry.error` field name vs `add_log_entry` `"message"` key | types.py | MEDIUM | Rename field to `message: Optional[str]` in TypedDict |
| Sync `self.db.query()` / `self.db.commit()` in async orchestrator methods | orchestrator.py | MEDIUM | Verify caller session type; fix if AsyncSession is passed |
| `_detect_phone_format` private name but exported | metrics.py | LOW | Document as intentional or rename without underscore |
| `query_helpers.py` missing `__all__` | query_helpers.py | LOW | Add `__all__ = ["metadata_key_equals"]` |
| `SagaLockError`, `SagaNotFoundError`, `SagaAlreadyCompletedError` never raised | exceptions.py | LOW | Document as reserved; do not remove from `__all__` |
| `CompensationResult` TypedDict never used | types.py | LOW | Document as unused; do not remove from `__all__` |
| `SagaCompensator.patient_repo` never used | compensation.py | LOW | Add `# noqa` or remove parameter with backward-compat default |

### Plan Split Recommendation

**Plan 29-01: Audit core saga modules** (AUDIT-01)
- Read and verify orchestrator.py, compensation.py, steps.py, persistence.py, compensation_handlers.py
- Fix confirmed issues: `.dict()` → `.model_dump()` in steps.py, sync/async session mismatch in orchestrator.py (verify and fix), document deprecated step 2 in compensation.py

**Plan 29-02: Audit shim exports and support modules** (AUDIT-02, AUDIT-03, AUDIT-04)
- Verify all 6 shim re-exports from `__init__.py` match canonical sub-module symbols (identity checks)
- Audit metrics.py, query_helpers.py, types.py, exceptions.py
- Fix `SagaLogEntry.error` → `SagaLogEntry.message` TypedDict field name
- Add `__all__` to query_helpers.py
- Verify `__init__.py` `__all__` is complete and correct

---

## Open Questions

1. **Does orchestrator.py receive an AsyncSession or sync Session from the API path?**
   - What we know: `patients/crud.py` uses `get_async_db` dependency. The saga orchestrator is instantiated somewhere in that path.
   - What's unclear: Whether the `SagaOrchestrator` instance in `patients/crud.py` receives an AsyncSession or sync Session.
   - Recommendation: Read `patients/crud.py` lines 80+ at plan time to find the instantiation. This determines whether the sync DB calls in orchestrator.py are bugs or correct.

2. **Is `steps.py` at 518 LOC a scope item for this phase?**
   - What we know: It was documented as "pre-existing out-of-budget, not in SPLIT-08 scope" in phase 19. AUDIT-01 says modules must be "reviewed for correctness" — not that LOC must be brought under 500.
   - Recommendation: Phase 29 is an audit, not a split. Do not split steps.py during this phase. Flag it as known technical debt in the SUMMARY.

3. **Should `CompensationResult` be used anywhere or removed?**
   - What we know: It is defined, exported, and unused.
   - Recommendation: Keep it (removal is out of scope for a correctness audit). Document in 29-02 SUMMARY as unused.

---

## Sources

### Primary (HIGH confidence)

- Direct file inspection — all 10 modules in `app/orchestration/saga_orchestrator/` read in full during research
- `.planning/phases/19-saga-integrity-splits/19-VERIFICATION.md` — Phase 19 verification confirming split structural correctness (19/19 truths)
- `.planning/phases/19-saga-integrity-splits/19-RESEARCH.md` — Phase 19 research documenting original split rationale and pitfalls
- `.planning/REQUIREMENTS.md` — AUDIT-01 through AUDIT-04 requirement definitions
- `backend-hormonia/app/models/patient_onboarding_saga.py` — `add_log_entry()` method showing actual log entry schema
- Existing contract tests: `tests/unit/orchestration/test_saga_orchestrator_split_contract.py`, `tests/unit/orchestration/test_saga_compensation_split_contract.py`

### Secondary (MEDIUM confidence)

- `.planning/STATE.md` — Current position and v1.3 decision: "Saga orchestrator and compensation split into focused modules with compatibility shims"

### Tertiary (LOW confidence)

- None — all findings are from direct codebase inspection.

---

## Metadata

**Confidence breakdown:**
- Module inventory and LOC: HIGH — direct file inspection
- Issue identification: HIGH — code read line-by-line
- Session type analysis: MEDIUM — async/sync usage patterns visible but runtime caller session type for orchestrator needs verification at plan time
- Fix feasibility: HIGH — all fixes are mechanical, no new dependencies

**Research date:** 2026-02-28
**Valid until:** 2026-03-28 (stable codebase, no external dependencies to track)
