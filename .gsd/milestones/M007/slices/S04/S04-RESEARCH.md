# S04: Personalização IA e armazenamento de respostas — Research

**Date:** 2026-03-16

## Summary

S04 covers two related but separable concerns: (A) calibrating the existing AI personalization pipeline with grounding verification, and (B) building structured storage for patient free-text responses linked to flow context.

**Personalization IA** — The pipeline is already fully wired. `PersonalizationMixin` in `sequencing.py`'s `_send_all_sequential` calls `_personalize_message_ai()` for every message before sending. This method already: uses `EnhancedFlowEngine.generate_flow_message()` with Gemini, checks grounding via `_personalization_is_grounded()` (SequenceMatcher similarity + keyword overlap), falls back to deterministic variation selection + light rephrasing, and records Prometheus metrics via `record_ai_fallback()`. The grounding thresholds are hardcoded at `overlap_ratio >= 0.2 OR similarity >= 0.6` (or `similarity >= 0.35` when no keywords). This slice needs focused unit tests proving the grounding check works correctly and that the thresholds produce reasonable behavior — not a rewrite of the pipeline.

**Response storage** — Currently, patient responses are stored in two places: (1) `PatientFlowState.step_data["responses_by_message"]` as JSONB blobs inside the flow state row (written by `FlowResponseMixin.process_patient_response`), and (2) `Message` table rows with `direction=INBOUND`. Neither is structured for querying by day/message/period. The roadmap calls for a dedicated `patient_flow_responses` table with columns `flow_state_id`, `day_number`, `message_index`, `response_text`, `responded_at`, plus an API endpoint `GET /api/v2/patients/{patient_id}/flow-responses`. This is a new table + migration + model + API — straightforward CRUD.

## Recommendation

Split into 3 tasks in this order:

1. **T01: Grounding calibration tests** — Write focused unit tests for `_personalization_is_grounded()`, `_select_template_variation()`, and `_lightly_rephrase_question()`. Prove the existing grounding logic works: test boundary cases at the thresholds, test that identical text passes, test that hallucinated content fails, test variation selection is deterministic. These are pure unit tests with no DB or AI dependency. Also add a test proving `_personalize_message_ai` skips AI for `expects_response=False` messages (existing behavior, not tested explicitly).

2. **T02: Patient flow responses table and model** — Create Alembic migration for `patient_flow_responses` table, SQLAlchemy model `PatientFlowResponse`, and wire the write path into `FlowResponseMixin.process_patient_response()` so responses are persisted to the new table alongside the existing `step_data` writes. This is the structural foundation.

3. **T03: Response query API and integration tests** — Build `GET /api/v2/patients/{patient_id}/flow-responses` with period filtering. Add integration-level tests proving the write-through from `process_patient_response` populates the new table and the API returns correct data.

## Implementation Landscape

### Key Files

- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/personalization.py` (299 lines) — `PersonalizationMixin` with `_personalize_message_ai()`, `_personalization_is_grounded()`, `_select_template_variation()`, `_lightly_rephrase_question()`, `_build_fallback_content()`. This is the IA calibration target. **No code changes needed** — only new tests to prove grounding works.

- `backend-hormonia/app/services/flow/metrics.py` (31 lines) — `record_ai_fallback()` Prometheus counter. Already used correctly by personalization. No changes.

- `backend-hormonia/app/services/enhanced_flow_engine_pkg/response_processing.py` (409 lines) — `FlowResponseMixin.process_patient_response()`. Currently writes responses to `step_data["responses_by_message"]` and `step_data["responses"]`. **Needs modification** to also write to new `patient_flow_responses` table.

- `backend-hormonia/app/models/flow.py` — `PatientFlowState`, `FlowTemplateVersion`, `FlowKind` models. The new `PatientFlowResponse` model should live here or in a new `patient_flow_response.py` file.

- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` — `StateMixin._set_flow_progress()` persists `pending_response_context` with `flow_day`, `flow_kind`, `message_index`, `prompt_message_id`. This context is consumed by response processing to link responses to the correct message.

- `backend-hormonia/app/services/webhook/handlers/message_handler.py` — The webhook handler that triggers `process_patient_response()` when a patient message arrives. Builds `response_context` from `step_data`. **No changes needed** — it already passes the right context through.

- `backend-hormonia/app/api/v2/routers/flows.py` — Has existing `POST /{patient_id}/response` endpoint. The new `GET /api/v2/patients/{patient_id}/flow-responses` should go in a new file or in an existing patient-scoped router.

- `backend-hormonia/app/api/v2/routers/patients/crud.py` — Existing patient CRUD router. Natural home for the new responses query endpoint.

- `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py` (20 tests) — Existing tests for personalization fallbacks. Pattern to follow for new grounding tests.

- `backend-hormonia/tests/unit/services/flow/test_flow_metrics.py` — Has `test_personalization_mixin_records_all_fallback_paths`. Pattern for testing personalization metric recording.

### Build Order

1. **T01 first** — Grounding tests are pure unit tests with zero dependencies. They prove R060 immediately and establish the grounding contract that the rest of the pipeline relies on. Fast to write, fast to verify.

2. **T02 second** — The `patient_flow_responses` table is the structural prerequisite for T03's API. Migration + model + write path wiring.

3. **T03 last** — API endpoint depends on the table existing (T02). Integration tests prove the full write-through path.

### Verification Approach

**T01 verification:**
```bash
cd backend-hormonia && python -m pytest tests/unit/services/flow/test_personalization_grounding.py -v
```
Expected: 10+ tests covering grounding thresholds, variation selection determinism, light rephrasing, and AI skip for non-response messages. All green.

**T02 verification:**
```bash
# Migration compiles
cd backend-hormonia && python -m alembic check
# Model imports cleanly
cd backend-hormonia && python -c "from app.models.patient_flow_response import PatientFlowResponse; print('OK')"
```

**T03 verification:**
```bash
cd backend-hormonia && python -m pytest tests/unit/services/flow/test_patient_flow_responses.py -v
```
Expected: tests proving write-through from `process_patient_response`, API query by patient+period, empty results for no data.

**Slice-level:**
```bash
cd backend-hormonia && python -m pytest tests/unit/services/flow/ -v --tb=short
```
All existing tests (36+ flow tests) still green, plus new tests green.

## Constraints

- Grounding thresholds in `_personalization_is_grounded()` are the existing calibration. This slice proves they work — it does not change them unless tests reveal a clear defect. Threshold tuning is experimental work that happens post-proof.
- The `EnhancedFlowEngine.generate_flow_message()` call chain goes through Gemini. Tests must mock the AI client — never call real Gemini in unit tests.
- `process_patient_response` in `response_processing.py` already does a lot (sentiment analysis, engagement scoring, reminder handling, step_data writes). The new table write must be additive — do not restructure the existing flow.
- Alembic migrations must follow the existing pattern: use the naming convention `m007_s04_tNN_description.py` and depend on the current head `m006_s02_t03_drop_users_firebase_residue`.
- The `patient_flow_responses` table should have a foreign key to `patient_flow_states.id` for `flow_state_id`, but the FK should be nullable since `process_patient_response` can run even without an active flow state (the code handles `flow_state is None`).

## Common Pitfalls

- **Testing grounding with real strings** — The `SequenceMatcher` ratio is sensitive to string length and character distribution. Tests should use realistic Portuguese oncology content, not lorem ipsum, to avoid false confidence in threshold calibration.
- **Migration dependency chain** — The latest Alembic head is `m006_s02_t03_drop_users_firebase_residue`. The new migration must depend on this exact revision. Check with `alembic heads` before writing.
- **Dual-write consistency** — Writing to both `step_data["responses_by_message"]` and the new `patient_flow_responses` table in `process_patient_response` must happen in the same transaction. The method already calls `await self.db.commit()` once at the end — the new write should happen before that commit, not in a separate transaction.

## Open Risks

- The `process_patient_response` method at 409 lines is complex with many try/except branches. Wiring a new table write into it without accidentally breaking the existing sentiment/engagement/reminder flow requires careful placement and testing.
- If `flow_state` is `None` (no active flow), responses can still be processed. The new table write must handle this case — either skip the write or store with `flow_state_id=NULL`.
