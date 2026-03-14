---
estimated_steps: 4
estimated_files: 8
---

# T03: Converge audit, admin, and operator docs surfaces on the canonical runtime

**Slice:** S05 — Resíduo funcional de Firebase removido do runtime adjacente
**Milestone:** M004

## Description

Remove Firebase from the adjacent backend surfaces that still describe or serialize it as if it were part of the live system. This task keeps the slice honest beyond auth/session helpers: audit context, admin audit responses, and routed operator docs all need to tell the same canonical story or the runtime remains operationally ambiguous even after the core session cleanup lands.

## Steps

1. Update `hipaa_audit_middleware.py` and `audit_service.py` so runtime audit extraction and persistence use canonical request/session identity and stop depending on `request.state.firebase_uid`.
2. Align admin audit serializers and schemas in `admin_extensions/utils.py` and `schemas/v2/admin_extensions.py` with the post-cut canonical runtime output, keeping M005 schema debt out of scope.
3. Rewrite the live routed docs guidance in `api/v2/routers/docs/data_providers.py` so operator examples and auth/session instructions describe cookie-backed canonical behavior instead of Firebase or `X-Session-ID` usage.
4. Extend the audit/admin/docs proof pack so failures show exactly which adjacent surface still leaks Firebase semantics.

## Must-Haves

- [ ] Audit extraction and persistence no longer rely on `request.state.firebase_uid` for the official runtime path.
- [ ] Admin audit payloads and examples stop advertising `firebase_uid` as an official runtime field.
- [ ] Routed docs content no longer tells operators to authenticate with Firebase or send `X-Session-ID`.
- [ ] Focused proof covers audit service behavior, admin extension serialization, and docs guidance together.

## Verification

- `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py`
- Confirm the updated assertions pin canonical session/audit fields and the docs guidance text, not just generic 200 responses.

## Observability Impact

- Signals added/changed: audit/admin/docs tests expose whether Firebase still leaks through runtime audit context, admin response serialization, or routed operator guidance.
- How a future agent inspects this: rerun the focused pytest pack and inspect the failing assertion to see whether the leak is in middleware/service behavior, admin schema output, or docs provider content.
- Failure state exposed: regressions stop hiding behind “auth still works” and instead point directly to the adjacent surface still treating Firebase as live.

## Inputs

- `backend-hormonia/app/middleware/hipaa_audit_middleware.py` — current audit extraction still reads `request.state.firebase_uid` even though canonical request state is already `user_id`-first.
- `backend-hormonia/app/services/audit/audit_service.py` — central runtime audit service still models/persists Firebase-era context.
- `backend-hormonia/app/api/v2/routers/admin_extensions/utils.py` and `backend-hormonia/app/schemas/v2/admin_extensions.py` — live admin audit serialization/schema seam.
- `backend-hormonia/app/api/v2/routers/docs/data_providers.py` — routed docs content still carries Firebase-era operator guidance.
- T02 output: shared login/session payloads already speak the canonical runtime contract.

## Expected Output

- `backend-hormonia/app/middleware/hipaa_audit_middleware.py` — audit extraction aligned to canonical session/request state.
- `backend-hormonia/app/services/audit/audit_service.py` — runtime audit context and writes no longer treat Firebase as live identity.
- `backend-hormonia/app/api/v2/routers/admin_extensions/utils.py` — admin audit serializer aligned to canonical runtime output.
- `backend-hormonia/app/schemas/v2/admin_extensions.py` — admin audit schema/examples updated for the post-cut contract.
- `backend-hormonia/app/api/v2/routers/docs/data_providers.py` — operator docs guidance rewritten around the canonical cookie-backed session contract.
- `backend-hormonia/tests/services/audit/test_audit_service.py` — proof for canonical audit context/output.
- `backend-hormonia/tests/api/v2/test_admin_extensions.py` — proof for canonical admin audit payloads.
- `backend-hormonia/tests/api/v2/test_docs.py` — proof for the updated routed docs guidance.
