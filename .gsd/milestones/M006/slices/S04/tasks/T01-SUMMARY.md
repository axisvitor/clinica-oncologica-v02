---
id: T01
parent: S04
milestone: M006
provides:
  - caplog blocker fix for test_get_current_user_from_session_db_timeout_logs_error under Postgres harness
  - full S02 verification list confirmed green
key_files:
  - backend-hormonia/tests/api/v2/test_auth_timeout.py
key_decisions:
  - Reset logger.disabled flag in test rather than changing alembic env.py or production code
patterns_established:
  - Restore logger.disabled/propagate in try/finally when alembic fileConfig may disable loggers during session-scoped Postgres provisioning
observability_surfaces:
  - none
duration: 15m
verification_result: passed
completed_at: 2026-03-15
blocker_discovered: false
---

# T01: Fix the S02 caplog blocker and confirm the full S02 verification list

**Fixed caplog capture under Postgres harness by resetting logger.disabled flag set by alembic's fileConfig(disable_existing_loggers=True)**

## What Happened

Root cause: `alembic/env.py` calls `fileConfig(config.config_file_name)` during `alembic upgrade head` in the session-scoped Postgres provisioning path. Python's `fileConfig` defaults to `disable_existing_loggers=True`, which sets `disabled=True` on every logger that already exists at that point. Since the test file imports `app.dependencies.auth_dependencies` at module level (creating the logger before the session fixture fires), the logger gets disabled. A disabled logger silently drops all records — caplog never sees them.

Under SQLite, alembic never runs, so the logger stays enabled and the test passes.

Fix: In the test function, save and reset `target_logger.disabled = False` and `target_logger.propagate = True` before calling the code under test, then restore both in a `finally` block. No production code touched.

## Verification

All checks passed:

- `TEST_DATABASE_URL=... pytest -q tests/api/v2/test_auth_timeout.py -vv` → **4 passed** (Postgres)
- `pytest -q tests/api/v2/test_auth_timeout.py -vv` → **4 passed** (SQLite)
- S02 pack 1 (`test_auth_session_cache_canonical_identity`, `test_auth_session_shared_canonical_identity`, `test_auth_uid_validation`, `test_auth_timeout`, `test_auth_fallback`) → **25 passed**
- S02 pack 2 (`test_canonical_user_profile_contracts`, `test_physicians_crud_regression`, `test_admin`, `test_admin_stats_service`) → **66 passed**
- Schema convergence under Postgres → **1 passed**

Slice-level checks completed by this task: 3 of 11 (the three backend pytest verification items).

## Diagnostics

If this test fails again under Postgres, check `logging.getLogger("app.dependencies.auth_dependencies").disabled` — if `True`, `fileConfig` ran again and the fix needs to re-apply.

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/tests/api/v2/test_auth_timeout.py` — Added logger.disabled/propagate reset in try/finally around the caplog-dependent test to survive alembic's fileConfig during Postgres provisioning.
