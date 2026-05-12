---
id: T01
parent: S04
milestone: M013
key_files:
  - backend-hormonia/tests/api/v2/test_private_upload_serving.py
key_decisions:
  - Use route-level FastAPI tests with temporary upload roots rather than helper-only tests.
  - Use the registered upload create/info path to avoid obscuring security assertions with the existing double-prefix mismatch, but assert `/api/v2/upload/{id}/download` as the desired gated download contract.
duration: 
verification_result: passed
completed_at: 2026-05-12T23:52:37.731Z
blocker_discovered: false
---

# T01: Added FastAPI regression coverage for private upload responses, public static denial, gated download authorization, metadata cache misses, missing IDs, and unsafe storage paths.

**Added FastAPI regression coverage for private upload responses, public static denial, gated download authorization, metadata cache misses, missing IDs, and unsafe storage paths.**

## What Happened

Created `backend-hormonia/tests/api/v2/test_private_upload_serving.py` as a route-level regression suite for the S04 private upload boundary. The tests patch upload storage and the `/uploads` StaticFiles mount to a temporary directory, disable external scan/quota dependencies inside tests, switch auth dependency overrides between anonymous/owner/foreign doctor/admin users, and seed persisted upload records for DB-backed scenarios. Coverage now documents that private uploads must return gated URLs instead of `/uploads`, private storage paths must not be publicly served, owner/admin gated downloads must return bytes while anonymous/foreign users fail, metadata cache misses must read persisted uploads without public URLs, missing IDs must return generic 404s, and `..`/absolute persisted paths must fail closed without leaking bytes or filesystem paths.

## Verification

Ran the focused verification command `cd backend-hormonia && pytest tests/api/v2/test_private_upload_serving.py -q`. The command exited 1 as expected for this TDD regression task: 3 tests passed and 4 failed for the current implementation's security-contract gaps (private response URL still starts with `/uploads`, public static `/uploads` returns private bytes, owner gated download route returns 404 because the route is not implemented, and metadata cache miss returns 404 instead of DB-backed private metadata).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && pytest tests/api/v2/test_private_upload_serving.py -q` | 1 | ✅ expected-red regression failures captured | 35767ms |

## Deviations

Added a transactional Postgres test-schema guard for the existing local `uploads` table because the developer test database can contain an older placeholder schema; this keeps failures focused on private-serving behavior instead of setup DDL drift. Also added a helper that targets the currently registered create/info route when it is double-prefixed, while still asserting the desired gated download URL contract exactly.

## Known Issues

Expected red failures remain for later S04 tasks: private upload responses expose `/uploads`, public static serving returns private file bytes, `/api/v2/upload/{id}/download` is not implemented for owner/admin access, and metadata cache misses do not return persisted upload metadata.

## Files Created/Modified

- `backend-hormonia/tests/api/v2/test_private_upload_serving.py`
