---
id: T05
parent: S05
milestone: M004
provides:
  - Republished the S01 residue boundary and slice handoff so the verifier now describes the post-S05 runtime honestly, with stale `firebase_uid` approvals removed and the surviving boundary aligned to the focused S05 proof packs.
key_files:
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json
  - .gsd/milestones/M004/slices/S01/S01-RESEARCH.md
  - .gsd/milestones/M004/slices/S01/S01-SUMMARY.md
  - .gsd/milestones/M004/slices/S01/S01-UAT.md
  - .gsd/DECISIONS.md
key_decisions:
  - Surviving post-S05 verifier hits are passive compatibility/rejection bookkeeping only; cleaned shared-auth/Redis/auth-user-adapter surfaces left the allowlist and stay guarded by focused proof packs instead.
  - M005 remains the owner of excluded schema/model Firebase debt only, while S06 owns assembled-stack replay against the reduced runtime residue boundary.
patterns_established:
  - Republish residue shrinkage as one change: update the allowlist, research, summary, and UAT together, then rerun both the verifier and the focused proof packs.
  - Delete stale approvals and retarget moved anchors to their new meaning instead of preserving dead bookkeeping by inertia.
observability_surfaces:
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all
  - python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py
  - cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py
  - cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py
  - cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts
  - cd frontend-hormonia && npm run build
duration: ~45m
verification_result: passed
completed_at: 2026-03-14T18:39:31-03:00
blocker_discovered: false
---

# T05: Republish the post-S05 residue boundary and slice handoff

**Republished the S01 verifier boundary after S05 so the approved runtime residue now matches the cleaned codebase, the handoff artifacts use the same category vocabulary as the verifier, and S06/M005 ownership is separated explicitly.**

## What Happened

I reran the S01 residue report against the post-T01–T04 tree and used that output as the source of truth instead of trusting the pre-S05 allowlist. The first `--report all` exposed five stale approvals: three files no longer matching any approved `firebase_uid` residue (`backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/core/redis_manager/session_cache.py`, and `backend-hormonia/app/dependencies/auth_user_adapter.py`) plus two anchors whose meaning changed in place (`backend-hormonia/app/api/v2/routers/auth.py` and `backend-hormonia/app/api/v2/user_cache_shared.py`).

I updated `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` to remove the dead approvals, retarget the two surviving anchors to the current comment/sanitizer lines, and rewrite the `firebase_uid` category description so it matches the post-S05 boundary: passive compatibility/sanitization/admin-helper residue only, not live session/cache/login/audit/docs/frontend emission.

Then I republished the S01 handoff pack:

- `S01-RESEARCH.md` now describes the reduced post-S05 inventory, exact file/count totals, the cleaned surfaces that left the verifier, and the split between verifier-owned residue, focused S05 proof packs, S06 assembled-stack proof, and M005 schema debt.
- `S01-SUMMARY.md` now frames the S01 boundary as post-S05 state instead of post-S04 state and records the final verification surface.
- `S01-UAT.md` now replays the boundary with `--report all` / `--check all`, names the exact surviving approved files, and documents the focused proof-pack checks needed when a cleaned surface drifts back in.

I also appended the durable project decision that surviving post-S05 verifier hits are passive compatibility/rejection bookkeeping only, and that cleaned surfaces stay out of the allowlist under focused proof instead.

## Verification

Passed the full slice verification set after republishing the boundary:

- `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py`
- `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py`
- `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts`
- `cd frontend-hormonia && npm run build`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`

Results:

- All backend/frontend proof packs passed.
- `--report all` ended with `RESULT: --report all OK`.
- `--check all` ended with `RESULT: --check all OK`.
- The only recurring non-blocking noise was the existing `pytest_asyncio` loop-scope deprecation warning during backend pytest runs.

## Diagnostics

For future inspection, start here:

1. `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
   - Shows the exact approved category/file/count boundary.
2. `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
   - Fails on newly introduced residue, stale approvals, or moved anchors.
3. If the verifier starts listing a cleaned hotspot again, rerun the focused S05 proof packs to localize the regression:
   - auth/session seam: `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py`
   - audit/admin/docs: `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py`
   - frontend types/build: `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts && npm run build`
4. Keep the ownership split straight:
   - S06: assembled-stack replay against this reduced boundary
   - M005: excluded schema/model Firebase debt only

## Deviations

None.

## Known Issues

- Remaining approved `firebase_uid` hits still exist in backend compatibility/helper code, especially `auth_dependencies.py`, `auth_legacy_firebase.py`, `auth_session_cache.py`, and the generic admin helper `backend-hormonia/app/api/v2/routers/admin/utils.py`.
- Legacy transport rejection text still survives in `backend-hormonia/app/api/websockets.py`, `backend-hormonia/app/api/v2/routers/admin/dependencies.py`, and `backend-hormonia/app/dependencies/auth_session_contract.py` by design.

## Files Created/Modified

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — removed stale post-S04 `firebase_uid` approvals, retargeted two moved anchors, and relabeled the category for post-S05 semantics.
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` — republished the readable hotspot map and ownership split for the reduced boundary.
- `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md` — condensed S01 handoff updated for the post-S05 verifier state and proof packs.
- `.gsd/milestones/M004/slices/S01/S01-UAT.md` — reviewer replay updated to the new approved file set and proof-pack alignment.
- `.gsd/DECISIONS.md` — appended the post-S05 residue-boundary meaning decision.
