---
estimated_steps: 5
estimated_files: 1
---

# T01: Fix the S02 caplog blocker and confirm the full S02 verification list

**Slice:** S04 — Publicar o closeout final e provar o sistema montado pós-purga
**Milestone:** M006

## Description

The test `test_get_current_user_from_session_db_timeout_logs_error` in `backend-hormonia/tests/api/v2/test_auth_timeout.py` fails when run against a real Postgres database via `TEST_DATABASE_URL`. The 504 timeout behavior itself works — only the log observation assertion is broken. The root cause is that the conftest's session-scoped Postgres provisioning path runs `alembic upgrade head`, which triggers early imports that may reconfigure the `app.dependencies.auth_dependencies` logger's propagation/handler chain before the individual test's `caplog` captures.

The fix must stay in the test file only — no production logging changes.

## Steps

1. **Reproduce the failure.** Run `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' .venv/bin/pytest -q tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error -vv` and confirm it fails on the caplog assertion.

2. **Diagnose the root cause.** Check the `app.dependencies.auth_dependencies` logger's `propagate` and `handlers` state during the Postgres harness. The Alembic provisioning path imports app modules at session scope, which can attach handlers or set `propagate=False` on the module logger before `caplog` gets control. Inspect with a temporary debug print like:
   ```python
   import logging
   target = logging.getLogger("app.dependencies.auth_dependencies")
   print(f"propagate={target.propagate}, handlers={target.handlers}, parent={target.parent}")
   ```

3. **Fix the test's log capture.** Based on the diagnosis, apply the narrowest fix:
   - If `propagate=False`: set `propagate=True` on the target logger within the test (and restore after).
   - If handlers are attached that swallow the record: capture at root level and filter by logger name in the assertion.
   - If the logger name is different under Postgres: adjust the `caplog.set_level` call to target the actual logger.

4. **Verify under Postgres harness.** Run `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' .venv/bin/pytest -q tests/api/v2/test_auth_timeout.py -vv` — all 4 tests must pass.

5. **Verify under default (SQLite) harness.** Run `cd backend-hormonia && .venv/bin/pytest -q tests/api/v2/test_auth_timeout.py -vv` — all 4 tests must still pass. Then run the full S02 verification list:
   - `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_uid_validation.py tests/api/v2/test_auth_timeout.py tests/integration/test_auth_fallback.py`
   - `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/api/v2/test_physicians_crud_regression.py tests/api/v2/test_admin.py tests/unit/services/test_admin_stats_service.py`
   - `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_canonical_schema_head_convergence.py`

## Must-Haves

- [ ] `test_get_current_user_from_session_db_timeout_logs_error` passes under `TEST_DATABASE_URL` Postgres harness.
- [ ] All 4 tests in `test_auth_timeout.py` pass under both SQLite default and Postgres harnesses.
- [ ] No production logging code changes — only `test_auth_timeout.py` is modified.
- [ ] The full S02 focused backend packs pass.

## Verification

- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' .venv/bin/pytest -q tests/api/v2/test_auth_timeout.py -vv` → 4 passed
- `cd backend-hormonia && .venv/bin/pytest -q tests/api/v2/test_auth_timeout.py -vv` → 4 passed
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_uid_validation.py tests/api/v2/test_auth_timeout.py tests/integration/test_auth_fallback.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/api/v2/test_physicians_crud_regression.py tests/api/v2/test_admin.py tests/unit/services/test_admin_stats_service.py`
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_canonical_schema_head_convergence.py`

## Inputs

- `backend-hormonia/tests/api/v2/test_auth_timeout.py` — the test file with the broken caplog assertion (the only file to modify).
- `backend-hormonia/app/dependencies/auth_dependencies.py` — production code with `logger = logging.getLogger(__name__)` at line 27 and the timeout log emission. Read-only for diagnosis; do NOT modify.
- `backend-hormonia/tests/conftest.py` — the session-scoped `test_engine` fixture that provisions Postgres via `alembic upgrade head` (lines ~1008–1027). Read-only for diagnosis.
- S02 summary documents `test_get_current_user_from_session_db_timeout_logs_error` as the single remaining red edge.

## Expected Output

- `backend-hormonia/tests/api/v2/test_auth_timeout.py` — modified with a caplog fix that makes the log assertion work under both SQLite and Postgres harnesses, without touching production code.
