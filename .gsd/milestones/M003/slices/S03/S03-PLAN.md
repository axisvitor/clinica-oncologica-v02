# S03: Frontend Client/Type Surface Refactor

**Goal:** Split the frontend API-client and transport-type hotspots into focused modules behind the stable `@/lib/api-client`, `@/lib/api-client/types`, and `@/types/api` façades, while isolating compatibility residue instead of widening type churn.
**Demo:** Focused frontend proof passes while `frontend-hormonia/src/lib/api-client/index.ts` is reduced to composition over extracted `createXApi(client)` modules, `frontend-hormonia/src/lib/api-client/types.ts` becomes a barrel over domain type files with no duplicate `RiskAssessmentRequest`, and `frontend-hormonia/src/hooks/usePatients.ts` no longer depends on the `src/lib/types/api.ts` compatibility barrel.

## Requirement Coverage

- Supported by this slice: **R034** — materially split the frontend client/type hotspot into smaller ownership modules without changing the stable façade imports.
- Supported by this slice: **R036** — isolate legacy compatibility residue by migrating the live `usePatients.ts` caller away from `src/lib/types/api.ts` while leaving actual deletion to S04 proof.
- Supported by this slice: **R037** — keep `@/lib/api-client`, `@/lib/api-client/types`, and `@/types/api` stable while moving internal ownership behind them.
- Supported by this slice: **R038** — clarify which modules own transport methods, which own DTOs, and which remain compatibility layers so future edits stay local.
- Supported by this slice: **R039** — leave focused client/auth/session/type verification plus structural checks that prove the refactor held.
- Not claimed here: **R035** remains the S01 evidence contract, and final deletion/tombstoning of proven-dead compat layers remains S04.

## Must-Haves

- `frontend-hormonia/src/lib/api-client.ts` remains the stable public façade, while `frontend-hormonia/src/lib/api-client/index.ts` becomes composition over extracted domain modules for the remaining inline namespaces.
  _Covers: R034, R037_
- `frontend-hormonia/src/lib/api-client/types.ts` becomes the stable barrel over domain-focused type files, and the duplicated `RiskAssessmentRequest` declaration is reduced to one canonical owner.
  _Covers: R034, R037, R038_
- `frontend-hormonia/src/types/api.ts` stays the app/UI-facing façade, and `frontend-hormonia/src/hooks/usePatients.ts` migrates off `frontend-hormonia/src/lib/types/api.ts` without deleting the compatibility barrel in this slice.
  _Covers: R036, R037, R038_
- Focused proof stays green through new structural contract tests, existing client/auth/session/realtime suites, hook coverage, typecheck/build, and the frontend evidence-map verifier.
  _Covers: R034, R039_

## Proof Level

- This slice proves: integration
- Real runtime required: no
- Human/UAT required: no

## Verification

- `cd frontend-hormonia && npm run test -- tests/lib/api-client/index-split.contract.test.ts tests/unit/types/api-client-types-barrel.contract.test.ts tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts`
- `cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts`
- `cd frontend-hormonia && npm run test -- tests/integration/auth/session-first-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx tests/components/dashboard/QuickStats.test.tsx`
- `cd frontend-hormonia && npm run test -- src/hooks/__tests__/usePatients.test.ts tests/unit/types-validation.test.ts`
- `cd frontend-hormonia && npm run typecheck && npm run build`
- "cd frontend-hormonia && python3 - <<'PY'
from pathlib import Path
required = [
    Path('src/lib/api-client/messages.ts'),
    Path('src/lib/api-client/flows.ts'),
    Path('src/lib/api-client/alerts.ts'),
    Path('src/lib/api-client/reports.ts'),
    Path('src/lib/api-client/notifications.ts'),
    Path('src/lib/api-client/admin-legacy.ts'),
    Path('src/lib/api-client/admin-users.ts'),
    Path('src/lib/api-client/ai.ts'),
    Path('src/lib/api-client/quiz.ts'),
    Path('src/lib/api-client/quizzes.ts'),
    Path('src/lib/api-client/physician.ts'),
    Path('src/lib/api-client/types/quiz.ts'),
    Path('src/lib/api-client/types/physician.ts'),
]
missing = [str(path) for path in required if not path.exists()]
if missing:
    raise SystemExit(f'missing split modules: {missing}')
index_source = Path('src/lib/api-client/index.ts').read_text()
types_source = Path('src/lib/api-client/types.ts').read_text()
if len(index_source.splitlines()) >= 800:
    raise SystemExit(f'api-client/index.ts still too large: {len(index_source.splitlines())} lines')
if len(types_source.splitlines()) >= 450:
    raise SystemExit(f'api-client/types.ts still too large: {len(types_source.splitlines())} lines')
if index_source.count("from './messages'") != 1:
    raise SystemExit('messages module not wired exactly once from index.ts')
if types_source.count('RiskAssessmentRequest') < 1:
    raise SystemExit('RiskAssessmentRequest export missing from types barrel')
if Path('src/hooks/usePatients.ts').read_text().count('lib/types/api'):
    raise SystemExit('usePatients.ts still imports the compatibility type barrel')
print({
    'index_lines': len(index_source.splitlines()),
    'types_lines': len(types_source.splitlines()),
    'required_modules': [str(path) for path in required],
})
PY"
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check frontend`

## Observability / Diagnostics

- Runtime signals: preserve user-safe `ApiError`/auth diagnostics through the session/auth/realtime suites, and add structural contract tests that fail on missing extracted modules, duplicate type ownership, or lingering compatibility imports.
- Inspection surfaces: targeted Vitest suites above, `npm run typecheck`, `npm run build`, the structural Python check, and `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report frontend`.
- Failure visibility: regressions surface as named missing-module failures, duplicate `RiskAssessmentRequest`/barrel drift, canonical-import drift in `usePatients.ts`, or existing session/realtime/dashboard client failures.
- Redaction constraints: proof should stay limited to source paths, public export names, and user-safe client errors; do not print secrets, cookies, or patient payloads.

## Integration Closure

- Upstream surfaces consumed: `frontend-hormonia/src/lib/api-client.ts`, `frontend-hormonia/src/lib/api-client/index.ts`, `frontend-hormonia/src/lib/api-client/types.ts`, existing extracted client modules (`auth.ts`, `patients.ts`, `dashboard.ts`, `analytics.ts`, `monthly-quiz.ts`, `admin.ts`), `frontend-hormonia/src/types/api.ts`, `frontend-hormonia/src/lib/types/api.ts`, `frontend-hormonia/src/lib/ai-adapters.ts`, and `frontend-hormonia/src/hooks/usePatients.ts`.
- New wiring introduced in this slice: `src/lib/api-client/index.ts` becomes a pure composition seam over extracted `createXApi(client)` modules; `src/lib/api-client/types.ts` becomes the stable barrel over domain type files; `usePatients.ts` consumes a canonical type source instead of the compat barrel.
- What remains before the milestone is truly usable end-to-end: S04 still has to prove and remove or tombstone cold compatibility layers such as `src/lib/api.ts` / `src/lib/types/api.ts`, and S05 still has to replay integrated cross-surface smoke.

## Tasks

- [x] **T01: Add failing structural contract tests for the client/type seam** `est:55m`
  - Why: Freeze the frontend split boundary before moving code so the refactor closes a real contract around stable façades, extracted module ownership, duplicate type cleanup, and the `usePatients` compatibility caller.
  - Files: `frontend-hormonia/tests/lib/api-client/index-split.contract.test.ts`, `frontend-hormonia/tests/unit/types/api-client-types-barrel.contract.test.ts`, `frontend-hormonia/tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts`
  - Do: Add new Vitest contract tests that read the hotspot source files and assert the intended end-state: `index.ts` delegates remaining namespaces to dedicated modules while `@/lib/api-client` still exposes the same domain surface, `types.ts` becomes a barrel with one canonical `RiskAssessmentRequest`, and `usePatients.ts` stops importing `src/lib/types/api.ts`; make the tests fail initially for the expected pre-refactor reasons.
  - Verify: `cd frontend-hormonia && npm run test -- tests/lib/api-client/index-split.contract.test.ts tests/unit/types/api-client-types-barrel.contract.test.ts tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts`
  - Done when: The new tests exist, express the structural contract in executable form, and their initial failures point at missing module extraction / barrel cleanup / canonical import migration rather than unrelated harness issues.
- [x] **T02: Extract the operational and admin client namespaces out of `index.ts`** `est:1h45m`
  - Why: The biggest immediate size win is removing the remaining operational/admin inline namespaces from the hotspot file while keeping the public `apiClient` surface stable and reducing the legacy `admin` vs `adminV2` naming ambiguity.
  - Files: `frontend-hormonia/src/lib/api-client/index.ts`, `frontend-hormonia/src/lib/api-client/messages.ts`, `frontend-hormonia/src/lib/api-client/flows.ts`, `frontend-hormonia/src/lib/api-client/alerts.ts`, `frontend-hormonia/src/lib/api-client/reports.ts`, `frontend-hormonia/src/lib/api-client/notifications.ts`, `frontend-hormonia/src/lib/api-client/admin-legacy.ts`, `frontend-hormonia/src/lib/api-client/admin-users.ts`
  - Do: Move the inline `messages`, `flows`, `alerts`, `reports`, `notifications`, legacy `admin`, and `adminUsers` namespaces into dedicated `createXApi(client)` modules following the repo’s existing module pattern; wire them back through `index.ts`; and pick a legacy-admin module/function name that cannot be confused with the existing `./admin` `createAdminApi` used for `adminV2`.
  - Verify: `cd frontend-hormonia && npm run test -- tests/lib/api-client/index-split.contract.test.ts tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts`
  - Done when: `index.ts` delegates these namespaces instead of implementing them inline, the public `apiClient` namespace names still resolve for callers, and the legacy admin module naming no longer amplifies the current ambiguity.
- [x] **T03: Extract the quiz/clinical namespaces and turn `types.ts` into a domain barrel** `est:2h`
  - Why: The remaining inline namespaces (`ai`, `quiz`, `quizzes`, `physician`) are coupled to the hottest transport-type duplication, so finishing their extraction together with the type-barrel split closes the central ownership seam instead of leaving half the hotspot behind.
  - Files: `frontend-hormonia/src/lib/api-client/index.ts`, `frontend-hormonia/src/lib/api-client/ai.ts`, `frontend-hormonia/src/lib/api-client/quiz.ts`, `frontend-hormonia/src/lib/api-client/quizzes.ts`, `frontend-hormonia/src/lib/api-client/physician.ts`, `frontend-hormonia/src/lib/api-client/types.ts`, `frontend-hormonia/src/lib/api-client/types/quiz.ts`, `frontend-hormonia/src/lib/api-client/types/physician.ts`
  - Do: Extract the remaining inline client namespaces into dedicated modules, create domain-focused type files under `src/lib/api-client/types/`, convert `types.ts` into the stable re-export barrel, and collapse the duplicate `RiskAssessmentRequest` declaration to one canonical transport owner; preserve `@/types/api` as the UI-facing façade and use adapters where UI and transport models diverge instead of forcing a repo-wide type rewrite.
  - Verify: `cd frontend-hormonia && npm run test -- tests/lib/api-client/index-split.contract.test.ts tests/unit/types/api-client-types-barrel.contract.test.ts tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts`
  - Done when: All formerly inline namespaces are extracted, `types.ts` is primarily barrel glue instead of the transport monolith, `RiskAssessmentRequest` has one owner, and the stable façade imports still compile.
- [x] **T04: Migrate the remaining compat caller and close the focused frontend proof gate** `est:1h25m`
  - Why: S03 is only complete when the last live app caller leaves the `src/lib/types/api.ts` compatibility barrel, the hook/type tests are aligned with the canonical path, and the full focused proof pack shows the structural split did not regress auth/session/client behavior.
  - Files: `frontend-hormonia/src/hooks/usePatients.ts`, `frontend-hormonia/src/lib/types/api.ts`, `frontend-hormonia/src/lib/api-client/patients.ts`, `frontend-hormonia/src/hooks/__tests__/usePatients.test.ts`, `frontend-hormonia/tests/unit/types-validation.test.ts`, `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx`, `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts`, `frontend-hormonia/tests/integration/initialization/session-auth-operational-surfaces.test.tsx`
  - Do: Move `usePatients.ts` onto a canonical type/source import, refresh the hook/type-validation assertions to match the new ownership boundary, keep `src/lib/types/api.ts` present but more isolated for S04, and run the full focused proof pack including the structural split check, typecheck/build, and the frontend evidence-map verifier.
  - Verify: `cd frontend-hormonia && npm run test -- src/hooks/__tests__/usePatients.test.ts tests/unit/types-validation.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx tests/components/dashboard/QuickStats.test.tsx && npm run typecheck && npm run build && python3 - <<'PY'
from pathlib import Path
index_source = Path('src/lib/api-client/index.ts').read_text()
types_source = Path('src/lib/api-client/types.ts').read_text()
if len(index_source.splitlines()) >= 800:
    raise SystemExit(f'api-client/index.ts still too large: {len(index_source.splitlines())} lines')
if len(types_source.splitlines()) >= 450:
    raise SystemExit(f'api-client/types.ts still too large: {len(types_source.splitlines())} lines')
if Path('src/hooks/usePatients.ts').read_text().count('lib/types/api'):
    raise SystemExit('usePatients.ts still imports the compatibility type barrel')
if Path('src/lib/api-client/types.ts').read_text().count('RiskAssessmentRequest') < 1:
    raise SystemExit('RiskAssessmentRequest export missing from types barrel')
print({'index_lines': len(index_source.splitlines()), 'types_lines': len(types_source.splitlines())})
PY && bash ../.gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check frontend`
  - Done when: `usePatients.ts` no longer depends on the compat barrel, the focused frontend auth/session/client/type proof pack is green, and the structural checks show the hotspot files materially shrank behind the same public façades.

## Files Likely Touched

- `frontend-hormonia/src/lib/api-client/index.ts`
- `frontend-hormonia/src/lib/api-client/types.ts`
- `frontend-hormonia/src/lib/api-client/messages.ts`
- `frontend-hormonia/src/lib/api-client/flows.ts`
- `frontend-hormonia/src/lib/api-client/alerts.ts`
- `frontend-hormonia/src/lib/api-client/reports.ts`
- `frontend-hormonia/src/lib/api-client/notifications.ts`
- `frontend-hormonia/src/lib/api-client/admin-legacy.ts`
- `frontend-hormonia/src/lib/api-client/admin-users.ts`
- `frontend-hormonia/src/lib/api-client/ai.ts`
- `frontend-hormonia/src/lib/api-client/quiz.ts`
- `frontend-hormonia/src/lib/api-client/quizzes.ts`
- `frontend-hormonia/src/lib/api-client/physician.ts`
- `frontend-hormonia/src/lib/api-client/types/quiz.ts`
- `frontend-hormonia/src/lib/api-client/types/physician.ts`
- `frontend-hormonia/src/hooks/usePatients.ts`
- `frontend-hormonia/tests/lib/api-client/index-split.contract.test.ts`
- `frontend-hormonia/tests/unit/types/api-client-types-barrel.contract.test.ts`
- `frontend-hormonia/tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts`
- `frontend-hormonia/src/hooks/__tests__/usePatients.test.ts`
- `frontend-hormonia/tests/unit/types-validation.test.ts`
