---
id: T01
parent: S01
milestone: M003
provides:
  - Executable slice verifier plus scaffolded summary/UAT artifacts that later tasks must complete.
key_files:
  - .gsd/milestones/M003/slices/S01/verify-evidence-map.sh
  - .gsd/milestones/M003/slices/S01/S01-RESEARCH.md
  - .gsd/milestones/M003/slices/S01/S01-SUMMARY.md
  - .gsd/milestones/M003/slices/S01/S01-UAT.md
key_decisions:
  - The verifier reads machine-friendly anchors from research instead of trusting prose-only counts.
  - All-scope verification intentionally stays red while scaffold checklist items remain open in the slice handoff artifacts.
patterns_established:
  - Boundary scopes (`backend`, `frontend`, `all`) let later tasks verify only the surface they changed.
observability_surfaces:
  - bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report <backend|frontend|all>
  - bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check <backend|frontend|all>
duration: ~1h
verification_result: passed
completed_at: 2026-03-12T22:58:49Z
blocker_discovered: false
---

# T01: Add an executable evidence verifier and artifact scaffolds

**Added the executable evidence-map verifier, refreshed the research artifact with deterministic anchors, and scaffolded the slice handoff pack.**

## What Happened

Built `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` as a rerunnable bash verifier with `--report` / `--check` modes and `backend` / `frontend` / `all` scopes. The script derives live repo evidence from `rg`, `wc`, and a small `python3` duplicate-export scan instead of trusting pasted numbers. It emits only static repo metadata: file paths, counts, symbol names, and verification commands.

Updated `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` so the verifier has deterministic targets: explicit hotspot sections, verifier-anchor lines for live counts, deletion-candidate anchors, explicit non-candidates, and a downstream command pack. Created `.gsd/milestones/M003/slices/S01/S01-SUMMARY.md` and `.gsd/milestones/M003/slices/S01/S01-UAT.md` as scaffolds with the final command lists and open checklist items that T03 must close.

Fixed one real harness bug during execution: backticks in verifier string checks were being interpreted by Bash as command substitution. Rewrote the string-matching portion around a `require_exact` helper so the verifier now checks literal markdown anchors safely.

## Verification

- `bash -n .gsd/milestones/M003/slices/S01/verify-evidence-map.sh`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check backend` → pass
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check frontend` → pass
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all` → pass with drift notes only for open scaffold checklist items in `S01-SUMMARY.md` / `S01-UAT.md`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all` → expected fail; failures name the remaining open scaffold items instead of any shell/harness error

## Diagnostics

Run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report <backend|frontend|all>` to inspect current hotspot line counts, caller/import blast radius, duplicate export names, candidate-reference counts, and open scaffold counts. Run `--check <scope>` to get a non-zero exit with named missing/drifting anchors or open scaffold checklist items.

## Deviations

None.

## Known Issues

`--check all` is intentionally still red because `S01-SUMMARY.md` and `S01-UAT.md` contain open scaffold checklist items that T03 must replace with the real handoff pack.

## Files Created/Modified

- `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` — executable verifier with scoped report/check modes and live repo scans.
- `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` — refreshed with deterministic headings, anchors, non-candidates, and exact verification commands.
- `.gsd/milestones/M003/slices/S01/S01-SUMMARY.md` — scaffolded slice summary with handoff sections and command pack.
- `.gsd/milestones/M003/slices/S01/S01-UAT.md` — scaffolded artifact-driven UAT with reviewer checklist and command pack.
- `.gsd/DECISIONS.md` — appended the verifier/scaffold failure-surface decision for downstream tasks.
- `.gsd/milestones/M003/slices/S01/S01-PLAN.md` — marked T01 complete.
- `.gsd/STATE.md` — advanced next action to T02.
