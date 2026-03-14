---
id: T02
parent: S05
milestone: M004
provides:
  - Shared auth/cache helpers and local login now emit canonical runtime payloads without `firebase_uid`, and websocket-adjacent auth keeps the cookie-only/error-code contract pinned.
key_files:
  - backend-hormonia/app/api/v2/auth_session_shared.py
  - backend-hormonia/app/api/v2/user_cache_shared.py
  - backend-hormonia/app/api/v2/routers/auth.py
  - backend-hormonia/app/dependencies/auth_user_adapter.py
  - backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py
  - backend-hormonia/tests/api/v2/test_auth_local_login.py
  - backend-hormonia/tests/api/test_websocket_session_auth_contract.py
  - backend-hormonia/tests/auth/test_user_conversion.py
key_decisions:
  - Treat the shared runtime adapter layer as `user_id`-only for live session/cache identity, and sanitize stale cached payloads before returning them instead of preserving `firebase_uid` in emitted auth state.
patterns_established:
  - Shared auth/session restore rejects `firebase_uid`-only session payloads before any cache or DB fallback.
  - Local login proof captures the actual Redis `create_session` call and asserts both top-level kwargs and session metadata omit `firebase_uid`.
  - Websocket auth proof pins the S04 cookie-only transport and stable `AUTH_WEBSOCKET_SESSION_INVALID` / `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED` diagnostics while asserting no `firebase_uid` cache lookup occurs.
observability_surfaces:
  - Focused pytest packs now distinguish canonical user-id success from stale Firebase-shaped runtime payload writing; websocket tests preserve stable auth error codes and session-source details.
duration: 1h40m
verification_result: passed
completed_at: 2026-03-14T17:49:00-03:00
blocker_discovered: false
---

# T02: Remove `firebase_uid` from shared auth/cache adapters and login-written session payloads

**Shared auth/cache restore, local login session writes, and websocket-adjacent proof now run on canonical `user_id` payloads without emitting `firebase_uid` in the live runtime path.**

## What Happened

I removed the live `firebase_uid` pivot from the shared adapter layer named in the task plan.

- `backend-hormonia/app/api/v2/auth_session_shared.py`
  - dropped `firebase_uid` from embedded session-user extraction
  - made canonical `id` / `user_id` mandatory for non-embedded session recovery
  - removed the shared `firebase_uid` DB/cache fallback path entirely
- `backend-hormonia/app/api/v2/user_cache_shared.py`
  - narrowed the helper contract to canonical `user_id` only
  - stopped serializing `firebase_uid` into runtime cache payloads
  - sanitized stale cached user payloads so returned auth state no longer re-emits `firebase_uid`
- `backend-hormonia/app/api/v2/routers/auth.py`
  - removed login-time `firebase_uid` injection from the authenticated user payload
  - updated the Redis session creation compatibility shim so it no longer sends `firebase_uid` in the canonical write path
- `backend-hormonia/app/dependencies/auth_user_adapter.py`
  - stopped emitting `firebase_uid` from the shared user-to-cache/session serializer

I also tightened the focused proof pack so it catches regression at the right seam instead of only checking happy-path auth success:

- shared helper tests now assert `firebase_uid` is absent from emitted runtime user payloads and that `firebase_uid`-only sessions are rejected before any lookup
- local login tests now inspect the actual captured `create_session` call and assert both kwargs and metadata omit `firebase_uid`
- websocket contract proof was repaired from committed merge markers and kept on the cookie-only transport/error-code boundary while asserting no `firebase_uid` cache lookup occurs
- direct adapter serializer proof (`tests/auth/test_user_conversion.py`) was updated to match the canonical payload shape

## Verification

Task-level proof passed:

- `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py`
- `cd backend-hormonia && pytest -q tests/auth/test_user_conversion.py`

Slice-level verification status recorded during this task:

- ✅ `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py`
- ✅ `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts`
- ✅ `cd frontend-hormonia && npm run build`
- ❌ `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py` — failures are in the later T03 surface (`AuditService` API/utility drift and admin extension RBAC/DLQ behavior), not in the T02 auth/cache/login/websocket seam
- ❌ `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all && bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` — now failing on expected S05/T05 allowlist drift because the removed `firebase_uid` hotspots in `auth_session_shared.py`, `auth_user_adapter.py`, `routers/auth.py`, `user_cache_shared.py`, and `session_cache.py` no longer match the published approved anchors

## Diagnostics

For future inspection:

- rerun `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py`
  - shared helper failure => canonical session payload extraction / stale cache sanitization regressed
  - login failure => canonical Redis `create_session` write path started serializing `firebase_uid` again
  - websocket failure => cookie-only transport or stable websocket auth diagnostics drifted
- rerun `cd backend-hormonia && pytest -q tests/auth/test_user_conversion.py` if the shared adapter serializer is touched again
- rerun `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all` to confirm only republication drift remains until T05 republishes the allowlist/handoff

## Deviations

- Added `tests/auth/test_user_conversion.py` coverage update even though it was outside the task’s expected-output list, because `auth_user_adapter.py` stopped emitting `firebase_uid` and the direct serializer proof needed to stay honest.

## Known Issues

- The slice-level audit/admin/docs pack is still red in the T03-owned surface (`tests/services/audit/test_audit_service.py`, `tests/api/v2/test_admin_extensions.py`); this task did not change those failures.
- The S01 residue check is now red because the approved hotspot list still names seams removed by this task; that republication work belongs to T05.
- `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` still contains unrelated committed merge markers outside this task’s verification pack.

## Files Created/Modified

- `backend-hormonia/app/api/v2/auth_session_shared.py` — removed shared `firebase_uid` fallback/serialization from session restore.
- `backend-hormonia/app/api/v2/user_cache_shared.py` — narrowed shared cache hydration to canonical `user_id` and sanitized stale cached payloads.
- `backend-hormonia/app/api/v2/routers/auth.py` — removed login-time `firebase_uid` injection from canonical Redis session writes.
- `backend-hormonia/app/dependencies/auth_user_adapter.py` — stopped emitting `firebase_uid` from the shared runtime serializer.
- `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` — added absence/rejection proof for shared helper and cache seams.
- `backend-hormonia/tests/api/v2/test_auth_local_login.py` — captured Redis session writes and asserted canonical payload shape.
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` — restored the websocket contract file and kept cookie-only/stable-diagnostic proof green.
- `backend-hormonia/tests/auth/test_user_conversion.py` — aligned direct adapter serializer expectations with the canonical runtime payload.
