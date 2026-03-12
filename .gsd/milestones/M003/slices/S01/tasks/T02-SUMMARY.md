---
id: T02
parent: S01
milestone: M003
provides:
  - Backend hotspot ranking, contract guardrails, and proof-before-removal commands pinned to live repo evidence.
key_files:
  - .gsd/milestones/M003/slices/S01/S01-RESEARCH.md
  - .gsd/milestones/M003/slices/S01/verify-evidence-map.sh
  - .gsd/DECISIONS.md
patterns_established:
  - Backend evidence rows pair static repo scans (`rg`, line counts) with focused pytest proof commands before any compatibility residue can be deleted.
key_decisions:
  - Backend cleanup work must preserve three separate contracts: mapping-style session dicts, `User` adapters, and `request.state` side effects.
  - `backend-hormonia/app/routers/auth_session.py` and `firebase_uid`-dependent backend residues remain compatibility constraints for S02/S04, not early deletion targets.
observability_surfaces:
  - bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report backend
  - bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check backend
  - bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all
  - bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all
duration: ~1h
verification_result: passed
completed_at: 2026-03-12T18:10:00-03:00
blocker_discovered: false
---

# T02: Finalize backend hotspot evidence and cleanup guardrails

**Locked the backend auth/session seam to measured contracts, wrapper constraints, and command-backed deletion proof.**

## What Happened

Re-scanned the backend auth/session seam and confirmed the live blast radius behind `backend-hormonia/app/dependencies/auth_dependencies.py`: `auth_dependencies.py` is still 1579 lines, the canonical v2 auth router is 1245 lines, and the still-live legacy compatibility route `backend-hormonia/app/routers/auth_session.py` is 731 lines. The backend caller counts are still `Depends(get_current_user_from_session)=202`, `Depends(get_current_user_object_from_session)=7`, `Depends(get_current_user)=60`, and `Depends(get_admin_user)=68`, with `hardcoded_session_id_alias=9` still coming from auth-adjacent wrappers.

Updated `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` so the backend section now states the real attack order for S02: preserve the mapping-style session dict seam first, preserve the `User` adapter seam second, preserve `request.state.session_id` / `request.state.user_id` / `request.state.user_role` side effects, and only then isolate wrapper drift or legacy compatibility. The research now also names the still-live constraints explicitly: `admin/dependencies.py`, `reports.py`, `enhanced_reports.py`, and `roles/dependencies.py` are documented as wrapper drift that S02 must carry, not hand-wave away.

Filled the backend guardrail and deletion-proof sections with concrete contract language and exact commands. The cleanup guardrail matrix now distinguishes mapping-style session dict consumers from `User` consumers, pins canonical writer/reader alignment to `_create_canonical_session_cache_entry()` plus the reader path in `auth_dependencies.py`, and keeps admin/dashboard plus websocket adjacency explicit. The deletion ledger now names backend suspects (`verify_firebase_token`, `get_doctor_user`, `get_current_user_websocket`, legacy Firebase-only branches, and `auth_session.py` compatibility behavior) with exact `rg` and pytest proof commands required before removal or isolation. It also records the explicit non-candidates that stay live for now: the `permissions` field and `firebase_uid`-dependent compatibility residues.

Tightened `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` so backend verification now checks the new machine-readable anchors (`auth_session.py` line count and `Depends(get_current_user_object_from_session)` count), requires the backend contract-boundary and wrapper-drift sections, enforces the new proof-before-removal command strings, and reports the extra backend metrics. That keeps the backend research from drifting back to prose-only claims.

## Verification

- `bash -n .gsd/milestones/M003/slices/S01/verify-evidence-map.sh`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check backend` → pass
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report backend` → pass
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all` → expected fail; only open scaffold items remain in `S01-SUMMARY.md` / `S01-UAT.md`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all` → pass with drift notes only for the open scaffold items above

## Diagnostics

Run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report backend` to inspect the current backend hotspot sizes, dependency caller counts, alias drift count, and backend deletion-candidate reference counts. Run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check backend` to fail fast on missing backend anchors, missing wrapper-constraint sections, missing proof commands, or missing backend explicit non-candidates. Use the `all` scope when T03 closes the slice handoff artifacts; until then, all-scope failure should point only at open scaffold checklist items.

## Deviations

None.

## Known Issues

`bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all` is still intentionally red because `S01-SUMMARY.md` and `S01-UAT.md` remain scaffolded for T03. No backend evidence drift remained after this task.

## Files Created/Modified

- `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` — finalized backend hotspot ranking, contract boundary, wrapper drift constraints, guardrail rows, deletion ledger entries, and explicit backend non-candidates.
- `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` — added backend legacy-writer/object-adapter anchors plus stricter backend contract/proof checks and report metrics.
- `.gsd/DECISIONS.md` — appended the backend-boundary decision so S02/S04 inherit the same contract split.
