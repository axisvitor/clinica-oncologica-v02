---
estimated_steps: 4
estimated_files: 8
---

# T02: Quarantine `firebase_uid` from canonical audit and API contracts

**Slice:** S02 — Legado Firebase isolado como histórico explícito
**Milestone:** M005

## Description

Stop the official read/write surfaces from treating `firebase_uid` as live contract data while preserving only the chosen historical residue in audit storage, and keep the still-live Firebase-era user fields out of this slice’s archival story.

## Steps

1. Narrow the audit model and legacy audit-writer behavior so `firebase_uid` is preserved only as explicit historical/read-only residue and canonical writes keep it null/sanitized.
2. Remove `firebase_uid` from the official user, admin, and physician serializer/schema surfaces while leaving still-live fields like `firebase_custom_claims`, `firebase_last_sign_in`, `firebase_display_name`, `firebase_photo_url`, and `auth_provider` untouched for S03.
3. Align admin/read-side helpers so any preserved historical audit residue is filtered out of canonical payloads and exports.
4. Add focused API/service proof that the canonical payload boundary and audit-write contract stay honest.

## Must-Haves

- [ ] Official user/admin/physician payloads stop exposing `firebase_uid` as canonical field without falsely classifying still-live Firebase-era fields as archival.
- [ ] Canonical audit writes persist `firebase_uid=None`, and any preserved forensic value remains accessible only through the chosen historical/read-only boundary.

## Verification

- `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_firebase_boundary_contracts.py -k 'audit or canonical_payload'`

## Observability Impact

- Signals added/changed: named audit/service assertions for canonical null writes and API assertions for sanitized payloads.
- How a future agent inspects this: rerun the targeted audit/API tests and inspect the serialized payload keys plus persisted audit row fields.
- Failure state exposed: whether the regression came from write-side audit handling or read-side canonical serialization.

## Inputs

- `backend-hormonia/app/models/audit_log.py` — current audit schema still carrying `firebase_uid` and legacy index narrative.
- `backend-hormonia/app/services/audit_log.py` — legacy writer that still accepts direct `firebase_uid` input today.
- `backend-hormonia/app/api/v2/routers/users.py`, `backend-hormonia/app/api/v2/routers/physicians/crud.py`, `backend-hormonia/app/schemas/v2/physicians.py`, `backend-hormonia/app/schemas/v2/admin.py` — canonical payload surfaces that still need narrowing.
- Research constraint — `firebase_custom_claims`, `firebase_last_sign_in`, `firebase_display_name`, `firebase_photo_url`, and `auth_provider` still carry live behavior and cannot be archived in this task.

## Expected Output

- `backend-hormonia/app/models/audit_log.py` and `backend-hormonia/app/services/audit_log.py` — audit boundary aligned with historical-only `firebase_uid` retention.
- `backend-hormonia/app/api/v2/routers/users.py`, `backend-hormonia/app/api/v2/routers/physicians/crud.py`, `backend-hormonia/app/schemas/v2/physicians.py`, `backend-hormonia/app/schemas/v2/admin.py`, `backend-hormonia/app/api/v2/routers/admin_extensions/utils.py` — canonical payloads with `firebase_uid` removed.
- `backend-hormonia/tests/api/v2/test_firebase_boundary_contracts.py` — focused proof of the canonical read/write contract.
