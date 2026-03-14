---
id: S01
parent: M004
milestone: M004
provides:
  - Executable guardrails for official-runtime auth/session residue; after S03 the frontend scope is zero-approved and only backend-owned residue remains live inside the approved boundary.
requires: []
affects:
  - M004/S04
  - M004/S05
  - M004/S06
key_files:
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json
  - .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh
  - .gsd/milestones/M004/slices/S01/S01-RESEARCH.md
  - .gsd/milestones/M004/slices/S01/S01-UAT.md
  - backend-hormonia/tests/unit/test_runtime_residue_guard.py
key_decisions:
  - The official-runtime residue boundary remains enforced per category and per scope, but after S03 the frontend scopes stay present with empty approved sets so they act as reintroduction guards instead of disappearing.
  - Published handoff artifacts reuse the verifier's exact category ids and backend/frontend scope names so later slices cannot drift into alternate naming.
  - Boundary shrinkage is only complete when the allowlist, research, summary, UAT, and current-slice handoff move together with green report/check output.
patterns_established:
  - Slice-local shell verification delegates deterministic scanning and JSON parsing to embedded Python while remaining black-box testable through subprocess pytest.
  - Guardrail slices close with both an executable gate and a readable hotspot map so later cleanup work updates one boundary contract instead of reopening discovery.
  - Empty approved sets are valid state when a scope has converged; keep the roots and let the verifier police reintroduction.
observability_surfaces:
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all
  - cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k unexpected_residue
  - cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k moved_hotspot_reports_anchor_name
drill_down_paths:
  - .gsd/milestones/M004/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S01/tasks/T02-SUMMARY.md
duration: ~3h40m
verification_result: passed
completed_at: 2026-03-14T00:45:23-03:00
---

# S01: Guardrails do corte canônico de runtime

**Scoped runtime-residue guardrails now freeze a backend-only live residue boundary; after S03 the `frontend` scope reports `no approved residue` and exists only as a reintroduction guard.**

## What Happened

S01 turned the runtime-cut discussion into an executable boundary. The slice added `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` as the machine-readable contract for the six residue classes that still matter to the official runtime: `firebase_uid`, root legacy `/session/*`, `X-Session-ID`, session-as-Bearer fallback, websocket `session_id` query fallback, and Firebase narrative residue. On top of that contract, the slice shipped `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`, which reports approved residue by scope/category/file/count and fails on drift with named diagnostics like `unexpected_file=` and `moved_hotspot=`.

S02 already republished the handoff to reflect backend semantic shrinkage without lowering raw backend counts. S03 completed the frontend side of that story. The official frontend loop no longer emits `X-Session-ID`, `Authorization: Bearer <session_id>`, websocket `session_id` query fallback, browser `session_id` storage/rehydration, or Firebase-shaped auth/admin narrative baggage. The latest report now shows `frontend` as `no approved residue`; every approved residue class is backend-owned.

The allowlist and readable handoff were updated to encode that new truth directly. The frontend scope roots were kept in place with empty approved sets so later work still fails if those seams reappear. `S01-RESEARCH.md`, this summary, and `S01-UAT.md` now tell the same post-S03 story as the verifier: S03 is done on the official frontend path; S04 owns backend transport retirement and root `/session/*`; S05 owns the remaining backend/adjacent Firebase residue; S06 owns assembled-stack proof.

## Verification

Latest republish reruns confirmed the new boundary state:

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`

Expected diagnostic surfaces remain authoritative:

- `--report frontend` prints `no approved residue`.
- `--report all` prints backend category/file/count rows and no approved frontend rows.
- `--check frontend` / `--check all` fail if frontend hotspots reappear or approved anchors drift.
- The subprocess pytest harness remains the trusted failure-path proof for `unexpected_file=` and `moved_hotspot=` behavior.

## Requirements Advanced

- R047 — The official-runtime Firebase residue boundary is still executable and now distinguishes the backend-only residue left after the frontend cut.
- R048 — The legacy auth/session surface inside the official runtime is now measurable as a backend-only live boundary plus a zero-approved frontend guard.
- R049 — Remaining `firebase_uid` hotspots in the official runtime are now clearly backend-owned compatibility residue.
- R050 — The boundary now records that the official frontend has no approved runtime residue in scope.

## Requirements Validated

- none — S01 still proves the residue boundary and guardrails, not the full milestone behavior.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

None. This republish is the intended way S01 stays truthful as later slices shrink the live boundary.

## Known Limitations

- The approved residue is still live by design. After S03, it is concentrated entirely in backend compatibility, transport, and narrative seams; a green guard is still not full milestone convergence.
- `backend-hormonia` pytest still emits the existing `pytest_asyncio` loop-scope deprecation warning during the guard suite. It is unchanged and non-blocking.

## Follow-ups

- S04 should retire the root `/session/*` island and backend acceptance of `X-Session-ID`, session-as-Bearer, and websocket query fallback before collapsing the backend Firebase narrative.
- S05 should remove the remaining backend fallback-only/helper/admin `firebase_uid` residue and any adjacent runtime Firebase baggage that survives after transport retirement.
- S06 should replay the assembled no-Firebase stack across the critical routed surfaces after the backend legacy contract is gone.
- Any later slice that removes or relocates approved residue must update `runtime-residue-allowlist.json`, `S01-RESEARCH.md`, this summary, `S01-UAT.md`, and the current slice handoff in the same change.

## Files Created/Modified

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — machine-readable boundary for approved residue classes, roots, anchors, and the zero-approved frontend scopes after S03.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — executable `--report` / `--check` guard with deterministic counts and drift diagnostics.
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py` — black-box regression harness for approved residue, unexpected residue, scope handling, and moved hotspots.
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` — readable hotspot map aligned to the post-S03 live verifier output.
- `.gsd/milestones/M004/slices/S01/S01-UAT.md` — reviewer script for the backend-only live boundary plus frontend reintroduction guard.
- `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md` — condensed guardrail handoff updated for the post-S03 boundary.

## Forward Intelligence

### What the next slice should know
- The verifier is already scoped tightly enough to be actionable. Do not broaden it repo-wide; shrink the backend allowlist and keep the empty frontend scopes intact.
- `frontend` reporting `no approved residue` is not a special case to work around; it is the intended post-S03 steady state.
- The current highest-value live residue is transport-heavy backend behavior, not stray frontend leftovers.

### What's fragile
- Backend acceptance paths in `auth_session.py`, `auth_dependencies.py`, and `app/api/websockets.py` — these files still mix legacy transport handling with compatibility semantics, so S04 changes will move anchors quickly.
- The distinction between official-runtime scope and out-of-scope schema/history strings — broadening scans casually will create noise and weaken the guard.

### Authoritative diagnostics
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend` — fastest way to confirm the official frontend still has zero approved residue.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all` — source of truth for what backend residue is still approved right now.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` — fastest way to catch new live residue or stale hotspot bookkeeping.
- `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k moved_hotspot_reports_anchor_name` — trusted proof that moved approved hotspots still surface anchor-aware failures.

### What assumptions changed
- "The frontend cut would still leave some approved S01 hotspots behind" — not true; after S03 the correct boundary is zero-approved frontend scope.
- "Zero frontend residue means the milestone is done" — not true; the remaining approved work is backend-owned and still substantial enough for S04/S05/S06.
