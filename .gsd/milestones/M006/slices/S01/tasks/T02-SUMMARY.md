---
id: T02
parent: S01
milestone: M006
provides:
  - Runtime residue guard republished with zero approved backend auth/session hotspots and explicit proof-only reporting for surviving legacy boundaries.
key_files:
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json
  - .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh
  - backend-hormonia/tests/unit/test_runtime_residue_guard.py
  - backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py
  - backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py
  - .gsd/DECISIONS.md
key_decisions:
  - Keep backend auth/session residue categories at `approved: []` and move surviving explicit legacy surfaces into anchored `proof_only` boundaries instead of hiding them behind generic excludes or leaving them as approved debt.
patterns_established:
  - Zero-approved residue does not mean silent omission: `verify-runtime-residue.sh --report backend` now prints proof-only boundaries separately, and anchor drift on those boundaries still fails the guard.
  - Canonical operational proofs should stop sending legacy auth headers when a cookie-backed session is sufficient; explicit legacy transport proof belongs in dedicated rejection tests.
observability_surfaces:
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
  - `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_validation.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/v2/test_system_auth_hard_cut_operational.py`
  - `cd backend-hormonia && pytest -q tests/unit/test_auth_session_identity_contract.py tests/unit/test_auth_session_cache_canonical_identity.py`
duration: 1h13m
verification_result: passed
completed_at: 2026-03-15T15:23:01-03:00
blocker_discovered: false
---

# T02: Republicar o guard de resíduo com zero-approved no backend auth/session

**Republished the backend auth/session residue guard so the four target categories now have zero approved hits, surviving legacy text is reported as proof-only boundaries, and the focused rejection/tombstone pack stays green.**

## What Happened

I changed `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` so the verifier understands a second boundary type, `proof_only`, alongside the old `approved` hotspots. `approved` remains the true allowlist surface; `proof_only` is for explicit rejection/tombstone or quarantined compatibility text that still exists and must stay inspectable, but should no longer count as approved runtime residue. Report mode now prints those boundaries in separate `[scope-proof-only]` sections, while check mode still fails on unexpected files and now also fails if a proof-only anchor drifts.

With that model in place, `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` was republished for the four backend categories targeted by this slice: `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query` all now have `approved: []` in the backend scope. The surviving backend auth/session mentions were either:

- moved into anchored `proof_only` entries tied to focused proof packs, or
- scoped out explicitly when they are known non-S01 ownership (the structural `users.py` `firebase_uid` sanitizer) or an already-isolated legacy bridge not part of the live chokepoint (`auth_legacy_firebase.py`).

I extended `backend-hormonia/tests/unit/test_runtime_residue_guard.py` so the guard now has regression coverage for the new semantics: a proof-only boundary passes and reports separately, and a proof-only anchor drift fails with `moved_proof_boundary=...`.

On the proof side, I strengthened the HTTP/admin surfaces that now back the republished guard:

- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py` now proves `/api/v2/auth/verify-session` rejects both `X-Session-ID` and session-as-Bearer transport without a cookie, in addition to the existing password/admin rejection checks.
- `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py` no longer sends `X-Session-ID` on its canonical admin fixture; the operational system checks now exercise the cookie-backed path without reintroducing legacy header narrative into the green-path proof.

I also appended the guard-model decision to `.gsd/DECISIONS.md` so later slices know that zero-approved is now represented as visible proof-only boundaries rather than silent exclusions.

## Verification

Passed focused task verification:

- `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py tests/unit/test_auth_session_identity_contract.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_validation.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/v2/test_system_auth_hard_cut_operational.py`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`

Passed slice-level verification:

- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependencies.py tests/unit/test_runtime_residue_guard.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_validation.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_hard_cut_cleanup.py -k "rejects_legacy_header_transport_without_cookie or stable_diagnostics"`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
- `python3 - <<'PY'
from pathlib import Path
text = Path('backend-hormonia/app/dependencies/auth_dependencies.py').read_text(encoding='utf-8')
for needle in ('authenticate_legacy_bearer_user', '_get_auth_legacy_firebase', '_get_firebase_service'):
    assert needle not in text, needle
print('legacy auth seam retired')
PY`

Observed guard result after republication:

- `[backend]` prints `no approved residue`
- `[backend-proof-only]` prints the surviving anchored boundaries for `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query`
- `RESULT: --check backend OK`

## Diagnostics

Future inspection surfaces:

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` — authoritative backend residue map, now split into approved vs proof-only sections.
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py::test_proof_only_boundary_passes_check_and_reports_separately`
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py::test_moved_proof_boundary_reports_anchor_name`
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py::test_verify_session_rejects_legacy_transport_without_cookie`
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py::test_admin_dependency_rejects_legacy_transport_without_cookie_even_in_test_mode`
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py::test_websocket_rejects_legacy_session_transport_without_cookie`
- `backend-hormonia/tests/auth/test_session_validation.py::test_retired_root_session_routes_ignore_legacy_headers_and_cookies`

Failure visibility is improved in two directions now:

- real reintroductions still fail as `unexpected_file=...`
- bookkeeping drift on the republished proof-only boundary fails as `moved_proof_boundary=... anchor=...`

## Deviations

- None.

## Known Issues

- None in the verified slice/task surface. The backend report still shows proof-only `firebase_uid` compatibility bridges in auth/session helpers; that is intentional for this slice and no longer treated as approved debt.

## Files Created/Modified

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — cleared backend approved hotspots for the four target categories and republished surviving legacy surfaces as proof-only boundaries or explicit out-of-scope ownership.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — added proof-only boundary support, separate report sections, and anchor-drift failures for proof-only entries.
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py` — added regression coverage for proof-only pass/report behavior and proof-boundary anchor drift.
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py` — added direct `/api/v2/auth/verify-session` rejection proof for `X-Session-ID` and session-as-Bearer without a cookie.
- `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py` — removed legacy `X-Session-ID` from the canonical admin operational fixture so green-path system proof stays cookie-only.
- `.gsd/DECISIONS.md` — recorded the zero-approved/publication model for backend auth/session residue.
- `.gsd/milestones/M006/slices/S01/tasks/T02-SUMMARY.md` — recorded execution, verification, and recovery-ready handoff for this unit.
