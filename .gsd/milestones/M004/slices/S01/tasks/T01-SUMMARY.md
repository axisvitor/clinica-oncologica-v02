---
id: T01
parent: S01
milestone: M004
provides:
  - Scoped runtime-residue guardrails with an allowlisted boundary, executable verifier, and regression harness for later M004 cleanup slices.
key_files:
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json
  - .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh
  - backend-hormonia/tests/unit/test_runtime_residue_guard.py
key_decisions:
  - The runtime residue boundary is enforced per category and per scope, with explicit file anchors so cleanup must update the allowlist instead of silently drifting.
patterns_established:
  - Slice-local shell verifier delegates JSON parsing and repo scanning to embedded Python, keeping report/check behavior deterministic and temp-fixture friendly.
  - Guard regressions run the real shell script in subprocesses with overrideable repo/allowlist env vars rather than importing implementation details.
observability_surfaces:
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report <backend|frontend|all>`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check <backend|frontend|all>`
  - `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py`
duration: ~2h30m
verification_result: passed
completed_at: 2026-03-14T00:19:36-03:00
blocker_discovered: false
---

# T01: Build the scoped runtime-residue verifier and regression harness

**Added the scoped runtime-residue allowlist, shipped the `--report` / `--check` verifier, and locked it down with subprocess regression tests that prove approved residue passes while new header/bearer/query/comment drift fails.**

## What Happened

Built `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` as the machine-readable contract for the six approved residue classes: `firebase_uid`, root legacy `/session/*`, `X-Session-ID`, session-as-Bearer fallback, websocket `session_id` query fallback, and Firebase narrative residue. The allowlist is split by `backend` and `frontend` scopes and carries explicit out-of-scope exclusions for schema/model residue, historical docs/tests, and unrelated vendor/public session strings.

Implemented `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` with `--report` and `--check` modes plus `backend`, `frontend`, and `all` scope selection. The script scans the current repo state from category roots, counts live residue per file, emits approved category/file/count rows in report mode, and fails in check mode with `category=... unexpected_file=...` or `category=... moved_hotspot=...` messages when the boundary drifts. Output is redaction-safe: it reports only categories, paths, counts, and anchor labels.

Added `backend-hormonia/tests/unit/test_runtime_residue_guard.py` as a black-box regression harness. The tests create temp repos and temp allowlists, run the real shell verifier via subprocess, prove approved fixtures pass, prove unallowlisted header/bearer/query/comment residue fails with useful messages, verify scope separation, and verify moved-hotspot detection by anchor label.

As part of the pre-flight repair, updated `S01-PLAN.md` so the slice verification list includes an explicit failure-path regression command for the new guard.

## Verification

- `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py` ✅
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all` ✅
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` ✅

## Diagnostics

- Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` to inspect backend-approved residue by category/file/count.
- Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend` to inspect frontend-approved residue by category/file/count.
- Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` to fail on unexpected files or moved approved hotspots.
- Read `backend-hormonia/tests/unit/test_runtime_residue_guard.py` for the expected failure messages and the temp-fixture invocation pattern.

## Deviations

- Added an explicit failure-path verification command to `.gsd/milestones/M004/slices/S01/S01-PLAN.md` before implementation because the pre-flight guard flagged an observability gap in the slice verification block.

## Known Issues

- None.

## Files Created/Modified

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — category/scope allowlist with approved hotspots and explicit exclusions.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — executable scoped residue verifier with `--report` / `--check` and drift messaging.
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py` — subprocess regression harness for approved residue, forbidden residue, scope handling, and moved hotspots.
- `.gsd/milestones/M004/slices/S01/S01-PLAN.md` — added the explicit failure-path verification step and marked T01 complete.
