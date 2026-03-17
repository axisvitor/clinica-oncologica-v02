# S02: Injeção no pipeline de envio — UAT

**Milestone:** M012
**Written:** 2026-03-17

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: This slice modifies backend pipeline logic only — no UI surfaces. All deliverables are proven by contract verification (ast.parse, grep patterns). Runtime verification deferred to S04's integrated proof.

## Preconditions

- S01 completed: `patient_flow_overrides` table exists, `PatientFlowOverride` model available, PUT endpoint with cache invalidation operational
- Python 3.11+ available for `ast.parse` checks
- Access to the 4 modified source files in backend-hormonia/

## Smoke Test

Run `ast.parse` on all 4 modified files — confirms no syntax errors in the injected override logic:
```bash
python3 -c "import ast; ast.parse(open('backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py').read())"
python3 -c "import ast; ast.parse(open('backend-hormonia/app/services/flow/_flow_message_flow.py').read())"
python3 -c "import ast; ast.parse(open('backend-hormonia/app/services/flow/_flow_response_flow.py').read())"
python3 -c "import ast; ast.parse(open('backend-hormonia/app/tasks/helpers/flow_helpers.py').read())"
```
All must exit 0.

## Test Cases

### 1. Override lookup is wired into on-demand path (state.py)

1. Grep for `patient_flow_state_id` in `state.py`: `grep -c "patient_flow_state_id" backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py`
2. **Expected:** Count ≥ 3 (parameter declaration + cache key + DB query usage)
3. Grep for cache key pattern: `grep "flow_override:" backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py`
4. **Expected:** Line containing `flow_override:{patient_flow_state_id}:days`
5. Grep for send_mode in override return: `grep "send_mode" backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py`
6. **Expected:** Override day_config includes `send_mode: "single"`

### 2. On-demand callers pass patient_flow_state_id

1. Grep message flow: `grep "patient_flow_state_id=flow_state.id" backend-hormonia/app/services/flow/_flow_message_flow.py`
2. **Expected:** Kwarg present in `_get_day_config` call
3. Grep response flow: `grep "patient_flow_state_id=" backend-hormonia/app/services/flow/_flow_response_flow.py`
4. **Expected:** Kwarg present (uses `getattr(flow_state, "id", None)`)

### 3. Batch cron path has override helper

1. Grep for helper function: `grep "_check_patient_override_for_day" backend-hormonia/app/tasks/helpers/flow_helpers.py`
2. **Expected:** Function definition and at least one call site
3. Grep for cache key in batch path: `grep "flow_override:" backend-hormonia/app/tasks/helpers/flow_helpers.py`
4. **Expected:** Same cache key pattern as on-demand path
5. Grep for DB query: `grep "db.query(PatientFlowOverride)" backend-hormonia/app/tasks/helpers/flow_helpers.py`
6. **Expected:** Sync DB fallback query present

### 4. Skip logic exists in batch path

1. Grep for skip reason: `grep "Day skipped by patient override" backend-hormonia/app/tasks/helpers/flow_helpers.py`
2. **Expected:** Skip reason string present in return value

### 5. Override content bypasses AI personalization in batch path

1. Grep for override metadata: `grep '"override": True' backend-hormonia/app/tasks/helpers/flow_helpers.py`
2. **Expected:** Override flag present in message metadata
3. Grep for personalization bypass: `grep '"personalized": False' backend-hormonia/app/tasks/helpers/flow_helpers.py`
4. **Expected:** Personalized=False marker present

### 6. Failure-path logging exists

1. Count warning/fallback references: `grep -c "warning\|Warning\|fallback" backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py`
2. **Expected:** Count ≥ 1 (Redis error fallback to DB)
3. Grep in batch path: `grep "fallback" backend-hormonia/app/tasks/helpers/flow_helpers.py`
4. **Expected:** Fallback logging present for Redis errors

### 7. Backward compatibility of _get_day_config signature

1. Grep for default parameter: `grep "patient_flow_state_id.*=.*None" backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py`
2. **Expected:** Parameter defaults to `None`, preserving backward compatibility

## Edge Cases

### Patient without overrides (miss sentinel)

1. Inspect `_get_day_config` in state.py for empty dict caching logic
2. **Expected:** When no `PatientFlowOverride` rows exist for a patient, an empty dict `{}` is cached at key `flow_override:{state_id}:days` with 3600s TTL, preventing repeated DB queries

### Redis unavailable during override lookup

1. Inspect both state.py and flow_helpers.py for try/except around Redis operations
2. **Expected:** Redis errors logged as warnings, execution falls through to DB query. DB errors also logged as warnings, execution falls through to global template. Pipeline never fails due to override lookup errors.

### Override lookup with patient_flow_state_id=None (backward compat)

1. Inspect `_get_day_config` in state.py for the None check
2. **Expected:** When `patient_flow_state_id` is None, override lookup block is skipped entirely, falling through to existing global template logic

## Failure Signals

- Any `ast.parse` command exits non-zero → syntax error introduced
- `patient_flow_state_id` grep count < 3 → override parameter not properly threaded
- Missing `flow_override:` cache key pattern → cache not implemented
- Missing `_check_patient_override_for_day` → batch path not wired
- Missing skip reason string → skip logic not implemented
- Missing fallback/warning logging → failure path not resilient

## Requirements Proved By This UAT

- R106 — `_get_day_config` consults override before global template with Redis cache and fallback
- R107 — Days with skip=true are skipped by both pipeline paths

## Not Proven By This UAT

- Runtime behavior under actual Redis/DB connections (deferred to S04 integrated verification)
- Cache invalidation on PUT actually clears the cached overrides in flight (S01 responsibility, S04 verifies)
- End-to-end flow: physician creates override → next daily cron skips/uses override content → patient receives correct message (S04)

## Notes for Tester

- This is a contract-level slice — all checks are static (ast.parse + grep). No running server needed.
- The two pipeline paths (on-demand in state.py, batch cron in flow_helpers.py) are independent code but share the same Redis cache key pattern. Verify both use `flow_override:{state_id}:days`.
- S04 will perform integrated verification with actual runtime behavior.
