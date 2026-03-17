---
estimated_steps: 4
estimated_files: 1
---

# T01: Create Alembic migration for patient_flow_states composite index

**Slice:** S01 — Backend caching + index composto
**Milestone:** M011

## Description

Create an Alembic migration that adds a composite index on `patient_flow_states(patient_id, started_at DESC)`. This index accelerates the ROW_NUMBER() window function in the physician/patients endpoint, which partitions by patient_id and orders by started_at DESC. Without it, PostgreSQL does a sequential scan + in-memory sort per patient — scales poorly as flow states accumulate.

The migration must chain from the current Alembic head `m008_s01_t03_sessions_align`. Use `if_not_exists=True` for idempotent re-runs.

## Steps

1. Create file `backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py`
2. Set metadata: `revision = "m011_s01_patient_flow_states_index"`, `down_revision = "m008_s01_t03_sessions_align"`, `branch_labels = None`, `depends_on = None`
3. In `upgrade()`: use `op.create_index("idx_pfs_patient_started", "patient_flow_states", ["patient_id", sa.text("started_at DESC")], unique=False, if_not_exists=True)` — import `sa` from `sqlalchemy`
4. In `downgrade()`: use `op.drop_index("idx_pfs_patient_started", table_name="patient_flow_states")`

## Must-Haves

- [ ] `revision = "m011_s01_patient_flow_states_index"` 
- [ ] `down_revision = "m008_s01_t03_sessions_align"`
- [ ] Index name: `idx_pfs_patient_started`
- [ ] Columns: `patient_id` + `started_at DESC` (DESC is critical for the window function ordering)
- [ ] `if_not_exists=True` in create_index for safety
- [ ] `downgrade()` drops the index
- [ ] File passes `ast.parse`

## Verification

- `python3 -c "import ast; ast.parse(open('backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py').read()); print('OK')"` → prints OK
- `grep 'down_revision = "m008_s01_t03_sessions_align"' backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py` → match
- `grep 'idx_pfs_patient_started' backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py` → match
- `grep 'started_at DESC' backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py` → match

## Inputs

- Alembic migration chain head: `backend-hormonia/alembic/versions/m008_s01_t03_sessions_align.py` — current head, our `down_revision`
- Table schema: `patient_flow_states` has columns `patient_id` (UUID, indexed) and `started_at` (DateTime with timezone, `server_default=func.now()`)

## Observability Impact

- **New signal:** Index `idx_pfs_patient_started` visible via `SELECT indexname FROM pg_indexes WHERE tablename = 'patient_flow_states'` — confirms migration applied.
- **Inspection:** `EXPLAIN ANALYZE` on the physician/patients ROW_NUMBER() query should show Index Scan on `idx_pfs_patient_started` instead of sequential scan + sort.
- **Failure state:** If migration fails to apply, `alembic current` will show head at `m008_s01_t03_sessions_align` (not `m011_s01_patient_flow_states_index`). The endpoint still works but slower — no hard error.
- **Idempotency:** `if_not_exists=True` means re-running `alembic upgrade head` after a partial failure won't crash on duplicate index.

## Expected Output

- `backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py` — new Alembic migration creating composite index `idx_pfs_patient_started` on `patient_flow_states(patient_id, started_at DESC)`
