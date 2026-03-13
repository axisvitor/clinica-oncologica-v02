---
estimated_steps: 5
estimated_files: 8
---

# T03: Extract the quiz/clinical namespaces and turn `types.ts` into a domain barrel

**Slice:** S03 — Frontend Client/Type Surface Refactor
**Milestone:** M003

## Description

Finish the main ownership split by moving the remaining quiz/clinical client namespaces out of `index.ts` and breaking the transport-type monolith into domain files behind the stable `@/lib/api-client/types` barrel. This is the task that closes the biggest type-surface ambiguity, especially around `RiskAssessmentRequest`.

## Steps

1. Extract the remaining inline `ai`, `quiz`, `quizzes`, and `physician` namespaces into dedicated `createXApi(client)` modules and rewire `src/lib/api-client/index.ts` to compose them.
2. Create domain-focused type files under `frontend-hormonia/src/lib/api-client/types/` that align with the split modules, then convert `frontend-hormonia/src/lib/api-client/types.ts` into the stable re-export barrel over those domains.
3. Deduplicate `RiskAssessmentRequest` by choosing one canonical transport owner and updating the barrel exports so callers still import it from `@/lib/api-client/types`.
4. Preserve `frontend-hormonia/src/types/api.ts` as the app/UI-facing façade and use explicit adapter seams where transport and UI models differ instead of forcing a repo-wide type rewrite.
5. Run the structural contract tests plus the existing api-client suites to confirm the client/type split stays compatible.

## Must-Haves

- [ ] All remaining inline namespaces leave `src/lib/api-client/index.ts`, and the file becomes composition-first rather than another partial hotspot.
- [ ] `src/lib/api-client/types.ts` is primarily barrel glue, `RiskAssessmentRequest` has one transport owner, and no new `@/types/api` cycle is introduced.

## Verification

- `cd frontend-hormonia && npm run test -- tests/lib/api-client/index-split.contract.test.ts tests/unit/types/api-client-types-barrel.contract.test.ts tests/integration/api-client.test.ts tests/lib/api-client/core.test.ts`
- `cd frontend-hormonia && npm run typecheck`

## Observability Impact

- Signals added/changed: Type-surface regressions now appear as barrel contract failures or typecheck errors instead of being buried inside one giant `types.ts` file.
- How a future agent inspects this: Re-run the focused Vitest/typecheck commands and inspect the domain type files under `src/lib/api-client/types/` for the missing or cyclic owner.
- Failure state exposed: duplicate transport ownership, missing barrel exports, and new type-cycle regressions become localized failures.

## Inputs

- `frontend-hormonia/src/lib/api-client/types.ts` — current transport/shared DTO hotspot that still owns multiple domains and duplicate `RiskAssessmentRequest` declarations.
- `frontend-hormonia/src/lib/ai-adapters.ts` — the existing local precedent for keeping transport DTOs and UI-facing models distinct.
- `frontend-hormonia/src/types/api.ts` — the app/UI-facing façade that must stay stable even as transport ownership moves behind it.

## Expected Output

- `frontend-hormonia/src/lib/api-client/ai.ts`, `quiz.ts`, `quizzes.ts`, and `physician.ts` — dedicated client modules replacing the last inline namespace bodies.
- `frontend-hormonia/src/lib/api-client/types.ts` plus new domain files under `frontend-hormonia/src/lib/api-client/types/` — a stable barrel over focused transport type owners with one canonical `RiskAssessmentRequest` export.
