---
id: S01
parent: M004
milestone: M004
provides:
  - Published the executable official-runtime residue map, downstream cut order, and reviewer checklist that bind S02–S05 to one shared boundary contract.
requires: []
affects:
  - S02
  - S03
  - S04
  - S05
  - backend-hormonia
  - frontend-hormonia
key_files:
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json
  - .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh
  - .gsd/milestones/M004/slices/S01/S01-RESEARCH.md
  - .gsd/milestones/M004/slices/S01/S01-SUMMARY.md
  - .gsd/milestones/M004/slices/S01/S01-UAT.md
  - backend-hormonia/tests/unit/test_runtime_residue_guard.py
key_decisions:
  - The S01 boundary is defined by the verifier's `backend` / `frontend` scopes and documented with the same category ids used by the allowlist.
  - Later slices must update the allowlist, research, summary, and UAT together whenever an approved hotspot disappears, moves, or changes ownership.
patterns_established:
  - Close a guardrail slice with a readable residue map, a cut-order handoff, and an artifact-driven reviewer checklist so downstream cleanup starts from one contract instead of reopening discovery.
  - Treat `--report all` as the readable inventory and `--check all` plus focused regression tests as the failure/diagnostic surface for boundary drift.
observability_surfaces:
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all
  - cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py
  - .gsd/milestones/M004/slices/S01/S01-RESEARCH.md
  - .gsd/milestones/M004/slices/S01/S01-UAT.md
drill_down_paths:
  - .gsd/milestones/M004/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S01/tasks/T02-SUMMARY.md
duration: ~3h20m across 2 tasks
verification_result: passed
completed_at: 2026-03-14T00:28:42-03:00
---

# S01: Guardrails do corte canônico de runtime

**S01 shipped an executable residue boundary for the official auth/session runtime, published the approved hotspot map and exclusions, and handed S02–S05 one explicit cut order instead of another repo-wide rediscovery pass.**

## What Happened

T01 built the machine-readable boundary: `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`, `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`, and `backend-hormonia/tests/unit/test_runtime_residue_guard.py`. The verifier now reports the approved live residue by category/file/count and fails when a new runtime file appears or a tracked hotspot moves without the boundary being updated.

T02 turned that executable boundary into a durable slice handoff. `S01-RESEARCH.md` now mirrors the final `--report all` output category by category, separates official runtime surfaces from retained compatibility islands and explicit out-of-scope exclusions, and records which later slice owns each residue family. `S01-UAT.md` converts that into a reviewer checklist that asks three concrete questions: did new residue appear, did an approved hotspot move without a boundary update, and did any out-of-scope string get pulled into the official failure surface.

The cut order is now explicit:
- **S02** removes backend `firebase_uid` dependence from the canonical auth/session/cache path.
- **S03** removes official frontend emission of `X-Session-ID`, session-as-Bearer, and websocket `session_id` query fallback.
- **S04** retires the root `/session/*` island and removes backend acceptance of the legacy auth/session inputs.
- **S05** removes the remaining adjacent `firebase_uid` and Firebase-narrative residue in admin/types/helper surfaces.

The slice closes with one durable rule: if later cleanup changes the approved boundary, the allowlist, research, summary, and UAT must all move together. A green verifier against stale handoff docs is still drift.

## Verification

Passed on final rerun:
- `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py`
- `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k unexpected_residue`
- `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k moved_hotspot_reports_anchor_name`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
  - ended with `RESULT: --report all OK`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
  - ended with `RESULT: --check all OK`

Those checks verify both the happy path and the diagnostic surface: the report inventory stays readable, the gate stays green on the approved boundary, and the focused pytest cases prove unexpected residue / moved hotspots fail with inspectable messages.

## Requirements Advanced

- R047 — froze the official runtime failure surface where Firebase-era behavior still survives, so later slices can remove it deliberately instead of guessing.
- R048 — turned the scattered auth/session drift into one executable boundary contract with explicit scope, ownership, and diagnostics.
- R049 — isolated the live `firebase_uid` runtime pivots that still block canonical identity convergence on the backend and in adjacent admin/type surfaces.
- R050 — isolated the official frontend header/bearer/query and Firebase-narrative residue that must disappear before the contract is truly canonical.

## Requirements Validated

- none — S01 proves the boundary and guardrails, not the final no-Firebase runtime behavior.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- Added `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k moved_hotspot_reports_anchor_name` to `S01-PLAN.md` during the pre-flight repair so slice verification includes an explicit diagnostic/failure-path check, not just green-path inventory and gate reruns.

## Known Limitations

- The residue is still live. S01 makes it visible and enforceable; it does not remove it.
- Backend resolver/header/bearer/query fallback behavior is still spread across multiple helper families and remains fragile until S04 retires the legacy acceptance paths.
- Frontend admin/type Firebase narrative and compatibility fields still survive after S01 and need an explicit S05 cleanup pass.

## Follow-ups

- Start S02 from `S01-RESEARCH.md` and treat the `firebase_uid` section as the backend cut checklist.
- Keep using `verify-runtime-residue.sh --report all` before and after each later slice task; if the report shrinks intentionally, update the handoff artifacts in the same change.
- Use `S01-UAT.md` as the review checklist whenever `runtime-residue-allowlist.json` changes.

## Files Created/Modified

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — machine-readable official boundary with category ids, scope roots, approved hotspots, and exclusions.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — executable `--report` / `--check` surface for approved residue and drift detection.
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py` — subprocess regression harness for approved residue, unexpected residue, scope handling, and moved-hotspot diagnostics.
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` — finalized residue map aligned with the live report output and downstream slice ownership.
- `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md` — condensed slice handoff and cut order for S02–S05.
- `.gsd/milestones/M004/slices/S01/S01-UAT.md` — reviewer checklist for new residue, moved hotspots, and scope-discipline drift.
- `.gsd/milestones/M004/slices/S01/S01-PLAN.md` — added the explicit diagnostic verification command and closed T02.

## Forward Intelligence

### What the next slice should know
- `firebase_uid` is not one thing: the backend auth/session/cache core is S02 work, while the adjacent patient/admin/type compatibility residue is S05 work.
- `X-Session-ID`, Bearer-as-session, and websocket query fallback are intentionally split: frontend emission dies in S03, backend acceptance dies in S04.

### What's fragile
- `backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/dependencies/auth_session_contract.py`, and the spread V2 helper files — they all participate in session resolution today, so changing only the obvious auth router will leave the runtime half-converged.
- `backend-hormonia/app/routers/auth_session.py` — it is both a live compatibility island and the backend Firebase-narrative hotspot, so S04 needs real retirement proof rather than a blind delete.

### Authoritative diagnostics
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all` and `--check all` — fastest authoritative read on approved residue versus drift.
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py` — authoritative proof that the guard still emits structured failure output for unexpected files and moved hotspots.
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` — authoritative readable ownership map for the approved hotspots and exclusions.

### What assumptions changed
- We assumed the slice would mainly need a new script; in practice the durable part was publishing the same boundary in human-readable form so later slices do not reopen discovery.
- We assumed the obvious auth router files would dominate the residue map; the final report showed the header/bearer drift is wider in V2 helper families and that frontend/admin narrative residue also needs its own explicit owner.
