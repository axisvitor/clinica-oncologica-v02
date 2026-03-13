---
estimated_steps: 4
estimated_files: 8
---

# T02: Extract the operational and admin client namespaces out of `index.ts`

**Slice:** S03 — Frontend Client/Type Surface Refactor
**Milestone:** M003

## Description

Shrink the main client hotspot quickly by moving the operational and admin-oriented inline namespaces into dedicated `createXApi(client)` modules. This task focuses on the most mechanical extraction pass and resolves the current `admin` vs `adminV2` naming ambiguity before it spreads further.

## Steps

1. Create dedicated modules for the remaining operational/admin namespaces: `messages`, `flows`, `alerts`, `reports`, `notifications`, legacy `admin`, and `adminUsers`, following the repo’s existing `createXApi(client)` extraction pattern.
2. Rewire `frontend-hormonia/src/lib/api-client/index.ts` so those namespaces are composed from imports instead of inline implementations, while keeping the same public namespace names under `apiClient`.
3. Rename the legacy-admin module/function in a way that cannot be confused with the already-extracted `./admin` `createAdminApi` used for `adminV2`.
4. Run the structural contract test plus the existing api-client/core suites to prove the public client surface stayed stable while the hotspot shrank.

## Must-Haves

- [ ] `src/lib/api-client/index.ts` stops owning the inline bodies for the operational/admin namespaces covered by this task.
- [ ] Public callers still use the same `@/lib/api-client` surface, and the legacy `admin` vs `adminV2` distinction is clearer after the extraction, not murkier.

## Verification

- `cd frontend-hormonia && npm run test -- tests/lib/api-client/index-split.contract.test.ts tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts`
- Confirm the extracted modules are the only implementation home for the namespaces moved in this task.

## Observability Impact

- Signals added/changed: Existing api-client suites now fail at the delegated module boundary instead of deep inside the monolith if one namespace wiring regresses.
- How a future agent inspects this: Run the targeted Vitest command and inspect `src/lib/api-client/index.ts` imports to see which namespace is miswired.
- Failure state exposed: missing namespace exports, changed method shapes, or legacy-admin wiring mistakes surface as focused client test failures.

## Inputs

- `frontend-hormonia/src/lib/api-client/index.ts` — current hotspot still owning the remaining inline operational/admin namespaces.
- `frontend-hormonia/src/lib/api-client/auth.ts`, `frontend-hormonia/src/lib/api-client/patients.ts`, and `frontend-hormonia/src/lib/api-client/dashboard.ts` — working examples of the `createXApi(client)` composition pattern this task should mirror.
- `frontend-hormonia/tests/lib/api-client/index-split.contract.test.ts` — the structural contract from T01 that should turn green for the namespaces extracted here.

## Expected Output

- `frontend-hormonia/src/lib/api-client/messages.ts`, `flows.ts`, `alerts.ts`, `reports.ts`, `notifications.ts`, `admin-legacy.ts`, and `admin-users.ts` — dedicated modules owning the extracted namespace implementations.
- `frontend-hormonia/src/lib/api-client/index.ts` — a smaller composition-focused client seam with reduced naming ambiguity around admin ownership.
