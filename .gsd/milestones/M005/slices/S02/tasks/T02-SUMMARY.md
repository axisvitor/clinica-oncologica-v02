---
id: T02
parent: S02
milestone: M005
provides:
  - Canonical audit writes now discard `firebase_uid`, and official user/admin/physician payloads no longer publish it as live contract data.
key_files:
  - backend-hormonia/app/services/audit_log.py
  - backend-hormonia/app/api/v2/routers/users.py
  - backend-hormonia/app/api/v2/routers/admin/utils.py
  - backend-hormonia/app/api/v2/routers/physicians/crud.py
  - backend-hormonia/tests/api/v2/test_firebase_boundary_contracts.py
  - backend-hormonia/tests/services/audit/test_audit_service.py
key_decisions:
  - Keep `audit_logs.firebase_uid` as historical residue only, but force canonical write paths to persist it as `NULL` and strip it from metadata.
  - Sanitize stale cached `/api/v2/users/me` payloads on read so old cache entries cannot republish `firebase_uid` after the contract narrows.
patterns_established:
  - Canonical payload boundaries strip quarantined legacy identity fields even when legacy callers or caches still send them.
  - Focused boundary tests use named `audit_contract` / `canonical_payload` assertions so write-side and read-side regressions fail separately.
observability_surfaces:
  - `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py`
  - `cd backend-hormonia && pytest -q tests/api/v2/test_firebase_boundary_contracts.py -k 'audit or canonical_payload'`
  - `cd backend-hormonia && pytest -q tests/unit/test_firebase_sync_history.py tests/services/audit/test_audit_service.py tests/api/v2/test_firebase_boundary_contracts.py`
duration: 1h05m
verification_result: passed
completed_at: 2026-03-15T10:19:14-03:00
# Set blocker_discovered: true only if execution revealed the remaining slice plan
# is fundamentally invalid (wrong API, missing capability, architectural mismatch).
# Do NOT set true for ordinary bugs, minor deviations, or fixable issues.
blocker_discovered: false
---

# T02: Quarantine `firebase_uid` from canonical audit and API contracts

**Canonical audit writes now null out `firebase_uid`, cached/profile/admin/physician payloads stop emitting it, and the slice has focused proof for both the write-side and read-side boundary.**

## What Happened

I narrowed the canonical read/write seam instead of deleting the preserved residue outright.

On the write side, `backend-hormonia/app/services/audit_log.py` now treats any `firebase_uid` input as legacy compatibility only: it strips `firebase_uid` out of metadata, logs the drop without echoing the value, and persists canonical audit rows with `firebase_uid=None`. `backend-hormonia/app/models/audit_log.py` was updated to describe the column/index honestly as historical-only residue rather than live authenticated identity.

On the read side, I removed `firebase_uid` from the official admin and physician serializers/schemas and kept the still-live Firebase-era fields in place (`firebase_last_sign_in`, `firebase_display_name`, `firebase_photo_url`, `firebase_email_verified`). `backend-hormonia/app/api/v2/routers/admin/utils.py` now sources `last_login` from `firebase_last_sign_in`, and `backend-hormonia/app/api/v2/routers/admin/users.py` uses a versioned cache prefix for single-user responses so stale cached admin payloads do not outlive the contract change. `backend-hormonia/app/api/v2/routers/users.py` now sanitizes stale cached `/users/me` payloads before returning or rewriting them, so old cache entries cannot reintroduce `firebase_uid`.

For admin audit read surfaces, `backend-hormonia/app/api/v2/routers/admin_extensions/utils.py` now makes the filtered historical metadata keys explicit, and I added focused proof in `backend-hormonia/tests/api/v2/test_firebase_boundary_contracts.py` plus extra legacy-writer proof in `backend-hormonia/tests/services/audit/test_audit_service.py`.

## Verification

Passed targeted task verification:
- `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_firebase_boundary_contracts.py -k 'audit or canonical_payload'`

Passed slice-level checks touched by T02:
- `cd backend-hormonia && pytest -q tests/unit/test_firebase_sync_history.py tests/services/audit/test_audit_service.py tests/api/v2/test_firebase_boundary_contracts.py`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py`
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py tests/migrations/test_firebase_historical_boundary.py`

Still failing outside T02’s code path:
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_firebase_historical_boundary.py -k 'sync_history_surface or named_failure'`
  - existing-db upgrade branch still fails on `relation "alembic_version" does not exist` while upgrading to `a9c4e1d2b7f0`; this was reproduced after T02 but not introduced by these contract changes.

## Diagnostics

Future agents can inspect the boundary with:
- `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py -k 'audit_contract or legacy_writer or login_success_helper'`
- `cd backend-hormonia && pytest -q tests/api/v2/test_firebase_boundary_contracts.py -k 'audit or canonical_payload'`
- `cd backend-hormonia && pytest -q tests/unit/test_firebase_sync_history.py tests/services/audit/test_audit_service.py tests/api/v2/test_firebase_boundary_contracts.py`

The focused assertions expose failures as either:
- `audit_contract ...` for canonical audit write regressions, or
- `canonical_payload ...` for read-side/user/admin/physician/export regressions.

## Deviations

- I also version-bumped the cached admin single-user key prefix in `backend-hormonia/app/api/v2/routers/admin/users.py` so stale cached payloads cannot keep serving the pre-T02 contract after deploy.

## Known Issues

- The slice’s focused existing-db migration proof still fails on a pre-existing Alembic upgrade path (`alembic_version` missing during upgrade to `a9c4e1d2b7f0`). That failure was reproduced during T02 verification but not fixed here.

## Files Created/Modified

- `backend-hormonia/app/models/audit_log.py` — reworded `firebase_uid`/index metadata as historical-only audit residue.
- `backend-hormonia/app/services/audit_log.py` — sanitized legacy `firebase_uid` input out of canonical audit writes and metadata.
- `backend-hormonia/app/api/v2/routers/users.py` — sanitized stale cached `/users/me` payloads and rewrote cleaned cache entries.
- `backend-hormonia/app/api/v2/routers/admin/utils.py` — removed `firebase_uid` from admin serialization and mapped `last_login` to the still-live sign-in field.
- `backend-hormonia/app/api/v2/routers/admin/users.py` — versioned the single-user cache key to avoid stale pre-T02 payloads.
- `backend-hormonia/app/api/v2/routers/physicians/crud.py` — removed `firebase_uid` from physician payload assembly.
- `backend-hormonia/app/schemas/v2/admin.py` — removed `firebase_uid` from the official admin user response schema.
- `backend-hormonia/app/schemas/v2/physicians.py` — removed `firebase_uid` from the physician response schema and kept live Firebase-era profile fields explicit.
- `backend-hormonia/app/api/v2/routers/admin_extensions/utils.py` — made the filtered historical audit metadata key set explicit.
- `backend-hormonia/tests/services/audit/test_audit_service.py` — added legacy audit-writer proof for canonical null writes and metadata sanitization.
- `backend-hormonia/tests/api/v2/test_firebase_boundary_contracts.py` — added focused API/export proof for cached user payloads, admin user payloads, physician payloads, and audit export filtering.
- `.gsd/DECISIONS.md` — recorded the canonical `firebase_uid` quarantine decision for downstream slices.
