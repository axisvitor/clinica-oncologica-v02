---
id: T04
parent: S06
milestone: M009
provides:
  - 7 test files with zero Celery/deleted-module imports, all collecting cleanly (36 tests)
  - 1 dead test deleted (test_register_task_persists_metadata_to_store — depended on deleted celery_integration)
key_files:
  - backend-hormonia/tests/unit/tasks/test_followup_retry_task.py
  - backend-hormonia/tests/unit/tasks/test_send_retry_task.py
  - backend-hormonia/tests/unit/tasks/test_stuck_detection.py
  - backend-hormonia/tests/integration/test_flow_recovery_retry_e2e.py
  - backend-hormonia/tests/unit/tasks/test_messaging_dlq_wiring.py
  - backend-hormonia/tests/unit/services/test_flow_cancel.py
  - backend-hormonia/tests/unit/api/v2/test_task_registry_dragonfly_fallback.py
key_decisions:
  - Taskiq retry tests verify exception propagation (transient → raises, exhausted → returns permanently_failed) instead of mocking .retry()/.apply_async — SmartRetryMiddleware handles scheduling
  - test_flow_cancel.py verifies cancel_patient_flow's logged no-op for celery_task_id messages (D013) instead of mocking celery.result.AsyncResult.revoke
  - Deleted test_register_task_persists_metadata_to_store — celery_integration module removed by S05, function no longer exists
  - test_messaging_dlq_wiring.py rewritten for async send_scheduled_message from messaging_taskiq — old messaging.py module deleted
patterns_established:
  - "Taskiq retry task test pattern: pass _fake_context(retries=N) via context kwarg to task.fn(); retries < max → pytest.raises(Exception); retries >= max → result['status'] == 'permanently_failed'"
  - "Patch targets for flows_taskiq lazy imports: use 'app.tasks.flows_taskiq.get_scoped_session' and 'app.tasks.flows_taskiq.UnifiedWhatsAppService' (lazy imports inside task body resolve against defining module)"
observability_surfaces:
  - "pytest --collect-only on 7 test files → 36 collected, 0 errors"
  - "AST zero-import scan on tests/ → PASS (zero deleted-module imports)"
duration: ~25min
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T04: Fix retry, exception, and Celery-deep test files

**Rewrote 7 test files with deep Celery dependencies (MaxRetriesExceededError, celery_app, .run(), AsyncResult, celery_integration) to use Taskiq async patterns; 36 tests collect with 0 errors.**

## What Happened

Fixed 7 test files that had the deepest Celery coupling in the test suite:

1. **test_followup_retry_task.py** (190→142 lines): Removed `celery.exceptions.MaxRetriesExceededError` import, `app.tasks.flows.followup_retry` imports, `.run()` calls, `.apply_async` mock, and `.retry()` mock. Rewritten as async tests calling `retry_failed_followup_send.fn()` with `_fake_context(retries=N)`. Tests verify: action_not_found, successful rescheduling, transient failure raises, exhaustion returns permanently_failed.

2. **test_send_retry_task.py** (299→212 lines): Same pattern — removed `celery.exceptions.MaxRetriesExceededError`, `app.tasks.flows.send_retry` imports, `.run()` calls, and all Celery-specific `.retry()` mocks. Rewritten as async tests. Tests verify: message_not_found, already_finalized, successful resend, transient raises, false result raises, exhaustion permanently_failed, flow_context preservation (explicit and metadata fallback).

3. **test_stuck_detection.py** (147→145 lines): Removed `from app.celery_app import celery_app` and beat_schedule assertion test. Converted 4 sync `.run()` tests to async `await detect_stuck_flows.fn()`. Patch targets updated from `app.tasks.flows.stuck_detection.*` to `app.tasks.flows_taskiq.*`. `attempt_recovery` patched with `new_callable=AsyncMock`.

4. **test_flow_recovery_retry_e2e.py** (641→487 lines): The largest file. Removed `celery.exceptions.MaxRetriesExceededError` import, 3 `app.tasks.flows.*` module imports, and all `.run()` calls on tasks. Defined local stub `MaxRetriesExceededError`. All task calls converted to async `.fn()` with `_fake_context()`. Monkeypatch targets updated to `app.tasks.flows_taskiq.*`. Kept recovery_service sync tests unchanged (they test the service, not the task).

5. **test_messaging_dlq_wiring.py** (175→105 lines): Completely rewritten. Old tests mocked `app.tasks.messaging` (deleted module) with sync `.run()` calls, `run_async`, and `get_db_session`. New tests use async `send_scheduled_message.fn()` from `messaging_taskiq` with `AsyncMock` db and `_fake_context()`. Tests verify DLQ routing on non-retriable failure, transient retry raises, and FlowMessageRetryConfig values.

6. **test_flow_cancel.py** (138→134 lines): Removed `celery.result.AsyncResult` mock in `test_cancel_revokes_celery_tasks`. Replaced with `test_cancel_logs_noop_for_celery_task_ids` that verifies messages are cancelled without needing Celery revoke (per D013). Updated patch targets from `app.services.flow_management.*` to `app.services.flow.management.pause_resume.*` (actual source module).

7. **test_task_registry_dragonfly_fallback.py** (67→44 lines): Deleted `test_register_task_persists_metadata_to_store` that imported `celery_integration` (deleted by S05). Kept 2 `tasks_dependencies` tests unchanged.

## Verification

- `pytest --collect-only` on all 7 files → **36 tests collected, 0 errors** ✅
- AST zero-import scan on all 7 files → **PASS: zero banned imports** ✅
- No `.run()` calls on Taskiq tasks → **PASS** ✅
- Full `pytest --collect-only` across entire test suite → **4791 tests collected, 5 pre-existing errors** (none in T04 files) ✅
- AST zero-import scan on entire `tests/` → **PASS: zero deleted-module imports** ✅
- `app/tasks/__init__.py` still parses → **PASS** ✅

### Slice-level verification status (T04 is intermediate, not final):
- `pytest --collect-only 2>&1 | grep -c ERROR` → 5 (pre-existing, not from S06 work) — partial pass
- AST zero-import scan on `tests/` → **PASS** ✅
- `app/tasks/__init__.py` parses → **PASS** ✅

## Diagnostics

- Run `pytest --collect-only` on any of the 7 files to verify collection health
- AST scan script from slice plan can be re-run to check for import regressions
- Each test file documents the Taskiq test pattern in its module docstring

## Deviations

- **test_messaging_dlq_wiring.py**: Plan said to just change import from `app.tasks.messaging` to `app.tasks.messaging_taskiq`. In practice, `app.tasks.messaging` was completely deleted and the new `messaging_taskiq.send_scheduled_message` has a fundamentally different async API (no `run_async`, `get_db_session`, or `handle_retry`). Required full rewrite, not just import swap.
- **test_flow_cancel.py**: Plan said "update import paths if needed". The patch targets also needed updating from `app.services.flow_management` shim to `app.services.flow.management.pause_resume` (actual source where `FlowManagementService.__init__` and `cancel_patient_flow` live). Also `_compat_now_sao_paulo` is the actual function name, not `now_sao_paulo`.
- **test_flow_recovery_retry_e2e.py**: Plan suggested restructuring module imports like `from app.tasks import flows_taskiq as followup_retry_task`. Instead, imported individual functions directly since they're all in `flows_taskiq` — cleaner than aliasing the whole module.

## Known Issues

- 5 pre-existing collection errors in other test files (test_session_validation.py, test_patient_onboarding_e2e.py, test_saga_transaction_duration.py, test_message_extractor.py, test_async_helpers_loop_lifecycle.py) — not related to S06 work.

## Files Created/Modified

- `backend-hormonia/tests/unit/tasks/test_followup_retry_task.py` — rewritten: async, flows_taskiq + helpers imports, _fake_context pattern
- `backend-hormonia/tests/unit/tasks/test_send_retry_task.py` — rewritten: async, flows_taskiq + helpers imports, _fake_context pattern
- `backend-hormonia/tests/unit/tasks/test_stuck_detection.py` — rewritten: async, flows_taskiq imports, removed celery_app/beat_schedule
- `backend-hormonia/tests/integration/test_flow_recovery_retry_e2e.py` — rewritten: async .fn() calls, local MaxRetriesExceededError stub, flows_taskiq imports
- `backend-hormonia/tests/unit/tasks/test_messaging_dlq_wiring.py` — rewritten: async, messaging_taskiq imports, new DLQ test patterns
- `backend-hormonia/tests/unit/services/test_flow_cancel.py` — updated: removed AsyncResult mock, D013 no-op test, fixed patch targets
- `backend-hormonia/tests/unit/api/v2/test_task_registry_dragonfly_fallback.py` — deleted celery_integration test, kept dependencies tests
- `.gsd/milestones/M009/slices/S06/tasks/T04-PLAN.md` — added Observability Impact section
