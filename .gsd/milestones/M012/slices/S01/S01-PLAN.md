# S01: Tabela de overrides + API de merge

**Goal:** Persist per-patient flow day overrides in a dedicated table and expose GET/PUT endpoints that merge global template days with patient-specific overrides, annotating each day with its source.
**Demo:** GET `/api/v2/patients/{id}/flow-overrides` returns the full merged day list with `source: "global" | "override"` and `editable` per day. PUT saves overrides and returns the updated merged view. `ast.parse` green on all modified files.

## Must-Haves

- Alembic migration `m012_s01_patient_flow_overrides` creates table with UNIQUE(patient_flow_state_id, day_number)
- `PatientFlowOverride` SQLAlchemy model in `app/models/flow.py` with FK to `patient_flow_states`
- Pydantic schemas for request/response in `app/schemas/v2/patient_overrides.py`
- GET endpoint returns merged global+override days with `source` and `editable` fields
- PUT endpoint validates future-only editability, replaces overrides via DELETE+INSERT, invalidates Redis cache
- Override immutability: overrides are in separate table, global template changes don't touch them (R109)
- Router registered in `patients/__init__.py` before `crud_router`

## Proof Level

- This slice proves: contract
- Real runtime required: no
- Human/UAT required: no

## Verification

```bash
python3 -c "
import ast, sys
files = [
    'backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py',
    'backend-hormonia/app/models/flow.py',
    'backend-hormonia/app/schemas/v2/patient_overrides.py',
    'backend-hormonia/app/api/v2/routers/patients/flow_overrides.py',
    'backend-hormonia/app/api/v2/routers/patients/__init__.py',
]
for f in files:
    try:
        ast.parse(open(f).read())
        print(f'PASS {f}')
    except SyntaxError as e:
        print(f'FAIL {f}: {e}')
        sys.exit(1)
print('All AST checks passed')
"
```

- `grep "down_revision" backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py` → shows `m011_s01_patient_flow_states_index`
- `grep "flow_overrides" backend-hormonia/app/api/v2/routers/patients/__init__.py` → router registered
- `grep "source" backend-hormonia/app/schemas/v2/patient_overrides.py` → source field present in response schema
- `grep "UniqueConstraint\|unique=True" backend-hormonia/app/models/flow.py` → UNIQUE on (patient_flow_state_id, day_number)

## Observability / Diagnostics

- Runtime signals: structured logging on PUT override save (patient_id, flow_state_id, override_count), Redis cache invalidation log
- Inspection surfaces: `patient_flow_overrides` table queryable by patient_flow_state_id, GET endpoint shows full merged state
- Failure visibility: 404 on missing flow state, 400 on past-day edit attempt with specific error message, 422 on schema validation failure
- Redaction constraints: none (no PII in override config data)

## Integration Closure

- Upstream surfaces consumed: `_project_steps_to_day_configs()` from `app/api/v2/routers/flow_templates.py`, `PatientFlowState` model from `app/models/flow.py`, `GenericRedisCache` from `app/dependencies/auth_dependencies.py`
- New wiring introduced in this slice: `flow_overrides_router` registered in `patients/__init__.py`, new `patient_flow_overrides` table via Alembic
- What remains before the milestone is truly usable end-to-end: S02 (pipeline injection + cache), S03 (frontend editor), S04 (integrated verification)

## Tasks

- [x] **T01: Create migration, model, and schemas for patient_flow_overrides** `est:45m`
  - Why: Data layer is prerequisite for the API — table, ORM model, and request/response schemas must exist before endpoints can be built
  - Files: `backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py`, `backend-hormonia/app/models/flow.py`, `backend-hormonia/app/schemas/v2/patient_overrides.py`
  - Do: Create Alembic migration chained from `m011_s01_patient_flow_states_index`. Add `PatientFlowOverride` model to `flow.py` using `BaseModel` (provides id/created_at/updated_at). Create Pydantic schemas with `source` literal and `editable` bool in response, `skip` bool in request. UNIQUE constraint on (patient_flow_state_id, day_number).
  - Verify: `ast.parse` on all 3 files, `grep down_revision` shows correct chain, model has FK + unique constraint
  - Done when: Migration file exists with correct head chain, model has all columns and FK relationship, schemas define request/response shapes with source/editable/skip fields

- [x] **T02: Build GET/PUT flow-overrides endpoints with merge logic and register router** `est:1h`
  - Why: Core slice deliverable — the merge logic (overlay overrides onto global template days, annotate source, gate editability) and the PUT with future-only validation + Redis cache invalidation
  - Files: `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py`, `backend-hormonia/app/api/v2/routers/patients/__init__.py`
  - Do: Create router following `flow_responses.py` pattern. GET loads active flow state, projects global template via `_project_steps_to_day_configs()`, overlays overrides by day_number, appends extra override-only days, annotates source/editable. PUT validates future-only, DELETE+INSERT in transaction, invalidates Redis `flow_override:{state_id}:*`. Register router before `crud_router` in `__init__.py`.
  - Verify: `ast.parse` on both files, `grep flow_overrides` in `__init__.py`, full slice verification script
  - Done when: GET returns merged day list with source/editable per day, PUT saves overrides with future-only validation and cache invalidation, router registered, all AST checks pass

## Files Likely Touched

- `backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py`
- `backend-hormonia/app/models/flow.py`
- `backend-hormonia/app/schemas/v2/patient_overrides.py`
- `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py`
- `backend-hormonia/app/api/v2/routers/patients/__init__.py`
