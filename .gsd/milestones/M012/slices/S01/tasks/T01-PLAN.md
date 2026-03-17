---
estimated_steps: 5
estimated_files: 3
---

# T01: Create migration, model, and schemas for patient_flow_overrides

**Slice:** S01 — Tabela de overrides + API de merge
**Milestone:** M012

## Description

Create the data layer for per-patient flow overrides: an Alembic migration for the `patient_flow_overrides` table, a SQLAlchemy model in the existing `flow.py`, and Pydantic request/response schemas in a new `patient_overrides.py`. This is pure data scaffolding — no endpoints, no logic. T02 builds on top of everything created here.

The model follows the established pattern in `flow.py` (where `PatientFlowState` and `FlowTemplateVersion` already live). The schemas follow the pattern in `app/schemas/v2/templates.py` (where `DayConfigItem` is defined). BaseModel from `app.models.base` provides `id` (UUID PK), `created_at`, and `updated_at` — do NOT redeclare these.

## Steps

1. **Create Alembic migration** `backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py`:
   - `revision = "m012_s01_patient_flow_overrides"`
   - `down_revision = "m011_s01_patient_flow_states_index"`
   - Table `patient_flow_overrides` with columns:
     - `id` UUID PK DEFAULT `gen_random_uuid()` (from BaseModel, but migration needs explicit)
     - `patient_flow_state_id` UUID NOT NULL FK → `patient_flow_states.id` ON DELETE CASCADE
     - `day_number` INTEGER NOT NULL
     - `content` TEXT NOT NULL
     - `message_type` VARCHAR(50) NOT NULL DEFAULT `'question'`
     - `expects_response` BOOLEAN NOT NULL DEFAULT `false`
     - `skip` BOOLEAN NOT NULL DEFAULT `false`
     - `created_by` UUID (nullable)
     - `created_at` TIMESTAMPTZ NOT NULL DEFAULT `now()`
     - `updated_at` TIMESTAMPTZ NOT NULL DEFAULT `now()`
   - `UniqueConstraint('patient_flow_state_id', 'day_number')`
   - Index `idx_pfo_state_id` on `patient_flow_state_id`
   - Downgrade: `op.drop_table('patient_flow_overrides')`

2. **Add SQLAlchemy model** to `backend-hormonia/app/models/flow.py`:
   - Class `PatientFlowOverride(BaseModel)` with `__tablename__ = "patient_flow_overrides"`
   - Columns: `patient_flow_state_id` (UUID FK), `day_number` (Integer), `content` (Text), `message_type` (String(50) default 'question'), `expects_response` (Boolean default False), `skip` (Boolean default False), `created_by` (UUID nullable)
   - `__table_args__` with `UniqueConstraint('patient_flow_state_id', 'day_number', name='uq_pfo_state_day')`
   - Relationship: `flow_state = relationship("PatientFlowState", backref="overrides")`
   - Place AFTER `PatientFlowState` class (around line 220+)

3. **Create Pydantic schemas** in `backend-hormonia/app/schemas/v2/patient_overrides.py`:
   - `OverrideDayInput(BaseModel)`: `day_number: int`, `content: str`, `message_type: str = "question"`, `expects_response: bool = False`, `skip: bool = False`
   - `OverrideDayUpdateRequest(BaseModel)`: `days: list[OverrideDayInput]`
   - `MergedDayItem(BaseModel)`: `day_number: int`, `content: str`, `message_type: str`, `expects_response: bool`, `skip: bool`, `source: Literal["global", "override"]`, `editable: bool`
   - `MergedDayListResponse(BaseModel)`: `patient_id: UUID`, `flow_state_id: UUID`, `current_flow_day: int`, `days: list[MergedDayItem]`
   - Use `from __future__ import annotations`, `from pydantic import BaseModel` (Pydantic BaseModel, not SQLAlchemy)

4. **Verify** all three files parse cleanly with `ast.parse`

5. **Verify** migration chains correctly from `m011_s01_patient_flow_states_index`

## Must-Haves

- [ ] Migration revision chains from `m011_s01_patient_flow_states_index`
- [ ] Table has UNIQUE(patient_flow_state_id, day_number) constraint
- [ ] Table has FK to patient_flow_states with ON DELETE CASCADE
- [ ] Model uses BaseModel from `app.models.base` (not redeclaring id/created_at/updated_at)
- [ ] Pydantic response schema has `source: Literal["global", "override"]` and `editable: bool` fields
- [ ] All 3 files pass `ast.parse`

## Verification

- `python3 -c "import ast; ast.parse(open('backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py').read()); print('PASS migration')"` → PASS
- `python3 -c "import ast; ast.parse(open('backend-hormonia/app/models/flow.py').read()); print('PASS model')"` → PASS
- `python3 -c "import ast; ast.parse(open('backend-hormonia/app/schemas/v2/patient_overrides.py').read()); print('PASS schemas')"` → PASS
- `grep "down_revision" backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py` → `m011_s01_patient_flow_states_index`
- `grep -n "UniqueConstraint\|patient_flow_state_id" backend-hormonia/app/models/flow.py | tail -5` → FK + unique constraint visible

## Observability Impact

- **New table:** `patient_flow_overrides` queryable via SQL (`SELECT * FROM patient_flow_overrides WHERE patient_flow_state_id = :id`) to inspect per-patient overrides
- **Model relationship:** `PatientFlowState.overrides` backref allows inspecting overrides from any flow state in REPL/debug
- **Schema validation:** Pydantic schemas surface 422 errors with field-level detail on invalid override input
- **Failure visibility:** FK constraint with ON DELETE CASCADE ensures orphan cleanup; UNIQUE constraint on (state_id, day_number) prevents duplicate day overrides at DB level

## Inputs

- `backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py` — current Alembic head, new migration chains from this
- `backend-hormonia/app/models/flow.py` — contains `PatientFlowState` (line ~146), new model goes after it
- `backend-hormonia/app/models/base.py` — provides `BaseModel` with `id`, `created_at`, `updated_at`
- `backend-hormonia/app/schemas/v2/templates.py` — contains `DayConfigItem` (line ~784) for reference on field names/types

## Expected Output

- `backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py` — complete Alembic migration with table creation, FK, unique constraint, index
- `backend-hormonia/app/models/flow.py` — modified with `PatientFlowOverride` model added after `PatientFlowState`
- `backend-hormonia/app/schemas/v2/patient_overrides.py` — new file with `OverrideDayInput`, `OverrideDayUpdateRequest`, `MergedDayItem`, `MergedDayListResponse`
