---
id: T01
parent: S03
milestone: M005
provides:
  - Canonical `users` profile/settings storage plus route/helper dual-write so official user/auth/physician surfaces stop treating Firebase-named fields and claims as the live contract.
key_files:
  - backend-hormonia/alembic/versions/m005_s03_t01_republish_users_canonical_contract.py
  - backend-hormonia/app/models/user.py
  - backend-hormonia/tests/api/v2/test_canonical_user_profile_contracts.py
key_decisions:
  - Canonical `users` columns (`last_login`, `photo_url`, `preferences`, physician/profile fields) become the live source of truth now, while legacy Firebase-named storage is mirrored only for transition compatibility.
patterns_established:
  - Read canonical first with legacy fallback at the model/helper edge; write canonical first and mirror legacy storage only where active readers/tests still exist.
observability_surfaces:
  - tests/api/v2/test_canonical_user_profile_contracts.py
  - tests/api/v2/test_auth_session_shared_canonical_identity.py
  - tests/migrations/test_canonical_schema_head_convergence.py
duration: ~2h
verification_result: passed
completed_at: 2026-03-15T11:44:36-03:00
blocker_discovered: false
---

# T01: Republicar o contrato vivo de `users` sob nomes canônicos

**Republished the live `users` contract under neutral columns, rewired user/auth/physician reads and writes to those columns with legacy mirroring, and added focused proof for canonical profile/preferences surfaces.**

## What Happened

Added a new linear Alembic revision after the S02 historical-boundary head to publish neutral `users` storage for the still-live login/profile/settings data: `last_login`, `auth_created_at`, `email_verified`, `display_name`, `photo_url`, `preferences`, `specialty`, `specialties`, `license_number`, `phone`, `bio`, and `avatar_url`. The revision backfills from the existing `firebase_*` columns and `firebase_custom_claims`, then hardens the JSON/bool defaults so fresh rows land on the canonical shape.

`app.models.user` now exposes those neutral columns as the live contract and centralizes the transition behavior with canonical-first getters/setters that mirror the legacy Firebase-named columns/claims only when compatibility still matters. `firebase_uid` and `auth_provider` remain explicit compatibility linkage.

Rewired the official surfaces around that model contract:

- `users.py` now reads canonical `last_login` / `photo_url` / `preferences` and persists preferences into the neutral `preferences` column while still mirroring the legacy claims bag.
- `auth.py` and `app/services/auth.py` now serialize/login/update against canonical profile storage, including `last_login`, profile updates, and avatar persistence.
- `physicians/crud.py` and `schemas/v2/physicians.py` now publish canonical field names (`display_name`, `photo_url`, `email_verified`) and persist physician profile data through the neutral columns instead of treating `firebase_custom_claims` as the live store.
- Shared auth/session/cache helpers (`auth_user_adapter.py`, `auth_session_cache.py`, `user_cache_shared.py`) now emit canonical runtime payload fields from canonical storage first, with legacy fallback for older fakes/fixtures.
- `FirebaseUserSyncService` was updated so new syncs/linking/update flows keep the canonical columns fresh instead of only mutating legacy Firebase-named fields.

Added the focused proof file `tests/api/v2/test_canonical_user_profile_contracts.py` with named `canonical_profile` / `canonical_preferences` assertions covering `/api/v2/users/me`, preferences persistence, auth/session user payload serialization, and physician detail serialization.

Per the auto-mode first-task requirement, also created `tests/migrations/test_canonical_schema_head_convergence.py`. It is still an explicit named pending failure for T02 (`canonical_head surface=head_convergence pending_t02_alignment=true`) so the slice verifier fails honestly instead of erroring on a missing file.

To keep the focused API proof runnable against the shared Postgres test harness, `tests/conftest.py` now patches Postgres test schemas with the new canonical `users` columns when they are missing, similar to the existing session/audit guards.

## Verification

Passed task-level verification:

- `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_shared_canonical_identity.py -k canonical_identity`

Also updated the slice plan verification to include a direct diagnostic replay step:

- `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py -k 'canonical_profile or canonical_preferences'`

Not fully rerun in this recovery pass:

- The combined slice migration pack still remains intentionally incomplete because `tests/migrations/test_canonical_schema_head_convergence.py` is only a named T02 placeholder at this point.
- A combined rerun of the wider slice commands was interrupted by queued recovery messages after the task-level checks had already passed.

## Diagnostics

Fastest inspection surfaces for what shipped here:

- `backend-hormonia/tests/api/v2/test_canonical_user_profile_contracts.py` — authoritative proof for `users_me`, preferences persistence, auth user payload serialization, and physician detail naming.
- `backend-hormonia/app/models/user.py` — canonical-first getters/setters and legacy mirroring behavior.
- `backend-hormonia/app/api/v2/routers/users.py`
- `backend-hormonia/app/api/v2/routers/auth.py`
- `backend-hormonia/app/api/v2/routers/physicians/crud.py`
- `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py` — explicit pending named failure for T02 instead of a missing-file error.

## Deviations

- Created `tests/migrations/test_canonical_schema_head_convergence.py` early as an explicit named pending failure, even though the full convergence proof belongs to T02. This was necessary so the slice verifier would fail honestly and durably instead of on file collection.
- Updated shared auth/cache helpers and `FirebaseUserSyncService` in addition to the task’s listed router/model files because leaving those writers/serializers on `firebase_*` storage would have made the new canonical columns stale immediately.

## Known Issues

- `tests/migrations/test_canonical_schema_head_convergence.py` is still a deliberate T02 placeholder failure: `canonical_head surface=head_convergence pending_t02_alignment=true`.
- Full slice-level migration verification was not completed in this recovery pass after the last queued recovery interruption; T02 should rerun the migration pack after replacing the placeholder convergence proof.

## Files Created/Modified

- `backend-hormonia/alembic/versions/m005_s03_t01_republish_users_canonical_contract.py` — new linear revision adding/backfilling canonical `users` profile/settings columns.
- `backend-hormonia/app/models/user.py` — canonical profile/settings columns plus transition getters/setters and legacy mirroring helpers.
- `backend-hormonia/app/api/v2/routers/users.py` — `/users/me` and preferences now read/write canonical storage.
- `backend-hormonia/app/api/v2/routers/auth.py` — auth/session/profile serialization and writes now prefer canonical storage.
- `backend-hormonia/app/api/v2/routers/physicians/crud.py` — physician payloads renamed to canonical field names and canonical profile writes.
- `backend-hormonia/app/schemas/v2/auth.py` — auth user schema widened for neutral profile fields.
- `backend-hormonia/app/schemas/v2/physicians.py` — physician response schema renamed from `firebase_*` live fields to canonical names.
- `backend-hormonia/app/services/auth.py` — local login now stamps canonical `last_login` while mirroring legacy sign-in storage.
- `backend-hormonia/app/services/firebase_user_sync_service.py` — Firebase sync/link/update flows keep canonical columns current.
- `backend-hormonia/app/dependencies/auth_user_adapter.py` — canonical cache payload conversion prefers neutral columns with legacy fallback.
- `backend-hormonia/app/dependencies/auth_session_cache.py` — shared session-cache serialization now points to canonical profile fields.
- `backend-hormonia/app/api/v2/user_cache_shared.py` — canonical runtime user cache serialization updated.
- `backend-hormonia/app/api/v2/routers/admin/utils.py` — admin user serialization now prefers canonical `last_login`.
- `backend-hormonia/tests/api/v2/test_canonical_user_profile_contracts.py` — focused contract proof for canonical user/profile/preferences surfaces.
- `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py` — explicit named pending failure placeholder for T02.
- `backend-hormonia/tests/migrations/test_alembic_operability.py` — head expectation moved to the new T01 revision.
- `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py` — boundary tests now point at the current T01 head revision.
- `backend-hormonia/tests/api/v2/test_firebase_boundary_contracts.py` — physician boundary assertions renamed to canonical field names.
- `backend-hormonia/tests/conftest.py` — shared Postgres test schema guard now patches in the canonical `users` columns.
- `.gsd/milestones/M005/slices/S03/S03-PLAN.md` — added the missing diagnostic verification step and marked T01 complete.
- `.gsd/DECISIONS.md` — recorded the canonical-users dual-write transition decision.
- `.gsd/STATE.md` — moved next action to T02.
