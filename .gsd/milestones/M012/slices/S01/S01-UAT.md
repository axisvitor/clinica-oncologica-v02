# S01: Tabela de overrides + API de merge — UAT

**Milestone:** M012
**Written:** 2026-03-17

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S01 delivers data layer (migration, model, schemas) and API endpoints verified via AST parsing and structural checks. Runtime verification deferred to S04 which tests with a live stack.

## Preconditions

- PostgreSQL running with `hormonia_dev` database at Alembic head (including `m012_s01_patient_flow_overrides`)
- Dragonfly/Redis running on configured port
- Backend running (`uvicorn app.main:app`)
- At least one seeded physician user with valid session
- At least one patient with an active `PatientFlowState` (status="active") linked to a flow template that has steps

## Smoke Test

```
curl -s -b session_cookie http://localhost:8000/api/v2/patients/{patient_id}/flow-overrides | python3 -m json.tool
```
Should return JSON with `days` array where each entry has `day_number`, `content`, `source` ("global" for all), and `editable` fields.

## Test Cases

### 1. GET returns global-only days when no overrides exist

1. Pick a patient with active flow state and no overrides in `patient_flow_overrides` table
2. `GET /api/v2/patients/{patient_id}/flow-overrides`
3. **Expected:** Response contains `days` array sorted by `day_number`, every day has `source: "global"`, `editable` is `true` for days after `current_flow_day` and `false` for days at or before it. `current_flow_day` and `total_days` populated.

### 2. PUT saves an override and GET reflects it

1. `GET /api/v2/patients/{patient_id}/flow-overrides` — note a future day_number (e.g., day 10 if current is day 3)
2. `PUT /api/v2/patients/{patient_id}/flow-overrides` with body:
   ```json
   {
     "overrides": [
       {
         "day_number": 10,
         "content": {"text": "Mensagem personalizada para o paciente"},
         "message_type": "motivational",
         "expects_response": false,
         "skip": false
       }
     ]
   }
   ```
3. **Expected:** 200 response with updated merged view. Day 10 now shows `source: "override"`, `content` matches the PUT body, and all other days remain `source: "global"`.

### 3. PUT rejects override for past/current day

1. Determine `current_flow_day` from GET response (e.g., 3)
2. `PUT /api/v2/patients/{patient_id}/flow-overrides` with `day_number: 2`
3. **Expected:** 400 response with message containing "Cannot override day 2: already sent (current day is 3)"

### 4. PUT with skip=true saves correctly

1. `PUT /api/v2/patients/{patient_id}/flow-overrides` with a future day set to `skip: true`
2. `GET /api/v2/patients/{patient_id}/flow-overrides`
3. **Expected:** The skipped day shows `source: "override"`, `skip: true` in the merged view.

### 5. PUT adds extra override-only days beyond template

1. Check template total days (e.g., template has 15 days)
2. `PUT /api/v2/patients/{patient_id}/flow-overrides` with `day_number: 20` (beyond template range)
3. `GET /api/v2/patients/{patient_id}/flow-overrides`
4. **Expected:** Day 20 appears in the response with `source: "override"`, appended after global template days. `total_days` reflects the extended range.

### 6. PUT replaces all overrides atomically (DELETE+INSERT)

1. `PUT` with overrides for days 10 and 12
2. Verify via GET that days 10 and 12 are overridden
3. `PUT` again with override only for day 14
4. `GET /api/v2/patients/{patient_id}/flow-overrides`
5. **Expected:** Only day 14 has `source: "override"`. Days 10 and 12 revert to `source: "global"`. Previous overrides were deleted.

### 7. GET returns 404 for patient without active flow state

1. Pick a patient_id that has no active `PatientFlowState` (or a non-existent patient)
2. `GET /api/v2/patients/{patient_id}/flow-overrides`
3. **Expected:** 404 with "No active flow state found for this patient"

### 8. Redis cache invalidated on PUT

1. `PUT /api/v2/patients/{patient_id}/flow-overrides` with a valid override
2. Check Redis for keys matching `flow_override:{flow_state_id}:*`
3. **Expected:** No cached keys remain (invalidated by PUT). Backend logs show "Flow overrides saved" with `patient_id`, `flow_state_id`, `override_count`.

### 9. Router registration order prevents path shadowing

1. `GET /api/v2/patients/{patient_id}/flow-overrides` (flow-overrides path)
2. `GET /api/v2/patients/{patient_id}` (crud path)
3. **Expected:** Both endpoints resolve correctly. flow-overrides does not get caught by the crud router's `/{patient_id}` parameter.

## Edge Cases

### Concurrent PUT for same patient

1. Two simultaneous PUT requests with different overrides for the same patient
2. **Expected:** Both complete without error due to DELETE+INSERT transaction. Last write wins. No constraint violations (overrides replaced atomically).

### PUT with empty overrides array

1. `PUT /api/v2/patients/{patient_id}/flow-overrides` with `{"overrides": []}`
2. **Expected:** 200 — all overrides deleted. GET shows all days as `source: "global"`.

### Template with no steps

1. Patient's flow template has zero steps configured
2. `GET /api/v2/patients/{patient_id}/flow-overrides`
3. **Expected:** Response with empty `days` array (no global days, no overrides). No 500 error.

### UNIQUE constraint violation (DB-level safety net)

1. Attempt to INSERT two overrides with the same (patient_flow_state_id, day_number) directly in DB
2. **Expected:** IntegrityError referencing constraint `uq_pfo_state_day`. API code prevents this via DELETE+INSERT, but DB constraint is the safety net.

### FK CASCADE on flow state deletion

1. Delete a `PatientFlowState` that has overrides
2. **Expected:** All overrides for that flow state are automatically deleted (ON DELETE CASCADE). No orphan rows.

## Failure Signals

- 500 error on GET/PUT → likely `_project_steps_to_day_configs` import issue or missing flow template version
- All days show `editable: true` when some should be false → `current_flow_day` not found in `step_data` (defaults to 0)
- PUT returns 200 but GET still shows old data → Redis cache not invalidated (check logs for "Failed to invalidate flow_override cache")
- PUT returns 200 but day still shows `source: "global"` → override was saved but merge logic has a day_number matching bug

## Requirements Proved By This UAT

- R104 — patient_flow_overrides table persists overrides with content, type, expects_response, skip, FK to patient_flow_states
- R105 — GET returns merged global+override list with source indicator; PUT saves overrides
- R109 — override immutability: overrides in separate table, global template changes don't overwrite (test case 6 proves replacement is explicit, not implicit)

## Not Proven By This UAT

- R106/R107/R108 — pipeline injection (`_get_day_config` override priority, skip logic in `process_daily_flows`, Redis cache read path) — deferred to S02
- R064 (full) — frontend editor for overrides — deferred to S03
- Runtime performance under load — deferred to S04

## Notes for Tester

- The `current_flow_day` value comes from `step_data` JSONB in `patient_flow_states`. If a patient was just created and has no step_data, current_flow_day defaults to 0, making all days editable. This is expected behavior.
- Rate limits: GET is 30/min, PUT is 10/min. Hit these limits if you want to verify rate limiting.
- Override content is JSONB — any valid JSON object is accepted. The structure `{"text": "..."}` is conventional but not enforced at schema level.
- The merge response includes `message_type` as optional string. Global days may have it populated from the template; override days have whatever was sent in PUT.
