---
estimated_steps: 5
estimated_files: 5
---

# T02: Publish the official-runtime residue map and slice handoff

**Slice:** S01 — Guardrails do corte canônico de runtime
**Milestone:** M004

## Description

Close S01 by making the scoped residue boundary durable for the next slices. This task reconciles the verifier and allowlist with the research artifact, then writes the slice summary and reviewer checklist so S02–S05 can remove residue from one explicit map instead of reopening discovery.

## Steps

1. Update `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` with the finalized category-by-category residue map, explicitly separating official runtime surfaces, retained compatibility islands, and out-of-scope exclusions.
2. Record the approved surface list for each residue class in the research artifact using the same categories and scope names as `runtime-residue-allowlist.json` and `verify-runtime-residue.sh`.
3. Write `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md` with the downstream cut order for S02–S05, the inherited verifier commands, and the exact surfaces that later slices must remove versus temporarily preserve.
4. Write `.gsd/milestones/M004/slices/S01/S01-UAT.md` with a reviewer checklist that asks whether any new residue appeared, any approved hotspot moved without an allowlist update, or any out-of-scope strings were accidentally pulled into the official failure surface.
5. Re-run `--report all` and `--check all`, reconciling any mismatch until the verifier, allowlist, research, summary, and UAT all describe the same boundary.

## Must-Haves

- [ ] `S01-RESEARCH.md` names the approved hotspot files for all six residue classes and the explicit exclusions that keep the guard actionable.
- [ ] `S01-SUMMARY.md` tells S02–S05 exactly which surfaces to cut next and which verifier commands they inherit.
- [ ] `S01-UAT.md` gives a reviewer a concrete checklist for spotting new residue or stale allowlist bookkeeping.
- [ ] The published artifacts use the same category names and scope assumptions as the verifier and allowlist.
- [ ] The final verifier pass is green against the completed slice handoff pack.

## Verification

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`

## Observability Impact

- Signals added/changed: the slice gains a durable handoff pack that turns the verifier output into an explainable map of approved residue, exclusions, and next-slice obligations.
- How a future agent inspects this: read `S01-SUMMARY.md` for the condensed handoff, `S01-RESEARCH.md` for the full residue map, `S01-UAT.md` for review criteria, and rerun `verify-runtime-residue.sh --report all` when drift is suspected.
- Failure state exposed: stale allowlist bookkeeping, newly live runtime residue, or widened failure scope becomes visible as a mismatch between the report output and the published slice artifacts.

## Inputs

- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` — existing research baseline that already identifies the live residue families and the intended scope boundary.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — approved residue boundary produced by T01.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — executable report/check surface produced by T01.
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py` — regression proof that the verifier behavior being documented is actually enforced.

## Expected Output

- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` — finalized residue map aligned with the allowlist and verifier.
- `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md` — downstream execution handoff for S02–S05.
- `.gsd/milestones/M004/slices/S01/S01-UAT.md` — reviewer checklist for residue-map drift and scope discipline.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` and `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — reconciled, if needed, so the published docs and executable guard describe the same boundary.
