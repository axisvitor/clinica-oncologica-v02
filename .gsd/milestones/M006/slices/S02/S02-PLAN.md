# S02: Remover o resíduo de schema que ainda prende o runtime ao passado

**Goal:** Advance R052 by removing the remaining Firebase-era `users` schema/runtime residue that still behaves as live state, without widening this slice into `auth_provider` cleanup.
**Demo:** The post-S02 head no longer carries the Firebase-prefixed `users` columns or `ix_users_firebase_uid`, and the canonical auth/profile/admin/physician runtime surfaces still pass on that head through the published fresh/existing final-schema proof.

## Must-Haves

- Auth/session resolution, admin session loading, and the `User` helper layer stop depending on `users.firebase_uid` or `users.firebase_*` as active runtime state.
- Official profile/admin/physician surfaces and shared fixtures write/read only the canonical `users` fields that survive the cut, with focused proof for session fallback, physician search/detail, and admin/user stats.
- A new Alembic head drops `users.firebase_uid`, `firebase_last_sign_in`, `firebase_created_at`, `firebase_email_verified`, `firebase_display_name`, `firebase_photo_url`, `firebase_custom_claims`, `last_firebase_sync`, and `ix_users_firebase_uid`, while preserving `auth_provider` and `firebase_sync_history` as the explicit live/historical boundaries.

## Proof Level

- This slice proves: integration
- Real runtime required: yes
- Human/UAT required: no

## Verification

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_uid_validation.py tests/api/v2/test_auth_timeout.py tests/integration/test_auth_fallback.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_timeout.py -k "db_timeout_returns_504 or db_timeout_logs_error"`
- `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/api/v2/test_physicians_crud_regression.py tests/api/v2/test_admin.py tests/unit/services/test_admin_stats_service.py`
- `cd backend-hormonia && pytest -q tests/migrations/test_canonical_schema_head_convergence.py`
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh`
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --existing`

## Observability / Diagnostics

- Runtime signals: `run-final-schema-proof.sh` phase/status JSON, canonical-head fingerprint diffs, and stable auth/session failure assertions for malformed session payloads and fallback timeouts.
- Inspection surfaces: `/tmp/gsd-m005-s04-final-schema-proof/*/status.json`, `tests/migrations/test_canonical_schema_head_convergence.py` diff output, and `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`.
- Failure visibility: schema drift is localized as `canonical_head` fingerprint deltas; runtime regressions are localized as focused auth/session/profile/admin assertion failures; mounted proof failures keep per-phase log pointers.
- Redaction constraints: mounted-proof artifacts must stay on the masked helper path; no secrets or raw session credentials belong in logs, fixtures, or status files.

## Integration Closure

- Upstream surfaces consumed: S01 cookie-only auth/session contract, `backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/api/v2/user_cache_shared.py`, `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py`, and `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh`.
- New wiring introduced in this slice: a new Alembic head after `m005_s03_t02_align_audit_history_head`, plus final-schema replay that includes the focused S02 runtime packs on the post-drop schema before mounted backend proof.
- What remains before the milestone is truly usable end-to-end: S03 still needs to purge repo-wide bridges/tombstones/docs/workflows, and S04 still needs to publish the combined absence pack and replay the full post-purge closeout.

## Tasks

- [x] **T01: Retire firebase-shaped auth/session identity fallback from the live runtime** `est:1h15m`
  - Why: The schema drop is dishonest until the live auth/session resolver and admin-session loader stop treating `firebase_uid` as an accepted identity path.
  - Files: `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/dependencies/auth_session_contract.py`, `backend-hormonia/app/dependencies/auth_session_cache.py`, `backend-hormonia/app/dependencies/auth_role_dependencies.py`, `backend-hormonia/app/repositories/user.py`, `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py`, `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py`, `backend-hormonia/tests/api/v2/test_auth_uid_validation.py`, `backend-hormonia/tests/api/v2/test_auth_timeout.py`, `backend-hormonia/tests/integration/test_auth_fallback.py`
  - Do: Remove `firebase_uid` serialization/cache/DB fallback from the live session resolver, admin-session loader, and related compatibility tests; keep only canonical `user_id` plus session-table fallback behavior, and republish the S01 residue boundary instead of silently relying on proof-only leftovers.
  - Verify: `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend && cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_uid_validation.py tests/api/v2/test_auth_timeout.py tests/integration/test_auth_fallback.py`
  - Done when: Firebase-only session payloads no longer authenticate or load admins, and the focused auth/session pack plus backend residue guard are green.
- [x] **T02: Republish canonical user/profile/admin/physician surfaces and fixtures** `est:1h15m`
  - Why: Even after T01, the runtime and harness can still repopulate or read the doomed `users.firebase_*` columns through helper defaults, physician search/update code, admin serializers, and shared fixtures.
  - Files: `backend-hormonia/app/models/user.py`, `backend-hormonia/app/api/v2/routers/physicians/crud.py`, `backend-hormonia/app/api/v2/routers/admin/utils.py`, `backend-hormonia/app/services/analytics/admin_stats_service.py`, `backend-hormonia/tests/api/v2/test_canonical_user_profile_contracts.py`, `backend-hormonia/tests/api/v2/test_physicians_crud_regression.py`, `backend-hormonia/tests/api/v2/test_admin.py`, `backend-hormonia/tests/unit/services/test_admin_stats_service.py`, `backend-hormonia/tests/api/v2/conftest.py`, `backend-hormonia/tests/conftest.py`
  - Do: Flip the `User` helper contract to canonical-only for the fields slated to survive, remove direct `firebase_*` reads/writes from physician/admin/runtime helpers, choose the canonical activity signal for stats, and republish shared fixtures so focused API proof no longer depends on Firebase-era mirrors.
  - Verify: `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/api/v2/test_physicians_crud_regression.py tests/api/v2/test_admin.py tests/unit/services/test_admin_stats_service.py`
  - Done when: The surviving user/profile/admin/physician surfaces and fixtures read/write only canonical `users` fields, and the focused API pack passes without the soon-to-be-dropped columns.
- [x] **T03: Drop the remaining Firebase-named `users` columns and replay the final-schema pack** `est:1h30m`
  - Why: The slice only lands when the runtime from T01/T02 runs on a head that actually no longer contains the Firebase-prefixed `users` residue.
  - Files: `backend-hormonia/alembic/versions/<new_s02_drop_users_firebase_residue>.py`, `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py`, `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh`
  - Do: Add a new revision after `m005_s03_t02_align_audit_history_head` that drops the Firebase-prefixed `users` columns and `ix_users_firebase_uid` while keeping `auth_provider` and `firebase_sync_history`; update the convergence fingerprint and the published final-schema runner so both fresh and existing histories replay the focused S02 runtime packs before mounted backend proof.
  - Verify: `cd backend-hormonia && pytest -q tests/migrations/test_canonical_schema_head_convergence.py && bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh && bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --existing`
  - Done when: Both replay histories converge on a head without the Firebase-prefixed `users` residue, and the mounted backend/auth replay stays green on that head.

## Files Likely Touched

- `backend-hormonia/app/dependencies/auth_dependencies.py`
- `backend-hormonia/app/dependencies/auth_session_contract.py`
- `backend-hormonia/app/dependencies/auth_session_cache.py`
- `backend-hormonia/app/dependencies/auth_role_dependencies.py`
- `backend-hormonia/app/repositories/user.py`
- `backend-hormonia/app/models/user.py`
- `backend-hormonia/app/api/v2/routers/physicians/crud.py`
- `backend-hormonia/app/api/v2/routers/admin/utils.py`
- `backend-hormonia/app/services/analytics/admin_stats_service.py`
- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py`
- `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py`
- `backend-hormonia/tests/api/v2/test_canonical_user_profile_contracts.py`
- `backend-hormonia/tests/unit/services/test_admin_stats_service.py`
- `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py`
- `backend-hormonia/alembic/versions/<new_s02_drop_users_firebase_residue>.py`
- `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh`
