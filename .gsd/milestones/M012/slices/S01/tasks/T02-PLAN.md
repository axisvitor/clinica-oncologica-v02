---
estimated_steps: 6
estimated_files: 2
---

# T02: Build GET/PUT flow-overrides endpoints with merge logic and register router

**Slice:** S01 — Tabela de overrides + API de merge
**Milestone:** M012

## Description

Build the core API layer: a new router file with GET and PUT endpoints for patient flow overrides, then register it in the patients router. This task contains the slice's most important logic — the **merge algorithm** that overlays per-patient overrides onto global template days, annotating each day with its source and editability.

Follow the structural pattern of `flow_responses.py` (same directory) for auth decorators, dependencies, limiter, and error handling. Import `_project_steps_to_day_configs` from `flow_templates.py` to load global template days — don't duplicate that logic.

**Critical constraint:** Register the router in `patients/__init__.py` BEFORE `crud_router` (line ~37). Static routes must come before the dynamic `/{patient_id}` catch-all.

## Steps

1. **Create router file** `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py`:
   - Import patterns from `flow_responses.py`: `APIRouter`, `Depends`, `get_async_db`, `get_current_user_from_session`, `require_doctor_or_admin`, `limiter`, `Request`
   - Import `_project_steps_to_day_configs` from `app.api.v2.routers.flow_templates`
   - Import models: `PatientFlowOverride` from `app.models.flow`, `PatientFlowState` from `app.models.flow`
   - Import schemas: `OverrideDayInput`, `OverrideDayUpdateRequest`, `MergedDayItem`, `MergedDayListResponse` from `app.schemas.v2.patient_overrides`
   - Import `GenericRedisCache` / `get_generic_cache` from `app.dependencies.auth_dependencies`
   - Router: `router = APIRouter(tags=["patient-flow-overrides"])`

2. **Implement helper: `_get_active_flow_state`**:
   - Query `PatientFlowState` WHERE `patient_id = patient_id` AND `status = 'active'`, order by `started_at DESC`, limit 1
   - Return the flow state or raise `HTTPException(404, "No active flow state found for this patient")`
   - This is used by both GET and PUT

3. **Implement GET `/{patient_id}/flow-overrides`**:
   - Auth: `@require_doctor_or_admin()`
   - Rate limit: `@limiter.limit("30/minute")`
   - Load active flow state via helper
   - Load the template: `flow_state.flow_template_version_id` → query `FlowTemplateVersion` → get `steps` JSONB
   - Project to day configs: `_project_steps_to_day_configs(steps)` → list of DayConfigItem-like dicts
   - Load overrides: query all `PatientFlowOverride` WHERE `patient_flow_state_id = flow_state.id`
   - Build override lookup: `{override.day_number: override for override in overrides}`
   - Merge: for each global day, if override exists → use override fields + `source="override"`, else → global fields + `source="global"`. Add `skip` from override (default False for global). Add `editable = day_number > current_flow_day`
   - Append extra override-only days (day_numbers not in global template) with `source="override"`
   - Sort by `day_number`
   - Get `current_flow_day` from `flow_state.step_data.get("current_flow_day", 0)` (step_data is JSONB dict)
   - Return `MergedDayListResponse`

4. **Implement PUT `/{patient_id}/flow-overrides`**:
   - Auth: `@require_doctor_or_admin()`
   - Rate limit: `@limiter.limit("10/minute")`
   - Body: `OverrideDayUpdateRequest`
   - Load active flow state via helper
   - Get `current_flow_day` from `flow_state.step_data.get("current_flow_day", 0)`
   - **Validate**: every `day.day_number` in request must be `> current_flow_day`. If any fail, raise `HTTPException(400, f"Cannot override day {day.day_number}: already sent (current day is {current_flow_day})")`
   - **Transaction**: DELETE all existing overrides for this `patient_flow_state_id`, then INSERT new ones from request body. Set `created_by = current_user.id`
   - **Cache invalidation**: `await cache.delete_pattern(f"flow_override:{flow_state.id}:*")` — this prepares for S02's cache layer
   - **Log**: structured log with `patient_id`, `flow_state_id`, `override_count`
   - **Return**: call the GET merge logic and return `MergedDayListResponse` (reuse by extracting merge into a helper function)

5. **Register router** in `backend-hormonia/app/api/v2/routers/patients/__init__.py`:
   - Add import: `from .flow_overrides import router as flow_overrides_router`
   - Add `router.include_router(flow_overrides_router, prefix="")` BEFORE the `crud_router` include (line ~37)
   - This ensures `/patients/{patient_id}/flow-overrides` routes resolve before `/{patient_id}` CRUD catch-all

6. **Run full slice verification**:
   - `ast.parse` all 5 modified files (migration, model, schemas, router, __init__)
   - `grep` checks: down_revision chain, router registration, source field, unique constraint
   - Confirm the merge logic handles: global-only days, overridden days, extra override days, skip field, editable gating

## Must-Haves

- [ ] GET returns merged list with `source: "global" | "override"` per day
- [ ] GET includes `editable: bool` per day based on `current_flow_day`
- [ ] GET appends extra override-only days not in global template
- [ ] PUT validates future-only editability (day_number > current_flow_day)
- [ ] PUT uses DELETE+INSERT in transaction (not individual upserts)
- [ ] PUT invalidates Redis cache pattern `flow_override:{state_id}:*`
- [ ] PUT returns updated merged view (same as GET response)
- [ ] Router registered in `__init__.py` before `crud_router`
- [ ] All modified files pass `ast.parse`

## Verification

- Full AST parse script from S01-PLAN verification section — all 5 files PASS
- `grep "flow_overrides" backend-hormonia/app/api/v2/routers/patients/__init__.py` → import and include_router visible
- `grep "source" backend-hormonia/app/schemas/v2/patient_overrides.py` → Literal["global", "override"]
- `grep "delete_pattern\|flow_override" backend-hormonia/app/api/v2/routers/patients/flow_overrides.py` → cache invalidation present
- `grep "_project_steps_to_day_configs" backend-hormonia/app/api/v2/routers/patients/flow_overrides.py` → global template loading reused

## Observability Impact

- Signals added: structured log on PUT with `patient_id`, `flow_state_id`, `override_count`
- How a future agent inspects this: query `patient_flow_overrides` table by `patient_flow_state_id`, or call GET endpoint to see full merged state
- Failure state exposed: 404 for missing flow state (with message), 400 for past-day edit attempt (with specific day number and current_flow_day in error message)

## Inputs

- `backend-hormonia/app/models/flow.py` — T01 added `PatientFlowOverride` model here
- `backend-hormonia/app/schemas/v2/patient_overrides.py` — T01 created schemas: `OverrideDayInput`, `OverrideDayUpdateRequest`, `MergedDayItem`, `MergedDayListResponse`
- `backend-hormonia/app/api/v2/routers/patients/flow_responses.py` — structural template for auth decorators, dependencies, limiter, error patterns
- `backend-hormonia/app/api/v2/routers/flow_templates.py` — contains `_project_steps_to_day_configs()` (line ~211) for projecting template steps to day config shape
- `backend-hormonia/app/api/v2/routers/patients/__init__.py` — router registration, `crud_router` at line ~37 (new router must go before it)
- `backend-hormonia/app/dependencies/auth_dependencies.py` — `get_generic_cache` (line ~298) returns `GenericRedisCache` with `delete_pattern` method

## Expected Output

- `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py` — new router file with GET/PUT endpoints, merge logic, future-only validation, cache invalidation
- `backend-hormonia/app/api/v2/routers/patients/__init__.py` — modified with flow_overrides_router import and registration before crud_router
