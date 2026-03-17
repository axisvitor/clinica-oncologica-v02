---
id: T03
parent: S06
milestone: M009
provides:
  - 8 test files with corrected imports (flow, batch, monitoring, monthly, auto-resume, messaging)
  - Zero imports from `app.tasks.flows.*`, `app.tasks.flow_automation`, `app.tasks.messaging` in these files
  - Zero references to `process_daily_flows_async` in test tree
  - QueuePool/async engine compatibility fix in database_optimization.py
key_files:
  - backend-hormonia/tests/tasks/flows/test_batch_processing.py (sed — flows.batch_tasks → helpers.flow_helpers)
  - backend-hormonia/tests/tasks/flows/test_flow_tasks_hardening.py (sed + manual — flows.flow_tasks → flows_taskiq, .fn() call)
  - backend-hormonia/tests/tasks/flows/test_monitoring_health_task.py (rewritten — async, flows_taskiq)
  - backend-hormonia/tests/tasks/flows/test_monthly_tasks_async_bridge.py (rewritten — async, flows_taskiq)
  - backend-hormonia/tests/unit/tasks/test_auto_resume_flows.py (rewritten — async, flows_taskiq)
  - backend-hormonia/tests/unit/services/test_flow_pause_detection.py (sed + manual — flows_taskiq, .fn() call)
  - backend-hormonia/tests/services/test_sanity_with_import.py (sed — messaging → messaging_taskiq)
  - backend-hormonia/tests/services/test_patient_deletion.py (sed — messaging → messaging_taskiq)
key_decisions:
  - Taskiq task tests call `.fn()` instead of direct `await task(...)` to bypass TaskiqDepends injection
  - Patch targets for lazy imports inside task body use the defining module (e.g. `app.database.get_scoped_session`) not the consuming module
  - monitor_flow_task_health test rewritten fully (old sync db.query() API incompatible with new async select() API)
  - monthly_tasks and auto_resume tests rewritten (old .run() sync API replaced by async .fn() with mock AsyncSession)
patterns_established:
  - "Taskiq task test pattern: use `await task.fn(db=mock_async_db, ...)` with AsyncMock db session for tasks that accept `db: AsyncSession = DbSession`"
  - "Patch lazy imports at their source module, not at the consuming module's namespace (lazy `from X import Y` inside function body)"
  - "Flow state SimpleNamespace mocks need both `step_data` and `state_data` for Taskiq version (paused filtering reads state_data)"
observability_surfaces:
  - "`pytest --collect-only` on these 8 files → 32 collected, 0 errors"
  - "AST zero-import scan on these 8 files → zero deleted-module imports"
duration: 30m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T03: Fix flow, batch, and simple service test files

**Fixed 8 test files importing from deleted flow/messaging modules; rewrote 3 deeply-changed tests (monitoring, monthly, auto-resume) for async Taskiq API; fixed QueuePool/async engine incompatibility that blocked all test collection.**

## What Happened

Converted 8 test files from Celery module imports to Taskiq equivalents:

1. **test_batch_processing.py** — sed replacement: `app.tasks.flows.batch_tasks` → `app.tasks.helpers.flow_helpers` (12 imports + 4 patch targets)
2. **test_flow_tasks_hardening.py** — sed + manual: `process_daily_flows_async` → `process_daily_flows` from `flows_taskiq`; added `.fn()` calls; fixed patch targets for lazy imports; added `state_data` to mock SimpleNamespace
3. **test_monitoring_health_task.py** — full rewrite: old sync `db.query()` + `.run()` → async `monitor_flow_task_health.fn(db=AsyncMock())` with async mock db
4. **test_monthly_tasks_async_bridge.py** — full rewrite: old `.run()` + `run_async` bridge → async `.fn()` with patched lazy imports
5. **test_auto_resume_flows.py** — full rewrite: old sync fixture with `.run()` → async fixture with `resume_paused_flows.fn(db=AsyncMock())`
6. **test_flow_pause_detection.py** — sed + manual: `process_daily_flows_async` → `process_daily_flows`; `.fn()` call; fixed patch targets
7. **test_sanity_with_import.py** — sed: `app.tasks.messaging` → `app.tasks.messaging_taskiq`
8. **test_patient_deletion.py** — sed: `app.tasks.messaging` → `app.tasks.messaging_taskiq`

**Infrastructure fix:** `app/utils/database_optimization.py` — `create_optimized_engine` was passing sync `QueuePool` to `create_async_engine`, causing `ArgumentError: Pool class QueuePool cannot be used with asyncio engine`. Fixed by auto-swapping to `AsyncAdaptedQueuePool` for asyncpg URLs. Also fixed event listener registration on `engine.sync_engine` for async engines to avoid `NotImplementedError: asynchronous events are not implemented`.

## Verification

### Task-level must-haves:
- **Zero old imports**: `grep -rn` for `app.tasks.flows.*`, `app.tasks.flow_automation`, `app.tasks.messaging[^_]` → empty — PASS
- **All 8 files collect**: `pytest --collect-only` → 32 tests collected, 0 errors — PASS
- **No `process_daily_flows_async`**: `grep -rn process_daily_flows_async` → empty — PASS

### Task-level verification:
- `cd backend-hormonia && pytest tests/tasks/flows/ tests/unit/tasks/test_auto_resume_flows.py tests/unit/services/test_flow_pause_detection.py tests/services/test_sanity_with_import.py tests/services/test_patient_deletion.py --collect-only 2>&1 | grep ERROR` → empty — PASS

### AST scan on T03 files:
- Zero deleted-module imports — PASS

### Slice-level checks (partial — T03 is task 3 of 5):
- Collection of T03's 8 files: PASS (32 collected, 0 errors)
- AST scan on T03's 8 files: PASS
- Full workspace AST scan: 14 remaining violations (all in T04/T05 files)
- Full workspace collection errors: 23 remaining (T04/T05 files)
- `app/tasks/__init__.py` parses: PASS
- Full pytest run: NOT YET

## Diagnostics

- `DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test_db" QUIZ_TOKEN_SECRET="test-secret" pytest tests/tasks/flows/ tests/unit/tasks/test_auto_resume_flows.py tests/unit/services/test_flow_pause_detection.py tests/services/test_sanity_with_import.py tests/services/test_patient_deletion.py --collect-only` → 32 collected, 0 errors
- `QUIZ_TOKEN_SECRET` env var required for quiz import chain
- QueuePool fix allows `conftest.py` to import `app.database.Base` without crashing

## Deviations

- **Fixed QueuePool/async engine bug in `database_optimization.py`** — Not in plan, but without this fix no tests could collect at all. The root `conftest.py` imports `app.database.Base` which triggers engine creation. The bug (`QueuePool` passed to `create_async_engine`) was pre-existing.
- **Rewrote 3 tests instead of simple import swap** — `test_monitoring_health_task.py`, `test_monthly_tasks_async_bridge.py`, and `test_auto_resume_flows.py` had deep Celery sync patterns (`.run()`, `run_async` bridge, sync db.query) incompatible with the fully async Taskiq API. Simple sed replacement was insufficient.
- **Fixed patch targets for lazy imports** — `test_flow_tasks_hardening.py` and `test_flow_pause_detection.py` patched module-level names that don't exist in `flows_taskiq` (lazy imports inside function body). Fixed to patch the source modules.

## Known Issues

- 14 deleted-module import violations remain in T04/T05 scope
- 23 collection errors remain workspace-wide (T04/T05 files)

## Files Created/Modified

- `backend-hormonia/tests/tasks/flows/test_batch_processing.py` — sed: 12 imports + patch targets from flows.batch_tasks → helpers.flow_helpers
- `backend-hormonia/tests/tasks/flows/test_flow_tasks_hardening.py` — sed + manual: process_daily_flows_async → process_daily_flows, .fn() calls, state_data mock
- `backend-hormonia/tests/tasks/flows/test_monitoring_health_task.py` — full rewrite: async + flows_taskiq
- `backend-hormonia/tests/tasks/flows/test_monthly_tasks_async_bridge.py` — full rewrite: async + flows_taskiq
- `backend-hormonia/tests/unit/tasks/test_auto_resume_flows.py` — full rewrite: async + flows_taskiq
- `backend-hormonia/tests/unit/services/test_flow_pause_detection.py` — sed + manual: flows_taskiq, .fn(), patch targets
- `backend-hormonia/tests/services/test_sanity_with_import.py` — sed: messaging → messaging_taskiq
- `backend-hormonia/tests/services/test_patient_deletion.py` — sed: messaging → messaging_taskiq
- `backend-hormonia/app/utils/database_optimization.py` — QueuePool→AsyncAdaptedQueuePool for asyncpg; event listeners on sync_engine
- `.gsd/milestones/M009/slices/S06/tasks/T03-PLAN.md` — added Observability Impact section
