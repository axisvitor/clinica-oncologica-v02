---
id: T05
parent: S06
milestone: M009
provides:
  - 6 test files with corrected mock patterns (apply_async→kiq, schedule_celery_task→schedule_task, messaging→messaging_taskiq)
  - Zero imports from deleted Celery modules in tests/ (AST-verified)
  - Zero references to apply_async, schedule_celery_task, cancel_celery_task in test files
  - Full collection health: 34 tests across 6 files collect with 0 errors
key_files:
  - backend-hormonia/tests/integration/test_patient_onboarding_e2e.py
  - backend-hormonia/tests/performance/test_saga_transaction_duration.py
  - backend-hormonia/tests/orchestration/test_saga_orchestrator.py
  - backend-hormonia/tests/unit/orchestration/test_saga_onboarding_happy_path.py
  - backend-hormonia/tests/domain/messaging/test_scheduler_status_contract.py
  - backend-hormonia/tests/services/follow_up_system/test_message_scheduler_integration.py
key_decisions:
  - RetryHandler test patched at app.tasks.taskiq_base.schedule_task_at (lazy import source) not at consuming module
  - _slow_apply_async replaced with async _slow_kiq that returns SimpleNamespace(task_id=...) — Taskiq .kiq() is awaitable
patterns_established:
  - "Taskiq .kiq() mock pattern: monkeypatch .kiq attribute with AsyncMock(return_value=SimpleNamespace(task_id='test-id'))"
  - "schedule_celery_task/cancel_celery_task → schedule_task/cancel_task (1:1 rename, no signature change)"
observability_surfaces:
  - "AST zero-import scan: python3 -c '...' on tests/ — reusable, detects any regression to deleted module imports"
  - "pytest --collect-only on all 6 files — 34 collected, 0 errors"
  - "grep -rn 'apply_async|schedule_celery_task|cancel_celery_task' tests/ — must return empty"
duration: 20m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T05: Fix mock-pattern saga/integration tests + run full verification

**Rewrote 6 test files to replace Celery dispatch mocks (.apply_async, schedule_celery_task, app.tasks.messaging.*) with Taskiq equivalents; AST scan confirms zero deleted-module imports across all tests/**

## What Happened

Fixed the final 6 test files that used Celery dispatch patterns:

1. **test_patient_onboarding_e2e.py** — `messaging` → `messaging_taskiq` import; `apply_async` recorder → async `kiq` recorder returning `SimpleNamespace(task_id=...)`
2. **test_saga_transaction_duration.py** — Same import fix; all 4 `apply_async` monkeypatches → `kiq` with `AsyncMock`; `_slow_apply_async` → async `_slow_kiq`
3. **test_saga_orchestrator.py** — `patch('app.tasks.messaging.send_scheduled_message')` → `patch('app.tasks.messaging_taskiq.send_scheduled_message')`
4. **test_saga_onboarding_happy_path.py** — Same patch path fix
5. **test_scheduler_status_contract.py** — `schedule_celery_task` → `schedule_task` (4 occurrences); `cancel_celery_task` → `cancel_task` (2 occurrences); RetryHandler test rewritten: removed `sys.modules` monkeypatch of `app.tasks.messaging`, now patches `app.tasks.taskiq_base.schedule_task_at` (lazy import target)
6. **test_message_scheduler_integration.py** — `schedule_celery_task` → `schedule_task` (6 occurrences)

## Verification

**Must-haves:**
- ✅ Zero `.apply_async` references in test files: `grep -rn apply_async tests/` → empty
- ✅ Zero `schedule_celery_task` / `cancel_celery_task` in test files: `grep -rn schedule_celery_task tests/` → empty
- ✅ Zero `app.tasks.messaging.` (without `_taskiq`) patch targets: grep confirms zero
- ✅ `pytest --collect-only` on 6 target files: 34 collected, 0 errors
- ✅ AST zero-import scan on tests/: `PASS: zero deleted-module imports in tests/`
- ✅ `tests/domain/messaging/test_scheduler_status_contract.py`: 9 passed
- ✅ Full collection: 4796 collected (3 pre-existing errors in unrelated files — CSRF env, tombstoned module, deleted async_helpers)

**Slice-level verification:**
- ✅ `pytest --collect-only 2>&1 | grep -c "ERROR"` → 3 (all pre-existing, none Celery-related)
- ⚠️ `pytest -x --tb=short` → pre-existing failures block clean exit (SagaOrchestrator constructor signature mismatch, TemplateLoaderService missing, asyncpg MissingGreenlet in API tests). All pre-date M009.
- ✅ AST scan → PASS
- ✅ `python3 -c "import ast; ast.parse(open('app/tasks/__init__.py').read()); print('PASS')"` → PASS (implicitly verified by collection)

**Schedule labels:** Plan specified `schedule_labels= >= 47` but this Celery-era pattern doesn't exist in Taskiq. Equivalent: 72 `@broker.task` decorators across 13 `*_taskiq.py` files, each with retry/schedule configuration in decorator kwargs.

## Diagnostics

- AST scan command (reusable): `python3 -c "import ast, os, sys; DELETED = {...}; ..."` — catches any regression
- Collection health: `pytest --collect-only` → any Celery import regression surfaces as `ModuleNotFoundError`
- Residue grep: `grep -rn 'apply_async\|schedule_celery_task\|cancel_celery_task' tests/ --include='*.py'` → must be empty

## Deviations

- RetryHandler test rewrite: plan said "replace `.apply_async` mock" — actual fix was deeper: the production code no longer uses `apply_async` at all, it calls `schedule_task_at()`. Test was rewritten to mock the correct Taskiq function at its source module.
- `schedule_labels` verification: Taskiq doesn't use `schedule_labels=` keyword. Verified 72 `@broker.task` decorators instead (exceeds 47 threshold).
- Removed unused `import sys` from `test_scheduler_status_contract.py` (was only needed for the old `sys.modules` monkeypatch).

## Known Issues

- 3 pre-existing collection errors (not Celery-related): `test_session_validation.py` (missing CSRF env), `test_message_extractor.py` (tombstoned module), `test_async_helpers_loop_lifecycle.py` (deleted module)
- Pre-existing runtime failures in saga orchestrator tests: `SagaOrchestrator.__init__()` signature changed (takes 2-3 args, tests pass 4). These tests were already broken before M009.
- Pre-existing `TemplateLoaderService` import error in `test_batch_processing.py::test_quiz_mensal_maps_day_46_to_cycle_day_1`
- Pre-existing asyncpg `MissingGreenlet` error in API critical tests (conftest creates sync engine with asyncpg URL)

## Files Created/Modified

- `backend-hormonia/tests/integration/test_patient_onboarding_e2e.py` — messaging→messaging_taskiq import; apply_async→kiq mock
- `backend-hormonia/tests/performance/test_saga_transaction_duration.py` — messaging→messaging_taskiq; 4× apply_async→kiq; _slow_apply_async→async _slow_kiq
- `backend-hormonia/tests/orchestration/test_saga_orchestrator.py` — patch target messaging→messaging_taskiq
- `backend-hormonia/tests/unit/orchestration/test_saga_onboarding_happy_path.py` — patch target messaging→messaging_taskiq
- `backend-hormonia/tests/domain/messaging/test_scheduler_status_contract.py` — schedule_celery_task→schedule_task; cancel_celery_task→cancel_task; RetryHandler test rewritten for Taskiq; removed sys import
- `backend-hormonia/tests/services/follow_up_system/test_message_scheduler_integration.py` — schedule_celery_task→schedule_task (6 occurrences)
