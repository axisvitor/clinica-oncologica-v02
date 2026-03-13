---
id: T04
parent: S03
milestone: M003
provides:
  - Closed the live compat-barrel seam by keeping `usePatients.ts` on the canonical type surface, refreshing the hook/type/admin proof around that boundary, and clearing the remaining slice-close proof gates (`api-client` integration drift, websocket TS4111 errors, build/typecheck, and evidence-map anchors).
key_files:
  - frontend-hormonia/src/hooks/__tests__/usePatients.test.ts
  - frontend-hormonia/tests/unit/types-validation.test.ts
  - frontend-hormonia/tests/integration/api-client.test.ts
  - frontend-hormonia/tests/integration/admin-auth-flow.test.tsx
  - frontend-hormonia/src/hooks/useWebSocket.ts
  - frontend-hormonia/src/lib/websocket.ts
  - frontend-hormonia/src/lib/types/api.ts
  - .gsd/milestones/M003/slices/S01/S01-RESEARCH.md
key_decisions:
  - Admin auth integration proof now targets the shipped session-first `AuthProvider` + `apiClient.auth.*` contract instead of the retired Firebase login path.
patterns_established:
  - When a structural refactor closes on a compatibility seam, keep the legacy barrel explicitly marked compat-only, move live callers/tests to canonical façades, and align integration proof to the current runtime contract rather than preserving stale legacy expectations.
observability_surfaces:
  - Structural Vitest contracts, focused auth/session/realtime/admin/dashboard/hook/type suites, `npm run typecheck`, `npm run build`, the shrink Python check, and `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check frontend`.
duration: 50m
verification_result: passed
completed_at: 2026-03-13T00:51:54-03:00
blocker_discovered: false
---

# T04: Migrate the remaining compat caller and close the focused frontend proof gate

**Closed the remaining frontend compat seam, refreshed the stale proof suites to the session-first runtime contract, and finished S03 with a fully green slice verification pack.**

## What Happened

`frontend-hormonia/src/hooks/usePatients.ts` was already on the canonical `@/types/api` surface from T03, so I treated T04 as a proof-and-isolation closeout instead of redoing the migration. I strengthened the seam around that move by updating `src/hooks/__tests__/usePatients.test.ts` to assert the canonical import directly and by refactoring `tests/unit/types-validation.test.ts` so canonical app/transport/websocket types come from `src/types/api`, `src/lib/api-client/types`, and `src/types/websocket`, while the remaining `src/lib/types/api.ts` residue is exercised only as an explicit legacy compatibility layer.

I isolated the compat barrel itself by rewriting the `frontend-hormonia/src/lib/types/api.ts` header as a deprecated S04-only compatibility surface: new production code should use `@/types/api`, `@/lib/api-client/types`, or `@/types/websocket`, and the file now documents that it remains only for cleanup/tombstoning in S04.

To close the red slice gates that were still open after T03, I fixed the websocket TS4111 bracket-notation errors in `src/hooks/useWebSocket.ts` and `src/lib/websocket.ts`, rewrote `tests/integration/api-client.test.ts` to match the actual modular client contract (base URL without duplicated `/api/v2`, seeded CSRF for state-changing requests, current auth/logout/session endpoint behavior, and current flow/message payload shapes), and replaced the stale Firebase-based `tests/integration/admin-auth-flow.test.tsx` with a session-first admin route/auth-provider integration suite that exercises the shipped `/admin` flow through `AuthProvider` + `apiClient.auth.*` mocks.

Finally, I refreshed the stale frontend anchor metrics in `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` so the evidence-map verifier reflects filesystem truth after the S03 split (`index.ts`=223 lines, `types.ts`=26 lines, no duplicate exports, no remaining live `lib/types/api` imports).

## Verification

Passed:
- `cd frontend-hormonia && npm run test -- tests/lib/api-client/index-split.contract.test.ts tests/unit/types/api-client-types-barrel.contract.test.ts tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts`
- `cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts`
- `cd frontend-hormonia && npm run test -- tests/integration/auth/session-first-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx`
- `cd frontend-hormonia && npm run test -- tests/integration/admin-auth-flow.test.tsx tests/components/dashboard/QuickStats.test.tsx`
- `cd frontend-hormonia && npm run test -- src/hooks/__tests__/usePatients.test.ts tests/unit/types-validation.test.ts`
- `cd frontend-hormonia && npm run typecheck && npm run build`
- `cd frontend-hormonia && python3 - <<'PY' ...` (shrink check)
  - confirmed `src/lib/api-client/index.ts` = 223 lines
  - confirmed `src/lib/api-client/types.ts` = 26 lines
  - confirmed `src/hooks/usePatients.ts` no longer references `lib/types/api`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check frontend`

## Diagnostics

- Canonical compat-import drift is inspectable with:
  - `frontend-hormonia/tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts`
  - `frontend-hormonia/src/hooks/__tests__/usePatients.test.ts`
  - `frontend-hormonia/tests/unit/types-validation.test.ts`
- Session-first admin/auth/client behavior is inspectable with:
  - `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx`
  - `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx`
  - `frontend-hormonia/tests/integration/api-client.test.ts`
- Structural shrink/evidence proof is inspectable with:
  - the Python seam check in the slice plan
  - `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check frontend`
- The compat barrel isolation note now lives at the top of `frontend-hormonia/src/lib/types/api.ts`.

## Deviations

- None.

## Known Issues

- None.

## Files Created/Modified

- `frontend-hormonia/src/hooks/__tests__/usePatients.test.ts` — added a direct canonical-import assertion alongside the existing hook behavior checks.
- `frontend-hormonia/tests/unit/types-validation.test.ts` — moved validation coverage onto canonical app/transport/websocket type surfaces and isolated the legacy compat wrappers.
- `frontend-hormonia/src/lib/types/api.ts` — marked the legacy barrel as compat-only S04 cleanup residue.
- `frontend-hormonia/tests/integration/api-client.test.ts` — aligned the integration proof with the current modular client/runtime contract and seeded-CSRF request behavior.
- `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx` — replaced the stale Firebase-era admin auth spec with a session-first admin route/auth-provider integration suite.
- `frontend-hormonia/src/hooks/useWebSocket.ts` — fixed TS4111 index-signature access for websocket auth diagnostics.
- `frontend-hormonia/src/lib/websocket.ts` — fixed TS4111 index-signature access for websocket auth diagnostics.
- `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` — refreshed frontend verifier-anchor metrics so the evidence-map contract matches the refactored hotspot sizes and ownership counts.
