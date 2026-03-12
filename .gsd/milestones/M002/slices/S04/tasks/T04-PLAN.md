---
estimated_steps: 5
estimated_files: 8
---

# T04: Replace remaining Firebase-only auth seams with first-party password and session behavior

**Slice:** S04 — Hard Cut Cleanup And Integrated Proof
**Milestone:** M002

## Description

Finish the functional hard cut by removing the last Firebase-auth behavior still reachable in staff auth: in-app password change, logout-all cache invalidation keyed to Firebase identity, Firebase verify/debug routes, and websocket Firebase fallback modes. The result must be a fully first-party staff-auth runtime with inspectable errors.

## Steps

1. Replace `/api/v2/auth/password` in `backend-hormonia/app/api/v2/routers/auth.py` with first-party current-password verification, shared password-strength validation, local password-hash update, `last_password_change` / `force_change_password` state updates, and full session revocation keyed to canonical `user_id`.
2. Update logout-all/session cache invalidation and any supporting auth service helpers so session revocation operates on canonical user identity rather than requiring `firebase_uid` on the happy path.
3. Remove or explicit-tombstone `/api/v2/auth/firebase/verify`, its middleware exemptions, Firebase-only debug token inspection, and websocket `auth_type="firebase"` / `auto` behavior so the shipped runtime keeps only the S03 session-first contract.
4. Rewire `frontend-hormonia/src/hooks/useSettings.ts` and `src/features/settings/sections/SecuritySettings.tsx` to the first-party password-change endpoint, preserving stable user-safe diagnostics and post-change logout/session revocation behavior.
5. Run the dedicated backend/frontend hard-cut proofs plus websocket/session auth regressions, fixing any remaining Firebase-only seam that surfaces.

## Must-Haves

- [ ] Staff password change works through first-party current-password verification and local credential update, not Firebase Admin SDK.
- [ ] Logout-all and related session invalidation use canonical user identity and revoke both DB and Redis-backed sessions.
- [ ] Firebase verify/debug/session websocket fallback seams are removed or explicit tombstones, not live compatibility entrypoints.
- [ ] Password/session failure paths expose stable, user-safe diagnostics without leaking secrets.

## Verification

- `cd backend-hormonia && pytest tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py tests/api/v2/test_auth_password_recovery.py -q`
- `cd frontend-hormonia && npx vitest run tests/integration/auth/hard-cut-cleanup-proof.test.tsx tests/unit/hooks/useSettings.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`

## Observability Impact

- Signals added/changed: Password-change, logout-all, and websocket-auth failures now flow through stable first-party auth diagnostics instead of Firebase-origin errors.
- How a future agent inspects this: Use the dedicated hard-cut cleanup pytest suite, frontend settings-hook tests, and websocket contract proof to localize regressions.
- Failure state exposed: Wrong current password, invalid/revoked session, and removed Firebase route access produce explicit status/error assertions rather than silent fallback behavior.

## Inputs

- `backend-hormonia/app/api/v2/routers/auth.py` — still contains Firebase verify, Firebase-based password change, and logout-all keyed to Firebase identity.
- `frontend-hormonia/src/hooks/useSettings.ts` / `frontend-hormonia/src/features/settings/sections/SecuritySettings.tsx` — still wired to the legacy password-change path.

## Expected Output

- Backend auth/router/websocket staff-auth seams are fully session-first, including password change and logout-all.
- Frontend settings security flow uses the new first-party password-change contract with safe diagnostics.
- The hard-cut cleanup proofs pass without any live Firebase-auth compatibility route in the staff-auth runtime.
