# S03: Frontend oficial convergido para contrato session-first canônico — UAT

**Milestone:** M004
**Written:** 2026-03-14

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S03 closes on focused proof, build, and residue-guard agreement rather than a mounted end-to-end environment. The slice proves the official frontend contract directly at the seam level and publishes the remaining backend-owned legacy explicitly.

## Preconditions

- Run from the repository root: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1`.
- Frontend dependencies are installed.
- The working tree includes the updated S01 handoff artifacts and `runtime-residue-allowlist.json`.
- No local edits are reintroducing frontend auth/session transport residue.

## Smoke Test

1. Run `cd frontend-hormonia && npx vitest run tests/integration/admin-auth-flow.test.tsx`.
2. **Expected:** All 3 tests pass. `/admin/login` redirects to canonical `/login`, successful login returns to `/admin/system/compensation`, and an already-authenticated admin restores directly into `/admin/templates`.

## Test Cases

### 1. Shared auth/client cutover

1. Run `cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx`.
2. **Expected:** All tests pass. Official shared requests stay cookie-backed, `Authorization` / `X-Session-ID` stay absent, and `AuthProvider` does not persist or rehydrate `localStorage.session_id`.

### 2. Routed admin proof through canonical `/login`

1. Run `cd frontend-hormonia && npx vitest run tests/integration/admin-auth-flow.test.tsx`.
2. **Expected:** All 3 tests pass. The proof exercises the shipped protected `/admin/*` tree rather than a standalone admin shell.

### 3. Realtime cutover plus stable diagnostics

1. Run `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts tests/unit/hooks/useWebSocket.test.ts tests/unit/hooks/useWebSocket.comprehensive.test.ts`.
2. Run `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts -t "pins stable invalid-session diagnostics on the frontend websocket auth path"`.
3. **Expected:** All tests pass. No official websocket bootstrap path emits `?session_id=`, and stable auth diagnostics such as `AUTH_WEBSOCKET_SESSION_INVALID` remain visible.

### 4. Type/narrative/build closeout

1. Run `cd frontend-hormonia && npx vitest run tests/unit/hooks/useSessionManagement.test.ts tests/unit/types/admin-types.test.ts tests/lib/api-client/__tests__/normalizers.test.ts src/utils/__tests__/init-validator.test.ts`.
2. Run `cd frontend-hormonia && npm run build`.
3. **Expected:** The tests and build pass. Canonical frontend/shared admin types no longer carry Firebase-shaped baggage on the official path, and the build stays green after the narrative/type cleanup.

### 5. Residue boundary closeout

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend`.
2. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`.
3. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`.
4. **Expected:** `frontend` prints `no approved residue`; `report all` shows only backend-owned approved residue categories; the check commands end with `OK`.

## Edge Cases

### Routed nested admin children still render under the shell

1. Run `cd frontend-hormonia && npx vitest run tests/integration/admin-auth-flow.test.tsx`.
2. **Expected:** The assertions for `Compensation failures mock` and `Template management mock` pass, which proves the routed admin shell still exposes nested content.

### Frontend residue reintroduction guard

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend` after any future frontend auth/session refactor.
2. **Expected:** The command stays green. Any new frontend hit in `firebase_uid`, `x_session_id`, `session_bearer_fallback`, `websocket_session_id_query`, or `firebase_narrative` should fail immediately.

## Failure Signals

- `tests/integration/admin-auth-flow.test.tsx` passes route transitions but never renders the nested admin child content.
- `tests/unit/api-client/auth-headers.test.ts` or `tests/lib/api-client/core.test.ts` detect `Authorization` or `X-Session-ID` on official requests.
- `tests/integration/auth/session-first-cutover.test.tsx` finds `localStorage.session_id` rehydration or persistence.
- `tests/integration/realtime/session-websocket-cutover.test.ts` finds `?session_id=` in websocket URLs or loses the stable websocket auth error codes.
- `npm run build` fails with type drift in the cleaned admin/shared canonical surfaces.
- `verify-runtime-residue.sh --report frontend` lists approved residue instead of `no approved residue`.

## Requirements Proved By This UAT

- R050 — The official frontend uses only the canonical session-first contract on the happy path and no longer carries approved runtime residue in the scoped guard.
- R047 — The official frontend no longer treats Firebase-era narrative/type baggage as live runtime contract.
- R048 — The frontend side of auth/session now converges on the canonical contract while the remaining backend-owned legacy is named explicitly.

## Not Proven By This UAT

- This UAT does not retire backend acceptance of `root_legacy_session`, `x_session_id`, `session_bearer_fallback`, `websocket_session_id_query`, or backend `firebase_narrative`; S04 still owns that work.
- This UAT does not remove the remaining backend/adjacent `firebase_uid` compatibility residue; S05 still owns that work.
- This UAT does not prove the fully assembled no-Firebase stack on a mounted environment; S06 still owns that proof.

## Notes for Tester

- A green result here means the official frontend path is clean and the residue handoff is honest. It does **not** mean the milestone is fully complete.
- If the residue report changes, update the S01 allowlist and the S01/S03 handoff artifacts in the same change; a green verifier with stale docs is still drift.
- The routed admin proof is intentionally narrow and valuable. If it fails by showing only the admin shell, check whether the route shell still renders nested children before changing runtime code.
