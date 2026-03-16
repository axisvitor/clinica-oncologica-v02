---
estimated_steps: 5
estimated_files: 1
---

# T02: Backend tests — Prove day-config API contract with focused pytest

**Slice:** S03 — Editor de templates dia-a-dia para o médico
**Milestone:** M007

## Description

Write focused unit tests for the GET/PUT day-config endpoints proving the steps↔day-config projection is correct, validation catches errors, draft-only editing is enforced, and the output is compatible with the runtime loader and dispatcher.

## Steps

1. **Create test file** `backend-hormonia/tests/unit/services/flow/test_day_config_editor_api.py`. Import the Pydantic schemas and the projection/hydration logic. Tests should validate the data transformation layer directly (not through HTTP — mock the DB and Redis boundaries).

2. **Test: round-trip projection fidelity.** Build a `steps` list in the internal format:
   ```python
   steps = [
       {"day": 1, "send_mode": "wait_each", "messages": [{"order": 1, "content": "Como você está?", "expects_response": True}], "intent": "day_1_message", "message_type": "question"},
       {"day": 2, "send_mode": "single", "messages": [{"order": 1, "content": "Lembre-se de tomar o medicamento", "expects_response": False}], "intent": "day_2_message", "message_type": "reminder"},
   ]
   ```
   Project to day-configs (simulating GET), modify content of day 1, hydrate back to steps (simulating PUT), verify:
   - Day 1 step has updated content in `messages[0]["content"]`
   - Day 2 step is unchanged
   - Each step has `"day"`, `"send_mode"`, `"messages"` (list with dict containing `"content"` and `"expects_response"`), `"intent"`

3. **Test: validation rejects invalid input.** Verify `DayConfigItem` Pydantic validation:
   - Empty `content` → ValidationError
   - `message_type` = `"invalid"` → ValidationError
   - `day_number` = 0 → ValidationError (ge=1)

4. **Test: hydrated steps pass `validate_day_config()`.** Take a `DayConfigItem`, hydrate to step format, pass through `validate_day_config()` from `app.services.flow.config_validation` — must not raise. Test for both `expects_response=True` (send_mode "wait_each") and `expects_response=False` (send_mode "single").

5. **Test: draft-only enforcement and edge cases.** Test the business logic:
   - Duplicate `day_number` values in the `days` list should be detectable (assert len(set(day_numbers)) == len(day_numbers))
   - Empty days list `[]` is valid (produces empty steps list)
   - Multi-message step: when projecting a step that has 2+ messages, verify `content` comes from `messages[0]["content"]` (first message)

## Must-Haves

- [ ] Round-trip test proves content changes survive GET→modify→PUT→GET cycle
- [ ] Pydantic validation catches empty content, invalid message_type, day_number < 1
- [ ] Hydrated steps pass `validate_day_config()` for both response/no-response cases
- [ ] Multi-message step projection uses first message's content
- [ ] All tests pass: `python -m pytest tests/unit/services/flow/test_day_config_editor_api.py -v`

## Verification

- `cd backend-hormonia && python -m pytest tests/unit/services/flow/test_day_config_editor_api.py -v` — 6+ tests pass, 0 failures
- `cd backend-hormonia && python -m pytest tests/unit/services/flow/ -v --tb=short` — no regressions in existing flow tests

## Inputs

- `backend-hormonia/app/schemas/v2/templates.py` — `DayConfigItem`, `DayConfigListResponse`, `DayConfigListUpdate` schemas (created in T01)
- `backend-hormonia/app/services/flow/config_validation.py` — `validate_day_config()` function for compatibility verification. Expects step dict with: `send_mode` (str, one of `_CANONICAL_SEND_MODES`), `messages` (list of dicts with `content` str and optional `expects_response` bool). Does NOT require `day` key.
- `backend-hormonia/app/services/flow/_flow_orchestration_utils.py` — `_CANONICAL_SEND_MODES = frozenset({"single", "sequential_auto", "wait_response", "wait_each"})`
- T01 produced the endpoints and schemas — this task tests the data transformation logic

## Expected Output

- `backend-hormonia/tests/unit/services/flow/test_day_config_editor_api.py` — New test file with 6+ focused tests covering round-trip, validation, loader compatibility, and edge cases
