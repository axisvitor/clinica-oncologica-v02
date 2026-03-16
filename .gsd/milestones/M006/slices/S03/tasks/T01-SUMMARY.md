---
id: T01
parent: S03
milestone: M006
provides:
  - merge-marker-free test collection paths (backend + frontend)
  - dead SessionService/auth_legacy_firebase cluster removed
  - updated S01 residue allowlist (stale auth_legacy_firebase exclude removed)
key_files:
  - backend-hormonia/app/services/session_service.py (deleted)
  - backend-hormonia/app/dependencies/auth_legacy_firebase.py (deleted)
  - backend-hormonia/tests/unit/test_auth_dependency_module_split.py (deleted)
  - backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py (merge markers resolved)
  - backend-hormonia/tests/unit/services/test_auth_session_services_async.py (SessionService tests removed)
  - backend-hormonia/tests/integration/test_phase23_service_async_missinggreenlet.py (SessionService usage removed)
  - frontend-hormonia/tests/unit/types-validation.test.ts (merge markers resolved)
  - frontend-hormonia/tests/integration/admin-auth-flow.test.tsx (merge markers resolved)
  - frontend-hormonia/src/hooks/__tests__/usePatients.test.ts (merge markers resolved)
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json (stale exclude removed)
key_decisions:
  - Resolved all merge-marker conflicts keeping HEAD/S04 version (canonical cookie-first auth) over S02/S03 branches
  - Kept test_auth_dependency_override_contract.py (useful auth contract tests) — resolved conflicts rather than deleting
patterns_established:
  - none
observability_surfaces:
  - verify-runtime-residue.sh --check backend (S01 guard confirms no anchor drift after dead file removal)
  - verify-runtime-residue.sh --report backend (inspectable proof-only boundary state)
duration: 20m
verification_result: passed
completed_at: 2026-03-15
blocker_discovered: false
---

# T01: Stabilize proof surfaces and delete dead backend auth/session cluster

**Deleted dead SessionService + auth_legacy_firebase cluster and resolved all 5 merge-marker files in active test collection paths.**

## What Happened

1. Scanned for merge markers — found 5 files across backend and frontend test paths, plus `auth_legacy_firebase.py` itself.
2. Triaged each file:
   - **Deleted** `auth_legacy_firebase.py` (dead legacy Firebase bearer auth with 4 layers of merge conflicts).
   - **Deleted** `test_auth_dependency_module_split.py` (tests for auth_legacy_firebase consumers, full of merge conflicts).
   - **Fixed** `test_auth_dependency_override_contract.py` — resolved merge conflicts keeping HEAD version with `session_id` state setting and the `test_session_contract_sets_request_state_for_mapping_style_payloads` test.
   - **Fixed** `types-validation.test.ts` — resolved keeping canonical S04 type ownership (SharedApiResponse, TransportApiResponse).
   - **Fixed** `admin-auth-flow.test.tsx` — resolved keeping HEAD canonical router test (ProtectedRoute + AdminRoutes, not legacy AdminApp).
   - **Fixed** `usePatients.test.ts` — trivial trailing whitespace conflict.
3. Deleted `session_service.py` — confirmed zero runtime imports (only `SimpleSessionService` is wired via `service_provider.py`).
4. Cleaned `test_auth_session_services_async.py` — removed `SessionService` import and 2 dead tests, kept `FirebaseUserSyncService` tests.
5. Cleaned `test_phase23_service_async_missinggreenlet.py` — removed `SessionService` import, db setup, gather calls, and assertion.
6. Updated S01 residue allowlist — removed stale `auth_legacy_firebase.py` from firebase_uid category exclude list.

## Verification

- `rg -l '^<<<<<<<|^=======$|^>>>>>>>' backend-hormonia/tests frontend-hormonia/tests frontend-hormonia/src --glob '!**/node_modules/**' | wc -l` → **0** ✓
- `cd backend-hormonia && python3 -c "from app.service_provider import ServiceProvider; print('ok')"` → **ok** ✓
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend` → **RESULT: --check backend OK** ✓
- `! test -f backend-hormonia/app/services/session_service.py && ! test -f backend-hormonia/app/dependencies/auth_legacy_firebase.py` → **dead cluster removed** ✓
- `! test -f backend-hormonia/tests/unit/test_auth_dependency_module_split.py` → **split test deleted** ✓

### Slice-level checks (partial — T01 scope):
- ✅ `backend imports clean` — ServiceProvider import succeeds
- ✅ S01 guard green — `verify-runtime-residue.sh --check backend` OK
- ✅ Backend absence scan — `session_service.py` and `auth_legacy_firebase.py` confirmed deleted
- ⏳ Frontend build/typecheck — T02 scope (frontend bridges not yet deleted)
- ⏳ Import-boundaries vitest — T02 scope
- ⏳ Full absence scan (includes frontend bridges) — T02 scope
- ⏳ FIREBASE_SESSION_TTL_SECONDS grep — T03 scope
- ⏳ WHATSAPP_EVOLUTION_ grep — T03 scope
- ⏳ HISTORICAL-ARCHIVE.md — T04 scope

## Diagnostics

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` — shows proof-only anchor state post-cleanup.
- If a future import of `session_service` or `auth_legacy_firebase` is introduced, the missing module will fail at import time with a clear `ModuleNotFoundError`.

## Deviations

- Plan said to potentially delete `test_auth_dependency_override_contract.py` — instead resolved merge conflicts since it contains useful auth contract tests (admin override signatures, role dependency delegation, session contract state mapping) that are independent of the deleted modules.

## Known Issues

- None

## Files Created/Modified

- `backend-hormonia/app/services/session_service.py` — **deleted** (dead SessionService class)
- `backend-hormonia/app/dependencies/auth_legacy_firebase.py` — **deleted** (dead legacy Firebase bearer auth)
- `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` — **deleted** (dead auth_legacy_firebase test consumers)
- `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py` — resolved merge conflicts (kept HEAD)
- `backend-hormonia/tests/unit/services/test_auth_session_services_async.py` — removed SessionService import and 2 tests
- `backend-hormonia/tests/integration/test_phase23_service_async_missinggreenlet.py` — removed SessionService usage
- `frontend-hormonia/tests/unit/types-validation.test.ts` — resolved merge conflicts (kept HEAD/S04)
- `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx` — resolved merge conflicts (kept HEAD)
- `frontend-hormonia/src/hooks/__tests__/usePatients.test.ts` — resolved merge conflicts (kept HEAD)
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — removed stale auth_legacy_firebase exclude
- `.gsd/milestones/M006/slices/S03/S03-PLAN.md` — added diagnostic verification steps
- `.gsd/milestones/M006/slices/S03/tasks/T01-PLAN.md` — added Observability Impact section
