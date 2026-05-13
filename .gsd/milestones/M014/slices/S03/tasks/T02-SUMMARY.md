---
id: T02
parent: S03
milestone: M014
key_files:
  - frontend-hormonia/src/lib/react-query/persistencePolicy.ts
  - frontend-hormonia/src/lib/react-query/persistentCache.ts
  - frontend-hormonia/src/lib/react-query/queryClient.ts
  - frontend-hormonia/src/App.tsx
  - frontend-hormonia/tests/unit/react-query/persistencePolicy.test.ts
key_decisions:
  - Dashboard React Query persistence is deny-by-default and only allowlisted static/non-PHI dictionary/template query roots may be written to IndexedDB.
  - Persisted mutations and legacy restored denied query payloads are filtered out so restore/write paths degrade to sanitized cached metadata instead of durable PHI.
duration: 
verification_result: passed
completed_at: 2026-05-13T19:53:59.204Z
blocker_discovered: false
---

# T02: Reconciled the dashboard React Query persistence hardening so IndexedDB persistence is deny-by-default and stores only explicit non-PHI static/template query data.

**Reconciled the dashboard React Query persistence hardening so IndexedDB persistence is deny-by-default and stores only explicit non-PHI static/template query data.**

## What Happened

Reconciled the already-implemented T02 work into the canonical GSD DB state after the artifact gate exposed S03 state drift. The dashboard now has a pure deny-by-default persistence policy that recursively inspects query-key shapes for patient/dashboard/report/message/AI/alert/physician/clinical/auth/user/session/monthly-quiz/session-like terms and allows only narrow static dictionary/template roots. The IndexedDB persister accepts a `filterClient` option and applies it before writes and after legacy restores, persists metadata from the filtered payload only, removes durable mutations, and drops to an empty persisted client if policy filtering fails. The singleton dashboard persister is wired to `filterPersistedClient`, and `App.tsx` passes `shouldDehydrateQuery` through `PersistQueryClientProvider` for defense in depth. Focused Vitest coverage proves allowlisted static data persists while patient/dashboard/quiz/report/message/auth payloads and mutations are removed, including object/array key variants and malformed legacy states.

## Verification

Ran the focused frontend verification command: `npm --prefix frontend-hormonia test -- tests/unit/react-query/persistencePolicy.test.ts`. It passed 1 Vitest file / 5 tests, proving mixed persisted-client fixtures drop PHI/auth/session/dashboard/report/message/quiz payloads and keep only allowlisted static/template queries.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix frontend-hormonia test -- tests/unit/react-query/persistencePolicy.test.ts` | 0 | ✅ pass — 1 Vitest file / 5 tests passed | 45484ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend-hormonia/src/lib/react-query/persistencePolicy.ts`
- `frontend-hormonia/src/lib/react-query/persistentCache.ts`
- `frontend-hormonia/src/lib/react-query/queryClient.ts`
- `frontend-hormonia/src/App.tsx`
- `frontend-hormonia/tests/unit/react-query/persistencePolicy.test.ts`
