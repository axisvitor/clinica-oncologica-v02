---
estimated_steps: 37
estimated_files: 5
skills_used: []
---

# T02: Add deny-by-default dashboard React Query persistence allowlist

---
estimated_steps: 8
estimated_files: 5
skills_used:
  - react-best-practices
  - tdd
  - verify-before-complete
---

Why: The Vite dashboard currently persists the entire dehydrated React Query client into IndexedDB for seven days. Patient, dashboard, clinical, report, alert, message, AI, and monthly quiz status query payloads can therefore outlive logout/tab close. This task makes persistence explicit and non-PHI by default.

Files: `frontend-hormonia/src/lib/react-query/persistencePolicy.ts`, `frontend-hormonia/src/lib/react-query/persistentCache.ts`, `frontend-hormonia/src/lib/react-query/queryClient.ts`, `frontend-hormonia/src/App.tsx`, `frontend-hormonia/tests/unit/react-query/persistencePolicy.test.ts`.

Do:
1. Create a pure persistence policy module exporting `isPersistableQueryKey`/`shouldPersistDashboardQuery` and a `filterPersistedClient` helper that defaults to deny for unknown keys.
2. Deny PHI/user/session keys and variants including `patients`, `patient`, `dashboard`, `messages`, `reports`, `ai`, `alerts`, `physician`, `clinical`, `auth`, `user`, `session`, `monthly-quiz-status`, patient quiz sessions/responses, and object/array keys containing patient/session/report identifiers.
3. Allow only explicit non-PHI/static keys needed for performance/offline UX, such as template catalogs, public/static configuration dictionaries, treatment type dictionaries, and similarly non-patient-bound metadata; keep the allowlist narrow and documented in code.
4. Extend `createIndexedDBPersister` to accept a filtering/sanitizing option and apply it immediately before `database.put('queryCache', ...)`, calculating metadata from the filtered client.
5. Wire the dashboard singleton persister in `queryClient.ts` to the policy and, if supported by the installed TanStack API, pass matching `dehydrateOptions.shouldDehydrateQuery` through `PersistQueryClientProvider` in `App.tsx` for defense in depth.
6. Ensure failures in policy/filtering or IndexedDB continue to degrade to in-memory React Query without throwing during app render.
7. Add pure Vitest coverage that constructs persisted-client fixtures with mixed PHI/non-PHI query keys and asserts denied payloads are absent while allowlisted static data remains.

Failure Modes (Q5): IndexedDB unavailable, malformed persisted clients, unknown query-key shapes, and filter exceptions should not crash the dashboard; they should drop persistence or return an empty persisted query set. Restore of legacy full-cache state should not rehydrate denied PHI queries.

Load Profile (Q6): Filtering is O(number of dehydrated queries) and should reduce persisted bytes under high dashboard usage. At 10x patient/dashboard query volume, the first pressure point should remain the existing `maxSize` cleanup, not uncontrolled PHI persistence.

Negative Tests (Q7): Array and object query keys containing patient/session/report/dashboard terms, false-positive static/template keys adjacent to denied keys, unknown/malformed keys, legacy persisted client with denied data, and empty client state.

Done when: the focused Vitest suite proves a mixed dashboard persisted-client state stores only allowlisted non-PHI queries and drops patient/dashboard/quiz/report/message/auth payloads.

## Inputs

- `frontend-hormonia/src/App.tsx` — provider wiring for `PersistQueryClientProvider`.
- `frontend-hormonia/src/lib/react-query/queryClient.ts` — singleton query client and persister configuration.
- `frontend-hormonia/src/lib/react-query/persistentCache.ts` — IndexedDB persister implementation.
- `frontend-hormonia/package.json` — test script/dependency context.
- `frontend-hormonia/vite.config.ts` — Vitest environment and alias setup.
- `frontend-hormonia/tests/setup.ts` — frontend test setup.

## Expected Output

- `frontend-hormonia/src/lib/react-query/persistencePolicy.ts` — deny-by-default non-PHI query persistence policy and filtering helper.
- `frontend-hormonia/src/lib/react-query/persistentCache.ts` — persister applies filtering before IndexedDB writes/restores metadata.
- `frontend-hormonia/src/lib/react-query/queryClient.ts` — dashboard persister wired to the allowlist policy.
- `frontend-hormonia/src/App.tsx` — provider-level persistence options aligned with the policy when supported.
- `frontend-hormonia/tests/unit/react-query/persistencePolicy.test.ts` — deterministic proof for allowed and denied query persistence.

## Verification

- `npm --prefix frontend-hormonia test -- tests/unit/react-query/persistencePolicy.test.ts`

## Inputs

- `frontend-hormonia/src/App.tsx`
- `frontend-hormonia/src/lib/react-query/queryClient.ts`
- `frontend-hormonia/src/lib/react-query/persistentCache.ts`
- `frontend-hormonia/package.json`
- `frontend-hormonia/vite.config.ts`
- `frontend-hormonia/tests/setup.ts`

## Expected Output

- `frontend-hormonia/src/lib/react-query/persistencePolicy.ts`
- `frontend-hormonia/src/lib/react-query/persistentCache.ts`
- `frontend-hormonia/src/lib/react-query/queryClient.ts`
- `frontend-hormonia/src/App.tsx`
- `frontend-hormonia/tests/unit/react-query/persistencePolicy.test.ts`

## Verification

npm --prefix frontend-hormonia test -- tests/unit/react-query/persistencePolicy.test.ts

## Observability Impact

Query-cache metadata remains useful through sanitized query counts/sizes only; debug logs must mention filtered counts/key classes rather than payload contents, patient IDs, names, answers, tokens, or report data.
