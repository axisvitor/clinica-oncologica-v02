---
id: S04
parent: M007
milestone: M007
provides:
  - 25 focused unit tests proving PersonalizationMixin grounding calibration (thresholds, variation determinism, question rephrasing, AI-skip)
  - PatientFlowResponse SQLAlchemy model and Alembic migration for structured patient response storage
  - Dual-write in process_patient_response() persisting to patient_flow_responses alongside existing step_data JSONB
  - GET /api/v2/patients/{patient_id}/flow-responses endpoint with date-range filtering and doctor_or_admin auth
  - FlowResponseItem Pydantic schema for structured response serialization
  - 14 integration-level tests proving dual-write, schema serialization, date filtering, and ordering
requires:
  - slice: S01
    provides: pending_response_context in step_data linking response to exact day_number + message_index; stable sequential pipeline
affects:
  - S05
  - S06
key_files:
  - backend-hormonia/tests/unit/services/flow/test_personalization_grounding.py
  - backend-hormonia/alembic/versions/m007_s04_t02_patient_flow_responses.py
  - backend-hormonia/app/models/patient_flow_response.py
  - backend-hormonia/app/services/enhanced_flow_engine_pkg/response_processing.py
  - backend-hormonia/app/api/v2/routers/patients/flow_responses.py
  - backend-hormonia/app/api/v2/routers/patients/__init__.py
  - backend-hormonia/tests/unit/services/flow/test_patient_flow_responses.py
key_decisions:
  - Dual-write block placed outside `if flow_state:` so responses persist even without active flow state; flow_state_id nullable with ON DELETE SET NULL
  - Mounted flow_responses_router before crud_router in patients/__init__.py to prevent /{patient_id} catch-all from shadowing /{patient_id}/flow-responses
  - Used _make_handler() helper with mock DB for PersonalizationMixin testing (same shim pattern as test_sequential_message_handler.py)
patterns_established:
  - Dual-write pattern for structured storage alongside existing JSONB step_data within same DB transaction
  - FlowResponseItem Pydantic schema with from_attributes=True for ORM-to-API serialization
  - Module-isolation shim pattern for PersonalizationMixin testing reused from existing test infrastructure
observability_surfaces:
  - SQL: SELECT * FROM patient_flow_responses WHERE patient_id = ? ORDER BY responded_at DESC
  - SQL: SELECT * FROM patient_flow_responses WHERE patient_id = ? AND responded_at BETWEEN ? AND ? (uses ix_pfr_patient_responded composite index)
  - API: GET /api/v2/patients/{id}/flow-responses?start_date=...&end_date=...
  - Failure: if dual-write fails, entire transaction rolls back (step_data + patient_flow_responses)
drill_down_paths:
  - .gsd/milestones/M007/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M007/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M007/slices/S04/tasks/T03-SUMMARY.md
duration: 42m
verification_result: passed
completed_at: 2026-03-16
---

# S04: Personalização IA e armazenamento de respostas

**IA grounding calibration proven by 25 focused tests, patient responses dual-written to structured table with full flow context, and queryable via date-filtered API endpoint**

## What Happened

Three tasks built the slice bottom-up:

**T01 (Grounding calibration proof):** Created 25 unit tests proving the existing PersonalizationMixin works correctly without changing any production code. Tests cover `_personalization_is_grounded()` boundary cases (identical text, hallucinated text, anchored reformulation, keyword overlap thresholds at 0.6/0.2/0.35), `_select_template_variation()` determinism (same inputs → same result, different patients → different selections, edge cases with empty/duplicate/non-string variations), `_lightly_rephrase_question()` (questions get prefix wrapper, non-questions unchanged, no double-wrapping), and `_personalize_message_ai` (AI skipped when `expects_response=False`, `ai_disabled` fallback reason recorded). All tests use realistic Portuguese oncology content matching production usage.

**T02 (Structured storage):** Created the `patient_flow_responses` table via Alembic migration with UUID PK, nullable FK to `patient_flow_states` (ON DELETE SET NULL), not-null FK to `patients` (ON DELETE CASCADE), `day_number`, `message_index`, `response_text`, `responded_at`, prompt/response message IDs, and timestamps. Four indexes including composite `(patient_id, responded_at)` for period queries. Created the `PatientFlowResponse` SQLAlchemy model with relationships. Wired dual-write into `process_patient_response()` — the new row is created OUTSIDE the `if flow_state:` block (fires even when `flow_state is None`) and BEFORE `await self.db.commit()`, so both writes share the same transaction.

**T03 (Query API):** Built `GET /{patient_id}/flow-responses` endpoint with optional `start_date`/`end_date` query params, `@require_doctor_or_admin()` auth, patient existence check (404), and ascending `responded_at` ordering. Created `FlowResponseItem` Pydantic response schema. Registered the router in `patients/__init__.py` before `crud_router` to avoid path shadowing. 14 integration tests prove schema serialization, dual-write with/without flow_state, date filtering, empty results, and ordering.

## Verification

| Check | Result |
|---|---|
| T01: `test_personalization_grounding.py` | 25 passed |
| T01 diagnostic: `hallucin or empty or ai_skip` | 7 passed |
| T02: Model import | OK |
| T02 diagnostic: NULL flow_state_id instantiation | OK |
| T03: `test_patient_flow_responses.py` | 14 passed |
| All flow tests: `tests/unit/services/flow/` | 154 passed, 4 skipped, 0 regressions |
| Pre-existing failure | `test_split_files_under_500_lines` (sequencing.py at 521 lines — not from S04) |

## Requirements Advanced

- R060 — Grounding calibration proven by 25 focused tests covering all threshold boundaries, variation determinism, question rephrasing logic, and AI-skip behavior. The existing IA personalization pipeline produces anchored reformulations with verified similarity thresholds.
- R061 — Patient free-text responses now persist to `patient_flow_responses` with `flow_state_id`, `day_number`, `message_index`, `response_text`, `responded_at`. Queryable via `GET /api/v2/patients/{id}/flow-responses` with date filtering.

## Requirements Validated

- R060 — 25 tests prove grounding thresholds reject hallucinated content and accept anchored reformulations at boundary values (similarity ≥ 0.6, keyword overlap ≥ 0.2, no-keyword similarity ≥ 0.35). Variation determinism and AI-skip for non-response messages proven.
- R061 — Dual-write path proven (step_data + patient_flow_responses in same transaction). API endpoint returns structured responses filtered by date. 14 integration tests cover write-through, schema serialization, filtering, empty results, and ordering.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- T01: One boundary test (`test_no_keyword_short_content_below_threshold_fails`) required text pair correction — original pair had similarity 0.389 > 0.35 threshold. Replaced with more divergent pair (similarity 0.308). Not a plan deviation, just empirical calibration during test authoring.

## Known Limitations

- Grounding calibration was proven via unit tests only — no human/UAT evaluation of real reformulation quality over 45+ days. R060 says "patient does not perceive repetition" which ultimately requires human judgment.
- The `patient_flow_responses` table has not been exercised against real Postgres — migration and model are proven via mock/test DB only. Live migration will run on first deployment.
- Pre-existing `test_split_files_under_500_lines` failure (sequencing.py at 521 lines) — not introduced by S04.

## Follow-ups

- S05 consumes `patient_flow_responses` for contextualizing quiz alerts — the table and query path are ready.
- S06 consumes `patient_flow_responses` via period query for `PatientSummaryService.generate_monthly_summary()` — the composite index `ix_pfr_patient_responded` is optimized for this pattern.

## Files Created/Modified

- `backend-hormonia/tests/unit/services/flow/test_personalization_grounding.py` — 25 focused tests for PersonalizationMixin (grounding, variations, rephrasing, AI skip)
- `backend-hormonia/alembic/versions/m007_s04_t02_patient_flow_responses.py` — Alembic migration creating patient_flow_responses table with 4 indexes
- `backend-hormonia/app/models/patient_flow_response.py` — SQLAlchemy model with relationships to PatientFlowState and Patient
- `backend-hormonia/app/models/__init__.py` — Added PatientFlowResponse to barrel exports
- `backend-hormonia/app/services/enhanced_flow_engine_pkg/response_processing.py` — Added dual-write block and PatientFlowResponse import
- `backend-hormonia/app/api/v2/routers/patients/flow_responses.py` — GET endpoint with FlowResponseItem schema and date filtering
- `backend-hormonia/app/api/v2/routers/patients/__init__.py` — Registered flow_responses_router before crud_router
- `backend-hormonia/tests/unit/services/flow/test_patient_flow_responses.py` — 14 integration-level tests

## Forward Intelligence

### What the next slice should know
- `patient_flow_responses` is ready for consumption. S05 can query it by `patient_id` + `responded_at` range to contextualize quiz alerts. S06 can query the same way for `PatientSummaryService`.
- The composite index `ix_pfr_patient_responded` on `(patient_id, responded_at)` is designed for monthly period queries — S06 should use this index pattern.
- The dual-write is unconditional — even responses without an active flow state are persisted with `flow_state_id=NULL`. This means S06 can rely on the table having all responses, not just flow-enrolled ones.

### What's fragile
- The `flow_responses_router` mount order in `patients/__init__.py` matters — it must stay before `crud_router` to avoid `/{patient_id}` catch-all shadowing. Future routers under patients/ need the same awareness.
- The grounding thresholds (0.6 similarity, 0.2 keyword overlap, 0.35 no-keyword) are now verified by tests. Changing them requires updating the test expectations too.

### Authoritative diagnostics
- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_personalization_grounding.py tests/unit/services/flow/test_patient_flow_responses.py -v` — proves both grounding and storage contracts in <3s
- `SELECT count(*) FROM patient_flow_responses WHERE patient_id = ?` — quick check that dual-write is working in production

### What assumptions changed
- The plan said "10+ tests" for grounding — actual is 25 tests covering more boundary cases than expected.
- The plan said "5+ tests" for response API — actual is 14 integration tests with broader coverage.
- pytest `--timeout` flag is not available in this project's config — verification commands in the plan needed adjustment.
