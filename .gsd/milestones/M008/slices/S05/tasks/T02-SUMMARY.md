---
id: T02
parent: S05
milestone: M008
provides:
  - FlowCore.advance_patient_flow(force_day=16) transitions flow_type from onboarding to daily_follow_up
  - determine_flow_type maps day boundaries: ≤15→onboarding, 16-45→daily_follow_up, 46+→quiz_mensal
  - _transition_flow_type records transition in step_data.transitions with from/to/timestamp/at_day
  - Observability logging for flow type transitions (success + failure paths)
key_files:
  - backend-hormonia/app/services/flow/core/transitions.py
  - backend-hormonia/tests/unit/services/test_flow_transition_onboarding_daily.py
key_decisions:
  - Transition logic already existed in FlowCoreTransitionsMixin; no new implementation needed — task focused on verification and observability
  - Added error handling + structured logging to _transition_flow_type for production observability
patterns_established:
  - FlowCore.advance_patient_flow(force_day=N) drives phase transitions via determine_flow_type → _transition_flow_type pipeline
  - step_data.transitions accumulates transition history as list of {timestamp, from_flow, to_flow, at_day}
  - Test pattern: _make_service(db, active_flow=flow_state) bypasses sync repo chain for unit testing FlowCore async methods
observability_surfaces:
  - Log: "Flow type transition recorded: X → Y at day Z" on successful transition
  - Log: "Flow transition failed: ..." on missing FlowKind/active template version
  - Log: "Patient X transitioned from X to Y" in advance_patient_flow
  - step_data.transitions in patient_flow_states table
  - step_data.flow_kind, step_data.current_flow_day after advancement
duration: 20m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T02: Transição onboarding → daily_follow_up

**Verified and hardened FlowCore.advance_patient_flow phase transition pipeline: force_day=16 transitions onboarding→daily_follow_up with step_data.transitions record and observability logging**

## What Happened

The transition logic already existed in `FlowCoreTransitionsMixin._transition_flow_type` and `determine_flow_type`. This task verified the complete pipeline works correctly and added production observability:

1. **Verified boundary logic**: `determine_flow_type` returns `ONBOARDING` for days 1-15, `DAILY_FOLLOW_UP` for 16-45, `QUIZ_MENSAL` for 46+. All boundary conditions tested.

2. **Verified transition recording**: `_transition_flow_type` updates `flow_state.flow_type` (which triggers model setter to switch `flow_template_version_id`), and appends to `step_data.transitions` with `{timestamp, from_flow, to_flow, at_day}`.

3. **Added observability**: Enhanced `_transition_flow_type` with structured `logger.info` on success and `logger.error` + re-raise on ValueError (missing FlowKind or active template version).

4. **Wrote 19 unit tests** covering:
   - `determine_flow_type` boundary conditions (8 tests)
   - `_transition_flow_type` recording logic (6 tests)
   - `advance_patient_flow` integration with transition (5 tests): transition trigger, step_data recording, no-transition case, awaiting_response block, broadcast milestone, platform sync data

## Verification

- **19/19 tests pass**: `python3 -m pytest tests/unit/services/test_flow_transition_onboarding_daily.py -v` → all green
- **Existing tests unbroken**: `test_flow_core_split_contract.py` (3), `test_flow_core_enroll_status.py` (1) → all pass
- **AST parse clean**: `transitions.py` parses without error, 6 functions defined
- **Type verification**: `FlowType.ONBOARDING`, `DAILY_FOLLOW_UP`, `QUIZ_MENSAL` values match `flow_kinds.kind_key`

### Slice-level verification:
- ✅ `advance_patient_flow(force_day=16)` transitions flow_type from onboarding to daily_follow_up
- ✅ `step_data.transitions` contains `{from_flow: "onboarding", to_flow: "daily_follow_up", at_day: 16, timestamp: ...}`
- ✅ `step_data.flow_kind = "daily_follow_up"` after transition
- ✅ `result["transitioned"] == True` in return value
- ✅ Broadcaster called with `milestone_reached="flow_transition"`
- ✅ T01 webhook pipeline still valid (T01 tests unaffected)
- ⏳ SQL query verification against real DB (UAT scope — requires running system)
- ⏳ Real WhatsApp flow end-to-end (UAT scope)

## Diagnostics

- **Transition success**: Search logs for `Flow type transition recorded: onboarding → daily_follow_up at day 16`
- **Transition failure**: Search logs for `Flow transition failed:` — indicates missing FlowKind or inactive template version for target flow type
- **SQL inspection**: `SELECT step_data->'transitions' FROM patient_flow_states WHERE patient_id = '<id>'` shows full transition history
- **Flow kind after transition**: `SELECT step_data->'flow_kind' FROM patient_flow_states WHERE patient_id = '<id>'` returns `daily_follow_up`

## Deviations

- Task plan suggested creating new transition logic in `transitions.py` — the logic already existed in `FlowCoreTransitionsMixin`. Task focused on verification, testing, and observability instead of new implementation.

## Known Issues

- `_transition_flow_type` calls `flow_state.flow_type = new_flow_type.value` which uses `object_session(self).query(FlowKind)` (sync). This works with sync sessions and with AsyncSession.sync_session proxy. If called with a pure AsyncSession without sync_session, the setter would fail. Current callers (FlowCore via get_flow_service_dependency) always have sync session available.

## Files Created/Modified

- `backend-hormonia/app/services/flow/core/transitions.py` — Added error handling + observability logging to `_transition_flow_type`
- `backend-hormonia/tests/unit/services/test_flow_transition_onboarding_daily.py` — New: 19 unit tests for transition boundary logic, recording, and advance_patient_flow integration
