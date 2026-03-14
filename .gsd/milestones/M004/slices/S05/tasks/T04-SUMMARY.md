---
id: T04
parent: S05
milestone: M004
provides:
  - Adjacent frontend user/RBAC/medico type surfaces now describe the canonical session-first runtime without `firebase_uid` or a live Firebase auth-provider enum, and focused type proof catches regressions at the barrel/type boundary.
key_files:
  - frontend-hormonia/src/types/api.ts
  - frontend-hormonia/src/types/rbac.ts
  - frontend-hormonia/src/types/medico.ts
  - frontend-hormonia/src/types/admin.ts
  - frontend-hormonia/src/lib/api-client/__tests__/normalizers.test.ts
  - frontend-hormonia/tests/unit/types/admin-types.test.ts
  - frontend-hormonia/tests/unit/types/type-consistency.test.ts
key_decisions:
  - Remove the dead auth-provider enum from the frontend RBAC/admin barrels entirely instead of narrowing it to a compatibility-only `LOCAL` value, so stale imports fail immediately instead of preserving the wrong runtime story.
patterns_established:
  - Canonical frontend auth/user types stay session-first and omit Firebase-shaped fields from the official `User` contract; focused proof uses type-key assertions plus runtime property checks to pin that boundary.
  - Adjacent medico validation helpers describe generic session/user context instead of Firebase claims while still tolerating legacy `'medico'` role labels at the compatibility edge.
observability_surfaces:
  - `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts`
  - `cd frontend-hormonia && npm run build`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all` / `--check all`
duration: 24m
verification_result: passed
completed_at: 2026-03-14T18:19:33-03:00
blocker_discovered: false
---

# T04: Remove Firebase-shaped adjacent frontend type residue

**The adjacent frontend auth type surface now stays on the canonical session-first contract, with Firebase-shaped user/provider residue removed from shared barrels and pinned by focused type proof.**

## What Happened

I cleaned the three adjacent frontend type surfaces named in the task plan and one shared barrel that still re-exported the old provider story.

- `frontend-hormonia/src/types/api.ts`
  - removed `firebase_uid` from the canonical `User` interface
  - rewrote the type comment to describe the session-first runtime instead of a generic auth story
  - kept `session_id` / optional token compatibility fields that the current app still consumes
- `frontend-hormonia/src/types/rbac.ts`
  - removed the unused `AuthProvider` enum entirely, including `AuthProvider.FIREBASE`
  - rewrote the file header so the module describes the permission/role contract actually consumed by the app
- `frontend-hormonia/src/types/medico.ts`
  - rewrote `MedicoRoleValidation` away from Firebase-claims terminology
  - renamed the payload field from `claims` to `context` and documented it as generic session/user validation context
  - kept legacy `'medico'` as a tolerated role label in the helper type so compatibility callers can still describe legacy input without teaching Firebase as the official contract
- `frontend-hormonia/src/types/admin.ts`
  - removed the stale `AuthProvider` re-export from the admin barrel so the dead provider surface does not survive through an adjacent import path

I also extended the focused proof pack so drift fails where it starts:

- `src/lib/api-client/__tests__/normalizers.test.ts` now pins both the runtime absence of `firebase_uid` after normalization and the compile-time absence of `firebase_uid` from the normalized frontend user key set
- `tests/unit/types/admin-types.test.ts` now asserts that neither `@/types/rbac` nor `@/types/admin` exports `AuthProvider`
- `tests/unit/types/type-consistency.test.ts` now adds type-key checks for the canonical `User` surface and the renamed medico validation context so Firebase-shaped field drift fails at the type boundary

## Verification

Task-level verification passed:

- `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts`
- `cd frontend-hormonia && npm run build`

Slice-level verification status after T04:

- ✅ `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py`
- ✅ `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py`
- ✅ `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py`
- ✅ `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts`
- ✅ `cd frontend-hormonia && npm run build`
- ✅ `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all` — report shows `frontend` has no approved residue
- ❌ `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` — failing on the expected stale allowlist anchors/moved-hotspot drift that T05 owns (`auth_session_shared.py`, `routers/auth.py`, `user_cache_shared.py`, `session_cache.py`, `auth_user_adapter.py`)

## Diagnostics

For future inspection:

- rerun `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts`
  - `normalizers.test.ts` failure => normalized frontend user shape or key-level Firebase residue regressed
  - `admin-types.test.ts` failure => the dead RBAC/admin provider enum was re-exported or resurrected
  - `type-consistency.test.ts` failure => canonical `User` or medico validation helper keys drifted back toward Firebase-shaped naming
- rerun `cd frontend-hormonia && npm run build`
  - build failure => a stale import still expects `AuthProvider` or another widened adjacent type surface
- rerun `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
  - confirms the current residue inventory before T05 republishes the approved hotspot list

## Deviations

- Updated `frontend-hormonia/src/types/admin.ts` even though it was not called out in the expected-output list, because the admin barrel still re-exported the removed `AuthProvider` surface and would have kept the provider-era contract alive through a parallel import path.
- Added the required `## Observability Impact` section to `.gsd/milestones/M004/slices/S05/tasks/T04-PLAN.md` before implementation, per the unit pre-flight instruction.

## Known Issues

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` is still red on stale allowlist/moved-hotspot bookkeeping; T05 owns republishing the post-S05 residue boundary.

## Files Created/Modified

- `frontend-hormonia/src/types/api.ts` — removed `firebase_uid` from the canonical frontend `User` surface and clarified the session-first contract.
- `frontend-hormonia/src/types/rbac.ts` — removed the dead `AuthProvider` enum and provider-era narrative from the RBAC barrel.
- `frontend-hormonia/src/types/medico.ts` — replaced Firebase-claims wording with generic session/user validation context.
- `frontend-hormonia/src/types/admin.ts` — removed the stale `AuthProvider` re-export from the shared admin barrel.
- `frontend-hormonia/src/lib/api-client/__tests__/normalizers.test.ts` — pinned normalized user key absence for `firebase_uid`.
- `frontend-hormonia/tests/unit/types/admin-types.test.ts` — added barrel-export proof that `AuthProvider` is gone from the RBAC/admin surface.
- `frontend-hormonia/tests/unit/types/type-consistency.test.ts` — added canonical `User` and medico validation key checks for the narrowed frontend contract.
- `.gsd/milestones/M004/slices/S05/tasks/T04-PLAN.md` — added the missing observability-impact section required by the unit pre-flight.
- `.gsd/DECISIONS.md` — recorded the decision to delete dead provider enums from adjacent frontend barrels instead of preserving a compatibility shim.
