---
id: T03
parent: S02
milestone: M004
provides:
  - Post-S02 backend residue bookkeeping aligned to the converged runtime, plus the slice summary/UAT handoff that separates finished backend identity convergence from later transport retirement work.
key_files:
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json
  - .gsd/milestones/M004/slices/S01/S01-RESEARCH.md
  - .gsd/milestones/M004/slices/S01/S01-SUMMARY.md
  - .gsd/milestones/M004/slices/S01/S01-UAT.md
  - .gsd/milestones/M004/slices/S02/S02-SUMMARY.md
  - .gsd/milestones/M004/slices/S02/S02-UAT.md
key_decisions:
  - Treat the S01 residue guard as a semantic contract: post-S02 helper hotspots that remain in the report but only as compatibility fallback/passthrough residue must be relabeled and documented even when backend counts do not drop.
patterns_established:
  - Close a convergence slice with one pass that reconciles the live verifier, the prior-slice boundary artifacts, and the current-slice handoff against the same final proof run.
observability_surfaces:
  - `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_dependency_override_contract.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py tests/integration/test_local_auth_core_flow.py`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
  - `.gsd/milestones/M004/slices/S02/S02-SUMMARY.md`
  - `.gsd/milestones/M004/slices/S02/S02-UAT.md`
duration: ~45m
verification_result: passed
completed_at: 2026-03-14T10:12:00-03:00
blocker_discovered: false
---

# T03: Shrink the backend residue boundary and publish the S02 handoff

**Reconciled the S01 backend residue contract with the converged helper runtime, then published the S02 summary/UAT handoff so later slices inherit an honest transport-vs-compatibility map.**

## What Happened

Started from the live backend residue report after T02 and confirmed the key closeout fact: the verifier stayed green and the backend category inventory did **not** shrink numerically. The post-T02 report still shows `firebase_uid` in 14 backend files / 133 matching lines, `root_legacy_session` in 2 / 8, `x_session_id` in 16 / 28, `session_bearer_fallback` in 8 / 11, `websocket_session_id_query` in 1 / 4, and `firebase_narrative` in 1 / 29. That ruled out a bookkeeping-only delete/update pass and pointed at the real task: republish the boundary so it describes what those surviving hits mean after helper convergence.

Updated `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` accordingly. The `firebase_uid` category description now describes compatibility-oriented residue instead of generic runtime dependence, and the surviving helper anchors in `auth_session_cache.py`, `auth_session_contract.py`, `auth_session_shared.py`, and `user_cache_shared.py` were relabeled as compatibility fallback/passthrough hotspots. The file inventory stayed intact because the runtime still preserves those literals for compatibility paths, but the allowlist now matches the post-S02 helper reality.

Then updated the paired S01 handoff artifacts. `S01-RESEARCH.md` now explains that the canonical backend helper family is already green and that the flat `firebase_uid` count reflects fallback-only helper residue plus deliberate legacy/admin seams, not happy-path identity selection. `S01-SUMMARY.md` now calls out the post-S02 interpretation directly and shifts follow-up ownership to S03/S04/S05. `S01-UAT.md` now warns reviewers that a green backend report after S02 does not mean `firebase_uid` still drives the canonical helper path.

Finally wrote `.gsd/milestones/M004/slices/S02/S02-SUMMARY.md` and `.gsd/milestones/M004/slices/S02/S02-UAT.md`. Those artifacts separate the work cleanly: S02 finished backend identity convergence; S03 still owns frontend transport emission cutover; S04 still owns retirement of root `/session/*`, `X-Session-ID`, session-as-Bearer, and websocket query fallback on the backend; S05 still owns the remaining adjacent/admin `firebase_uid` and Firebase narrative cleanup.

## Verification

Ran and passed:

- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_dependency_override_contract.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py tests/integration/test_local_auth_core_flow.py`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`

Observed results:

- focused helper proof + acceptance pack: passed (`32 passed`)
- backend residue report: passed (`RESULT: --report backend OK`)
- backend residue check: passed (`RESULT: --check backend OK`)
- known `pytest_asyncio` loop-scope deprecation warning still appeared and remained non-blocking

Confirmed must-haves:

- The S01 backend allowlist moved only where the converged runtime actually changed: the `firebase_uid` category meaning and surviving helper-anchor labels now describe compatibility-only fallback/passthrough behavior, while the raw file inventory stayed unchanged.
- S01 artifacts and S02 artifacts now use the same category names, scope assumptions, and remaining-legacy story.
- `S02-SUMMARY.md` clearly separates finished backend identity convergence from later transport retirement work.
- `S02-UAT.md` gives a concrete replay checklist for the backend proof and for spotting stale residue bookkeeping later.
- The final backend proof pack and S01 backend residue guard are green together.

## Diagnostics

Use these when revisiting the slice later:

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` — live backend residue inventory after S02.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend` — fastest check for stale allowlist/docs drift.
- `.gsd/milestones/M004/slices/S02/S02-SUMMARY.md` — condensed statement of what S02 finished vs. what S03/S04/S05 still own.
- `.gsd/milestones/M004/slices/S02/S02-UAT.md` — reviewer checklist for replaying the proof and interpreting flat backend residue counts correctly.

## Deviations

None.

## Known Issues

- The backend residue report still shows the same raw `firebase_uid` file/line count after S02; that is expected because compatibility literals remain. Future reviewers must read the handoff before assuming the count means the backend helper path is still Firebase-shaped.
- Root `/session/*`, `X-Session-ID`, session-as-Bearer, websocket query fallback, and Firebase narrative residue are still live by design and remain later-slice work.

## Files Created/Modified

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — updated `firebase_uid` description and helper-anchor labels to reflect post-S02 compatibility-only residue.
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` — updated backend residue interpretation and cut ownership after helper convergence.
- `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md` — updated condensed guardrail handoff for the post-S02 backend boundary.
- `.gsd/milestones/M004/slices/S01/S01-UAT.md` — updated reviewer notes for interpreting flat backend residue counts after semantic helper shrinkage.
- `.gsd/milestones/M004/slices/S02/S02-SUMMARY.md` — published the completed slice handoff.
- `.gsd/milestones/M004/slices/S02/S02-UAT.md` — published the slice replay checklist.
- `.gsd/milestones/M004/slices/S02/tasks/T03-SUMMARY.md` — recorded the closeout work, verification, and durable handoff.
- `.gsd/milestones/M004/slices/S02/S02-PLAN.md` — marked T03 complete.
- `.gsd/milestones/M004/M004-ROADMAP.md` — marked S02 complete at the milestone level.
- `.gsd/STATE.md` — advanced the next action to the post-S02 reassessment.
- `.gsd/DECISIONS.md` — recorded the semantic-boundary interpretation rule for future residue shrinkage.
