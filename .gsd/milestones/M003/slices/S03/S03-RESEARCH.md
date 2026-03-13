# S03 — Research

**Date:** 2026-03-12

## Summary

S03 should treat the frontend client/type problem as **two coupled but different seams**: a giant API-client ownership file (`frontend-hormonia/src/lib/api-client/index.ts`, 1304 lines) and a giant transport/type ownership file (`frontend-hormonia/src/lib/api-client/types.ts`, 1159 lines). The public façades identified in S01 are still the right guardrails: `@/lib/api-client`, `@/lib/api-client/types`, and `@/types/api` must stay stable while ownership moves behind them.

The codebase already contains a **partial modular split** under `src/lib/api-client/` (`auth.ts`, `patients.ts`, `dashboard.ts`, `admin.ts`, `monthly-quiz.ts`, `analytics.ts`, etc.), but `index.ts` still owns 11 inline namespaces plus their interface definitions. On the type side, `src/types/api.ts` is not a pure transport barrel; it is an app/UI-facing façade that imports selected transport types from `@/lib/api-client/types` and then defines many additional app-facing models. `src/lib/types/api.ts` remains a compatibility barrel with only **two exact callers** today: one app caller (`src/hooks/usePatients.ts`) and one validation test (`tests/unit/types-validation.test.ts`).

The safest S03 approach is therefore **seam-preserving extraction, not type-unification-by-force**: keep the façades stable, extract the inline client namespaces into dedicated modules that follow the existing `createXApi(client)` pattern, and reduce duplicated transport types behind `@/lib/api-client/types` without trying to redesign all app-facing types in one pass.

## Active Requirements Targeted

S03 directly supports these active M003 requirements:

- **R034 — Critical mixed-responsibility hotspots are split into smaller modules**
  - Primary S03 concern on the frontend side.
  - Evidence: `src/lib/api-client/index.ts` and `src/lib/api-client/types.ts` remain the hotspot pair.
- **R036 — Obsolete compatibility layers are removed or tightly isolated**
  - Support role in S03 by isolating compatibility barrels/shims and migrating the easiest live caller(s) toward canonical imports.
- **R037 — Visible contracts remain stable during the cleanup**
  - Support role in S03 by preserving `@/lib/api-client`, `@/lib/api-client/types`, and `@/types/api`, plus avoiding unnecessary import-path churn.
- **R038 — The codebase becomes safer to change in practice**
  - Support role in S03 by clarifying which modules own transport methods, which own DTOs, and which remain compatibility layers.
- **R039 — Structural cleanup leaves strong proof, not just nicer files**
  - Support role in S03 by keeping focused frontend verification tied to the refactored seams and by distinguishing authoritative tests from stale legacy ones.

## Recommendation

### Recommended implementation shape

1. **Keep the façade paths stable**
   - Preserve `frontend-hormonia/src/lib/api-client.ts` as the thin public façade for `@/lib/api-client`.
   - Preserve `frontend-hormonia/src/lib/api-client/types.ts` as the public transport/shared DTO façade for `@/lib/api-client/types`.
   - Preserve `frontend-hormonia/src/types/api.ts` as the app/UI-facing façade.
   - Do not delete `frontend-hormonia/src/lib/types/api.ts` or `frontend-hormonia/src/lib/api.ts` in S03; keep them isolated and proof-blocked for S04.

2. **Shrink `src/lib/api-client/index.ts` by extracting the remaining inline namespaces**
   - The file already follows the correct pattern for extracted domains: `createAuthApi`, `createPatientsApi`, `createDashboardApi`, etc.
   - Continue that exact pattern for the inline namespaces still embedded in `index.ts`:
     - `messages`
     - `flows`
     - `alerts`
     - `reports`
     - legacy `admin`
     - `adminUsers`
     - `ai`
     - `quiz`
     - `quizzes`
     - `notifications`
     - `physician`
   - This is the highest-value R034 move because it materially reduces the 1304-line central hotspot without changing the public entrypoint.

3. **Turn `src/lib/api-client/types.ts` into a true barrel over domain-focused type files**
   - Split the monolith into domain files that match the extracted client modules or existing namespaces.
   - Keep `types.ts` as the import-stable barrel that re-exports those domain types.
   - Deduplicate concrete collisions first, especially the duplicated `RiskAssessmentRequest` declaration.

4. **Use explicit adapters when transport and UI types differ**
   - Follow the existing precedent in `frontend-hormonia/src/lib/ai-adapters.ts`.
   - Do **not** try to force `@/types/api` to become a raw transport mirror during S03.
   - Keep UI-facing models in `@/types/api` when they serve app/view concerns; move only clearly transport-owned DTOs behind `@/lib/api-client/types` or dedicated client modules.

5. **Take the easy compatibility win, but stop before deletion**
   - Migrate `frontend-hormonia/src/hooks/usePatients.ts` from `../lib/types/api` to a canonical import path (`../lib/api-client/patients` or `@/types/api`, depending the final ownership choice).
   - After that, `src/lib/types/api.ts` becomes even more isolated, but actual deletion/removal still belongs to S04 after proof.

### Why this approach is safer than a broad rewrite

- It follows patterns the repo already uses successfully.
- It preserves the blast-radius-heavy façades from S01.
- It reduces the true hotspot files first.
- It avoids widening scope into repo-wide type unification (`R042` remains deferred).
- It keeps compatibility cleanup evidence-based instead of aesthetic.

## Hotspot Snapshot

| File | Lines | Role | Research takeaway |
|---|---:|---|---|
| `frontend-hormonia/src/lib/api-client.ts` | 75 | Public façade | Thin, keep stable. |
| `frontend-hormonia/src/lib/api-client/index.ts` | 1304 | Main client ownership hotspot | Biggest S03 code-split target. |
| `frontend-hormonia/src/lib/api-client/types.ts` | 1159 | Transport/shared DTO hotspot | Biggest S03 type-split target. |
| `frontend-hormonia/src/types/api.ts` | 900 | App/UI-facing façade | Preserve; narrow ownership gradually, don’t rewrite wholesale. |
| `frontend-hormonia/src/lib/types/api.ts` | 526 | Compatibility barrel | Only 2 exact callers; isolate now, delete later with proof. |
| `frontend-hormonia/src/lib/api.ts` | 4 | Compatibility shim | Exact repo-local callers currently 0; strong S04 candidate, not S03 deletion. |
| `frontend-hormonia/src/hooks/usePatients.ts` | 342 | Live compat caller | Only app caller of `lib/types/api`; low-risk migration target. |
| `frontend-hormonia/src/hooks/use-quiz-session.ts` | 476 | Suspicious-but-live hook | Not dead by static evidence; keep proof-blocked. |

## Key Findings And Surprises

### 1) The frontend client is only half-modularized

`frontend-hormonia/src/lib/api-client/index.ts` already composes extracted modules:

- `auth`
- `patients`
- `appointments`
- `treatments`
- `medications`
- `monthlyQuiz`
- `analytics`
- `adminV2`
- `dashboard`
- `tasks`
- `hiveMind`

But it still implements these namespaces inline:

- `messages`
- `flows`
- `alerts`
- `reports`
- `admin`
- `adminUsers`
- `ai`
- `quiz`
- `quizzes`
- `notifications`
- `physician`

This means S03 does **not** need a fresh architecture. It needs to finish the split that the code already started.

### 2) Exact import scans matter; naive grep overcounts compat usage

Exact import counts today:

- `@/lib/api-client`: **99** exact imports
- `@/lib/api-client/types`: **34** exact imports
- `@/types/api`: **50** exact imports
- `src/lib/types/api.ts`: **2** exact callers
  - `frontend-hormonia/src/hooks/usePatients.ts`
  - `frontend-hormonia/tests/unit/types-validation.test.ts`
- `src/lib/api.ts`: **0** exact repo-local callers found

Important pitfall: broad string searches for `@/lib/api` can falsely match `@/lib/api-client`. S04 deletion proof must use exact import regexes, not substring counts.

### 3) `src/types/api.ts` is not just “duplicate transport types”

`frontend-hormonia/src/types/api.ts`:

- imports selected transport types from `@/lib/api-client/types`
- re-exports them for app use
- defines many app/UI-facing models on top
- still carries some legacy or app-facing auth/client shapes

This confirms the S01 distinction: `@/types/api` is an app/UI façade, not merely a transport DTO dump.

### 4) `src/lib/types/api.ts` is a compatibility layer, but one live hook still depends on it

Exact live callers:

- `frontend-hormonia/src/hooks/usePatients.ts`
- `frontend-hormonia/tests/unit/types-validation.test.ts`

That makes `usePatients.ts` the cleanest migration target in S03, while the barrel itself remains proof-blocked for S04.

### 5) `use-quiz-session.ts` is not dead by grep alone

`use-quiz-session` only has one literal self-name match, but `useQuizSession` has many live references in the hook itself and related code paths. S01’s caution still holds: this hook needs route/e2e proof before anyone treats it as dead.

### 6) There is concrete duplicate type debt right now

`frontend-hormonia/src/lib/api-client/types.ts` defines `RiskAssessmentRequest` **twice**:

- once near the quiz/risk section
- once again near the physician section

This is a real ownership ambiguity and a good S03 cleanup target.

### 7) The client layer already depends upward on app-facing type façades

Exact `@/types/api` imports inside `src/lib/api-client/*.ts` exist in:

- `frontend-hormonia/src/lib/api-client/dashboard.ts`
- `frontend-hormonia/src/lib/api-client/analytics.ts`
- `frontend-hormonia/src/lib/api-client/monthly-quiz.ts`
- `frontend-hormonia/src/lib/api-client/patients.ts`

That means the api-client layer is **not** currently a pure lower-level transport layer. S03 should not try to purify this whole boundary in one cut.

### 8) There is already a working transport→UI adapter pattern

`frontend-hormonia/src/lib/ai-adapters.ts` maps `@/lib/api-client/types` payloads into `@/types/api` UI-friendly structures. This is the right precedent when transport and UI models differ.

### 9) Some verification files look stale relative to the current auth cutover

Two files stand out as verification-risk signals, especially in light of the failed prior attempt:

- `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx`
  - still mocks `firebase/auth` and old Firebase-driven admin login behavior.
- `frontend-hormonia/tests/hooks/usePatientImport.test.ts`
  - uses `jest.mock`, `jest.Mock`, and semicolon-heavy Jest style inside a Vitest project.

These may represent legacy verification debt rather than authoritative S03 acceptance gates. They should be treated carefully during execution.

## Don’t Hand-Roll

| Problem | Existing Solution | Why Use It |
|---|---|---|
| Splitting large API namespaces | Existing `createXApi(client)` modules such as `auth.ts`, `patients.ts`, `dashboard.ts`, `admin.ts` | Reuses the codebase’s current composition pattern and minimizes churn in `ApiClient` wiring. |
| Mapping transport models to UI-facing app models | `frontend-hormonia/src/lib/ai-adapters.ts` | Shows an accepted local pattern for keeping transport DTOs and UI models distinct without forcing one giant barrel to do both jobs. |
| Proving compat deadness | Exact import scans (`rg` with precise import regex) + focused tests + typecheck/build | Avoids false positives like `@/lib/api` matching `@/lib/api-client`, and matches S01’s evidence-before-deletion rule. |

## Existing Code And Patterns

- `frontend-hormonia/src/lib/api-client.ts` — thin public façade; keep stable.
- `frontend-hormonia/src/lib/api-client/index.ts` — central hotspot; should become mostly composition and exports, not inline namespace bodies.
- `frontend-hormonia/src/lib/api-client/dashboard.ts` — good example of `createXApi(client)` + domain-local type definitions.
- `frontend-hormonia/src/lib/api-client/admin.ts` — extracted admin module pattern already exists, even though `index.ts` still keeps a second legacy admin namespace inline.
- `frontend-hormonia/src/lib/ai-adapters.ts` — explicit adapter seam between transport DTOs and app/UI types.
- `frontend-hormonia/src/lib/types/api.ts` — compatibility barrel with low remaining live usage; isolate, don’t broaden.
- `frontend-hormonia/src/hooks/usePatients.ts` — best low-risk migration target away from the compat barrel.

## Constraints

- Preserve the stable façade imports from S01:
  - `@/lib/api-client`
  - `@/lib/api-client/types`
  - `@/types/api`
- Be careful with direct submodule imports already used in app/tests, including:
  - `@/lib/api-client/core`
  - `@/lib/api-client/auth`
  - `@/lib/api-client/dashboard`
  - `@/lib/api-client/monthly-quiz`
  - `@/lib/api-client/analytics`
  - `@/lib/api-client/admin`
- `src/lib/api-client/index.ts` currently has a naming ambiguity:
  - imported `createAdminApi` from `./admin` for `adminV2`
  - private `createAdminApi()` method for the inline legacy `admin` namespace
  - S03 should reduce, not amplify, this ambiguity.
- `src/lib/api-client` modules already import from `@/types/api`; avoid a large purity rewrite.
- `frontend-hormonia/src/lib/api-client/analytics.ts` also imports `AnalyticsPeriod` from `@/types/api-wave2`; do not broaden S03 into repo-wide type unification.
- S04 owns deletion/tombstoning of cold compatibility files after proof. S03 should isolate and migrate, not over-delete.

## Common Pitfalls

- **Using substring grep to justify deletion** — `@/lib/api` matches `@/lib/api-client`; use exact import regexes.
- **Treating `@/types/api` as a transport-only barrel** — it is app/UI-facing and already used that way.
- **Deleting `src/lib/types/api.ts` too early** — migrate `usePatients.ts` first, then leave actual removal to S04 proof.
- **Trying to “clean” every type surface at once** — `api.ts`, `api-wave2.ts`, app-facing façades, and transport DTOs already overlap; a full unification pass is beyond S03.
- **Assuming inherited tests are all authoritative** — some auth/import tests still look legacy or stale relative to the current first-party session cutover.

## Verification Guidance

### Most relevant S03 proof pack

- `cd frontend-hormonia && npm run typecheck`
- `cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts`
- `cd frontend-hormonia && npm run test -- tests/integration/auth/session-first-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts`
- `cd frontend-hormonia && npm run build`
- After migrating `usePatients.ts` off the compat barrel:
  - `cd frontend-hormonia && npm run test -- src/hooks/__tests__/usePatients.test.ts`

### Tests to treat as verification-risk / likely stale

- `cd frontend-hormonia && npm run test -- tests/integration/admin-auth-flow.test.tsx tests/components/dashboard/QuickStats.test.tsx`
  - `QuickStats` looks current and cheap.
  - `admin-auth-flow.test.tsx` still mocks Firebase-driven auth behavior and may not be the right S03 contract gate anymore.
- `cd frontend-hormonia && npm run test -- src/hooks/__tests__/usePatients.test.ts tests/hooks/usePatientImport.test.ts`
  - `usePatients` is relevant.
  - `usePatientImport.test.ts` uses Jest-style globals in a Vitest repo and should be treated as suspicious legacy coverage unless refreshed.

## Open Risks

- `frontend-hormonia/src/types/api.ts` contains app-facing auth/client interfaces that may no longer perfectly match the first-party session auth transport contract.
- Direct submodule imports mean even purely internal refactors can create hidden blast radius if files are renamed or export shapes drift.
- `src/lib/api-client/types.ts` duplication may hide additional silent type ownership conflicts beyond `RiskAssessmentRequest`.
- Cross-imports between `src/lib/api-client/*` and `@/types/api` create a risk of barrel cycles if the split is done carelessly.

## Skills Discovered

| Technology | Skill | Status |
|---|---|---|
| React | `frontend-design` | Installed locally, but mostly styling/UI-focused; tangential to this refactor. |
| React | `vercel-labs/agent-skills@vercel-react-best-practices` | Available — install with `npx skills add vercel-labs/agent-skills@vercel-react-best-practices` |
| TypeScript | `wshobson/agents@typescript-advanced-types` | Available — install with `npx skills add wshobson/agents@typescript-advanced-types` |
| TypeScript/React review | `dotneet/claude-code-marketplace@typescript-react-reviewer` | Available — install with `npx skills add dotneet/claude-code-marketplace@typescript-react-reviewer` |

## Sources

### Local code examined

- `frontend-hormonia/src/lib/api-client.ts`
- `frontend-hormonia/src/lib/api-client/index.ts`
- `frontend-hormonia/src/lib/api-client/types.ts`
- `frontend-hormonia/src/lib/api-client/core.ts`
- `frontend-hormonia/src/lib/api-client/auth.ts`
- `frontend-hormonia/src/lib/api-client/patients.ts`
- `frontend-hormonia/src/lib/api-client/admin.ts`
- `frontend-hormonia/src/lib/api-client/dashboard.ts`
- `frontend-hormonia/src/lib/api-client/analytics.ts`
- `frontend-hormonia/src/lib/api-client/monthly-quiz.ts`
- `frontend-hormonia/src/types/api.ts`
- `frontend-hormonia/src/lib/types/api.ts`
- `frontend-hormonia/src/lib/api.ts`
- `frontend-hormonia/src/lib/ai-adapters.ts`
- `frontend-hormonia/src/hooks/usePatients.ts`
- `frontend-hormonia/src/hooks/use-quiz-session.ts`

### Tests examined

- `frontend-hormonia/tests/integration/api-client.test.ts`
- `frontend-hormonia/tests/lib/api-client/core.test.ts`
- `frontend-hormonia/tests/integration/auth/session-first-cutover.test.tsx`
- `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts`
- `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx`
- `frontend-hormonia/tests/components/dashboard/QuickStats.test.tsx`
- `frontend-hormonia/src/hooks/__tests__/usePatients.test.ts`
- `frontend-hormonia/tests/hooks/usePatientImport.test.ts`
- `frontend-hormonia/tests/unit/types-validation.test.ts`

### Repo scans used

- exact import scans for:
  - `@/lib/api-client`
  - `@/lib/api-client/types`
  - `@/types/api`
  - `@/lib/types/api`
  - `@/lib/api`
- module size scan for `frontend-hormonia/src/lib/api-client/*.ts`
- duplicate type scan for `RiskAssessmentRequest`
- direct submodule import scan for `@/lib/api-client/*`
- cross-import scan between `src/lib/api-client/*` and `@/types/api`

### Skill discovery

- React results from `npx skills find "react"`
- TypeScript results from `npx skills find "typescript"`
