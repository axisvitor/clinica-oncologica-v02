---
id: T01
parent: S02
milestone: M005
provides:
  - Explicit Firebase sync history boundary with an honest Alembic rename, append-only ORM surface, and focused migration/runtime proof.
key_files:
  - backend-hormonia/alembic/versions/m005_s02_t01_publish_firebase_history_boundary.py
  - backend-hormonia/app/models/user_sync_log.py
  - backend-hormonia/app/services/firebase_user_sync_service.py
  - backend-hormonia/tests/migrations/test_firebase_historical_boundary.py
  - backend-hormonia/tests/unit/test_firebase_sync_history.py
  - backend-hormonia/tests/migrations/test_alembic_operability.py
key_decisions:
  - Publish the preserved sync residue as `firebase_sync_history` instead of keeping the live-looking `user_sync_log` contract.
  - Model the history surface as append-only and drop the bogus live-looking `updated_at` ORM expectation from this boundary.
patterns_established:
  - Historical Firebase residue is exposed through explicitly named archival tables plus focused migration/runtime proof.
  - Migration tests distinguish clean replay from existing-db upgrade and use named failure prefixes to localize regressions.
observability_surfaces:
  - `pytest -q tests/migrations/test_firebase_historical_boundary.py -k sync_history`
  - `pytest -q tests/unit/test_firebase_sync_history.py`
  - Named assertion prefixes: `sync_history_surface`, `named_failure`, and `append_only_history_write`
duration: ~55m
verification_result: passed
completed_at: 2026-03-14T16:10:00-03:00
blocker_discovered: false
---

# T01: Make Firebase sync history explicit

**Renamed the preserved sync residue to `firebase_sync_history`, rewired the Firebase writer to append explicit history rows, and added proof for clean replay, existing-db upgrade, and append-only writes.**

## What Happened

Added `backend-hormonia/alembic/versions/m005_s02_t01_publish_firebase_history_boundary.py` to rename `user_sync_log` into `firebase_sync_history`, rename the primary key / FK / index names to match the new boundary, and preserve existing rows plus legacy residue columns for replay. Updated `backend-hormonia/app/models/user_sync_log.py` to expose an explicit `FirebaseSyncHistory` append-only model instead of a live-looking `UserSyncLog`, including removal of the ORM-only `updated_at` expectation that did not exist in the migrated table. Rewired `FirebaseUserSyncService` to append history through `_append_firebase_sync_history()` and the explicit history model without importing migration code or changing the recorded event meaning. Added focused proof in `tests/migrations/test_firebase_historical_boundary.py` for both clean replay and existing-db upgrade preservation, plus `tests/unit/test_firebase_sync_history.py` for append-only writer behavior and non-blocking rollback on history-write failure. Updated `tests/migrations/test_alembic_operability.py` so the S01 operability harness tracks the new head revision.

This addresses both task must-haves: clean and existing databases now land on an explicit Firebase history surface instead of the ambiguous `user_sync_log` contract, and the runtime sync writer still records historical rows without reviving Firebase as a canonical live model.

## Verification

Passed task-level checks:
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_firebase_historical_boundary.py -k sync_history`
- `cd backend-hormonia && pytest -q tests/unit/test_firebase_sync_history.py`

Passed slice-level checks already reachable from T01:
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py tests/migrations/test_firebase_historical_boundary.py`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py`

Current slice-level partial failure, expected to be owned by later tasks:
- `cd backend-hormonia && pytest -q tests/unit/test_firebase_sync_history.py tests/services/audit/test_audit_service.py tests/api/v2/test_firebase_boundary_contracts.py`
  - Fails immediately with `ERROR: file or directory not found: tests/api/v2/test_firebase_boundary_contracts.py`

## Diagnostics

Future agents can inspect this boundary by running:
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_firebase_historical_boundary.py -k 'sync_history_surface or named_failure'`
- `cd backend-hormonia && pytest -q tests/unit/test_firebase_sync_history.py -k append_only_history_write`

The migration proof localizes failures with `sync_history_surface` / `named_failure` prefixes so it is obvious whether the break is in clean replay or existing-db preservation. The runtime proof localizes failures with `append_only_history_write` so writer regressions show up separately from migration issues.

## Deviations

- Updated `tests/migrations/test_alembic_operability.py` to follow the new Alembic head revision created by this task. This was required to keep the S01 operability harness truthful after publishing the new boundary.
- Appended the T01 boundary decision to `.gsd/DECISIONS.md` because the table rename + append-only model contract affects downstream T02/T03 work.

## Known Issues

- `tests/api/v2/test_firebase_boundary_contracts.py` is still missing, so the second slice-level verification command cannot go green until T02/T03 add the canonical audit/API proof pack.
- `tests/services/audit/test_audit_service.py` was not changed in T01; the audit-side Firebase residue cleanup still belongs to T02.

## Files Created/Modified

- `backend-hormonia/alembic/versions/m005_s02_t01_publish_firebase_history_boundary.py` — new Alembic revision that publishes `firebase_sync_history` and renames legacy constraints/indexes.
- `backend-hormonia/app/models/user_sync_log.py` — replaced the live-looking `UserSyncLog` model with the explicit append-only `FirebaseSyncHistory` surface.
- `backend-hormonia/app/models/__init__.py` — exported `FirebaseSyncHistory` instead of `UserSyncLog` from the model seam.
- `backend-hormonia/app/services/firebase_user_sync_service.py` — rewired runtime sync logging to `_append_firebase_sync_history()`.
- `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py` — added clean replay and existing-db upgrade proof with named migration failures.
- `backend-hormonia/tests/unit/test_firebase_sync_history.py` — added append-only writer and rollback-path proof.
- `backend-hormonia/tests/migrations/test_alembic_operability.py` — updated the expected Alembic head token.
- `.gsd/milestones/M005/slices/S02/S02-PLAN.md` — added the pre-flight diagnostic verification step and marked T01 done.
- `.gsd/DECISIONS.md` — recorded the explicit Firebase history publication boundary.
- `.gsd/STATE.md` — advanced the next action to T02.
