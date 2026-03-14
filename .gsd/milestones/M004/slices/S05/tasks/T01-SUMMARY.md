---
id: T01
parent: S05
milestone: M004
provides:
  - Auth dependency modules compile again, and the core Redis session contract now resolves staff sessions through canonical `user_id` instead of `firebase_uid`.
key_files:
  - backend-hormonia/app/dependencies/auth_session_contract.py
  - backend-hormonia/app/dependencies/auth_session_cache.py
  - backend-hormonia/app/dependencies/auth_dependencies.py
  - backend-hormonia/app/dependencies/__init__.py
  - backend-hormonia/app/core/redis_manager/session_cache.py
  - backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py
  - backend-hormonia/tests/unit/test_session_cache.py
key_decisions:
  - Keep Redis session/cache identity canonical on `user_id`; Firebase-era identity may remain only as passive compatibility data outside the live pivot.
  - Lazy-load the legacy Firebase dependency seam so session-first auth imports stay usable while later slice work cleans the remaining legacy module/test residue.
patterns_established:
  - Session helpers resolve `id`/`user_id` first, use `firebase_uid` only when the canonical ID is absent, and never use `firebase_uid` for Redis session listing or bulk invalidation.
observability_surfaces:
  - `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py`
  - `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
duration: 1h22m
verification_result: passed
completed_at: 2026-03-14T17:31:18-03:00
blocker_discovered: false
---

# T01: Restore auth dependency hygiene and canonicalize the core Redis session contract

**Cleaned the broken auth dependency seam, moved the core Redis session contract to canonical `user_id`, and pinned the post-cut behavior with focused unit proof.**

## What Happened

I resolved the committed merge markers in the four dependency files named by the task and kept the S04 transport cut intact: `auth_session_contract.py` now accepts only the session cookie for staff session resolution, logs rejected legacy transports, and still delegates user hydration through the extracted session-cache helper.

In `auth_session_cache.py` I restored the canonical helper surface around `id` / `user_id`, kept `firebase_uid` only as passive compatibility data when the canonical identity is absent, and made fallback rehydration create Redis sessions with canonical `user_id` plus metadata that no longer carries Firebase identity. The helper now prefers embedded canonical session payloads, then user-id cache / DB lookup, and only falls back to `firebase_uid` cache / DB lookup when no canonical user ID exists.

In `auth_dependencies.py` and `backend-hormonia/app/dependencies/__init__.py` I resolved the merge damage without reintroducing removed public legacy exports. I also moved the legacy Firebase dependency behind a lazy import/initialization seam so the session-first auth modules import cleanly again even though later slice tasks still own the remaining legacy file/test cleanup.

In `backend-hormonia/app/core/redis_manager/session_cache.py` I cut the live Redis pivot to canonical `user_id`: session creation no longer injects Firebase identity into the stored session payload, and session listing / bulk invalidation now match only `user_id` (including legacy `id` aliases), not `firebase_uid`. I preserved caller compatibility by keeping a compatibility slot/kwargs path for older call signatures without letting that data drive the runtime contract.

I updated the focused unit proof to distinguish canonical behavior from passive compatibility metadata. The auth-session helper tests now assert that fallback rehydration passes `firebase_uid=None` and keeps Firebase identity out of session metadata, and the Redis session-cache tests now pin user-id-only creation, listing, and bulk invalidation behavior even when stale `firebase_uid` data is present.

## Verification

Task-level verification passed:

- `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py`

Slice-level verification status after T01:

- Passed: `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py`
- Passed: `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py`
- Failed outside T01 scope: `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py` because `tests/api/test_websocket_session_auth_contract.py` still has committed merge markers
- Failed outside T01 scope: `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py` with pre-existing audit/admin behavior mismatches owned by later slice work
- Passed: `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts`
- Passed: `cd frontend-hormonia && npm run build`
- Failed as expected until T05 republishes the allowlist: `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` now reports that the old approved `session_cache.py` Firebase hotspot no longer matches the current scan
- Informational stale pre-fix run: `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all` was started before the final `session_cache.py` cleanup, so its drift note still references the removed hotspot

## Diagnostics

Future inspection for this task should start with:

- `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py` to catch merge-marker/syntax regressions in the dependency seam
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py` to localize regressions to helper hydration vs Redis payload/list/invalidation behavior
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` to confirm the remaining failure is only allowlist republication drift, not a live `session_cache.py` Firebase pivot

## Deviations

- To keep the dependency surface importable during this task, I lazily loaded the legacy Firebase module from `auth_dependencies.py` instead of importing it at module import time. This was not explicitly called out in the task plan, but it was the smallest way to restore dependency hygiene without dragging T01 into the broader legacy-module cleanup owned later in the slice.

## Known Issues

- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` still contains merge markers and blocks the broader backend auth slice pack during collection.
- The audit/admin/docs pytest pack still fails on pre-existing audit/admin behavior unrelated to the Redis session-contract cut.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` is now stale relative to the removed `session_cache.py` hotspot; T05 needs to republish the residue boundary so `verify-runtime-residue.sh --check all` goes green again.

## Files Created/Modified

- `backend-hormonia/app/dependencies/auth_session_contract.py` — removed merge markers and restored the cookie-only request/session resolver.
- `backend-hormonia/app/dependencies/auth_session_cache.py` — restored canonical helper logic and limited Firebase identity to compatibility-only fallback paths.
- `backend-hormonia/app/dependencies/auth_dependencies.py` — removed merge markers, kept the session-first dependency surface importable, and lazy-loaded the legacy Firebase seam.
- `backend-hormonia/app/dependencies/__init__.py` — removed merge markers and restored the intended auth dependency export surface.
- `backend-hormonia/app/core/redis_manager/session_cache.py` — moved Redis session creation/listing/invalidation to canonical `user_id` semantics and removed the lingering Firebase hotspot from the core contract.
- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py` — tightened fallback rehydration assertions so Firebase identity stays out of the live session metadata.
- `backend-hormonia/tests/unit/test_session_cache.py` — added focused proof for user-id-only session creation, listing, and bulk invalidation.
- `.gsd/DECISIONS.md` — recorded the canonical `user_id` session pivot and lazy legacy seam decision for downstream work.
