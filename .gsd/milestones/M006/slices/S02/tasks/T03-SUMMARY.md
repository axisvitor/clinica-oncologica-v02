---
id: T03
parent: S02
milestone: M006
provides:
  - Post-drop Alembic head for `users` that removes the remaining Firebase-prefixed columns and `ix_users_firebase_uid` while preserving `auth_provider`.
  - Explicit canonical-head fingerprinting for the final `users` schema plus an updated final-schema runner that replays the focused S02 runtime packs before mounted proof.
key_files:
  - backend-hormonia/alembic/versions/m006_s02_t03_drop_users_firebase_residue.py
  - backend-hormonia/app/models/user.py
  - backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py
  - .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh
  - .gsd/DECISIONS.md
key_decisions:
  - Remove the Firebase-prefixed `users` fields from the mapped ORM contract and keep only transient fail-closed compatibility accessors so the live ORM matches the post-drop head.
  - Pin the canonical head with explicit `users` column/index diffs instead of relying only on clean-vs-existing equivalence.
patterns_established:
  - Post-drop compatibility for removed ORM fields should be transient and fail closed at query time rather than silently remapping dropped schema back into the live model.
  - Final-schema replay should carry the focused slice runtime packs inside the published runner so schema and runtime regressions fail in one persisted proof surface.
observability_surfaces:
  - /tmp/gsd-m005-s04-final-schema-proof/fresh/status.json
  - /tmp/gsd-m005-s04-final-schema-proof/fresh/pytest-replay.log
  - backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py assertion diffs (`users_column_diff`, `users_index_diff`)
duration: 2h05m
verification_result: failed
completed_at: 2026-03-15
blocker_discovered: false
---

# T03: Drop the remaining Firebase-named `users` columns and replay the final-schema pack

**Added the post-drop `users` head and aligned the live ORM/proof surfaces to it, but the slice is still blocked by replay failures outside the schema diff itself.**

## What Happened

I added `m006_s02_t03_drop_users_firebase_residue` after `m005_s03_t02_align_audit_history_head` to remove `users.firebase_uid`, the remaining `firebase_*` fields, `last_firebase_sync`, and `ix_users_firebase_uid`, while intentionally leaving `auth_provider` and `firebase_sync_history` alone.

That exposed the real runtime seam: the `User` ORM still mapped the removed columns, so any final-head query would have selected columns that no longer exist. I updated `backend-hormonia/app/models/user.py` to stop mapping those Firebase-prefixed `users` fields and replaced them with transient compatibility accessors. Instance-level legacy callers can still read/write them temporarily, but class-level `User.firebase_uid` queries now fail closed instead of reintroducing a live schema dependency.

I rewrote `tests/migrations/test_canonical_schema_head_convergence.py` so it now pins the new head revision and emits explicit `users_column_diff` / `users_index_diff` failures if removed columns or `ix_users_firebase_uid` come back. The expected post-drop `users` index set was updated from the actual head (`idx_users_locked`, `idx_users_locked_until`, `ix_users_permissions_gin`, `users_email_key`) instead of assuming the ORM’s index names.

I also extended `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` so the published replay phase includes the focused S02 auth/profile/admin packs before the mounted backend proof.

## Verification

Passed:

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_uid_validation.py tests/api/v2/test_auth_timeout.py tests/integration/test_auth_fallback.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_timeout.py -k "db_timeout_returns_504 or db_timeout_logs_error"`
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_canonical_schema_head_convergence.py`

Failed:

- `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/api/v2/test_physicians_crud_regression.py tests/api/v2/test_admin.py tests/unit/services/test_admin_stats_service.py`
  - fails in `tests/api/v2/test_admin.py::{TestAuditLogs::test_get_audit_logs, TestAuditLogs::test_get_audit_logs_pagination, TestActivityStatistics::test_get_activity_statistics}` with the known audit enum decode error: `'SESSION_INVALIDATED' is not among the defined enum values. Enum name: audit_event_type.`
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh`
  - fails in `pytest_replay` before mounted proof on `tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error`
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --existing`
  - not rerun after `--fresh` failed in the replay phase

## Diagnostics

- Fresh final-schema status: `/tmp/gsd-m005-s04-final-schema-proof/fresh/status.json`
- Fresh replay log: `/tmp/gsd-m005-s04-final-schema-proof/fresh/pytest-replay.log`
- The fresh runner currently dies at:
  - `tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error`
  - assertion: expected canonical user-id prefix to appear in the timeout log, but it was absent under the `TEST_DATABASE_URL` replay path
- The broader admin pack still fails with the T02-known audit enum decode error when routes materialize `AuditLog.event_type` from uppercase `SESSION_INVALIDATED` rows.

## Deviations

- Added `backend-hormonia/app/models/user.py` to the task scope even though the written plan only named the migration, convergence test, and runner. The final head was unusable without aligning the ORM mapping to the dropped `users` columns.

## Known Issues

- `tests/api/v2/test_admin.py` still fails on the known `AuditLog.event_type` uppercase enum decode (`SESSION_INVALIDATED`) in the admin audit/activity routes.
- `run-final-schema-proof.sh --fresh` now reaches the S02 replay phase on the post-drop head, but the replay is still blocked by `tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error` under `TEST_DATABASE_URL`.
- `--existing` was intentionally not rerun after the fresh replay failed at the same pre-mounted proof phase.

## Files Created/Modified

- `backend-hormonia/alembic/versions/m006_s02_t03_drop_users_firebase_residue.py` — new head revision that drops the Firebase-prefixed `users` residue and `ix_users_firebase_uid`.
- `backend-hormonia/app/models/user.py` — removed the dropped Firebase-prefixed `users` fields from the mapped ORM contract and replaced them with transient fail-closed compatibility accessors.
- `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py` — pinned the new head revision and added explicit post-drop `users` column/index contract assertions.
- `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` — expanded the replay phase to include the focused S02 runtime packs before mounted backend proof.
- `.gsd/DECISIONS.md` — recorded the post-drop ORM compatibility seam decision.
