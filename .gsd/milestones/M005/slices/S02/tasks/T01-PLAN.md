---
estimated_steps: 4
estimated_files: 5
---

# T01: Make Firebase sync history explicit

**Slice:** S02 — Legado Firebase isolado como histórico explícito
**Milestone:** M005

## Description

Transform `user_sync_log` from an ambiguous live-looking model into an explicit Firebase historical surface, with an honest Alembic step and a runtime writer that still records sync events without promoting them back into the canonical domain.

## Steps

1. Add a new Alembic revision that renames or backfills `user_sync_log` into an explicit Firebase history surface while preserving existing rows and replay semantics.
2. Update the ORM model and any model export seam so the preserved table is clearly historical/append-only instead of a live domain object.
3. Rewire `FirebaseUserSyncService` to keep writing history through that explicit surface without changing the event meaning or adding runtime-coupled migration imports.
4. Add focused migration and unit proof for clean replay, existing-db upgrade, and append-only write behavior.

## Must-Haves

- [ ] Clean and existing databases both end with an explicit Firebase sync history surface rather than an ambiguous `user_sync_log` live contract.
- [ ] The sync writer still records historical rows without reintroducing a new canonical dependency on Firebase or breaking the S01 Alembic operability contract.

## Verification

- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_firebase_historical_boundary.py -k sync_history`
- `cd backend-hormonia && pytest -q tests/unit/test_firebase_sync_history.py`

## Observability Impact

- Signals added/changed: named assertions for `sync_history_surface` and append-only history writes.
- How a future agent inspects this: run the targeted migration/unit tests and inspect the historical-table naming and row-shape assertions.
- Failure state exposed: whether the regression is in clean/existing upgrade behavior or in the runtime writer path.

## Inputs

- `backend-hormonia/tests/migrations/test_alembic_operability.py` — S01 operability harness that must remain green.
- `backend-hormonia/app/models/user_sync_log.py` — current ambiguous sync-log model surface.
- `backend-hormonia/app/services/firebase_user_sync_service.py` — current writer that must survive the boundary publication.
- S01 summary insight — new revisions must preserve scrubbed-env replay and avoid module-import-time runtime dependencies.

## Expected Output

- `backend-hormonia/alembic/versions/<new_revision>_publish_firebase_history_boundary.py` — honest migration for the sync-history boundary.
- `backend-hormonia/app/models/user_sync_log.py` and related model/export seam — explicit historical ownership for the preserved sync rows.
- `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py` and `backend-hormonia/tests/unit/test_firebase_sync_history.py` — proof of upgrade and write-path behavior.
