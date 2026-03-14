---
estimated_steps: 4
estimated_files: 7
---

# T02: Remove HTTP and browser-storage legacy session transports from shared auth seams

**Slice:** S03 — Frontend oficial convergido para contrato session-first canônico
**Milestone:** M004

## Description

Cut the old session transport where the official frontend actually emits it today. `AuthProvider`, the auth API helper, the shared request core, and the direct analytics client are the seams that still turn a cookie-backed session into `session_id` browser state and legacy headers. This task removes that behavior without disturbing CSRF handling or user-safe auth diagnostics.

## Steps

1. Update `frontend-hormonia/src/app/providers/AuthContext.tsx` so staff login/restore/logout no longer persist or rehydrate `session_id` from browser storage and no longer call `apiClient.setAuthToken(session_id)`.
2. Update `frontend-hormonia/src/lib/api-client/auth.ts` and `frontend-hormonia/src/lib/api-client/core.ts` so official auth/session requests rely on `credentials: 'include'` plus CSRF instead of `Authorization` or `X-Session-ID` injection.
3. Remove equivalent storage/header fallback from `frontend-hormonia/src/lib/api-client/enhanced-analytics.ts` so dashboard/admin-adjacent fetches do not keep the legacy contract alive through a side client.
4. Re-run the focused auth/client proof and adjust only the user-safe diagnostics or fixtures needed to reflect the canonical contract; do not preserve a compat token path in the official frontend happy path.

## Must-Haves

- [ ] Staff auth no longer persists or restores `session_id` from browser storage on the official frontend path.
- [ ] Shared HTTP requests for the official app no longer emit `Authorization: Bearer <session_id>` or `X-Session-ID`.
- [ ] `credentials: 'include'`, CSRF behavior, and user-safe auth errors remain intact.
- [ ] The direct analytics client does not silently preserve the legacy transport for dashboard/admin surfaces.

## Verification

- `cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx`

## Observability Impact

- Signals added/changed: the official frontend auth surface now fails or passes entirely through cookie-backed verify-session semantics, while safe auth errors stay observable from the shared provider/client path.
- How a future agent inspects this: rerun the focused auth/client Vitest pack and inspect whether failures live in `AuthProvider`, auth fetch helpers, or the shared core client.
- Failure state exposed: regressions show up as explicit header/storage leakage or lost session/CSRF behavior rather than as a generic login failure.

## Inputs

- `.gsd/milestones/M004/slices/S03/tasks/T01-PLAN.md` — the proof boundary this task must satisfy.
- `.gsd/milestones/M004/slices/S03/S03-RESEARCH.md` — identifies the shared HTTP and browser-storage seams that still emit the old contract.
- `.gsd/milestones/M004/slices/S02/S02-SUMMARY.md` — backend contract reminder: canonical identity is already `user_id`-first, so the frontend does not need to carry its own session token transport.

## Expected Output

- `frontend-hormonia/src/app/providers/AuthContext.tsx` — canonical session restore/login/logout behavior without browser-stored `session_id` transport.
- `frontend-hormonia/src/lib/api-client/auth.ts` — verify-session/auth API path aligned to cookie-backed session semantics.
- `frontend-hormonia/src/lib/api-client/core.ts` — shared request path without legacy session header injection.
- `frontend-hormonia/src/lib/api-client/enhanced-analytics.ts` — official analytics client aligned to the same session-first contract.
- `frontend-hormonia/tests/unit/api-client/auth-headers.test.ts` — updated proof for the header/storage cut.
- `frontend-hormonia/tests/lib/api-client/core.test.ts` — updated core client proof for the new transport boundary.
- `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx` — green auth/restore/logout proof on the canonical contract.
