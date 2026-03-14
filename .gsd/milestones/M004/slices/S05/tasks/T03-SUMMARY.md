---
id: T03
parent: S05
milestone: M004
provides:
  - Audit extraction/persistence, admin audit output, and routed operator docs now describe the canonical `user_id` + cookie-backed session runtime instead of Firebase-era identity/header semantics.
key_files:
  - backend-hormonia/app/middleware/hipaa_audit_middleware.py
  - backend-hormonia/app/services/audit/audit_service.py
  - backend-hormonia/app/api/v2/routers/admin_extensions/utils.py
  - backend-hormonia/app/api/v2/routers/admin_extensions/audit.py
  - backend-hormonia/app/schemas/v2/admin_extensions.py
  - backend-hormonia/app/api/v2/routers/docs/data_providers.py
  - backend-hormonia/tests/services/audit/test_audit_service.py
  - backend-hormonia/tests/api/v2/test_admin_extensions.py
  - backend-hormonia/tests/api/v2/test_docs.py
key_decisions:
  - Treat async runtime audit context as canonical `user_id`/cookie-session state only; ignore legacy `firebase_uid` input and strip it from emitted runtime metadata/resource identifiers instead of preserving it in live audit writes.
  - Treat admin audit responses/exports and routed docs/examples as part of the live auth contract, so they must omit `firebase_uid` and stop teaching manual session-header transport.
patterns_established:
  - HIPAA audit middleware captures cookie session context up front and refreshes canonical `request.state.user_id` / `session_id` after downstream auth resolution before writing the audit record.
  - Admin audit serialization removes `firebase_uid` from both top-level output and `event_metadata`, and export only honors the supported canonical field list.
  - Focused audit/admin/docs proof is narrow by design: audit tests pin middleware/service behavior, admin tests pin serializer/schema/export shape, and docs tests pin guide/example content.
observability_surfaces:
  - `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py`
  - `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py`
  - `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
duration: 2h01m
verification_result: passed
completed_at: 2026-03-14T18:11:00-03:00
blocker_discovered: false
---

# T03: Converge audit, admin, and operator docs surfaces on the canonical runtime

**Audit extraction, admin audit output, and routed operator docs now converge on the canonical cookie-backed runtime and no longer emit Firebase-era identity as the official story.**

## What Happened

I updated the runtime audit path first.

- `backend-hormonia/app/middleware/hipaa_audit_middleware.py`
  - switched the middleware to the async audit service directly instead of the legacy package-default service
  - removed `request.state.firebase_uid` reads and stopped treating `X-Session-ID` as a live transport
  - kept cookie session capture in the request pre-pass, then refreshed canonical `request.state.user_id` / `request.state.session_id` after downstream auth dependencies ran so persisted audit rows reflect the resolved runtime identity
- `backend-hormonia/app/services/audit/audit_service.py`
  - removed `firebase_uid` from the async `AuditEventContext`
  - made the context explicitly ignore legacy extra input
  - normalized/sanitized runtime metadata before persistence so emitted audit rows no longer write `firebase_uid` back out through top-level context or `resource_identifiers`

Then I aligned the admin audit surface.

- `backend-hormonia/app/api/v2/routers/admin_extensions/utils.py`
  - removed top-level `firebase_uid` from serialized audit responses
  - stripped `firebase_uid` from emitted `event_metadata` before response/export redaction
- `backend-hormonia/app/api/v2/routers/admin_extensions/audit.py`
  - removed `firebase_uid` from the default export field list
  - constrained requested export fields to the supported canonical set so export no longer advertises the Firebase-era field as official output
- `backend-hormonia/app/schemas/v2/admin_extensions.py`
  - removed `firebase_uid` from the public audit schema and example payload
  - tightened the field description to make `user_id` the canonical identity field

Finally I rewrote the routed docs/operator examples.

- `backend-hormonia/app/api/v2/routers/docs/data_providers.py`
  - replaced Firebase/session-header guidance in the getting-started and authentication guides with cookie-backed `session_id` instructions
  - rewrote the live code examples to use cookie-aware clients (`requests.Session()`, `withCredentials: true`) instead of `X-Session-ID`
  - replaced the Firebase login example with the canonical cookie-backed login/session flow

I also replaced the stale proof files with focused contract tests so failures now point at the exact adjacent surface instead of unrelated historical behavior.

## Verification

Task-level proof passed:

- `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py`

Slice-level verification status recorded during this task:

- ✅ `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py`
- ✅ `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py`
- ✅ `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py`
- ✅ `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts`
- ✅ `cd frontend-hormonia && npm run build`
- ⚠️ `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all` — report completed, but it records allowlist drift that T05 still needs to republish
- ❌ `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` — still failing on expected S05/T05 allowlist drift (`auth_session_shared.py`, `routers/auth.py`, `user_cache_shared.py`, `session_cache.py`, `auth_user_adapter.py` no longer match the published approved hotspots)

## Diagnostics

For future inspection:

- rerun `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py`
  - `test_audit_service.py` failure => canonical audit extraction/persistence regressed (middleware refresh, context sanitization, or async audit write path)
  - `test_admin_extensions.py` failure => admin serializer/schema/export started leaking `firebase_uid` again
  - `test_docs.py` failure => routed guide/example content drifted back toward Firebase or header-based session guidance
- rerun `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` after T05 to confirm the published residue boundary caught up with the now-cleaned hotspots

## Deviations

- I replaced the stale audit/admin proof files with focused contract suites instead of repairing unrelated historical coverage. The old files were exercising the wrong audit service export and broad DLQ/RBAC behavior that obscured the exact adjacent-surface contract this task owns.

## Known Issues

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` and the related S01 handoff artifacts are now stale relative to the hotspots already removed by T01–T03, so `verify-runtime-residue.sh --check all` still fails until T05 republishes that boundary.

## Files Created/Modified

- `backend-hormonia/app/middleware/hipaa_audit_middleware.py` — switched runtime audit extraction to canonical cookie/request-state identity and the async audit service.
- `backend-hormonia/app/services/audit/audit_service.py` — removed `firebase_uid` from the async runtime context and sanitized legacy identity keys before audit persistence.
- `backend-hormonia/app/api/v2/routers/admin_extensions/utils.py` — removed `firebase_uid` from serialized admin audit output and nested metadata.
- `backend-hormonia/app/api/v2/routers/admin_extensions/audit.py` — removed `firebase_uid` from export defaults and limited export fields to the supported canonical contract.
- `backend-hormonia/app/schemas/v2/admin_extensions.py` — removed `firebase_uid` from the public admin audit schema/example.
- `backend-hormonia/app/api/v2/routers/docs/data_providers.py` — rewrote routed docs/examples around the cookie-backed session contract.
- `backend-hormonia/tests/services/audit/test_audit_service.py` — added focused proof for canonical middleware/service audit behavior.
- `backend-hormonia/tests/api/v2/test_admin_extensions.py` — added focused proof for admin audit serializer/schema/export output.
- `backend-hormonia/tests/api/v2/test_docs.py` — added focused proof for routed guide/example guidance.
- `.gsd/DECISIONS.md` — recorded the adjacent audit/admin/docs runtime-contract decision for downstream slice work.
