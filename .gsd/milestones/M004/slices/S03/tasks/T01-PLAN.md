---
estimated_steps: 5
estimated_files: 5
---

# T01: Freeze routed frontend proof for the canonical session-first contract

**Slice:** S03 — Frontend oficial convergido para contrato session-first canônico
**Milestone:** M004

## Description

Pin the real frontend contract before changing behavior. The current focused packs are useful, but they still miss the shipped `/admin/*` route tree and still tolerate legacy transport behavior. This task makes the missing boundary executable so the rest of S03 has to close real drift instead of preserving already-green but incomplete proof.

## Steps

1. Update `frontend-hormonia/tests/unit/api-client/auth-headers.test.ts` and `frontend-hormonia/tests/lib/api-client/core.test.ts` so the shared HTTP client proof asserts cookie-first requests without `Authorization` or `X-Session-ID` emission.
2. Extend `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx` to prove login, restore, and logout through `AuthProvider` without persisting or rehydrating `localStorage.session_id`.
3. Rework `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx` to exercise the shipped router and protected `/admin/*` path through canonical `/login`, rather than proving only a standalone `AdminApp` mount.
4. Tighten `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts` so websocket bootstrap explicitly rejects `?session_id=` fallback while preserving the existing auth diagnostics.
5. Run the focused pack red-first and confirm the first failures point at current transport/query/localStorage/admin-route gaps instead of fixture or mock instability.

## Must-Haves

- [ ] The focused proof names the canonical contract explicitly: cookie-backed session restore plus no legacy header/query/session-storage fallback on the official frontend path.
- [ ] The shipped `/admin/*` route tree is exercised through the real router and canonical `/login` entrypoint.
- [ ] The initial failures are attributable to current frontend contract drift, not unrelated environment noise.
- [ ] No assertions expose raw cookies, session tokens, passwords, or other secret-bearing values.

## Verification

- `cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`

## Observability Impact

- Signals added/changed: targeted failures now isolate HTTP header leakage, browser-storage leakage, websocket query-fallback leakage, and routed admin-entry drift.
- How a future agent inspects this: run the focused Vitest files directly to see whether drift lives in the shared client, `AuthProvider`, realtime bootstrap, or the real `/admin/*` route tree.
- Failure state exposed: test names and assertions should make it obvious whether the regression is transport leakage, missing router coverage, or stale session bootstrap assumptions.

## Inputs

- `.gsd/milestones/M004/slices/S03/S03-RESEARCH.md` — defines the shared-seam cut, the routed admin caveat, and the frontend residue hotspots.
- `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md` — current frontend residue categories and the requirement to update them intentionally when the boundary shrinks.
- `.gsd/milestones/M004/slices/S02/S02-SUMMARY.md` — backend canonical identity contract that the frontend proof should consume rather than redesign.
- `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx` — current focused auth proof baseline for the official frontend loop.

## Expected Output

- `frontend-hormonia/tests/unit/api-client/auth-headers.test.ts` — explicit proof that the shared client no longer accepts legacy auth/session header behavior as canonical.
- `frontend-hormonia/tests/lib/api-client/core.test.ts` — focused core-request proof that guards against `Authorization` / `X-Session-ID` regressions.
- `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx` — routed session-first auth proof that no longer tolerates `localStorage.session_id` behavior.
- `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx` — admin proof anchored on the shipped router and canonical login entrypoint.
- `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts` — realtime proof that rejects websocket `session_id` query fallback.
