---
id: T03
parent: S02
milestone: M005
provides:
  - Shared audit-schema fixtures now honor the historical Firebase boundary, and the slice proof localizes compat regressions under named `canonical_identity` failures.
key_files:
  - backend-hormonia/tests/conftest.py
  - backend-hormonia/tests/api/critical/conftest.py
  - backend-hormonia/tests/migrations/test_firebase_historical_boundary.py
  - backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py
  - backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py
key_decisions:
  - Shared Postgres fixture guards may patch only live `audit_logs` columns; they must not recreate historical `firebase_uid` residue or `idx_audit_firebase_time`.
  - Canonical session compatibility proof should fail under a dedicated `canonical_identity` prefix so fallback regressions stay distinct from migration/API boundary failures.
patterns_established:
  - Fixture drift on historical schema residue is enforced by migration proof that exercises shared conftest guards against a stripped table.
  - `user_id`-first session compatibility tests use named `canonical_identity` assertions to separate embedded canonical paths from quarantined `firebase_uid` fallback.
observability_surfaces:
  - `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_firebase_historical_boundary.py -k 'sync_history_surface or named_failure'`
  - `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py`
  - Named failures: `named_failure suite=... resurrected_historical_audit_firebase_*` and `canonical_identity surface=...`
duration: 1h10m
verification_result: passed
completed_at: 2026-03-15T10:34:15-03:00
# Set blocker_discovered: true only if execution revealed the remaining slice plan
# is fundamentally invalid (wrong API, missing capability, architectural mismatch).
# Do NOT set true for ordinary bugs, minor deviations, or fixable issues.
blocker_discovered: false
---

# T03: Make the proof pack and fixtures tell the new truth

**Shared fixture guards stopped resurrecting Firebase audit residue, and the final S02 proof pack now separates historical-boundary failures from canonical-identity compatibility failures.**

## What Happened

I removed the hidden schema backfill from both shared Postgres test harnesses. `backend-hormonia/tests/conftest.py` and `backend-hormonia/tests/api/critical/conftest.py` now patch only live `audit_logs` columns, with helper names and log messages updated to describe that live-column role honestly. They no longer recreate `audit_logs.firebase_uid` or `idx_audit_firebase_time` as default assumptions when a test database is behind the historical boundary.

To make that change durable instead of conventional, I extended `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py` with a focused proof that builds a stripped `audit_logs` table, runs both shared conftest guards, and fails with named `named_failure suite=... resurrected_historical_audit_firebase_*` diagnostics if either harness revives the historical Firebase column or index. The existing `sync_history_surface` / `named_failure` migration proof stayed intact.

The API/service boundary proof from T01/T02 was already carrying the named `sync_history_surface`, `audit_contract`, and `canonical_payload` failures, so T03’s remaining gap was the session compatibility side. I tightened `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py` and `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` with named `canonical_identity` assertions for embedded canonical sessions, `user_id`-first cache/db resolution, fallback session rehydration, cookie-only shared helpers, and the quarantined `firebase_uid` compat path. That makes compat regressions land in one bucket instead of generic assertion diffs.

## Verification

Passed task verification:
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py tests/migrations/test_firebase_historical_boundary.py`
- `cd backend-hormonia && pytest -q tests/unit/test_firebase_sync_history.py tests/services/audit/test_audit_service.py tests/api/v2/test_firebase_boundary_contracts.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py`

Passed full slice verification from `S02-PLAN.md`:
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py tests/migrations/test_firebase_historical_boundary.py`
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_firebase_historical_boundary.py -k 'sync_history_surface or named_failure'`
- `cd backend-hormonia && pytest -q tests/unit/test_firebase_sync_history.py tests/services/audit/test_audit_service.py tests/api/v2/test_firebase_boundary_contracts.py`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py`

## Diagnostics

Future agents can inspect the finished boundary with:
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_firebase_historical_boundary.py -k 'sync_history_surface or named_failure'`
- `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py -k 'audit_contract or legacy_writer or login_success_helper'`
- `cd backend-hormonia && pytest -q tests/api/v2/test_firebase_boundary_contracts.py -k 'audit or canonical_payload'`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py`

Failure localization now breaks down as:
- `sync_history_surface ...` / `named_failure ...` — migration replay, existing-db preservation, or fixture-drift regressions.
- `audit_contract ...` — canonical audit write/export regressions.
- `canonical_payload ...` — official API serialization regressions.
- `canonical_identity ...` — `user_id`-first session compatibility or quarantined fallback regressions.

## Deviations

- None.

## Known Issues

- None in the T03 slice verification pack; all listed S02 gates passed.

## Files Created/Modified

- `backend-hormonia/tests/conftest.py` — renamed the audit schema guard and removed the hidden Firebase audit column/index backfill.
- `backend-hormonia/tests/api/critical/conftest.py` — matched the critical-suite audit schema guard to the live-only historical boundary.
- `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py` — added named fixture-drift proof for both shared conftest guards alongside the existing sync-history checks.
- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py` — added named `canonical_identity` assertions for embedded canonical, `user_id`-first, fallback rehydration, and quarantined compat fallback paths.
- `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` — added named `canonical_identity` assertions for shared helper/session-id/user-cache compatibility proof.
- `.gsd/DECISIONS.md` — recorded the live-only audit fixture guard decision.
- `.gsd/milestones/M005/slices/S02/S02-PLAN.md` — marked T03 complete.
- `.gsd/milestones/M005/slices/S02/tasks/T03-SUMMARY.md` — recorded task outcome, verification, and diagnostics.
- `.gsd/STATE.md` — advanced the slice state past T03.
