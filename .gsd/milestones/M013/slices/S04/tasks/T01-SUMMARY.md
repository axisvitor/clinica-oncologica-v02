---
id: T01
parent: S04
milestone: M013
key_files:
  - backend-hormonia/tests/api/v2/test_private_upload_serving.py
key_decisions:
  - Regression coverage verifies private files only through app routes and temporary filesystem roots; public/static access is treated as a security failure.
duration: 
verification_result: passed
completed_at: 2026-05-13T00:42:09.284Z
blocker_discovered: false
---

# T01: Added FastAPI regression tests locking private upload defaults, public static denial, gated owner/admin downloads, DB metadata fallback, missing IDs, and unsafe storage-path failures.

**Added FastAPI regression tests locking private upload defaults, public static denial, gated owner/admin downloads, DB metadata fallback, missing IDs, and unsafe storage-path failures.**

## What Happened

Created `backend-hormonia/tests/api/v2/test_private_upload_serving.py` as an app-surface regression suite for the S04 private upload boundary. The tests use temporary upload roots and auth dependency overrides, avoid repository `uploads/`, and exercise real FastAPI routes for default-private upload responses, `/uploads` denial for private storage paths, gated download authorization for anonymous/owner/foreign/admin users, DB-backed metadata cache misses, missing upload IDs, and persisted unsafe storage paths. The assertions check generic failure responses and verify private bytes and filesystem details are not leaked.

## Verification

Ran the task verification command from the backend package: `cd backend-hormonia && pytest tests/api/v2/test_private_upload_serving.py -q`. All 7 focused private-upload serving tests passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && pytest tests/api/v2/test_private_upload_serving.py -q` | 0 | ✅ pass | 27632ms |

## Deviations

None.

## Known Issues

The pytest run emits existing warning output outside the focused assertions; no task-blocking issue remains for T01.

## Files Created/Modified

- `backend-hormonia/tests/api/v2/test_private_upload_serving.py`
