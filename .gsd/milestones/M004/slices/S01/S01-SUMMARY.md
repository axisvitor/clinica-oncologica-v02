---
id: S01
parent: M004
milestone: M004
provides:
  - Executable guardrails for official-runtime auth/session residue; after S04 the live verifier boundary excludes retired root `/session/*` and reports only backend-owned residue plus zero-approved frontend reintroduction guards.
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
  - backend-hormonia/tests/auth/test_session_validation.py
key_decisions:
  - The official-runtime residue boundary remains enforced per category and per scope, but root `/session/*` retirement is now proved by focused pytest instead of being kept as approved verifier debt.
  - Frontend scopes stay present with `approved: []` so they act as reintroduction guards instead of disappearing.
  - Boundary shrinkage is only complete when the allowlist, research, summary, UAT, and the focused `/session/*` retirement proof all agree.
patterns_established:
  - Slice-local shell verification delegates deterministic scanning and JSON parsing to embedded Python while remaining black-box testable through subprocess pytest.
  - Route retirement and residue shrinkage move together: update the runtime surface, focused route proof, allowlist, and handoff in the same change.
  - Empty approved sets are valid state when a scope has converged; keep the roots and let the verifier police reintroduction.
observability_surfaces:
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend
  - cd backend-hormonia && pytest -q tests/auth/test_session_validation.py
  - cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k unexpected_residue
  - cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k moved_hotspot_reports_anchor_name
duration: ~3h40m
verification_result: passed
completed_at: 2026-03-14T07:38:24-03:00
---

# S01: Guardrails do corte canônico de runtime

**Scoped runtime-residue guardrails now freeze the post-S04 boundary: root `/session/*` retirement is proved separately via focused pytest, the live backend verifier inventory shrank to `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query`, and the `frontend` scope still reports `no approved residue`.**

## What Happened

S01 turned the runtime-cut discussion into an executable boundary, and later slices kept republishing that boundary instead of leaving it frozen in an outdated state. The slice added `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` as the machine-readable contract for the auth/session residue classes that matter to the official runtime, plus `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`, which reports approved residue by scope/category/file/count and fails on drift with diagnostics like `unexpected_file=` and `moved_hotspot=`.

S03 already completed the frontend side of the story: the official frontend loop no longer emits `X-Session-ID`, `Authorization: Bearer <session_id>`, websocket `session_id` query fallback, browser `session_id` storage/rehydration, or Firebase-shaped auth/admin narrative baggage. The `frontend` scope therefore stays in the allowlist with empty approved sets so any reintroduction fails loudly instead of being silently lost.

S04 then tightened the backend boundary again. The old root `/session/*` compatibility island was rewritten as an explicit 410 tombstone, so that surface no longer belongs in the residue verifier. It is now guarded by `backend-hormonia/tests/auth/test_session_validation.py`. The allowlist was republished accordingly: backend-approved `root_legacy_session` and backend Firebase-narrative residue disappeared, stale helper/doc anchors removed earlier in S04 were deleted, and the remaining live backend inventory now consists only of `firebase_uid` plus the small rejection/detection residue left in `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query`.

## Verification

Latest republish reruns confirmed the new boundary state:

- `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`

Expected diagnostic surfaces remain authoritative:

- `tests/auth/test_session_validation.py` proves `/session/*` returns HTTP 410 with `AUTH_LEGACY_SESSION_ROUTE_RETIRED` instead of reviving or disappearing.
- `--report backend` lists only approved backend rows for `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query`.
- `--check backend` fails if new backend residue appears or approved anchors drift.
- `--report frontend` / `--check frontend` still act as zero-approved reintroduction guards.
- The subprocess pytest harness remains the trusted failure-path proof for `unexpected_file=` and `moved_hotspot=` behavior.

## Requirements Advanced

- R047 — The official-runtime Firebase residue boundary is still executable and now excludes the retired root-session island from the live residue inventory.
- R048 — Legacy auth/session surfaces inside the official runtime are now split honestly between live residue guarded by the verifier and retired `/session/*` behavior guarded by focused route proof.
- R049 — Remaining `firebase_uid` hotspots in the official runtime are now clearly backend-owned compatibility residue.
- R050 — The official frontend residue boundary remains proven clean inside the scoped runtime guard.

## Requirements Validated

- none — S01 still proves the boundary and guardrails, not the full milestone behavior.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

None. This republish is the intended way S01 stays truthful as later slices shrink the live boundary.

## Known Limitations

- Approved residue is still live by design. After S04, it is concentrated in backend compatibility, cache/auth fallback seams, and explicit rejection/detection plumbing.
- `backend-hormonia` pytest still emits the existing `pytest_asyncio` loop-scope deprecation warning during the guard suite. It is unchanged and non-blocking.

## Follow-ups

- S05 should remove the remaining backend `firebase_uid` compatibility residue and any rejection/detection text that no longer earns its keep, without reopening the cookie-only transport boundary.
- S06 should replay the assembled no-Firebase stack across the critical routed surfaces after the backend legacy contract is gone.
- Any later slice that removes or relocates approved residue must update `runtime-residue-allowlist.json`, `S01-RESEARCH.md`, this summary, `S01-UAT.md`, and the current-slice handoff in the same change.

## Files Created/Modified

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — machine-readable boundary for approved live residue classes, roots, anchors, and zero-approved frontend scopes after S04.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — executable `--report` / `--check` guard with deterministic counts and drift diagnostics.
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py` — black-box regression harness for approved residue, unexpected residue, scope handling, and moved hotspots.
- `backend-hormonia/tests/auth/test_session_validation.py` — focused proof for explicit `/session/*` retirement after the route left the live residue inventory.
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` — readable hotspot map aligned to the post-S04 live verifier output and tombstone split.
- `.gsd/milestones/M004/slices/S01/S01-UAT.md` — reviewer script for the reduced backend boundary, zero-approved frontend guard, and explicit `/session/*` retirement proof.
- `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md` — condensed guardrail handoff updated for the post-S04 boundary.

## Forward Intelligence

### What the next slice should know
- The verifier is already scoped tightly enough to be actionable. Do not broaden it repo-wide; shrink the backend allowlist and keep the empty frontend scopes intact.
- Root `/session/*` is no longer verifier debt. If it regresses, start with `tests/auth/test_session_validation.py`, not the allowlist.
- The highest-value live residue is now backend `firebase_uid` compatibility, not session transport.

### What’s fragile
- Backend `firebase_uid` compatibility seams in `auth_dependencies.py`, `auth_session_cache.py`, `auth_legacy_firebase.py`, `auth_session_shared.py`, and adjacent cache/user-adapter code.
- Websocket rejection plumbing in `app/api/websockets.py`, where legacy query/header text still exists for diagnostics.
- The distinction between official-runtime scope and out-of-scope schema/history strings — broadening scans casually will create noise and weaken the guard.

### Authoritative diagnostics
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` — source of truth for what backend residue is still approved right now.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend` — fastest way to catch new live residue or stale hotspot bookkeeping.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend` — fastest way to catch any frontend reintroduction.
- `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py` — fastest way to confirm `/session/*` remains an explicit tombstone.

### What assumptions changed
- "The verifier should keep tracking root `/session/*` as approved debt" — no longer true after S04; that surface is now intentionally dead and should stay under focused route proof.
- "Zero frontend residue means the milestone is done" — still false; the remaining approved work is backend-owned and still substantial enough for S05/S06.
