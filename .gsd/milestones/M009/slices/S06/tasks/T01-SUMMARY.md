---
id: T01
parent: S06
milestone: M009
provides:
  - 7 dead Celery test files removed (~648 lines)
  - Zero celery-named test files in tests/
  - Renamed test_celery_agent_bridge.py → test_agent_sync_bridge.py (live tests, misleading name)
key_files:
  - backend-hormonia/tests/integration/test_agent_sync_bridge.py (renamed from test_celery_agent_bridge.py)
key_decisions:
  - Renamed test_celery_agent_bridge.py instead of deleting — it tests live agent sync bridge code (app.ai.agents.base), not Celery
patterns_established:
  - none
observability_surfaces:
  - "`find backend-hormonia/tests -name '*celery*' -type f` returns empty — no celery-named test files remain"
duration: 5m
verification_result: passed
blocker_discovered: false
---

# T01: Delete dead Celery test files

**Deleted 7 dead Celery test files (~648 lines) and renamed 1 misnamed file to clear all celery-named tests from the tree.**

## What Happened

Deleted the 7 test files specified in the plan — all test Celery infrastructure removed in S05:
- `test_celery_app_async_helper.py` (34 lines)
- `test_celery_metrics_lifecycle.py` (111 lines)
- `test_celery_schedule_alignment.py` (114 lines)
- `test_queue_monitor.py` (56 lines)
- `test_monitoring_task_registration.py` (112 lines)
- `test_celery_ai_run_sync_path.py` (113 lines)
- `test_celery_async_isolation.py` (108 lines)

Discovered `test_celery_agent_bridge.py` also had "celery" in filename but imports only live modules (`app.ai.agents.base`, `app.ai.agents.deps`). Renamed it to `test_agent_sync_bridge.py` to meet the must-have of zero celery-named test files.

## Verification

- All 7 files confirmed gone (`ls` → "No such file or directory" for each)
- `find backend-hormonia/tests -name "*celery*" -type f` → empty (PASS)
- `grep` for imports from deleted file names → nothing (PASS)
- `python3 -c "import ast; ast.parse(open('backend-hormonia/app/tasks/__init__.py').read())"` → PASS

### Slice-level checks (partial — T01 is first of 5 tasks):
- AST zero-import scan: EXPECTED FAIL — 29 remaining test files still import deleted modules (addressed by T02–T05)
- `__init__.py` parse: PASS

## Diagnostics

- `find backend-hormonia/tests -name "*celery*" -type f` — should always return empty after this task
- Remaining Celery import residue in 29 test files is tracked by T02–T05

## Deviations

- Renamed `test_celery_agent_bridge.py` → `test_agent_sync_bridge.py` — not in original plan but required to meet must-have "no celery in filename". File imports only live modules.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/tests/tasks/test_celery_app_async_helper.py` — deleted
- `backend-hormonia/tests/tasks/test_celery_metrics_lifecycle.py` — deleted
- `backend-hormonia/tests/tasks/test_celery_schedule_alignment.py` — deleted
- `backend-hormonia/tests/tasks/test_queue_monitor.py` — deleted
- `backend-hormonia/tests/tasks/test_monitoring_task_registration.py` — deleted
- `backend-hormonia/tests/validation/test_celery_ai_run_sync_path.py` — deleted
- `backend-hormonia/tests/integration/test_celery_async_isolation.py` — deleted
- `backend-hormonia/tests/integration/test_agent_sync_bridge.py` — renamed from test_celery_agent_bridge.py
