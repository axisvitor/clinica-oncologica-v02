---
id: T01
parent: S01
milestone: M011
provides:
  - Alembic migration creating composite index idx_pfs_patient_started on patient_flow_states(patient_id, started_at DESC)
key_files:
  - backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py
key_decisions: []
patterns_established:
  - Use if_not_exists=True on create_index for idempotent migrations
observability_surfaces:
  - "SELECT indexname FROM pg_indexes WHERE tablename = 'patient_flow_states'" shows idx_pfs_patient_started after migration
  - "alembic current" shows m011_s01_patient_flow_states_index as head after upgrade
duration: 5m
verification_result: passed
completed_at: 2026-03-17
blocker_discovered: false
---

# T01: Create Alembic migration for patient_flow_states composite index

**Added Alembic migration m011_s01_patient_flow_states_index creating composite index idx_pfs_patient_started on patient_flow_states(patient_id, started_at DESC) for ROW_NUMBER() window function acceleration**

## What Happened

Created the migration file chaining from `m008_s01_t03_sessions_align`. The `upgrade()` uses `op.create_index` with `sa.text("started_at DESC")` for the DESC ordering and `if_not_exists=True` for idempotent re-runs. The `downgrade()` drops the index.

## Verification

All 7 must-haves confirmed:

- `ast.parse` → OK
- `down_revision = "m008_s01_t03_sessions_align"` → match
- `revision = "m011_s01_patient_flow_states_index"` → match
- Index name `idx_pfs_patient_started` → present in upgrade and downgrade
- `started_at DESC` → present in sa.text() call
- `if_not_exists=True` → present
- `drop_index` in downgrade → present

Slice-level verifications passing after T01: V1 (ast.parse migration), V3 (down_revision). V2, V4-V8 are for T02.

## Diagnostics

- After `alembic upgrade head`: `SELECT indexname FROM pg_indexes WHERE tablename = 'patient_flow_states'` should list `idx_pfs_patient_started`
- `EXPLAIN ANALYZE` on the physician/patients ROW_NUMBER() query should show Index Scan on idx_pfs_patient_started instead of Seq Scan + Sort
- If migration not applied: `alembic current` stays at m008_s01_t03_sessions_align — endpoint works but slower

## Deviations

None

## Known Issues

None

## Files Created/Modified

- `backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py` — new Alembic migration creating composite index for ROW_NUMBER() optimization
