---
id: T01
parent: S02
milestone: M006
provides:
  - Canonical-only live auth/session identity resolution: Redis/session payloads must carry `user_id`, Firebase-only payloads fail closed, and Redis outage recovery stays on session-table fallback.
key_files:
  - backend-hormonia/app/dependencies/auth_session_cache.py
  - backend-hormonia/app/dependencies/auth_session_contract.py
  - backend-hormonia/app/dependencies/auth_dependencies.py
  - backend-hormonia/app/dependencies/auth_role_dependencies.py
  - backend-hormonia/app/repositories/user.py
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json
  - backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py
  - backend-hormonia/tests/api/v2/test_auth_uid_validation.py
  - backend-hormonia/tests/api/v2/test_auth_timeout.py
  - backend-hormonia/tests/integration/test_auth_fallback.py
key_decisions:
  - Preserve the PostgreSQL session-table fallback for Redis failure, but reject Redis/session payloads that lack canonical `user_id` instead of recovering through `User.firebase_uid`.
patterns_established:
  - Auth/session cache hydration stores and returns only canonical user payloads; any stale legacy identity alias in cached data is stripped before reuse.
observability_surfaces:
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`; `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_uid_validation.py tests/api/v2/test_auth_timeout.py tests/integration/test_auth_fallback.py`
duration: 1h10m
verification_result: passed
completed_at: 2026-03-15T16:20:58-03:00
blocker_discovered: false
---

# T01: Retire firebase-shaped auth/session identity fallback from the live runtime

**Removed the live `firebase_uid` auth/session recovery path so runtime identity restore is now canonical-only, while keeping Redis→session-table fallback intact and observable.**

## What Happened

`backend-hormonia/app/dependencies/auth_session_cache.py` was narrowed to the surviving runtime contract: embedded session payloads and cache lookups now resolve only through canonical `id`/`user_id`, cache hydration writes only canonical user-id entries, and fallback session rehydration still republishes the session without any Firebase-shaped identity field. Redis payloads that contain only `firebase_uid` now fail closed as `Invalid session data` instead of probing legacy cache or DB paths.

`backend-hormonia/app/dependencies/auth_session_contract.py` and `backend-hormonia/app/dependencies/auth_dependencies.py` were rewired to drop the live `firebase_uid` loader/validator seam from session auth. The canonical user-id DB loader now carries the retry-aware timeout behavior and log surface that the old Firebase lookup used to provide, so timeout diagnostics still localize on the identity path after the seam removal.

`backend-hormonia/app/dependencies/auth_role_dependencies.py` no longer loads admin users by `firebase_uid`, and `backend-hormonia/app/repositories/user.py` no longer exposes the dead `get_by_firebase_uid()` shortcut. The S01 backend residue allowlist was republished to remove the proof-only anchors for the deleted auth/session/admin fallback branches, and the S02 slice plan verification list now explicitly includes the residue report diagnostic check.

Focused auth/session proof was updated around the new truth: unit/integration tests now assert Firebase-only session payload rejection, canonical-only timeout behavior, canonical cache/session rehydration, and fallback success without `firebase_uid` surfacing in runtime payloads.

## Verification

Passed task-level verification and the slice diagnostic check:

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_uid_validation.py tests/api/v2/test_auth_timeout.py tests/integration/test_auth_fallback.py`

Also confirmed the edited Python files compile with:

- `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_role_dependencies.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py backend-hormonia/tests/api/v2/test_auth_uid_validation.py backend-hormonia/tests/api/v2/test_auth_timeout.py backend-hormonia/tests/integration/test_auth_fallback.py`

Slice-level packs owned by T02/T03 were not run here.

## Diagnostics

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` now shows no approved backend residue and no proof-only boundary for `auth_session_cache.py` or `auth_role_dependencies.py`; the remaining `firebase_uid` proof-only hit in `auth_dependencies.py` is the standalone validator surface, not live session recovery.
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_uid_validation.py tests/api/v2/test_auth_timeout.py tests/integration/test_auth_fallback.py` is the fastest replay for malformed payload rejection, canonical timeout logs, and Redis→session-table fallback.
- Failure shape after this task: Redis session payload without canonical `user_id` returns `401 Invalid session data`; canonical DB timeout returns `504 Database query timeout after retry`; Redis failure still falls back through the session table and rehydrates canonical cache/session state.

## Deviations

- Added the missing residue-report diagnostic command to `.gsd/milestones/M006/slices/S02/S02-PLAN.md` before implementation because the unit pre-flight explicitly required at least one inspectable failure-path verification step.

## Known Issues

- Remaining S02 verification packs for profile/admin/physician surfaces, migration convergence, and final-schema replay are still pending later tasks in this slice.

## Files Created/Modified

- `backend-hormonia/app/dependencies/auth_session_cache.py` — removed live `firebase_uid` serialization/cache/DB fallback, stripped stale legacy identity aliases from returned payloads, and kept canonical session-table rehydration.
- `backend-hormonia/app/dependencies/auth_session_contract.py` — dropped the Firebase-shaped session resolver parameters and kept the cookie-only request contract on the canonical path.
- `backend-hormonia/app/dependencies/auth_dependencies.py` — removed session-auth wiring to `firebase_uid` DB fallback and added retry-aware canonical user-id DB lookup diagnostics.
- `backend-hormonia/app/dependencies/auth_role_dependencies.py` — removed admin-session fallback by `firebase_uid`; canonical IDs are now required.
- `backend-hormonia/app/repositories/user.py` — deleted the dead `get_by_firebase_uid()` repository shortcut.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — removed proof-only anchors for the retired auth/session/admin firebase fallback seams.
- `.gsd/milestones/M006/slices/S02/S02-PLAN.md` — added the missing backend residue report step and marked T01 complete.
- `.gsd/DECISIONS.md` — recorded the canonical-only session restore boundary for later S02/S03 work.
- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py` — republished unit proof around canonical-only cache/session identity resolution and Firebase-only payload rejection.
- `backend-hormonia/tests/api/v2/test_auth_uid_validation.py` — switched malformed Firebase-only payload tests from UID validation fallback to fail-closed canonical contract checks.
- `backend-hormonia/tests/api/v2/test_auth_timeout.py` — moved timeout proof to the canonical user-id DB path and preserved retry/log expectations.
- `backend-hormonia/tests/integration/test_auth_fallback.py` — republished Redis timeout/session fallback proof around canonical payloads, cache hydration, and session rehydration without `firebase_uid`.
- `.gsd/STATE.md` — advanced slice state to T02.
