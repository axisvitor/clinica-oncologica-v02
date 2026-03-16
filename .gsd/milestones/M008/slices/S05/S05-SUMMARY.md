---
id: S05
parent: M008
milestone: M008
provides:
  - WuzAPI webhook processes inbound patient WhatsApp responses through full pipeline (find patient → create message → dual-write → sequential continuation)
  - Patient responses persisted to patient_flow_responses table with flow_state_id, day_number, message_index, response_text, responded_at
  - Dual-write to step_data.responses_by_message and step_data.last_response in PatientFlowState
  - advance_patient_flow(force_day=16) transitions flow_type from onboarding to daily_follow_up
  - step_data.transitions accumulates transition history with from/to/timestamp/at_day records
  - Observability logging across full webhook → response → transition pipeline
requires:
  - slice: S04
    provides: Active patient with flow_state, welcome and daily messages sent via WuzAPI, step_data with current_flow_day and message tracking
  - slice: S01
    provides: Stack operational (backend + Celery + Dragonfly + Postgres)
  - slice: S02
    provides: WuzAPI connected with real WhatsApp number, webhook URL configured
  - slice: S03
    provides: Templates for onboarding (15 days) and daily_follow_up (16-45) seeded in DB
affects: []
key_files:
  - backend-hormonia/app/integrations/wuzapi/webhook.py
  - backend-hormonia/app/services/flow/core/transitions.py
  - backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py
  - backend-hormonia/tests/unit/services/test_flow_transition_onboarding_daily.py
key_decisions:
  - Used db.run_sync() bridge pattern for full message processing in async WuzAPI webhook handler (decision #72)
  - Dual-write to patient_flow_responses AND step_data.responses_by_message (decision #73, consistent with M007/S04 decision #54)
  - Added is_from_me guard to skip outgoing message echoes from WuzAPI
  - Transition logic already existed in FlowCoreTransitionsMixin; task focused on verification, observability, and proof rather than new implementation
patterns_established:
  - WuzAPI webhook → _process_patient_message() → _process_flow_response() → sequential continuation pipeline
  - run_sync bridge for PatientRepository, FlowStateRepository, MessageService from async webhook handlers
  - FlowCore.advance_patient_flow(force_day=N) drives phase transitions via determine_flow_type → _transition_flow_type
  - step_data.transitions as append-only list of {timestamp, from_flow, to_flow, at_day} records
  - Test pattern: _make_service(db, active_flow=flow_state) bypasses sync repo chain for unit testing FlowCore async methods
observability_surfaces:
  - Structured logs: "WuzAPI: created inbound message", "WuzAPI: persisted flow response", "WuzAPI: sequential continuation result"
  - Structured logs: "Flow type transition recorded: X → Y at day Z", "Patient X transitioned from X to Y"
  - patient_flow_responses table with full flow context (flow_state_id, day_number, message_index)
  - step_data.responses_by_message and step_data.last_response in patient_flow_states
  - step_data.transitions in patient_flow_states for transition history
drill_down_paths:
  - .gsd/milestones/M008/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M008/slices/S05/tasks/T02-SUMMARY.md
duration: 50m
verification_result: passed
completed_at: 2026-03-16
---

# S05: Resposta do paciente e transição de fase

**Wired WuzAPI webhook to full patient response processing pipeline (find patient → create message → dual-write → continuation) and verified onboarding→daily_follow_up phase transition at day 16 with 42 tests green and 0 regressions**

## What Happened

This slice closed the final two gaps in the M008 end-to-end patient onboarding flow: (1) capturing patient responses from WhatsApp and persisting them with full flow context, and (2) proving that the flow type transitions correctly when the patient reaches day 16.

**T01 — Webhook response processing:** The WuzAPI webhook's `_handle_message` function previously extracted message data and logged it but never processed it through the flow engine. T01 wired it to a full pipeline: `_process_patient_message()` finds the patient by phone via `db.run_sync()` bridge, checks for active flow state, creates an inbound message record, then `_process_flow_response()` handles dual-write persistence — creating a `PatientFlowResponse` row with `flow_state_id`, `day_number`, `message_index`, `response_text`, `responded_at` and updating `step_data.responses_by_message` and `step_data.last_response`. After persistence, `SequentialMessageHandler.handle_response_and_continue()` is triggered for flow progression. An `is_from_me` guard was added to skip WuzAPI echo messages. Messages for patients without active flows are stored as `general_chat`.

**T02 — Phase transition verification:** The transition logic already existed in `FlowCoreTransitionsMixin`. T02 verified the complete pipeline: `determine_flow_type()` maps day boundaries (≤15→onboarding, 16-45→daily_follow_up, 46+→quiz_mensal), `_transition_flow_type()` updates `flow_state.flow_type` and appends to `step_data.transitions`, and `advance_patient_flow(force_day=16)` orchestrates the full transition including broadcasting and platform sync. T02 added structured error handling + logging to `_transition_flow_type` and wrote 19 unit tests covering all boundary conditions, recording logic, and integration paths.

## Verification

- **42 tests green, 0 regressions:**
  - 23 WuzAPI webhook tests (test_wuzapi_webhook.py) — HMAC, idempotency, opt-out, LID routing, receipts, fixture processing, patient flow routing, patient-not-found, general_chat
  - 19 flow transition tests (test_flow_transition_onboarding_daily.py) — determine_flow_type boundaries, _transition_flow_type recording, advance_patient_flow integration
  - 4 existing flow core tests (split_contract + enroll_status) — all pass
- **AST parse clean:** webhook.py, transitions.py, both test files parse without error
- **Import verification:** `from app.integrations.wuzapi.webhook import _handle_message` succeeds
- **Observability surfaces confirmed:** structured logging at all pipeline stages (inbound message, patient lookup, flow response persistence, sequential continuation, transition recording)

## Requirements Advanced

- R072 — Webhook pipeline wired end-to-end: WuzAPI delivers inbound message → find patient → create message → dual-write to patient_flow_responses + step_data → trigger continuation. Code path verified by 23 webhook tests covering flow processing, patient-not-found, and general_chat paths.
- R073 — Transition pipeline verified: determine_flow_type returns correct FlowType at all boundaries, _transition_flow_type records in step_data.transitions, advance_patient_flow(force_day=16) transitions onboarding→daily_follow_up. Proven by 19 focused unit tests.

## Requirements Validated

- R072 — Patient response webhook processing is proven by code path verification (23 tests) covering the complete pipeline. Full end-to-end proof against real WhatsApp requires UAT (sending a real message and verifying the database row), which is documented in S05-UAT.md.
- R073 — Transition logic is proven by 19 unit tests covering all boundary conditions (day 1, 15, 16, 30, 45, 46, 100), recording in step_data.transitions, and advance_patient_flow integration. Full end-to-end proof against real database requires UAT (calling advance_patient_flow and verifying SQL), which is documented in S05-UAT.md.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- T01 did not use `MessageWebhookHandler.process_message()` directly — it requires sync `db.query()` session and cannot work with AsyncSession. Instead, replicated the essential pipeline using `db.run_sync()` bridge pattern (same pattern as dashboard.py, patients/crud.py).
- T02 did not create new transition logic — the logic already existed in `FlowCoreTransitionsMixin`. Task focused on verification, testing, and observability instead of new implementation.
- Added `is_from_me` guard not in original plan — prevents WuzAPI from echoing outbound messages back as inbound.
- Fixed autouse HMAC fixture in webhook tests — .env `WHATSAPP_WUZAPI_WEBHOOK_SECRET` was being loaded by settings, causing tests without explicit HMAC to fail with 403.

## Known Limitations

- `SequentialMessageHandler` instantiation uses `db.run_sync()` to create with sync session, but its `handle_response_and_continue` is async — may need adjustment if underlying flow functions need pure AsyncSession. Currently works because FlowCore has hybrid _resolve/_execute helpers (decision #70).
- Full end-to-end proof (real WhatsApp → webhook → database row → transition) requires the running stack + WuzAPI + a real WhatsApp response from the test phone. This is UAT scope, not automated test scope.
- `_transition_flow_type` calls `flow_state.flow_type = new_flow_type.value` which uses `object_session(self).query(FlowKind)` (sync). Works with sync sessions and AsyncSession.sync_session proxy. Would fail with a pure AsyncSession without sync_session.

## Follow-ups

- none — this is the terminal slice of M008.

## Files Created/Modified

- `backend-hormonia/app/integrations/wuzapi/webhook.py` — Added full response processing pipeline: `_process_patient_message()`, `_process_flow_response()`, enhanced `_handle_message()` with patient lookup, message creation, dual-write, and sequential continuation
- `backend-hormonia/app/services/flow/core/transitions.py` — Added error handling + observability logging to `_transition_flow_type`
- `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py` — Added 3 new tests for flow processing, patient-not-found, general_chat paths; added autouse HMAC fixture; total 23 tests
- `backend-hormonia/tests/unit/services/test_flow_transition_onboarding_daily.py` — New: 19 unit tests for transition boundary logic, recording, and advance_patient_flow integration

## Forward Intelligence

### What the next slice should know
- This is the terminal slice of M008. There is no next slice. The milestone is complete.
- The entire end-to-end flow is: doctor creates patient → saga sends welcome → process_daily_flows sends daily message → patient responds on WhatsApp → webhook persists response → advance_patient_flow transitions phase at day 16.

### What's fragile
- The `db.run_sync()` bridge in webhook.py creates a tight coupling between async webhook handlers and sync repositories. If repositories are refactored to async-native, the bridge must be updated or removed.
- The `flow_state.flow_type` setter internally queries `FlowKind` and `FlowTemplateVersion` from the database — it will fail if the target flow type has no active template version. This is currently guarded by error handling + logging.

### Authoritative diagnostics
- `patient_flow_responses` table — the authoritative source for patient responses with full flow context. SQL: `SELECT * FROM patient_flow_responses WHERE patient_id = '<id>'`
- `patient_flow_states.step_data` — contains `responses_by_message`, `last_response`, `transitions`, `flow_kind`, `current_flow_day`. SQL: `SELECT step_data FROM patient_flow_states WHERE patient_id = '<id>'`
- Backend logs: search for `WuzAPI: persisted flow response` and `Flow type transition recorded` for runtime evidence

### What assumptions changed
- Original assumption: MessageWebhookHandler.process_message() could be reused directly. Actual: it requires sync Session, so the pipeline was reimplemented using db.run_sync() bridge.
- Original assumption: Transition logic needed to be created. Actual: it already existed and only needed verification + observability.
