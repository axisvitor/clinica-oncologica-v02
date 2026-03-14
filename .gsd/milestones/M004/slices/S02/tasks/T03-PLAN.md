---
estimated_steps: 5
estimated_files: 6
---

# T03: Shrink the backend residue boundary and publish the S02 handoff

**Slice:** S02 — Backend auth/sessão convergido para identidade canônica
**Milestone:** M004

## Description

Close the slice by reconciling the live backend residue guard with the converged runtime and publishing a precise handoff. This task updates the S01 backend boundary for the helper hotspots that disappeared or moved, then writes the S02 summary and reviewer checklist so S03/S04 inherit an honest map of what legacy transport behavior still remains by choice.

## Steps

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` after T02 and identify which approved backend hotspots were removed, narrowed, or relocated.
2. Update `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` plus the paired S01 research/summary/UAT artifacts so the backend residue contract matches the new helper reality and any moved anchors are intentional.
3. Write `.gsd/milestones/M004/slices/S02/S02-SUMMARY.md` with the converged backend auth/session contract, the proof pack results, and the exact legacy transport seams still left for S03/S04.
4. Write `.gsd/milestones/M004/slices/S02/S02-UAT.md` with a reviewer checklist covering canonical backend identity behavior, remaining explicit compatibility islands, and the inherited proof commands.
5. Re-run the focused backend proof pack plus `--report backend` and `--check backend`, reconciling artifacts until the verifier and both slice handoff packs describe the same boundary.

## Must-Haves

- [ ] The S01 backend allowlist shrinks or moves only where the converged runtime actually changed.
- [ ] S01 artifacts and S02 artifacts use the same category names, scope assumptions, and remaining-legacy story.
- [ ] S02 summary clearly separates finished backend identity convergence from later transport retirement work.
- [ ] S02 UAT gives a future agent or reviewer a concrete checklist for replaying the backend proof and spotting stale residue bookkeeping.
- [ ] The final backend proof pack and S01 backend residue guard are green together.

## Verification

- `(cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_dependency_override_contract.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py tests/integration/test_local_auth_core_flow.py) && bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend && bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`

## Observability Impact

- Signals added/changed: the live backend residue report becomes a truthful post-S02 map instead of a stale pre-convergence snapshot.
- How a future agent inspects this: read `S02-SUMMARY.md` for the condensed contract, `S02-UAT.md` for replay steps, and compare against `verify-runtime-residue.sh --report backend` when debugging later slices.
- Failure state exposed: any mismatch between the converged code and the published boundary shows up as residue-guard drift instead of quietly leaking into S03/S04.

## Inputs

- `backend-hormonia/app/dependencies/auth_session_cache.py`, `backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/api/v2/user_cache_shared.py` — converged helper surfaces from T02.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`, `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md`, `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md`, `.gsd/milestones/M004/slices/S01/S01-UAT.md` — the current backend residue contract that must shrink in lockstep.
- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py` and `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` — focused proof that defines the new backend boundary.

## Expected Output

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` plus the paired S01 handoff artifacts — updated to the post-S02 backend residue boundary.
- `.gsd/milestones/M004/slices/S02/S02-SUMMARY.md` — condensed handoff for the completed backend convergence slice.
- `.gsd/milestones/M004/slices/S02/S02-UAT.md` — reviewer checklist for replaying the S02 proof and spotting later drift.
