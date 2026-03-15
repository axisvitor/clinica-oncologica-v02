# S02: Remover o resíduo de schema que ainda prende o runtime ao passado — UAT

**Milestone:** M006
**Written:** 2026-03-15

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S02 is a schema/runtime convergence slice. The important proof is replayable runtime + migration evidence on the canonical head, not manual browser behavior.

## Preconditions

1. Work from repo root `/mnt/c/Meu Projetos/clinica-oncologica-v02-1`.
2. Backend virtualenv exists at `backend-hormonia/.venv`.
3. Local Postgres test DB is reachable at `postgresql://postgres:postgres@localhost:55432/hormonia_test`.
4. The S01 residue verifier and the M005 final-schema runner are available at their published paths.
5. **Recovery note:** at the time this UAT file was written, one verification blocker still remained:
   - `backend-hormonia/tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error`
   - under `TEST_DATABASE_URL`, the 504 path still happens but `caplog` does not observe the expected log record.

## Smoke Test

Run the focused admin audit/activity regression that was repaired during recovery:

1. `cd backend-hormonia && .venv/bin/pytest -q tests/api/v2/test_admin.py::TestAuditLogs::test_get_audit_logs tests/api/v2/test_admin.py::TestAuditLogs::test_get_audit_logs_pagination tests/api/v2/test_admin.py::TestActivityStatistics::test_get_activity_statistics -vv`
2. **Expected:** all 3 tests pass. This confirms the admin audit/activity routes no longer 500 when dirty historical uppercase audit labels (for example `SESSION_INVALIDATED`) exist in upgraded/test data.

## Test Cases

### 1. Backend auth/session residue stays zero-approved after the canonical identity cut

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
2. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
3. **Expected:** `--check backend` is green and the report shows no approved backend auth/session residue for the S02-touched seams. Any remaining references must be explicit proof-only/historical boundaries, not live fallback logic.

### 2. Canonical auth/session timeout and fallback pack stays green on the slice head

1. Run:
   `cd backend-hormonia && .venv/bin/pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_uid_validation.py tests/api/v2/test_auth_timeout.py tests/integration/test_auth_fallback.py`
2. **Expected:** all tests pass.
3. **Expected behavioral meaning:** Firebase-only session payloads fail closed, canonical `user_id` payloads still restore session state, and Redis failure still falls back through the session table.

### 3. Canonical profile/admin/physician surfaces run without the dropped `users.firebase_*` columns

1. Run:
   `cd backend-hormonia && .venv/bin/pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/api/v2/test_physicians_crud_regression.py tests/api/v2/test_admin.py tests/unit/services/test_admin_stats_service.py`
2. **Expected:** all tests pass.
3. **Expected behavioral meaning:** `users/me`, physician search/detail/update, admin user serialization, admin user stats, and related fixtures all read/write canonical fields only.

### 4. Canonical schema convergence lands on the post-drop head

1. Run:
   `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' .venv/bin/pytest -q tests/migrations/test_canonical_schema_head_convergence.py`
2. **Expected:** the test passes.
3. **Expected structural meaning:** the head is `m006_s02_t03_drop_users_firebase_residue`, `users` no longer has the Firebase-prefixed columns, and `ix_users_firebase_uid` is gone.

### 5. Fresh final-schema replay runs on the post-drop head

1. Run:
   `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh`
2. **Expected:** the runner finishes green.
3. **Expected artifacts:** `/tmp/gsd-m005-s04-final-schema-proof/fresh/status.json` reports a passed terminal phase, and `pytest-replay.log` shows the focused S02 runtime packs completing before mounted proof.

### 6. Existing-history final-schema replay also converges on the post-drop head

1. Run:
   `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --existing`
2. **Expected:** the runner finishes green.
3. **Expected meaning:** both the `fresh` and `existing` histories land on the same canonical head and still support the focused S02 runtime packs plus mounted backend proof.

## Edge Cases

### Edge Case: Firebase-only session payload is rejected instead of silently restored

1. Run the focused auth/session pack in Test Case 2.
2. **Expected:** tests covering malformed/Firebase-only session payloads fail closed with `401 Invalid session data` rather than loading a user through `firebase_uid`.

### Edge Case: Dirty historical uppercase audit labels do not break admin routes

1. Run the smoke test command again after any change touching admin audit/activity routes.
2. **Expected:** the admin audit list and activity stats routes continue passing even if upgraded/test data still contains uppercase historical labels like `SESSION_INVALIDATED`.

### Edge Case: Postgres-only timeout-log proof

1. Run:
   `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' .venv/bin/pytest -q tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error -vv`
2. **Expected after final fix:** the test passes and observes the canonical user-id prefix in the timeout log record.
3. **Current recovery status:** this was still the only known blocker when this artifact was written.

## Failure Signals

- `verify-runtime-residue.sh --check backend` reports approved backend auth/session residue.
- `tests/migrations/test_canonical_schema_head_convergence.py` reports `users_column_diff`, `users_index_diff`, or a head different from `m006_s02_t03_drop_users_firebase_residue`.
- `tests/api/v2/test_admin.py` starts failing again in audit/activity routes with enum decode errors mentioning `SESSION_INVALIDATED`.
- `tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error` still fails under `TEST_DATABASE_URL` because the expected timeout log record is not visible to `caplog`.
- `/tmp/gsd-m005-s04-final-schema-proof/*/status.json` stops at `pytest_replay` or another non-terminal failure phase.

## Requirements Proved By This UAT

- R052 — once all test cases above are green, this UAT proves the schema/runtime residue in S02 was removed with replayable evidence rather than by grep only.

## Not Proven By This UAT

- S03 repo-wide bridge/tombstone/docs/workflow cleanup.
- S04 final combined closeout pack for the whole milestone.
- At the moment this file was written, S02 itself was **not fully proven yet** because the Postgres-only timeout-log assertion still blocked honest slice closeout.

## Notes for Tester

- Treat this as a recovery-time UAT script, not a green completion report.
- Start with the smoke test and the single-test blocker. If the timeout-log assertion is still red, do **not** treat S02 as fully closed even if the schema head and admin audit regressions are green.
- The most authoritative resume point is `backend-hormonia/tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error` plus `/tmp/gsd-m005-s04-final-schema-proof/*/pytest-replay.log` if the final-schema runner is rerun and still fails.
