---
id: T02
parent: S02
milestone: M006
provides:
  - Canonical-only helper defaults for the surviving `users` auth/profile fields, so normal runtime writes stop mirroring into `firebase_*` columns or `firebase_custom_claims`.
  - Canonical physician/profile/admin serialization, search, update, and admin stats activity signals published from `last_login`, `display_name`, `photo_url`, `preferences`, and the neutral physician fields.
  - Shared auth/session fixtures and focused proof files that seed and assert canonical profile data instead of Firebase-era mirrors.
key_files:
  - backend-hormonia/app/models/user.py
  - backend-hormonia/app/api/v2/routers/users.py
  - backend-hormonia/app/api/v2/routers/auth.py
  - backend-hormonia/app/api/v2/routers/physicians/crud.py
  - backend-hormonia/app/api/v2/routers/admin/utils.py
  - backend-hormonia/app/services/analytics/admin_stats_service.py
  - backend-hormonia/tests/api/v2/conftest.py
  - backend-hormonia/tests/conftest.py
  - backend-hormonia/tests/api/v2/test_canonical_user_profile_contracts.py
  - backend-hormonia/tests/api/v2/test_physicians_crud_regression.py
  - backend-hormonia/tests/api/v2/test_admin.py
  - backend-hormonia/tests/unit/services/test_admin_stats_service.py
key_decisions:
  - Published `User` helper getters/setters as canonical-only for the surviving profile/auth fields while preserving the method signatures so downstream callers keep working during the cut.
  - Chose canonical `users.last_login` as the admin user-activity signal and pinned it with unit proof instead of keeping `firebase_last_sign_in` as a silent metric dependency.
  - Republished default session/auth test payload builders with canonical `last_login`, `display_name`, `photo_url`, `preferences`, and `email_verified` so focused API assertions exercise the post-cut contract by default.
patterns_established:
  - Shared session/auth fixtures should build user payloads from model helper getters (`get_last_login`, `get_display_name`, `get_photo_url`, `get_preferences_data`) rather than reading legacy columns directly.
  - Focused API proof now checks canonical field drift (`last_login`, `display_name`, `photo_url`, `specialties`, `active_now`) and absence of legacy response keys, instead of asserting legacy mirror behavior.
  - Physician update/search code now stays on canonical columns (`display_name`, `specialties`, `license_number`, `phone`, `bio`, `is_active`) without writing compatibility claims.
observability_surfaces:
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
  - `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/api/v2/test_physicians_crud_regression.py tests/api/v2/test_admin.py tests/unit/services/test_admin_stats_service.py`
  - `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/api/v2/test_physicians_crud_regression.py tests/api/v2/test_admin.py::TestGetUser tests/api/v2/test_admin.py::TestUserStatistics tests/unit/services/test_admin_stats_service.py`
  - `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_uid_validation.py tests/api/v2/test_auth_timeout.py tests/integration/test_auth_fallback.py`
duration: ~2h15m
verification_result: partial
completed_at: 2026-03-14T16:45:00-03:00
blocker_discovered: false
---

# T02: Republish canonical user/profile/admin/physician surfaces and fixtures

**Republished the surviving user/profile/admin/physician runtime surfaces onto canonical `users` fields and moved the shared fixtures/proof pack onto canonical profile data.**

## What Happened

I flipped the `User` helper contract so the surviving auth/profile fields now read and write only canonical storage (`last_login`, `auth_created_at`, `email_verified`, `display_name`, `photo_url`, `preferences`, `specialty`, `specialties`, `license_number`, `phone`, `bio`, `avatar_url`). The helper methods keep their signatures, but they no longer mirror into `firebase_*` columns or `firebase_custom_claims` during routine writes.

On the live surfaces, I removed the remaining direct Firebase-era reads/writes from the touched runtime:

- `app/api/v2/routers/users.py` now publishes canonical `display_name` and `email_verified` alongside canonical `last_login`/`photo_url`.
- `app/api/v2/routers/auth.py` and `app/api/v2/routers/admin/utils.py` now serialize `last_login`/`photo_url` from canonical fields only.
- `app/api/v2/routers/physicians/crud.py` now searches only canonical `display_name`, serializes canonical physician profile fields, and updates physician fields without writing compatibility claims.
- `app/services/analytics/admin_stats_service.py` now counts active users from canonical `last_login` instead of `firebase_last_sign_in`.

I also republished the default test/session builders so the seeded admin/doctor fixtures and shared `TestUser` payloads carry canonical `last_login`, `display_name`, `photo_url`, `preferences`, and `email_verified` by default. The focused proof files were rewritten around that contract:

- canonical users/me profile payload
- canonical preferences patch persistence
- canonical physician search/detail/update behavior
- canonical admin user `last_login` serialization
- canonical admin stats activity signal

## Must-Haves Addressed

- No touched live serializer, search, update, or metric surface in this task still reads or writes the doomed `users.firebase_*` columns; the canonical proof files and residue report cover the republished profile/admin/physician/admin-stats paths.
- Shared fixtures and focused API proofs now seed and assert canonical `last_login`, `display_name`, `photo_url`, `preferences`, and canonical physician/admin profile data by default.

## Verification

Passed:

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend && bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
  - Result: `--check backend OK`; no approved backend residue. Remaining `firebase_uid` hits stayed proof-only outside the T02 surfaces.
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_uid_validation.py tests/api/v2/test_auth_timeout.py tests/integration/test_auth_fallback.py`
  - Result: 25 passed.
- `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/api/v2/test_physicians_crud_regression.py tests/api/v2/test_admin.py::TestGetUser tests/api/v2/test_admin.py::TestUserStatistics tests/unit/services/test_admin_stats_service.py`
  - Result: 15 passed.

T02 verification command rerun:

- `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/api/v2/test_physicians_crud_regression.py tests/api/v2/test_admin.py tests/unit/services/test_admin_stats_service.py`
  - Result: all T02-owned canonical profile/physician/admin-user/admin-stats assertions passed, but the command still fails on three existing admin audit/activity tests:
    - `tests/api/v2/test_admin.py::TestAuditLogs::test_get_audit_logs`
    - `tests/api/v2/test_admin.py::TestAuditLogs::test_get_audit_logs_pagination`
    - `tests/api/v2/test_admin.py::TestActivityStatistics::test_get_activity_statistics`
  - Failure shape: admin audit/activity routes hit a pre-existing enum decode error while reading audit rows — `LookupError: 'SESSION_INVALIDATED' is not among the defined enum values. Enum name: audit_event_type`.

Not rerun in this unit because they are T03-owned schema-drop proof steps:

- `cd backend-hormonia && pytest -q tests/migrations/test_canonical_schema_head_convergence.py`
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh`
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --existing`

## Diagnostics

To inspect this task later:

- Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` and confirm the touched runtime files do not show up as approved residue.
- Run `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/api/v2/test_physicians_crud_regression.py tests/api/v2/test_admin.py::TestGetUser tests/api/v2/test_admin.py::TestUserStatistics tests/unit/services/test_admin_stats_service.py` to replay the canonical profile/admin/physician proof that went green in this task.
- If the broader admin pack still fails, the current diagnostic signature is the admin audit/activity enum decode error on `SESSION_INVALIDATED` when the routes materialize `AuditLog.event_type`.

## Deviations

- Added the canonical profile serializer publish in `app/api/v2/routers/users.py` so `users/me` actually emits the canonical `display_name` and `email_verified` fields already present in the response schema.
- Added a new unit proof file `tests/unit/services/test_admin_stats_service.py` because the planned focused admin-stats proof did not exist yet.
- Added an explicit diagnostic verification step to `S02-PLAN.md` for the canonical DB-timeout failure surface, per the pre-flight observability fix.

## Known Issues

- The full T02 verification command is still red on three admin audit/activity tests because the routes hit a pre-existing `AuditLog.event_type` enum decode error on `SESSION_INVALIDATED`. This did not block the T02-owned canonical profile/admin-user/physician/admin-stats proofs, but it still needs cleanup before the whole admin pack is fully green.
- T03 schema-drop verification was not executed in this unit; the canonical-head convergence and final-schema replay remain owned by the next task.

## Files Created/Modified

- `backend-hormonia/app/models/user.py` — made the surviving profile/auth helper methods canonical-only and stopped default mirroring into Firebase-era columns/claims.
- `backend-hormonia/app/api/v2/routers/users.py` — published canonical `display_name` and `email_verified` on the users/me serializer.
- `backend-hormonia/app/api/v2/routers/auth.py` — removed direct Firebase-era fallback from authenticated-user serialization.
- `backend-hormonia/app/api/v2/routers/physicians/crud.py` — removed canonical-surface search/update dependence on `firebase_display_name` and compatibility claims.
- `backend-hormonia/app/api/v2/routers/admin/utils.py` — serialized admin user `last_login` from canonical storage only.
- `backend-hormonia/app/services/analytics/admin_stats_service.py` — switched active-user metrics to canonical `last_login`.
- `backend-hormonia/tests/api/v2/conftest.py` — republished API auth/session fixtures with canonical profile fields and canonical Redis session payloads.
- `backend-hormonia/tests/conftest.py` — republished shared `TestUser`/session payload builders with canonical profile fields.
- `backend-hormonia/tests/api/v2/test_canonical_user_profile_contracts.py` — rewrote focused proof around canonical users/me, preferences, auth payload, and physician detail behavior.
- `backend-hormonia/tests/api/v2/test_physicians_crud_regression.py` — added canonical physician search/update regression proof.
- `backend-hormonia/tests/api/v2/test_admin.py` — added canonical admin user `last_login` response proof.
- `backend-hormonia/tests/unit/services/test_admin_stats_service.py` — added canonical admin-stats unit proof for `active_now` based on `last_login`.
- `.gsd/milestones/M006/slices/S02/S02-PLAN.md` — added the missing diagnostic verification step flagged in pre-flight.
- `.gsd/DECISIONS.md` — recorded the canonical `last_login`/profile/admin/physician contract decision for T02.
