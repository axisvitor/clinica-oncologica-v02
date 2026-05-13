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
  - React Query IndexedDB persistence is deny-by-default and allows only explicit static/non-PHI dictionary/template query roots.
  - The IndexedDB persister filters both writes and legacy restores and removes all persisted mutations to avoid durable PHI/session mutation variables.
duration: 
verification_result: passed
completed_at: 2026-05-13T19:10:26.539Z
blocker_discovered: false
---

# T02: Added deny-by-default dashboard React Query persistence so IndexedDB stores only allowlisted static non-PHI query data and drops PHI/session/auth/report/message/quiz payloads.

**Added deny-by-default dashboard React Query persistence so IndexedDB stores only allowlisted static non-PHI query data and drops PHI/session/auth/report/message/quiz payloads.**

## What Happened

Created `persistencePolicy.ts` with pure deny-by-default helpers (`isPersistableQueryKey`, `shouldPersistDashboardQuery`, and `filterPersistedClient`) that reject PHI/user/session/dashboard/report/message/AI/alert/physician/clinical/monthly-quiz/session query keys and allow only narrow static dictionary/template roots. Extended `createIndexedDBPersister` with an optional `filterClient` hook applied before IndexedDB writes and after legacy restores; metadata is computed from the filtered client, filtered counts are sanitized, and all mutations are removed from persisted storage. Wired the singleton dashboard persister to `filterPersistedClient` in `queryClient.ts` and passed `dehydrateOptions.shouldDehydrateQuery` through `PersistQueryClientProvider` in `App.tsx` for defense in depth. Added pure Vitest coverage for mixed PHI/non-PHI persisted clients, denied array/object key variants, malformed/unknown legacy states, and provider-level predicate behavior.

## Verification

Ran the focused Vitest command from the task plan; it passed with 5 policy tests proving mixed persisted-client states keep only allowlisted static query keys and drop patient/dashboard/quiz/report/message/auth payloads plus mutations. Also ran the frontend TypeScript typecheck to verify the `PersistQueryClientProvider` and persister configuration wiring compiles.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm --prefix frontend-hormonia test -- tests/unit/react-query/persistencePolicy.test.ts` | 0 | ✅ pass | 50173ms |
| 2 | `npm --prefix frontend-hormonia run typecheck` | 0 | ✅ pass | 44471ms |

## Deviations

Added an extra frontend `typecheck` verification beyond the focused Vitest command to prove the provider-level `dehydrateOptions.shouldDehydrateQuery` wiring is type-compatible.

## Known Issues

None.

## Files Created/Modified

- `frontend-hormonia/src/lib/react-query/persistencePolicy.ts`
- `frontend-hormonia/src/lib/react-query/persistentCache.ts`
- `frontend-hormonia/src/lib/react-query/queryClient.ts`
- `frontend-hormonia/src/App.tsx`
- `frontend-hormonia/tests/unit/react-query/persistencePolicy.test.ts`
