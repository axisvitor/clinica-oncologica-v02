---
estimated_steps: 5
estimated_files: 8
---

# T04: Clean official auth/admin narrative and canonical type surfaces

**Slice:** S03 — Frontend oficial convergido para contrato session-first canônico
**Milestone:** M004

## Description

Close the non-transport half of R050. After the HTTP and websocket cuts, the shipped frontend still needs to stop describing Firebase as live behavior and stop carrying Firebase-shaped canonical admin/user contracts. This task cleans the official auth/admin narrative plus the canonical type/normalizer surfaces that would otherwise keep Firebase semantics alive in the frontend story.

## Steps

1. Rewrite the Firebase-era comments, copy, and operational wording in `frontend-hormonia/src/AdminApp.tsx`, `frontend-hormonia/src/features/admin/AdminSessionManager.tsx`, and `frontend-hormonia/src/hooks/auth/useSessionManagement.ts` so they describe backend cookies + verify-session/session restore.
2. Update `frontend-hormonia/src/utils/init-validator.ts` so its readiness/auth narrative matches the session-first runtime rather than a Firebase-shaped expectation.
3. Remove `firebase_uid` and Firebase-auth baggage from `frontend-hormonia/src/types/admin.ts`, `frontend-hormonia/shared-types/src/admin.ts`, `frontend-hormonia/src/lib/api-client/admin.ts`, and `frontend-hormonia/src/lib/api-client/normalizers.ts` where the official runtime no longer reads those fields.
4. Update the coupled tests (`frontend-hormonia/tests/unit/types/admin-types.test.ts`, `frontend-hormonia/tests/lib/api-client/__tests__/normalizers.test.ts`, `frontend-hormonia/tests/unit/hooks/useSessionManagement.test.ts`, `frontend-hormonia/src/utils/__tests__/init-validator.test.ts`) so they assert the canonical narrative and type contract.
5. Run the focused admin/type pack plus `npm run build`, and touch `src/app/routes/AdminRoutes.lazy.tsx` only if the canonical build/test path forces a minimal cleanup rather than as speculative residue chasing.

## Must-Haves

- [ ] Official auth/admin comments and runtime copy no longer describe Firebase as part of the live frontend contract.
- [ ] Canonical admin/user type surfaces no longer require `firebase_uid` or Firebase-auth fields where the official runtime does not read them.
- [ ] Init/session readiness messaging reflects backend-owned session auth, not Firebase config presence.
- [ ] The focused admin/type tests and the frontend build stay green.

## Verification

- `cd frontend-hormonia && npx vitest run tests/integration/admin-auth-flow.test.tsx tests/unit/types/admin-types.test.ts tests/lib/api-client/__tests__/normalizers.test.ts tests/unit/hooks/useSessionManagement.test.ts src/utils/__tests__/init-validator.test.ts && npm run build`

## Observability Impact

- Signals added/changed: auth/session readiness messaging and admin session narrative now describe the real backend-owned contract, keeping failure/debug copy aligned with runtime behavior.
- How a future agent inspects this: rerun the focused admin/type Vitest pack and `npm run build` to localize drift to copy/readiness surfaces versus canonical type/normalizer shape.
- Failure state exposed: regressions show up as stale Firebase-era wording, type drift, or build failures instead of silently surviving as narrative baggage.

## Inputs

- `.gsd/milestones/M004/slices/S03/tasks/T02-PLAN.md` — HTTP/session-storage contract already cut at the shared client seams.
- `.gsd/milestones/M004/slices/S03/tasks/T03-PLAN.md` — realtime transport contract already aligned to cookie-first semantics.
- `.gsd/milestones/M004/slices/S03/S03-RESEARCH.md` — lists the official narrative and type hotspots that still carry Firebase-era semantics.

## Expected Output

- `frontend-hormonia/src/AdminApp.tsx` — official admin shell wording aligned to session-first runtime.
- `frontend-hormonia/src/features/admin/AdminSessionManager.tsx` — admin session narrative aligned to backend cookies + verify-session.
- `frontend-hormonia/src/hooks/auth/useSessionManagement.ts` — canonical session-management wording without Firebase-era operational semantics.
- `frontend-hormonia/src/utils/init-validator.ts` — readiness/auth checks aligned to session-first runtime truth.
- `frontend-hormonia/src/types/admin.ts` — canonical frontend admin types without unused Firebase baggage.
- `frontend-hormonia/shared-types/src/admin.ts` — shared admin contract aligned to the official runtime.
- `frontend-hormonia/src/lib/api-client/admin.ts` — admin API shape aligned to the canonical frontend contract.
- `frontend-hormonia/src/lib/api-client/normalizers.ts` — canonical normalization without Firebase-shaped assumptions.
