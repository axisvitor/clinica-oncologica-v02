---
id: T03
parent: S04
milestone: M004
provides:
  - Explicit `/session/*` 410 tombstone behavior plus a republished backend residue boundary that no longer approves root-session or backend Firebase-narrative hotspots.
key_files:
  - backend-hormonia/app/routers/auth_session.py
  - backend-hormonia/app/core/router_registry.py
  - backend-hormonia/tests/auth/test_session_validation.py
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json
  - .gsd/milestones/M004/slices/S01/S01-RESEARCH.md
  - .gsd/milestones/M004/slices/S01/S01-SUMMARY.md
  - .gsd/milestones/M004/slices/S01/S01-UAT.md
key_decisions:
  - Keep the root `/session/*` prefix mounted only as an explicit 410 tombstone with stable diagnostics instead of letting it disappear into generic 404s.
  - Gate the tombstone via focused pytest and keep the runtime-residue verifier for the smaller backend inventory that remains after the cut.
patterns_established:
  - Route retirement and residue shrinkage move together: update the router behavior, focused route proof, allowlist, and readable handoff in the same change.
  - Legacy header/bearer/query strings that survive the S04 cut are modeled as rejection/detection residue, not accepted transport.
observability_surfaces:
  - cd backend-hormonia && pytest -q tests/auth/test_session_validation.py
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend
duration: ~1h20m
verification_result: passed
completed_at: 2026-03-14T07:38:24-03:00
blocker_discovered: false
---

# T03: Tombstone `/session/*` and republish the backend residue boundary

**Replaced the root `/session/*` compatibility island with a stable 410 tombstone, rewrote the focused proof around that retirement surface, and republished the S01 backend residue contract so it no longer approves dead root-session or backend Firebase-narrative anchors.**

## What Happened

`backend-hormonia/app/routers/auth_session.py` now serves only a minimal retirement router. The root `/session/*` surface still exists, but only to return a deterministic 410 payload with `AUTH_LEGACY_SESSION_ROUTE_RETIRED`, the retired path, the canonical replacement prefix, and the required session-cookie transport. `backend-hormonia/app/core/router_registry.py` registers that surface honestly as a retirement router instead of a live session-auth island.

`backend-hormonia/tests/auth/test_session_validation.py` was rewritten around the new contract. The file proves representative `/session/*` routes — including unknown subpaths and requests carrying legacy headers/cookies — all hit the same explicit tombstone instead of old behavior or accidental 404 drift.

The S01 residue artifacts were then republished to match the code. `runtime-residue-allowlist.json` no longer approves `root_legacy_session`, no longer approves backend Firebase-narrative residue, and trims stale hotspots removed earlier in S04. The remaining `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query` entries are documented as rejection/detection residue only. `S01-RESEARCH.md`, `S01-SUMMARY.md`, and `S01-UAT.md` now describe the same post-S04 split: use focused pytest for `/session/*` retirement, and use the residue verifier for the reduced backend inventory that remains live.

## Verification

Focused task verification passed:

- `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`

Slice-level verification for the final task also passed:

- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_priority.py tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_localization.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`

Observed signals after the republish:

- `/session/*` now fails with HTTP 410 and `AUTH_LEGACY_SESSION_ROUTE_RETIRED` under focused proof.
- The backend residue report/check is green and now lists only `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query`.
- Approved `root_legacy_session` and backend Firebase-narrative rows no longer appear in the backend report.

## Diagnostics

- Run `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py` when the root `/session/*` retirement surface is in doubt.
- Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` to see the current live backend residue inventory.
- Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend` to distinguish stale allowlist/docs bookkeeping from actual runtime drift.

## Deviations

None.

## Known Issues

- Backend pytest still emits the existing `pytest_asyncio` loop-scope deprecation warning. It is unchanged and non-blocking.

## Files Created/Modified

- `backend-hormonia/app/routers/auth_session.py` — replaced the legacy root router with a minimal 410 tombstone router and stable retirement diagnostics.
- `backend-hormonia/app/core/router_registry.py` — rewired the root `/session/*` registration/logging to describe the retirement surface honestly.
- `backend-hormonia/tests/auth/test_session_validation.py` — rewrote the focused proof around explicit tombstone behavior instead of legacy validation/logout behavior.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — removed dead root-session/backend Firebase-narrative approvals and republished the reduced backend residue inventory.
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` — updated the readable hotspot map for the post-S04 backend boundary.
- `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md` — condensed handoff aligned to the explicit tombstone split and reduced verifier output.
- `.gsd/milestones/M004/slices/S01/S01-UAT.md` — replay guidance aligned to the new retirement proof and reduced backend residue report.
