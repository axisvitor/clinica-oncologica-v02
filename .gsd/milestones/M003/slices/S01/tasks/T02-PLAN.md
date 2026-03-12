---
estimated_steps: 5
estimated_files: 7
---

# T02: Finalize backend hotspot evidence and cleanup guardrails

**Slice:** S01 — Evidence Map And Cleanup Guardrails
**Milestone:** M003

## Description

Turn the backend auth/session research into a hard boundary for S02 and S04. This task locks the real backend blast radius, the contracts that must not drift, and the proof required before any backend compatibility residue can be removed or isolated.

## Steps

1. Re-run the backend repo scans around `backend-hormonia/app/dependencies/auth_dependencies.py` and its auth-adjacent wrappers to confirm hotspot size, direct caller counts, wrapper drift, cookie alias usage, and any still-live compatibility reads.
2. Update the backend ranking and rationale in `S01-RESEARCH.md`, keeping the attack order explicit: backend auth/session first, frontend client/type second, adjacent critical flows/webhook hotspots guarded but out of scope for early refactor.
3. Fill the backend cleanup guardrail matrix with the exact contracts and verification commands for the session dict surface, `User` surface, canonical auth writer/reader alignment, admin/dashboard continuity, and websocket auth adjacency.
4. Fill the backend deletion-candidate ledger with current evidence, proof-before-removal requirements, and explicit non-candidates such as the still-read `permissions` field and any `firebase_uid`-dependent residues that are not yet dead.
5. Run the verifier and repair any mismatch until the backend sections are complete and the report output matches the documented scan results.

## Must-Haves

- [ ] The research keeps mapping-style session dict users and `User`-returning auth dependencies distinct instead of treating them as interchangeable.
- [ ] Backend guardrails include `request.state.user_id`, `request.state.user_role`, and `request.state.session_id` side effects as part of the preserved contract.
- [ ] The deletion ledger names concrete backend suspects and the exact proof commands required before removal or isolation.
- [ ] Adjacent wrapper drift (`admin`, `reports`, `enhanced_reports`, `roles`) is documented as a constraint on S02, not hand-waved away.

## Verification

- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check backend`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report backend`

## Observability Impact

- Signals added/changed: the verifier report now exposes backend hotspot size, dependency caller counts, and candidate-reference counts tied to the auth/session seam via the `backend` scope.
- How a future agent inspects this: consult the backend sections of `S01-RESEARCH.md` and rerun `verify-evidence-map.sh --report backend` to see whether the recorded blast radius still matches the repo.
- Failure state exposed: missing backend guardrail rows, missing proof commands, or newly live backend references show up as named verifier failures before refactor work starts.

## Inputs

- `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` — baseline hotspot findings and initial candidate list from slice research.
- `backend-hormonia/app/dependencies/auth_dependencies.py` plus auth-adjacent wrapper modules — the concrete backend surfaces the final guardrails must be derived from.

## Expected Output

- `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` — finalized backend hotspot ranking, guardrail matrix rows, and backend deletion-candidate ledger entries.
- `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` — updated, if needed, so backend evidence checks and report output match the finalized research contract.
