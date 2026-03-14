---
id: T02
parent: S01
milestone: M004
provides:
  - Published the finalized residue map, downstream cut-order handoff, and reviewer checklist that keep the S01 runtime boundary readable and enforceable for S02–S05.
key_files:
  - .gsd/milestones/M004/slices/S01/S01-RESEARCH.md
  - .gsd/milestones/M004/slices/S01/S01-SUMMARY.md
  - .gsd/milestones/M004/slices/S01/S01-UAT.md
  - .gsd/milestones/M004/slices/S01/S01-PLAN.md
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json
  - .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh
key_decisions:
  - The published handoff uses the verifier's exact category ids and `backend` / `frontend` scope names so later slices cannot drift into alternate naming or hidden scope changes.
  - Boundary shrinkage is not complete until the allowlist, research, summary, and UAT all move together; a green script alone is not enough.
patterns_established:
  - Close a guardrail slice by pairing the executable gate with a readable hotspot map and a reviewer checklist that turns future cleanup into bookkeeping plus proof instead of fresh discovery.
  - Keep at least one explicit failure-path proof in the slice verification list so moved anchors and unexpected residue stay inspectable, not just failing exit codes.
observability_surfaces:
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all
  - cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k unexpected_residue
  - cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k moved_hotspot_reports_anchor_name
  - .gsd/milestones/M004/slices/S01/S01-RESEARCH.md
  - .gsd/milestones/M004/slices/S01/S01-UAT.md
duration: ~1h10m
verification_result: passed
completed_at: 2026-03-14T00:39:53-03:00
blocker_discovered: false
---

# T02: Publish the official-runtime residue map and slice handoff

**Published the finalized official-runtime residue map, downstream cut order, and reviewer checklist so S02–S05 can shrink one shared boundary contract instead of reopening discovery.**

## What Happened

Updated `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` from a recommendation document into the authoritative readable map for the executed boundary. It now mirrors the final `--report all` output using the exact verifier category ids and scope names, lists the approved hotspot files for all six residue classes, separates official runtime surfaces from retained compatibility islands, and records the three explicit out-of-scope exclusion families from `runtime-residue-allowlist.json`.

Wrote `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md` as the downstream cut-order handoff for S02–S05. The summary compresses the slice into the one rule later slices need to follow: use `--report all` / `--check all` as the executable source of truth, but update the readable handoff pack in the same change whenever the boundary changes.

Wrote `.gsd/milestones/M004/slices/S01/S01-UAT.md` as an artifact-driven reviewer checklist. It asks whether new residue appeared, whether an approved hotspot moved without a boundary update, and whether any out-of-scope strings were accidentally pulled into the official failure surface.

During the pre-flight repair, updated `.gsd/milestones/M004/slices/S01/S01-PLAN.md` so the slice verification block includes an explicit diagnostic/failure-path command (`-k moved_hotspot_reports_anchor_name`) rather than only green-path reruns.

## Verification

Passed on final rerun:
- `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py`
- `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k unexpected_residue`
- `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k moved_hotspot_reports_anchor_name`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
  - ended with `RESULT: --report all OK`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
  - ended with `RESULT: --check all OK`

## Diagnostics

- Use `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all` to inspect the approved live boundary by category/file/count.
- Use `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` to catch new residue or moved approved hotspots.
- Use `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k unexpected_residue` to confirm the guard still reports `unexpected_file=` failures clearly.
- Use `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k moved_hotspot_reports_anchor_name` to confirm moved anchors still surface as `moved_hotspot=... anchor=...`.
- Read `S01-RESEARCH.md` for the full hotspot map and `S01-UAT.md` for the reviewer checklist.

## Deviations

- Added the explicit moved-hotspot diagnostic test to `S01-PLAN.md` during the required pre-flight observability repair.

## Known Issues

- Backend pytest still emits the existing `pytest_asyncio` loop-scope deprecation warning during the guard regression suite. It is non-blocking and unchanged by this task.

## Files Created/Modified

- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` — finalized residue map aligned with the allowlist and live report output.
- `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md` — downstream slice handoff and cut order for S02–S05.
- `.gsd/milestones/M004/slices/S01/S01-UAT.md` — reviewer checklist for new residue, moved hotspots, and scope-discipline drift.
- `.gsd/milestones/M004/slices/S01/S01-PLAN.md` — added the explicit diagnostic verification command and marked T02 complete.
- `.gsd/milestones/M004/slices/S01/tasks/T02-SUMMARY.md` — recorded the durable closeout for this unit.
- `.gsd/STATE.md` — updated quick-glance state after slice completion.
