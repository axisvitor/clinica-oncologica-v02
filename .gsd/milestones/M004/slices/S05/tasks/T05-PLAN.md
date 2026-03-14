---
estimated_steps: 4
estimated_files: 4
---

# T05: Republish the post-S05 residue boundary and slice handoff

**Slice:** S05 — Resíduo funcional de Firebase removido do runtime adjacente
**Milestone:** M004

## Description

Turn the finished cleanup into a durable boundary contract. S05 changes what the runtime is allowed to contain, but the verifier and its handoff artifacts are the only thing that make that boundary replayable for the next slice. This task republishes that boundary after the runtime, audit/docs, and adjacent type work are actually done.

## Steps

1. Rerun the S01 residue report after T01–T04 and compare the surviving hotspots to the current allowlist vocabulary instead of assuming the old approvals still make sense.
2. Update `runtime-residue-allowlist.json` to remove, relabel, or tighten approved Firebase hotspots so it matches the post-S05 runtime honestly.
3. Republish `S01-RESEARCH.md`, `S01-SUMMARY.md`, and `S01-UAT.md` so the handoff narrative explains what changed in S05 and what explicitly remains for M005 and S06.
4. Close the loop by running the report/check gate again and making sure the published boundary matches the focused S05 proof packs.

## Must-Haves

- [ ] The S01 residue report/check describe the post-S05 runtime boundary honestly.
- [ ] Removed or narrowed Firebase hotspots are no longer left approved in the allowlist by inertia.
- [ ] The S01 handoff artifacts explain the remaining boundary in the same vocabulary used by the verifier.
- [ ] M005 schema debt and S06 assembled-stack proof remain clearly separated from S05 in the published handoff.

## Verification

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`

## Observability Impact

- Signals added/changed: the residue guard becomes the durable regression surface for any surviving `firebase_uid` or Firebase-narrative hotspots after S05.
- How a future agent inspects this: rerun the report/check commands and compare the flagged category/file pairs against the republished S01 handoff artifacts.
- Failure state exposed: stale allowlist bookkeeping, newly reintroduced hotspots, or mismatched slice handoff narrative fail as explicit verifier drift instead of silent documentation rot.

## Inputs

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — current approved hotspot map from the pre-S05 boundary.
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md`, `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md`, `.gsd/milestones/M004/slices/S01/S01-UAT.md` — current handoff narrative the next slice will trust.
- T01–T04 outputs — the actual post-cut runtime, audit/docs, and adjacent type changes that the verifier must now describe honestly.

## Expected Output

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — updated approved hotspot map reflecting the post-S05 runtime.
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` — research handoff updated for the reduced Firebase residue boundary.
- `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md` — condensed verifier handoff aligned to the S05 result.
- `.gsd/milestones/M004/slices/S01/S01-UAT.md` — reviewer guidance updated so future replay interprets the S05 boundary correctly.
