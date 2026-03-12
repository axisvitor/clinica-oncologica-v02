---
estimated_steps: 5
estimated_files: 8
---

# T03: Finalize frontend hotspot evidence and close the handoff pack

**Slice:** S01 — Evidence Map And Cleanup Guardrails
**Milestone:** M003

## Description

Finish the slice by making the frontend client/type seam and cleanup candidates just as explicit as the backend side, then package the results into handoff artifacts that let S02–S05 start from a fixed evidence base instead of reopening discovery.

## Steps

1. Re-scan the frontend public façades and type surfaces around `src/lib/api-client.ts`, `src/lib/api-client/index.ts`, `src/lib/api-client/types.ts`, `src/types/api.ts`, and `src/lib/types/api.ts` to confirm import counts, duplicate export names, and remaining compatibility consumers.
2. Update the frontend ranking, guardrail matrix rows, and deletion-candidate ledger in `S01-RESEARCH.md`, preserving the distinction between stable façades, internal ownership modules, and legacy compatibility aliases.
3. Write `S01-SUMMARY.md` with the ranked execution order, the frontend/backend non-negotiable contracts, explicit non-candidates, and the exact proof commands S02–S05 inherit.
4. Write `S01-UAT.md` with a reviewer checklist that asks whether the attack order is sensible, the guardrails protect visible contracts, and no cleanup candidate is marked dead without concrete proof.
5. Run the verifier in both `--check` and `--report` modes and reconcile any drift so the final slice handoff is consistent and rerunnable.

## Must-Haves

- [ ] The research clearly separates the stable public façade `@/lib/api-client` from internal client/type ownership modules and legacy compatibility aliases.
- [ ] Frontend deletion candidates and proof gates are explicit for `src/lib/api.ts`, `src/lib/types/api.ts`, `src/hooks/use-quiz-session.ts`, and duplicate transport/app type declarations.
- [ ] `S01-SUMMARY.md` and `S01-UAT.md` let the next slices start without redoing repo-wide frontend discovery work.
- [ ] The final verifier pass is green and the report agrees with the written handoff artifacts.

## Verification

- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`

## Observability Impact

- Signals added/changed: the verifier report now exposes frontend façade import counts, duplicate-type counts, and compatibility-consumer counts alongside the backend evidence when run with `all` scope.
- How a future agent inspects this: read `S01-SUMMARY.md` for the condensed handoff, `S01-UAT.md` for review criteria, and rerun `verify-evidence-map.sh --report all` to confirm the evidence still matches the repo.
- Failure state exposed: drift in public façade ownership, missing proof gates for frontend cleanup candidates, or incomplete handoff artifacts fail loudly before S03/S04 starts.

## Inputs

- `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` — backend-complete research artifact that still needs frontend finalization and closeout packaging.
- `frontend-hormonia/src/lib/api-client.ts`, `frontend-hormonia/src/lib/api-client/index.ts`, `frontend-hormonia/src/lib/api-client/types.ts`, `frontend-hormonia/src/types/api.ts`, and `frontend-hormonia/src/lib/types/api.ts` — the concrete frontend seams the handoff must preserve.

## Expected Output

- `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` — finalized frontend hotspot/guardrail/candidate sections aligned with the verifier.
- `.gsd/milestones/M003/slices/S01/S01-SUMMARY.md` and `.gsd/milestones/M003/slices/S01/S01-UAT.md` — complete handoff and review artifacts for the rest of M003.
- `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` — final green verifier for the full slice evidence contract.
