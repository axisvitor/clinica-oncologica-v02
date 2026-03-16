# S04: Personalização IA e armazenamento de respostas — UAT

**Milestone:** M007
**Written:** 2026-03-16

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: All deliverables are backend-only (tests, model, migration, API endpoint). No frontend UI or live runtime is required to verify. Grounding calibration is proven by unit tests against the existing PersonalizationMixin. Structured storage and API are proven by integration tests with mock DB.

## Preconditions

- Python 3.12+ available as `python3`
- `cd backend-hormonia` (working directory)
- Backend dependencies installed (`pip install -e .` or equivalent)
- No live DB required — all tests use mock/in-memory fixtures

## Smoke Test

```bash
cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_personalization_grounding.py tests/unit/services/flow/test_patient_flow_responses.py -v --tb=short
```
Expected: 39 tests pass (25 grounding + 14 response storage/API).

## Test Cases

### 1. Grounding rejects hallucinated content

1. Run: `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_personalization_grounding.py -v -k "hallucin"`
2. **Expected:** 1 test passes — `test_hallucinated_content_fails` proves that unrelated content (e.g. "Hoje vamos falar sobre culinária") is rejected by `_personalization_is_grounded()`.

### 2. Grounding accepts anchored reformulation

1. Run: `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_personalization_grounding.py -v -k "anchored"`
2. **Expected:** 1 test passes — `test_anchored_reformulation_passes` proves that a natural Portuguese reformulation of a clinical question passes grounding.

### 3. Grounding threshold boundary: no-keyword path

1. Run: `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_personalization_grounding.py -v -k "no_keyword"`
2. **Expected:** 2 tests pass — `test_no_keyword_short_content_passes` (similarity ≥ 0.35 passes) and `test_no_keyword_short_content_below_threshold_fails` (similarity < 0.35 fails).

### 4. AI skip for non-response messages

1. Run: `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_personalization_grounding.py -v -k "ai_skip"`
2. **Expected:** 3 tests pass — `test_ai_skipped_for_non_response_messages` (expects_response=False triggers skip), `test_ai_engine_not_created_for_non_response` (AI engine never instantiated), `test_ai_disabled_reason_when_config_off` (use_ai_personalization=False records correct reason).

### 5. Variation selection determinism

1. Run: `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_personalization_grounding.py -v -k "deterministic or different_patient"`
2. **Expected:** 2 tests pass — same inputs always produce same variation, different patient IDs produce different selections.

### 6. PatientFlowResponse model import and instantiation

1. Run: `cd backend-hormonia && python3 -c "from app.models.patient_flow_response import PatientFlowResponse; print('OK')"`
2. **Expected:** Prints `OK` — model is importable and registered.
3. Run: `cd backend-hormonia && python3 -c "from app.models.patient_flow_response import PatientFlowResponse; r = PatientFlowResponse(flow_state_id=None, patient_id='00000000-0000-0000-0000-000000000001', response_text='test', responded_at='2026-01-01T00:00:00+00:00'); assert r.flow_state_id is None; print('NULL flow_state_id OK')"`
4. **Expected:** Prints `NULL flow_state_id OK` — nullable FK works.

### 7. Dual-write integration

1. Run: `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_patient_flow_responses.py -v -k "dual_write"`
2. **Expected:** 4 tests pass — verifies `PatientFlowResponse` creation with and without flow_state, and that `db.add()` is called for both write paths.

### 8. Response API date filtering

1. Run: `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_patient_flow_responses.py -v -k "date_filter"`
2. **Expected:** 4 tests pass — no filter returns all, start_date filters from, end_date filters to, combined range works. Uses `datetime.combine()` with `time.min`/`time.max` for inclusive day boundaries.

### 9. Response API ordering

1. Run: `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_patient_flow_responses.py -v -k "ordering"`
2. **Expected:** 1 test passes — responses are returned in ascending `responded_at` order.

### 10. Full flow test regression check

1. Run: `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/ -v --tb=short`
2. **Expected:** 154 passed, 4 skipped, 1 pre-existing failure (`test_split_files_under_500_lines` — sequencing.py at 521 lines, not from S04). Zero new failures.

## Edge Cases

### Empty response set

1. Run: `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_patient_flow_responses.py -v -k "empty"`
2. **Expected:** 2 tests pass — returns `[]` when patient has no responses and when date filter excludes all existing responses.

### Empty/None input to grounding check

1. Run: `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_personalization_grounding.py -v -k "empty"`
2. **Expected:** 2 tests pass — `_personalization_is_grounded()` returns False for both empty strings and empty original content.

### FlowResponseItem schema with nullable fields

1. Run: `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_patient_flow_responses.py -v -k "nullable"`
2. **Expected:** 1 test passes — schema correctly handles None for `flow_state_id`, `day_number`, `message_index`, `prompt_message_id`.

## Failure Signals

- Any test in `test_personalization_grounding.py` failing means grounding thresholds or PersonalizationMixin behavior changed
- Any test in `test_patient_flow_responses.py` failing means dual-write, schema, or API contract is broken
- `ImportError` on `from app.models.patient_flow_response import PatientFlowResponse` means model registration or barrel export is broken
- Regressions in existing flow tests (`test_sequencing_expects_response.py`, `test_sequential_message_handler.py`, etc.) would indicate S04 changes affected S01's sequencing contract
- More than 1 failure in full flow test suite (the pre-existing line-count test) means a real regression

## Requirements Proved By This UAT

- R060 — AI grounding calibration proven by 25 tests covering all threshold boundaries, variation determinism, question rephrasing, and AI-skip behavior
- R061 — Patient responses stored in structured table with full context and queryable via API with date filtering

## Not Proven By This UAT

- R060 subjective quality: human evaluation of whether reformulations "feel natural" over 45+ days — requires real patient interaction
- R061 live database: migration has not been run against real Postgres — will execute on first deployment
- R062 (quiz alerts → notifications) — deferred to S05
- R063 (monthly IA summary) — deferred to S06

## Notes for Tester

- The pre-existing `test_split_files_under_500_lines` failure is expected and not from S04 — `sequencing.py` grew to 521 lines during S01 work. Ignore this failure.
- All grounding tests use realistic Portuguese oncology content (e.g. "Como você está se sentindo hoje com o tratamento?") — this matches production usage.
- The `--timeout` pytest flag does not work in this project's config. Omit it from verification commands.
