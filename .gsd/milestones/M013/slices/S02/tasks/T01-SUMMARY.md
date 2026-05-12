---
id: T01
parent: S02
milestone: M013
key_files:
  - backend-hormonia/app/api/v2/patients_shared_helpers.py
  - backend-hormonia/tests/unit/api/v2/test_patient_access_helpers.py
key_decisions:
  - Centralized patient ownership denial logging in `patients_shared_helpers.py` with ID/reason-only structured fields and fail-closed authorization semantics.
duration: 
verification_result: passed
completed_at: 2026-05-12T18:36:49.157Z
blocker_discovered: false
---

# T01: Added a reusable patient ownership helper that allows admins or assigned doctors, fails closed on malformed contexts, and emits ID-only denial diagnostics.

**Added a reusable patient ownership helper that allows admins or assigned doctors, fails closed on malformed contexts, and emits ID-only denial diagnostics.**

## What Happened

Extended `patients_shared_helpers.py` with `assert_admin_or_assigned_doctor` and `load_patient_with_access`. The boundary uses the shared auth helper UUID/role extraction, validates actor context before any admin override, performs one `Patient.id` lookup in the loader, returns 404 only when the patient row is missing, and raises generic 403 responses for foreign, unassigned, malformed, or unsupported actor contexts. Denial logging is centralized behind a safe wrapper so logging failures do not alter authorization outcomes, and logged fields are restricted to actor id, actor role, patient/resource id, and reason.

## Verification

Ran the targeted helper unit suite. Tests cover dict and `User` model users, admin override, assigned doctor access, foreign doctor 403, missing/invalid user IDs including admin and doctor roles, malformed role sessions, unassigned patient 403, patient not-found 404, one lookup per loader call, generic 403 details, PHI-free deny log text, and logging failure resilience. The helper import path is exercised by the tests without circular import failure.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && pytest tests/unit/api/v2/test_patient_access_helpers.py -q` | 0 | ✅ pass | 24544ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/api/v2/patients_shared_helpers.py`
- `backend-hormonia/tests/unit/api/v2/test_patient_access_helpers.py`
