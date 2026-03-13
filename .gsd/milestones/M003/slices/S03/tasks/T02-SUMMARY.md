---
id: T02
parent: S03
milestone: M003
provides:
  - Extracted the operational/admin api-client namespaces into dedicated modules and reduced `src/lib/api-client/index.ts` to composition for those seams.
key_files:
  - frontend-hormonia/src/lib/api-client/index.ts
  - frontend-hormonia/src/lib/api-client/messages.ts
  - frontend-hormonia/src/lib/api-client/flows.ts
  - frontend-hormonia/src/lib/api-client/alerts.ts
  - frontend-hormonia/src/lib/api-client/reports.ts
  - frontend-hormonia/src/lib/api-client/notifications.ts
  - frontend-hormonia/src/lib/api-client/admin-legacy.ts
  - frontend-hormonia/src/lib/api-client/admin-users.ts
key_decisions:
  - Renamed the legacy admin factory to `createLegacyAdminApi` in `admin-legacy.ts` while preserving the public `apiClient.admin` namespace and leaving `adminV2` on `./admin/createAdminApi`.
  - Switched `index.ts` config probing to namespace/existence checks so partial Vitest mocks no longer fail during import just because `API_BASE_URL` is omitted.
patterns_established:
  - Extract namespace-specific `createXApi(client)` modules that own both the method bodies and their local API interfaces, then keep `index.ts` as a composition seam with stable public namespace names.
observability_surfaces:
  - `cd frontend-hormonia && npm run test -- tests/lib/api-client/index-split.contract.test.ts tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts`
  - `cd frontend-hormonia && python3 - <<'PY' ...` (module existence + `index.ts` line count check)
  - `cd frontend-hormonia && rg -n "from './(messages|flows|alerts|reports|admin-legacy|admin-users|notifications)'|this\.(messages|flows|alerts|reports|admin|adminUsers|notifications)\s*=\s*create[A-Z][A-Za-z0-9]*Api\(this\)" src/lib/api-client/index.ts`
duration: ~1h
verification_result: partial
completed_at: 2026-03-12T23:58:00-03:00
blocker_discovered: false
---

# T02: Extract the operational and admin client namespaces out of `index.ts`

**Shipped dedicated `createXApi(client)` modules for the operational/admin namespaces, rewired `index.ts` to compose them, and clarified the legacy `admin` versus `adminV2` ownership split.**

## What Happened

I moved the inline `messages`, `flows`, `alerts`, `reports`, `notifications`, legacy `admin`, and `adminUsers` implementations out of `frontend-hormonia/src/lib/api-client/index.ts` into new focused modules:

- `frontend-hormonia/src/lib/api-client/messages.ts`
- `frontend-hormonia/src/lib/api-client/flows.ts`
- `frontend-hormonia/src/lib/api-client/alerts.ts`
- `frontend-hormonia/src/lib/api-client/reports.ts`
- `frontend-hormonia/src/lib/api-client/notifications.ts`
- `frontend-hormonia/src/lib/api-client/admin-legacy.ts`
- `frontend-hormonia/src/lib/api-client/admin-users.ts`

`frontend-hormonia/src/lib/api-client/index.ts` now imports those factories and composes them in the `ApiClient` constructor instead of owning their inline method bodies. The legacy admin seam is now explicitly named `createLegacyAdminApi`/`admin-legacy.ts`, which keeps the public namespace name `apiClient.admin` stable while making it much harder to confuse with `apiClient.adminV2` from `./admin`.

I also adjusted the `../../config` import in `index.ts` to probe the config namespace defensively so partial test mocks can omit `API_BASE_URL` without throwing during module initialization.

## Verification

Passed:

- `cd frontend-hormonia && python3 - <<'PY' ...`
  - confirmed all seven extracted modules exist
  - confirmed `src/lib/api-client/index.ts` shrank to 717 lines
- `cd frontend-hormonia && npm run test -- tests/lib/api-client/core.test.ts`
  - passed as part of the targeted client-suite runs
- `cd frontend-hormonia && rg -n "from './(messages|flows|alerts|reports|admin-legacy|admin-users|notifications)'|this\.(messages|flows|alerts|reports|admin|adminUsers|notifications)\s*=\s*create[A-Z][A-Za-z0-9]*Api\(this\)" src/lib/api-client/index.ts`
  - confirmed the extracted namespaces are imported once and composed via delegated factories

Still red / partial:

- `cd frontend-hormonia && npm run test -- tests/lib/api-client/index-split.contract.test.ts tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts`
  - `tests/lib/api-client/index-split.contract.test.ts` now fails only on the still-inline namespaces left for T03: `ai`, `quiz`, `quizzes`, and `physician`
  - `tests/integration/api-client.test.ts` no longer dies on the missing `API_BASE_URL` mock export, but the suite still fails on older endpoint/URL expectations unrelated to the extracted modules (for example legacy `/messages/send` assertions, `/api/v2`-prefixed baseURL assumptions, and current auth/CSRF behavior)
- `cd frontend-hormonia && npm run typecheck`
  - still fails in untouched websocket files on `connection_id` index-signature access (`src/hooks/useWebSocket.ts`, `src/lib/websocket.ts`)

## Diagnostics

- Inspect `frontend-hormonia/src/lib/api-client/index.ts` imports and constructor assignments to confirm the moved namespaces are delegated from `./messages`, `./flows`, `./alerts`, `./reports`, `./notifications`, `./admin-legacy`, and `./admin-users`.
- Re-run `cd frontend-hormonia && npm run test -- tests/lib/api-client/index-split.contract.test.ts` to see the remaining seam gaps called out explicitly by module name.
- Re-run `cd frontend-hormonia && python3 - <<'PY' ...` from the slice plan to confirm module presence and the reduced `index.ts` line count.

## Deviations

- In addition to the extraction work, I hardened `frontend-hormonia/src/lib/api-client/index.ts` config lookup so partial Vitest mocks no longer crash import-time initialization when `API_BASE_URL` is absent.

## Known Issues

- The structural contract remains intentionally red for the not-yet-extracted `ai`, `quiz`, `quizzes`, and `physician` namespaces; T03 is the next task that closes those gaps.
- `tests/integration/api-client.test.ts` is still red after the import-shape fix because its expectations no longer match the current client/auth/request behavior in several untouched areas.
- `npm run typecheck` is still red in untouched websocket files due to `connection_id` index-signature access.

## Files Created/Modified

- `frontend-hormonia/src/lib/api-client/messages.ts` — extracted the messages namespace into a dedicated `createMessagesApi(client)` module.
- `frontend-hormonia/src/lib/api-client/flows.ts` — extracted the flows namespace into a dedicated `createFlowsApi(client)` module.
- `frontend-hormonia/src/lib/api-client/alerts.ts` — extracted the alerts namespace into a dedicated `createAlertsApi(client)` module.
- `frontend-hormonia/src/lib/api-client/reports.ts` — extracted the reports namespace into a dedicated `createReportsApi(client)` module.
- `frontend-hormonia/src/lib/api-client/notifications.ts` — extracted the notifications namespace into a dedicated `createNotificationsApi(client)` module.
- `frontend-hormonia/src/lib/api-client/admin-legacy.ts` — extracted the legacy admin namespace behind the disambiguated `createLegacyAdminApi(client)` factory.
- `frontend-hormonia/src/lib/api-client/admin-users.ts` — extracted the admin-users namespace into a dedicated `createAdminUsersApi(client)` module.
- `frontend-hormonia/src/lib/api-client/index.ts` — rewired the public client seam to compose the extracted modules and clarified `admin` vs `adminV2` ownership.
- `.gsd/DECISIONS.md` — recorded the legacy-admin naming split and config-mock compatibility decision.
- `.gsd/milestones/M003/slices/S03/S03-PLAN.md` — marked T02 complete.
- `.gsd/STATE.md` — advanced the slice state to T03.
