# S01: Tabela de overrides + API de merge — Research

**Date:** 2026-03-17
**Depth:** Targeted (known patterns, new table + endpoints following established conventions)

## Summary

S01 is a data + API slice: create a `patient_flow_overrides` table via Alembic, add a SQLAlchemy model, define Pydantic schemas, and wire GET/PUT endpoints under the existing `/api/v2/patients/{patient_id}/` prefix. The codebase has strong prior art for every piece — the `flow_responses` module (M007/S04) is a near-identical structural template (FK to patient, new table, new router file, Pydantic schema, registered in `patients/__init__.py`). The `DayConfigItem` schema is directly reusable as the base shape for override items.

The key design task is the **merge logic**: GET must load global template days (`_project_steps_to_day_configs`) and overlay per-patient overrides, annotating each day with `source: "global" | "override"`. PUT stores override rows and must validate against future-only editability (using the patient's `current_flow_day` from `step_data`).

No new technology, no new patterns, no unfamiliar APIs. This is straightforward application of established conventions.

## Recommendation

Follow the `flow_responses.py` structural pattern exactly:
1. Alembic migration creating `patient_flow_overrides` table
2. SQLAlchemy model in `app/models/flow.py` (co-located with `PatientFlowState`)
3. Pydantic schemas in a new `app/schemas/v2/patient_overrides.py`
4. New router file `app/api/v2/routers/patients/flow_overrides.py`
5. Register in `patients/__init__.py`

The merge is read-time only (D022): load global days from template, load overrides from table, overlay by `day_number`. Extra days from overrides are appended. Skipped days are included with `skip=true`. Override immutability (R109) is naturally satisfied — overrides live in a separate table, so global template changes don't touch them.

## Implementation Landscape

### Key Files

- **`backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py`** — Current Alembic head. New migration `m012_s01_patient_flow_overrides` must set `down_revision = "m011_s01_patient_flow_states_index"`.

- **`backend-hormonia/app/models/flow.py`** — Contains `PatientFlowState` (line 146) and `FlowTemplateVersion` (line 71). `PatientFlowOverride` model goes here, with FK to `patient_flow_states.id`. Uses `BaseModel` from `app.models.base` which provides `id`, `created_at`, `updated_at`.

- **`backend-hormonia/app/schemas/v2/templates.py`** — Contains `DayConfigItem` (line 784) with fields: `day_number`, `content`, `message_type`, `expects_response`. Override schema extends this shape with `source` (response) and `skip` (request/response) fields. New file `patient_overrides.py` reuses `DayConfigItem` fields but adds override-specific ones.

- **`backend-hormonia/app/api/v2/routers/patients/flow_responses.py`** — Structural template for new router. Uses `@require_doctor_or_admin()`, `get_current_user_from_session`, `get_async_db`, `limiter`. Same pattern for `flow_overrides.py`.

- **`backend-hormonia/app/api/v2/routers/patients/__init__.py`** — Router registration. New override router gets added: `from .flow_overrides import router as flow_overrides_router` + `router.include_router(flow_overrides_router, ...)`. Must be placed before `crud_router` (line 37: static routes before dynamic `/{patient_id}` handlers).

- **`backend-hormonia/app/api/v2/routers/flow_templates.py`** — Contains `_project_steps_to_day_configs()` (line 211) which projects internal JSONB `steps` to `DayConfigItem` list. The GET override endpoint reuses this function to load global days, then overlays overrides. Also contains `_hydrate_day_configs_to_steps()` (line 263) — not needed for overrides (overrides store flat DayConfigItem-shaped data, not internal step format).

- **`backend-hormonia/app/dependencies/auth_dependencies.py`** — `get_generic_cache` (line 298) returns `GenericRedisCache` with `get/set/delete/delete_pattern` async methods. Used by physician/patients endpoint. Overrides PUT should invalidate cache via `delete_pattern(f"flow_override:{patient_flow_state_id}:*")`.

### Table Schema

```sql
CREATE TABLE patient_flow_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_flow_state_id UUID NOT NULL REFERENCES patient_flow_states(id) ON DELETE CASCADE,
    day_number INTEGER NOT NULL,
    content TEXT NOT NULL,
    message_type VARCHAR(50) NOT NULL DEFAULT 'question',
    expects_response BOOLEAN NOT NULL DEFAULT false,
    skip BOOLEAN NOT NULL DEFAULT false,
    created_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(patient_flow_state_id, day_number)
);
CREATE INDEX idx_pfo_state_id ON patient_flow_overrides(patient_flow_state_id);
```

The UNIQUE constraint on `(patient_flow_state_id, day_number)` prevents duplicate overrides for the same day. One override row per day per flow state.

### Merge Logic (GET endpoint)

1. Load patient's active `PatientFlowState` (query by `patient_id`, `status='active'`)
2. Load the template via `flow_template_version_id` → `FlowTemplateVersion.steps`
3. Project steps to `DayConfigItem` list via `_project_steps_to_day_configs()`
4. Load all `PatientFlowOverride` rows for this `patient_flow_state_id`
5. Build merged list: for each global day, check if override exists for that `day_number` → use override fields + `source: "override"`, else use global fields + `source: "global"`
6. Append any override-only days (extra days not in global template) with `source: "override"`
7. Sort by `day_number`
8. Add `editable: bool` per day: `day_number > current_flow_day` from `step_data`

### PUT Logic

1. Validate each override item: `day_number` must be > patient's `current_flow_day`
2. Upsert override rows (delete existing + insert new, or use `ON CONFLICT DO UPDATE` via merge)
3. Invalidate Redis cache key `flow_override:{patient_flow_state_id}:*` for S02 compatibility
4. Return the merged view (same as GET)

### Build Order

1. **Alembic migration** — creates table, unblocks everything
2. **SQLAlchemy model** — `PatientFlowOverride` in `app/models/flow.py`, with relationship to `PatientFlowState`
3. **Pydantic schemas** — `OverrideDayItem`, `OverrideDayListResponse`, `OverrideDayListUpdate` in `app/schemas/v2/patient_overrides.py`
4. **Router file** — `app/api/v2/routers/patients/flow_overrides.py` with GET `/{patient_id}/flow-overrides` and PUT `/{patient_id}/flow-overrides`
5. **Router registration** — add to `patients/__init__.py`
6. **Verification** — `ast.parse` all modified Python files

### Verification Approach

```bash
# 1. AST parse all modified files
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

# 2. Verify migration chain
grep "down_revision" backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py
# Should show: m011_s01_patient_flow_states_index

# 3. Verify model has FK + unique constraint
grep -n "patient_flow_state_id\|UniqueConstraint\|day_number" backend-hormonia/app/models/flow.py | tail -10

# 4. Verify router registered
grep "flow_overrides" backend-hormonia/app/api/v2/routers/patients/__init__.py

# 5. Verify merge returns source field
grep "source" backend-hormonia/app/schemas/v2/patient_overrides.py
```

## Constraints

- **Alembic head**: Migration must chain from `m011_s01_patient_flow_states_index` — no branching.
- **BaseModel provides id/created_at/updated_at**: Don't re-declare these in the model — `BaseModel` from `app.models.base` already has all three (confirmed: `id` UUID PK, `created_at` TIMESTAMPTZ, `updated_at` TIMESTAMPTZ with `onupdate=func.now()`).
- **Router order in `__init__.py`**: Static routes before dynamic `/{patient_id}` routes — place `flow_overrides_router` include before `crud_router`.
- **`_project_steps_to_day_configs` is in `flow_templates.py`**: Import it rather than duplicating. It handles the extraction of `content`, `message_type`, `expects_response` from the internal JSONB `steps` format.
- **`step_data` stores `current_flow_day`**: This is the source for determining which days are editable (future only). Access via `flow_state.step_data.get("current_flow_day", 0)`.

## Common Pitfalls

- **Don't import from `app.tasks`** — The tasks `__init__.py` triggers full settings validation chain (Knowledge Rule #1). Override router imports should stay in the `app.models/schemas/api` layer.
- **`GenericRedisCache.set()` uses `json.dumps(value, default=str)`** — Response objects must be serializable. Use `.model_dump()` before caching, same as `physician/patients.py` does.
- **Override rows must use UPSERT, not blind INSERT** — PUT replaces the full override set for a patient. Use `DELETE WHERE patient_flow_state_id = X` + `INSERT` in a transaction, rather than individual upserts, to handle day removal cleanly.

## Forward Intelligence (for S02)

S02 will modify `_get_day_config` in `state.py` to check overrides before global template. What S02 needs from S01:

- **Table name**: `patient_flow_overrides`
- **Lookup key**: `patient_flow_state_id` + `day_number` (both available in the pipeline context via `flow_state.id` and `day_number` state param)
- **Cache key pattern**: `flow_override:{patient_flow_state_id}:days` — S01's PUT should delete this key. S02 will populate it on first read.
- **Skip detection**: `skip = True` on an override row → S02 returns `None` from `_get_day_config` → pipeline emits `status: "skip"` (existing behavior for missing day config).

## Forward Intelligence (for S03)

S03 will build the frontend editor. What S03 needs from S01:

- **GET response shape**: `{ patient_id, flow_state_id, current_flow_day, days: [{ day_number, content, message_type, expects_response, skip, source, editable }] }`
- **PUT request shape**: `{ days: [{ day_number, content, message_type, expects_response, skip }] }` — only overridden days, not the full list
- **Endpoint paths**: `GET/PUT /api/v2/patients/{patient_id}/flow-overrides`
- **`editable` field**: Boolean per day, `true` when `day_number > current_flow_day`
