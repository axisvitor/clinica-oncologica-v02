---
id: S01
parent: M006
milestone: M006
provides:
  - Backend staff auth/session chokepoints now resolve only through the canonical cookie-backed session contract, with legacy bearer/header/query transport retained only as explicit rejection or tombstone proof surfaces.
requires: []
affects:
  - slice: M006/S02
    provides: Canonical cookie-only auth/session behavior and a zero-approved backend residue guard that S02 can rely on while removing structural Firebase-era schema residue.
  - slice: M006/S03
    provides: An honest live-vs-retired backend auth/session boundary, so repo-wide cleanup can classify remaining legacy mentions as proof-only, historical, or dead instead of maybe-live runtime.
key_files:
  - backend-hormonia/app/dependencies/auth_dependencies.py
  - backend-hormonia/app/api/v2/routers/admin/dependencies.py
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json
  - .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh
  - backend-hormonia/tests/unit/test_auth_dependencies.py
  - backend-hormonia/tests/unit/test_runtime_residue_guard.py
  - backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py
  - backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py
key_decisions:
  - Keep `get_current_user()` and the admin-router export surface signature-compatible, but route all staff-auth HTTP resolution through `get_current_user_from_session()` so legacy bearer/header transport is observed only for rejection, never acceptance.
  - Represent zero-approved backend auth/session residue with explicit `proof_only` boundaries in the S01 verifier instead of silent excludes or approved debt.
patterns_established:
  - Staff-auth chokepoints may read legacy transport only to produce stable closed-failure diagnostics or suppress the no-auth test bypass; canonical identity resolution is cookie-session-only.
  - Residue publication should distinguish approved live residue from proof-only retired boundaries, and anchor drift on proof-only surfaces is a named verifier failure.
observability_surfaces:
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend
  - cd backend-hormonia && pytest -q tests/api/v2/test_auth_hard_cut_cleanup.py -k "rejects_legacy_header_transport_without_cookie or stable_diagnostics"
  - python3 - <<'PY' ... auth_dependencies.py seam check ... PY
drill_down_paths:
  - .gsd/milestones/M006/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M006/slices/S01/tasks/T02-SUMMARY.md
duration: 2h08m
verification_result: passed
completed_at: 2026-03-15T15:32:44-03:00
---

# S01: Fechar a costura auth/session legado ainda “viva”

**Retired the last live staff-auth bearer/Firebase seam, republished backend auth/session residue to zero approved hits, and kept the surviving legacy surfaces visible only as rejection/tombstone proof boundaries.**

## What Happened

S01 closed the last backend auth/session seam that still behaved as if Firebase-era compatibility were live runtime. `backend-hormonia/app/dependencies/auth_dependencies.py` no longer lazy-loads bearer/Firebase helpers from `get_current_user()`. The chokepoint keeps its existing call signature and downstream `request.state` behavior, but every staff-auth resolution now flows through `get_current_user_from_session()` and the canonical cookie-backed session contract.

That hard cut would have been dishonest if adjacent wrappers still masked legacy transport. `backend-hormonia/app/api/v2/routers/admin/dependencies.py` was tightened so `X-Session-ID` and session-as-Bearer attempts are forwarded only for explicit rejection or to suppress the no-auth test fallback. Cookie-backed requests still authorize. Legacy transport without the cookie now fails closed, including in the admin test-mode seam.

The slice then republished the S01 runtime residue guard around the new truth. `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` now carries zero approved backend hits for `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query`. Surviving backend mentions that still matter for explicit retirement or quarantined compatibility were moved into anchored `proof_only` boundaries. `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` now reports those boundaries separately in `[backend-proof-only]` sections and fails if a proof-only anchor drifts, so the guard no longer lies about what is still approved while keeping retired surfaces inspectable.

Focused proof was extended across the seam. Unit tests pin the source-level seam removal and direct `get_current_user()` behavior. HTTP/admin tests prove stable 401 diagnostics for `X-Session-ID` and session-as-Bearer without the cookie, plus fail-closed behavior in admin test mode. WebSocket and root-session retirement tests remain the proof for explicit legacy rejection/tombstone surfaces. The resulting backend report now shows `no approved residue` plus the named proof-only boundaries that later slices still need to either delete or keep explicitly historical.

## Verification

Passed the full slice verification pack from the plan:

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

Confirmed the published diagnostic surface works:

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` → `[backend] no approved residue`, plus `[backend-proof-only]` boundaries for the surviving explicit retirement/quarantine surfaces.

## Requirements Advanced

- R052 — Advanced the final cleanup requirement by making backend auth/session residue honest: the live bearer/Firebase seam is gone, legacy transports are rejection-only, and the S01 guard now treats reintroduction as drift instead of approved debt.

## Requirements Validated

- none — R052 remains active until S02–S04 also close schema residue, repo-wide cleanup, and the final integrated absence pack.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

none

## Known Limitations

S01 did not remove structural Firebase-era residue from `users` or every downstream compatibility reader. The backend report intentionally still shows proof-only `firebase_uid` boundaries in auth/session-adjacent helpers, and S02 still owns the schema/runtime cleanup that can delete or republish those surfaces honestly.

## Follow-ups

- S02 should remove the remaining structural Firebase-era identity residue in `users` and adjacent readers, then replay the M005 final-schema proof on the post-cleanup head.
- S03 should use the new proof-only/report split to classify repo-wide auth/session legacy mentions as dead, historical, or explicit tombstones instead of runtime ambiguity.

## Files Created/Modified

- `backend-hormonia/app/dependencies/auth_dependencies.py` — removed the lazy bearer/Firebase staff-auth seam and forced the chokepoint through the canonical session dependency.
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` — kept the admin wrapper signature stable while failing closed on legacy transport attempts, even in test mode.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — republished backend auth/session categories to zero approved hits with explicit proof-only boundaries.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — added proof-only reporting and anchor-drift failures for retired legacy boundaries.
- `backend-hormonia/tests/unit/test_auth_dependencies.py` — pinned direct `get_current_user()` behavior and the removed legacy seam.
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py` — added regression coverage for proof-only publication and drift detection.
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py` — proved stable rejection diagnostics for legacy HTTP transport without the session cookie.
- `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py` — kept the canonical operational path cookie-only instead of sending legacy headers.
- `.gsd/milestones/M006/slices/S01/tasks/T01-SUMMARY.md` — task-level execution record for the auth chokepoint hard cut.
- `.gsd/milestones/M006/slices/S01/tasks/T02-SUMMARY.md` — task-level execution record for the residue-guard republication.

## Forward Intelligence

### What the next slice should know
- `verify-runtime-residue.sh --report backend` is now the authoritative split between real drift and intentional retired/quarantined surfaces. If a backend auth/session file moves or is renamed, update the proof-only anchors deliberately instead of papering over the failure.
- The remaining `firebase_uid` mentions in auth/session helpers are no longer “allowed live residue”; they are explicit quarantine/proof surfaces that should only disappear when S02 republishes the structural users contract.

### What's fragile
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` proof-only anchors — moving or renaming anchored files without updating the verifier will fail the guard as `moved_proof_boundary`, which is correct but easy to trip accidentally.
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` compatibility export surface — `_admin_bearer` still exists for import stability, so later cleanup should remove the symbol only after checking router imports rather than assuming the hard cut deleted the export.

### Authoritative diagnostics
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` — shows the exact backend auth/session boundary as approved vs proof-only and is the fastest way to see whether a new hit is real drift or expected retirement surface.
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_hard_cut_cleanup.py -k "rejects_legacy_header_transport_without_cookie or stable_diagnostics"` — strongest focused proof for HTTP/admin stable failure behavior after the hard cut.
- Static seam check in `backend-hormonia/app/dependencies/auth_dependencies.py` — fastest truth source for whether the lazy Firebase/bearer seam was accidentally reintroduced.

### What assumptions changed
- “Zero approved residue means every legacy text mention must disappear immediately.” — Actually, the honest publication model for this seam is zero approved hits plus explicit `proof_only` boundaries for rejection/tombstone or quarantined compatibility surfaces.
- “Retiring the bearer/Firebase seam requires changing auth dependency signatures.” — Actually, the slice kept the public dependency/export signatures stable and hardened behavior underneath them through the canonical session contract.
