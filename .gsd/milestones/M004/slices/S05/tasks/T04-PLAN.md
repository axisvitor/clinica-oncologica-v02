---
estimated_steps: 4
estimated_files: 6
---

# T04: Remove Firebase-shaped adjacent frontend type residue

**Slice:** S05 — Resíduo funcional de Firebase removido do runtime adjacente
**Milestone:** M004

## Description

Clean the frontend-adjacent type surfaces that still describe Firebase as if it were part of the official auth/runtime story. The shipped frontend loop is already session-first after S03, so this task is about removing the remaining narrative and type-level drift that could quietly reintroduce Firebase-shaped assumptions through imports, guards, or future UI work.

## Steps

1. Update `src/types/api.ts` so the canonical frontend user/session-facing type surface no longer exposes `firebase_uid` as part of the official runtime shape.
2. Remove `AuthProvider.FIREBASE` and related provider-era narrative from `src/types/rbac.ts` while preserving only the runtime semantics still consumed by the app.
3. Rewrite lingering Firebase-claims narrative in `src/types/medico.ts` so the comments and helper types describe the canonical contract instead of Firebase claims.
4. Extend the existing type/normalizer proof and build checks so future drift is caught at the type boundary rather than during a later runtime slice.

## Must-Haves

- [ ] The adjacent frontend `User`/auth-facing types stop treating `firebase_uid` as a canonical field.
- [ ] RBAC/provider surfaces no longer expose Firebase as a live auth provider in the official runtime contract.
- [ ] Medico type narrative no longer describes role validation in Firebase-claims terms.
- [ ] Type-focused proof and the production build stay green on the narrowed frontend contract.

## Verification

- `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts`
- `cd frontend-hormonia && npm run build`

## Observability Impact

- Signals added/changed: the frontend type proof now asserts that canonical user shapes omit `firebase_uid`, RBAC barrels stop exporting a live auth-provider enum, and medico role-validation helpers describe canonical session/user context instead of Firebase claims.
- How to inspect later: rerun `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts` for the focused type boundary, then `cd frontend-hormonia && npm run build` to catch any stale imports or widened type drift in the production graph.
- Failure state exposed: regressions become visible as either reintroduced Firebase-shaped fields/exports in the focused type tests or as build failures from stale imports against the narrowed barrels, instead of surfacing later in unrelated runtime work.

## Inputs

- `frontend-hormonia/src/types/api.ts` — generic frontend type surface still exposing `firebase_uid`.
- `frontend-hormonia/src/types/rbac.ts` — adjacent RBAC/provider types still describe Firebase-era auth semantics.
- `frontend-hormonia/src/types/medico.ts` — narrative/type comments still lean on Firebase claims.
- `frontend-hormonia/src/lib/api-client/__tests__/normalizers.test.ts` and the existing type tests — current proof surfaces that must stay aligned with the narrowed contract.
- S03 handoff: the official frontend runtime path is already clean, so this task must preserve that runtime shape while removing residual type narrative.

## Expected Output

- `frontend-hormonia/src/types/api.ts` — canonical frontend user/auth type surface without `firebase_uid` residue.
- `frontend-hormonia/src/types/rbac.ts` — RBAC/provider types aligned to the canonical runtime semantics.
- `frontend-hormonia/src/types/medico.ts` — adjacent medico types/comments free of Firebase-claims narrative.
- `frontend-hormonia/src/lib/api-client/__tests__/normalizers.test.ts` — proof updated for the narrowed runtime type shape.
- `frontend-hormonia/tests/unit/types/admin-types.test.ts` — type proof still green against the post-cut frontend contract.
- `frontend-hormonia/tests/unit/types/type-consistency.test.ts` — broader type consistency proof aligned to the new adjacent surface.
