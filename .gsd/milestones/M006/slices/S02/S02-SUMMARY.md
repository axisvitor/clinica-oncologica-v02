---
id: S02
parent: M006
milestone: M006
provides:
  - Canonical `users` head without the Firebase-prefixed columns or `ix_users_firebase_uid`, with the live ORM republished onto the surviving canonical fields.
  - Canonical auth/session, profile, physician, admin-user, and admin-stats surfaces that no longer depend on the dropped `users.firebase_*` columns during normal runtime reads/writes.
  - A resilient admin audit/activity read surface that normalizes dirty historical `audit_logs.event_type` labels instead of 500ing on the canonical head.
requires:
  - slice: S01
    provides: Cookie-only staff auth/session resolution and the republished zero-approved backend residue boundary.
affects:
  - S04
key_files:
  - backend-hormonia/alembic/versions/m006_s02_t03_drop_users_firebase_residue.py
  - backend-hormonia/app/models/user.py
  - backend-hormonia/app/dependencies/auth_session_cache.py
  - backend-hormonia/app/dependencies/auth_dependencies.py
  - backend-hormonia/app/api/v2/routers/physicians/crud.py
  - backend-hormonia/app/api/v2/routers/admin/utils.py
  - backend-hormonia/app/api/v2/routers/admin/activity.py
  - backend-hormonia/app/api/v2/routers/admin/stats.py
  - backend-hormonia/tests/api/v2/test_auth_timeout.py
  - backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py
  - .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh
key_decisions:
  - Live staff session restore and admin-session loading accept only canonical `user_id` / `id`; Firebase-only session payloads now fail closed instead of probing `users.firebase_uid`.
  - The surviving user/profile/admin/physician contract is canonical-only for `last_login`, `display_name`, `photo_url`, `preferences`, and the neutral physician fields; admin activity metrics use canonical `last_login` only.
  - The post-drop ORM no longer maps Firebase-prefixed `users` columns; compatibility accessors fail closed instead of silently remapping the dropped schema back into runtime.
  - Admin audit/activity reads normalize dirty historical uppercase event labels at the read surface instead of widening S02 into a new audit-schema migration.
patterns_established:
  - Shared session/auth fixtures should seed canonical profile data by default and treat `firebase_uid` only as leftover compatibility noise, not as live identity.
  - Final-schema replay should include the focused S02 auth/profile/admin packs before mounted proof so schema and runtime regressions fail in one place.
  - Where historical audit rows can still carry bad enum labels, admin read surfaces should cast/normalize the stored label instead of trusting ORM enum decoding.
observability_surfaces:
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend
  - backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py
  - /tmp/gsd-m005-s04-final-schema-proof/*/status.json
  - /tmp/gsd-m005-s04-final-schema-proof/*/pytest-replay.log
  - backend-hormonia/tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error
  - backend-hormonia/tests/api/v2/test_admin.py::{TestAuditLogs::test_get_audit_logs,TestAuditLogs::test_get_audit_logs_pagination,TestActivityStatistics::test_get_activity_statistics}
drill_down_paths:
  - .gsd/milestones/M006/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M006/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M006/slices/S02/tasks/T03-SUMMARY.md
duration: multi-task slice; recovery artifact written after timeout pressure
verification_result: blocked
completed_at: 2026-03-15T17:40:00-03:00
---

# S02: Remover o resíduo de schema que ainda prende o runtime ao passado

**Best-effort closeout artifact: the Firebase-prefixed `users` residue was cut from the canonical head and the touched runtime surfaces were republished onto canonical fields, but the slice is not honestly closed yet because one Postgres-only auth-timeout log assertion still blocks the full published verification pack.**

## What Happened

S02 did the main structural work it set out to do.

T01 retired the live Firebase-shaped session/auth fallback. `get_current_user_from_session()` and the cache/session resolver now require canonical `user_id` / `id` identity, Redis failures still fall back through the session table, and Firebase-only payloads fail closed instead of probing `users.firebase_uid`. The S01 backend residue guard was republished to remove the old auth/session/admin fallback seams.

T02 republished the surviving user/profile/admin/physician contract onto canonical `users` storage. `User` helpers stopped mirroring into `firebase_*` columns during normal writes, `users/me` / auth / physician CRUD / admin serializers now read canonical `last_login`, `display_name`, `photo_url`, `preferences`, and neutral physician fields, and admin activity metrics count active users from canonical `last_login`.

T03 added `m006_s02_t03_drop_users_firebase_residue` after `m005_s03_t02_align_audit_history_head`, dropping `users.firebase_uid`, the remaining Firebase-prefixed `users` fields, `last_firebase_sync`, and `ix_users_firebase_uid` while intentionally preserving `auth_provider` and `firebase_sync_history`. The ORM was aligned to that head so the live model no longer selects removed columns.

During slice closeout, the broader admin pack exposed a separate read-side incompatibility: some upgraded/test histories can still surface uppercase historical audit labels like `SESSION_INVALIDATED`, which made the admin audit/activity routes 500 when they queried the ORM enum directly. That was narrowed by normalizing `audit_logs.event_type` at the admin read surface (`cast(... as text)` + canonical lowercase normalization) instead of widening S02 into new audit-schema work.

That admin blocker is now green. The remaining blocker is narrower: under the real-Postgres `TEST_DATABASE_URL` harness, `tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error` still does not observe the expected timeout log record through `caplog`, even though the same 504 timeout path itself still works and the admin audit/activity regression is fixed.

## Verification

### Passed earlier in slice execution

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_uid_validation.py tests/api/v2/test_auth_timeout.py tests/integration/test_auth_fallback.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/api/v2/test_physicians_crud_regression.py tests/api/v2/test_admin.py::TestGetUser tests/api/v2/test_admin.py::TestUserStatistics tests/unit/services/test_admin_stats_service.py`
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_canonical_schema_head_convergence.py`

### Passed during recovery work

- `cd backend-hormonia && .venv/bin/python -m py_compile app/api/v2/routers/admin/utils.py app/api/v2/routers/admin/activity.py app/api/v2/routers/admin/stats.py tests/api/v2/test_auth_timeout.py`
- `cd backend-hormonia && .venv/bin/pytest -q tests/api/v2/test_admin.py::TestAuditLogs::test_get_audit_logs tests/api/v2/test_admin.py::TestAuditLogs::test_get_audit_logs_pagination tests/api/v2/test_admin.py::TestActivityStatistics::test_get_activity_statistics -vv`
  - result: **3 passed**

### Still blocking honest slice completion

- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' .venv/bin/pytest -q tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error -vv`
  - result: **fails** because `caplog` does not observe the expected canonical-user-id timeout log record under the Postgres-backed harness.
- Because that assertion is still red, the full slice-level verification list has **not** been rerun green end to end, and `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh|--existing` was **not** revalidated after the recovery changes.

## Requirements Advanced

- R052 — S02 materially advanced the residue-removal front by dropping the Firebase-prefixed `users` columns from the canonical head, republishing the touched runtime surfaces onto canonical storage, and removing the live auth/session dependency on `users.firebase_uid`.

## Requirements Validated

- none — this recovery artifact does **not** move R052 to validated because the published slice verification remains blocked on the Postgres-only auth-timeout log assertion and the final-schema runner was not rerun green after recovery.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- S02 had to patch the admin audit/activity read surface to tolerate dirty historical uppercase `audit_logs.event_type` labels (`SESSION_INVALIDATED`) that were not part of the written slice scope but were preventing the full `tests/api/v2/test_admin.py` pack from passing on the canonical head.
- This file is a recovery-time partial closeout artifact written under idle-recovery pressure before the remaining Postgres-only timeout-log assertion was resolved.

## Known Limitations

- `tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error` still fails only when the suite runs against the real Postgres head via `TEST_DATABASE_URL`; the 504 timeout path still happens, but the expected log record is not visible to `caplog` under that harness.
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh` and `--existing` were not rerun green after the recovery edits, so S02 is not honestly re-closed yet.
- This summary exists so the unit leaves durable state, but the slice still needs one more verification/fix pass before it can be trusted as complete.

## Follow-ups

- Reproduce the Postgres-only `caplog` failure for `tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error` with a focused in-repo repro and either fix the log capture path or republish the assertion onto a stable diagnostic surface.
- Rerun the **full** S02 verification list from `.gsd/milestones/M006/slices/S02/S02-PLAN.md` once the timeout-log assertion is green.
- Rerun `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh` and `--existing` after the timeout-log fix, because those runners were still red/untested at the moment this recovery artifact was written.

## Files Created/Modified

- `backend-hormonia/alembic/versions/m006_s02_t03_drop_users_firebase_residue.py` — new canonical head that drops the Firebase-prefixed `users` residue and `ix_users_firebase_uid`.
- `backend-hormonia/app/models/user.py` — removed the dropped Firebase-prefixed `users` fields from the mapped ORM contract and kept only transient fail-closed compatibility accessors.
- `backend-hormonia/app/dependencies/auth_session_cache.py` — canonical-only session/cache hydration and fail-closed Firebase-only payload handling.
- `backend-hormonia/app/dependencies/auth_dependencies.py` — canonical user-id DB lookup and timeout diagnostics for session restore.
- `backend-hormonia/app/api/v2/routers/physicians/crud.py` — canonical physician search/update/read behavior only.
- `backend-hormonia/app/api/v2/routers/admin/utils.py` — shared canonical admin helpers plus audit-label normalization/severity helpers.
- `backend-hormonia/app/api/v2/routers/admin/activity.py` — admin audit listing now reads raw/cast audit labels and normalizes dirty historical enum text instead of failing ORM decode.
- `backend-hormonia/app/api/v2/routers/admin/stats.py` — activity stats now aggregate from raw audit rows and normalize event labels/severity safely on the canonical head.
- `backend-hormonia/tests/api/v2/test_auth_timeout.py` — timeout-log proof narrowed toward the module logger, but the Postgres-backed harness assertion is still red.
- `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py` — pinned the new post-drop head and explicit `users` column/index contract.
- `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` — published replay path includes the focused S02 runtime packs before mounted proof.
- `.gsd/milestones/M006/slices/S02/S02-SUMMARY.md` — this recovery artifact.

## Forward Intelligence

### What the next slice should know
- The admin audit/activity failures were not caused by the `users` schema drop itself; they were caused by dirty historical uppercase `audit_logs.event_type` labels surfacing only when the broader admin routes read from the real canonical head.
- The remaining blocker is isolated to `tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error` under `TEST_DATABASE_URL`; the 504 timeout behavior still works, but the log capture assertion does not.

### What's fragile
- `backend-hormonia/tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error` — it is the only red edge known at recovery time, and it blocks honest end-to-end rerun of the S02 slice verification and final-schema proof.
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh|--existing` — both still need a clean replay after the timeout-log assertion is fixed.

### Authoritative diagnostics
- `/tmp/gsd-m005-s04-final-schema-proof/*/status.json` — still the best top-level phase pointer for the final-schema runner.
- `/tmp/gsd-m005-s04-final-schema-proof/*/pytest-replay.log` — where a renewed replay failure will localize if the auth-timeout assertion or another focused pack still breaks.
- `backend-hormonia/tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error` — current single-test blocker for honest S02 closeout.

### What assumptions changed
- “The remaining admin failures are unrelated pre-existing noise.” — false; they blocked the full slice verification and needed a real read-surface fix before S02 could even get back to the final timeout-log blocker.
- “Once the new Alembic head passes, the slice is basically closed.” — false; the real-Postgres replay path still surfaced one observability assertion that the local default harness did not.
