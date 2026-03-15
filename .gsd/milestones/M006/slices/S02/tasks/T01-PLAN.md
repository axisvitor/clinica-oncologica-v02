---
estimated_steps: 4
estimated_files: 10
---

# T01: Retire firebase-shaped auth/session identity fallback from the live runtime

**Slice:** S02 — Remover o resíduo de schema que ainda prende o runtime ao passado
**Milestone:** M006

## Description

Stop treating `firebase_uid` and Firebase-only session payloads as a valid live identity path before the schema drop. This task narrows the remaining auth/session seam so the migration can remove `users.firebase_uid` honestly instead of turning routine session restore into delayed breakage.

## Steps

1. Remove `firebase_uid` serialization, cache lookup, and DB fallback from the live auth/session helpers in `auth_session_cache`, `auth_session_contract`, and `auth_dependencies`, keeping only canonical `user_id` and session-table fallback behavior.
2. Delete or republish the admin-session fallback and any now-dead repository/helper usage that still loads `User` by `firebase_uid`, including the old repository shortcut if nothing live still calls it.
3. Update the focused auth/session regressions so malformed Firebase-only session payloads fail closed and timeout/fallback tests assert the canonical identity path.
4. Re-run the backend residue guard and the focused auth/session pack to prove the seam stayed honest.

## Must-Haves

- [ ] Firebase-only session payloads are rejected or recover only through session-table fallback, never through `User.firebase_uid` lookup.
- [ ] Focused auth/session tests and the S01 backend residue guard both reflect the canonical-only identity contract.

## Verification

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_uid_validation.py tests/api/v2/test_auth_timeout.py tests/integration/test_auth_fallback.py`

## Observability Impact

- Signals added/changed: focused auth/session assertions should name missing canonical identity, malformed session payloads, and fallback timeout behavior instead of `firebase_uid` compatibility.
- How a future agent inspects this: run the backend residue report plus the focused auth/session pack to see whether drift is in request resolution, Redis hydration, or DB fallback.
- Failure state exposed: firebase-only cache/session payloads and timeout paths fail with named assertions instead of silently succeeding through a hidden compatibility path.

## Inputs

- `backend-hormonia/app/dependencies/auth_dependencies.py` — S01 already hard-cut bearer/header transport but left `firebase_uid` proof-only seams for this slice to retire.
- `backend-hormonia/app/dependencies/auth_session_cache.py` — current live fallback/serialization seam that still keeps `users.firebase_uid` reachable.
- `backend-hormonia/app/repositories/user.py` — low-risk `get_by_firebase_uid()` seam that should disappear if no live caller remains.
- `.gsd/milestones/M006/slices/S01/S01-SUMMARY.md` — explains why the remaining backend `firebase_uid` mentions are proof-only debt to remove here, not approved runtime behavior.

## Expected Output

- `backend-hormonia/app/dependencies/auth_session_cache.py` — canonical-only session/cache identity helpers with no live `firebase_uid` fallback.
- `backend-hormonia/app/dependencies/auth_role_dependencies.py` — admin-session loader that resolves only via canonical IDs.
- `backend-hormonia/app/repositories/user.py` — repository surface without a live `get_by_firebase_uid()` shortcut.
- `backend-hormonia/tests/integration/test_auth_fallback.py` — republished fallback proof around canonical session identity rather than Firebase-UID compatibility.
