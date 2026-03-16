---
id: S04
parent: M008
milestone: M008
provides:
  - Patient creation via API with 4-step onboarding saga (create → flow → welcome → commit)
  - PatientFlowService hybrid sync/async support for mixed session types
  - Welcome message delivered to real WhatsApp via Celery → WuzAPI pipeline
  - process_daily_flows executing successfully with AI-personalized onboarding messages
  - FlowCore hybrid _resolve/_execute/_commit helpers for sync Session in async code paths
  - step_data updated with last_message_sent, current_flow_day, flow_kind, last_task_id
  - next_scheduled_at calculated for next template day (day 2 at 9 AM)
requires:
  - slice: S01
    provides: Backend + Celery worker + Postgres + Dragonfly operational
  - slice: S02
    provides: WuzAPI connected with real WhatsApp number, send_text() delivers messages
  - slice: S03
    provides: flow_kinds + flow_template_versions with real clinical onboarding content
affects:
  - S05
key_files:
  - backend-hormonia/app/services/patient/flow_service.py
  - backend-hormonia/app/api/v2/routers/patients/crud.py
  - backend-hormonia/app/services/flow/core/operations.py
  - backend-hormonia/app/services/flow/core/transitions.py
  - backend-hormonia/app/services/enhanced_flow_engine_pkg/service.py
  - backend-hormonia/app/services/enhanced_flow_engine_pkg/orchestration.py
  - backend-hormonia/app/services/enhanced_flow_engine_pkg/conversation.py
  - backend-hormonia/tests/unit/services/test_patient_flow_service_async.py
  - backend-hormonia/tests/unit/services/test_flow_core_enroll_status.py
key_decisions:
  - Adapt PatientFlowService to support AsyncSession in saga path via hybrid helpers
  - Add _resolve/_execute/_commit/_flush/_refresh to FlowCoreOperationsMixin for sync/async compatibility
  - Refresh/reload created patient before serialization to avoid MissingGreenlet
  - Set status="active" explicitly in PatientFlowState creation during enroll_patient
patterns_established:
  - Hybrid sync/async execution pattern: `_resolve(maybe_awaitable)` detects session type
  - Manual dispatch of pending messages via send_scheduled_message.delay() when beat not running
  - process_daily_flows creates isolated session per patient, uses sync Session with async FlowCore helpers
observability_surfaces:
  - SQL: patient_onboarding_saga (status, current_step, error_message)
  - SQL: patients (flow_state, current_day)
  - SQL: patient_flow_states (status, current_step, step_data, next_scheduled_at)
  - SQL: messages (status, delivery_status, sent_at, content)
  - Runtime: celery worker logs (Successfully sent scheduled message)
  - Runtime: uvicorn logs (saga step completion, process_daily_flows results)
drill_down_paths:
  - .gsd/milestones/M008/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M008/slices/S04/tasks/T02-SUMMARY.md
duration: 2h
verification_result: passed
completed_at: 2026-03-16
---

# S04: Criação de paciente → welcome → ciclo diário

**Paciente criado via API com saga completa de 4 steps, welcome message e mensagem diária de onboarding (dia 1) ambas entregues no WhatsApp real via Celery → WuzAPI, com conteúdo clínico personalizado por Gemini.**

## What Happened

This slice proved the two critical runtime paths in the onboarding system: patient creation with welcome delivery, and daily flow processing with AI-personalized content.

**Patient creation + welcome (T01 scope):** The `POST /api/v2/patients` endpoint triggers a 4-step onboarding saga (create_patient → initialize_flow → send_welcome → commit). The first real execution immediately hit a sync/async mismatch: `PatientFlowService.initialize_default_flow()` received an `AsyncSession` from the saga coordinator but called synchronous `.query()` methods. Fixed by adding hybrid execution helpers that detect session type and `await` when the session is async. After the fix, the saga completed all 4 steps, the welcome message was persisted as `pending`, and the Celery worker dispatched it via WuzAPI to the real WhatsApp number with `status=sent`.

A second bug surfaced in the API response path: after the saga committed asynchronously, serializing the returned patient triggered `MissingGreenlet` because ORM attributes were expired. Fixed by refreshing/reloading the patient before serialization.

**Daily flow processing (T02 scope):** The previous session attempted `process_daily_flows_async()` and hit `object ChunkedIteratorResult can't be used in 'await' expression` — the FlowCore/EnhancedFlowEngine hybrid helpers written by T02 were incomplete. The T02 executor added `_resolve/_execute/_commit/_flush/_refresh` helpers to `FlowCoreOperationsMixin` and migrated all `await self.db.execute()` calls in `operations.py`, `transitions.py`, `service.py`, `orchestration.py`, and `conversation.py` to use these helpers. These changes were committed but not runtime-verified before the session crashed.

On resume, `process_daily_flows_async(10)` executed successfully: it found the active patient, advanced the flow (day 1, onboarding), loaded the template for day 1, called Gemini to personalize the content, persisted the message as `pending`, committed step_data updates (last_message_sent, current_flow_day, next_scheduled_at), and dispatched via `send_scheduled_message`. The Celery worker sent it through WuzAPI and it was marked `sent`.

**Final state:** Both welcome and day-1 onboarding messages delivered to WhatsApp with `status=sent`, `delivery_status=sent`. Patient flow state shows `status=active`, `current_step=1`, `next_scheduled_at` set for tomorrow 9 AM. All 4 unit tests pass.

## Verification

### SQL verification (all pass)

1. `SELECT id, name, flow_state FROM patients WHERE phone_hash IS NOT NULL` — 2 patients with `flow_state=active` ✅
2. `SELECT pfs.patient_id, fk.kind_key, pfs.status, pfs.current_step FROM patient_flow_states pfs JOIN flow_template_versions ftv ON ftv.id = pfs.flow_template_version_id JOIN flow_kinds fk ON fk.id = ftv.flow_kind_id WHERE pfs.status = 'active'` — onboarding, active, step 1 ✅
3. `SELECT content, status, direction FROM messages WHERE patient_id = '<id>' ORDER BY created_at` — welcome (sent) + daily (sent) ✅
4. `patient_flow_states.step_data` contains `last_message_sent`, `current_flow_day=1`, `flow_kind=onboarding`, `last_task_id` ✅
5. `patient_flow_states.next_scheduled_at` set to tomorrow 9 AM ✅
6. `patient_onboarding_saga.status = COMPLETED`, `current_step = 4` ✅

### Unit tests

- `test_flow_core_enroll_status.py` — 1 test PASS (enroll creates active flow state)
- `test_patient_flow_service_async.py` — 3 tests PASS (async session compatibility)

### Runtime verification

- `process_daily_flows_async(10)` returns `processed_count: 1, success_count: 1, error_count: 0`
- Celery worker logs: `Successfully sent scheduled message <id>` for both messages
- Backend health: `curl localhost:8000/health` returns healthy

## Requirements Advanced

- R070 — Patient created via API, saga completes 4 steps, welcome message delivered to WhatsApp real via WuzAPI. Full path proven: POST /api/v2/patients → saga → Celery worker → WuzAPI → WhatsApp.
- R071 — process_daily_flows executes, loads template for day 1, personalizes with Gemini, delivers via WuzAPI to WhatsApp real. step_data updated with scheduling metadata.

## Requirements Validated

- R070 — Welcome message received on WhatsApp (sent status confirmed in DB + worker logs), saga completed, PatientFlowState active with onboarding flow type.
- R071 — Daily onboarding message (day 1) personalized by Gemini and delivered via WuzAPI, step_data updated with last_message_sent and next_scheduled_at. process_daily_flows returns success_count=1.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- T01 was not executed as a separate task — its scope was fulfilled within the T02 execution when the executor found no patient in the database and had to create one first.
- The slice plan's SQL verification for `patient_flow_states.flow_type` doesn't match the real schema — the column doesn't exist directly. Verification uses a join through `flow_template_versions` → `flow_kinds` to get `kind_key`.
- Welcome message for the second patient was dispatched manually via `send_scheduled_message.delay()` because Celery beat was not running during the test window.

## Known Limitations

- Celery beat is not configured for automatic `process_daily_flows` scheduling — daily processing requires manual trigger or beat configuration.
- The `POST /api/v2/patients` response code after successful saga was not re-verified as a clean `201` with payload — the fix is in disk but the HTTP response was not retested end-to-end in this session.
- Visual confirmation on the physical phone (UAT) is deferred to user verification — DB + worker logs confirm `sent` status.
- The `response_processing.py` file in `enhanced_flow_engine_pkg` still has raw `await self.db.execute()` calls not migrated to the hybrid helpers — this path is only used for inbound response processing (S05 scope) and is not exercised by daily flow sending.

## Follow-ups

- Configure Celery beat schedule for `process_daily_flows` if automated daily processing is needed before S05.
- Migrate remaining `await self.db.execute()` in `response_processing.py` to hybrid helpers before S05 exercises the inbound response path.

## Files Created/Modified

- `backend-hormonia/app/services/patient/flow_service.py` — hybrid sync/async support for AsyncSession in saga onboarding path
- `backend-hormonia/app/api/v2/routers/patients/crud.py` — refresh patient before serialization post-saga
- `backend-hormonia/app/services/flow/core/operations.py` — _resolve/_execute/_commit/_flush/_refresh hybrid helpers + status="active" in enroll_patient
- `backend-hormonia/app/services/flow/core/transitions.py` — migrated to hybrid _execute/_rollback helpers
- `backend-hormonia/app/services/enhanced_flow_engine_pkg/service.py` — migrated to hybrid _execute
- `backend-hormonia/app/services/enhanced_flow_engine_pkg/orchestration.py` — migrated to hybrid _execute
- `backend-hormonia/app/services/enhanced_flow_engine_pkg/conversation.py` — migrated to hybrid _execute
- `backend-hormonia/tests/unit/services/test_patient_flow_service_async.py` — 3 unit tests for async session compatibility
- `backend-hormonia/tests/unit/services/test_flow_core_enroll_status.py` — 1 unit test for enroll_patient status=active

## Forward Intelligence

### What the next slice should know
- The patient `bc9b5253-f626-4957-b957-7dcd83ffc522` has an active onboarding flow at day 1 with welcome + daily message sent. Use this patient for S05 response/transition testing.
- `process_daily_flows` works end-to-end with sync Session via the hybrid helpers. The call path is: `process_daily_flows` (Celery task) → `async_to_sync(process_daily_flows_async)` → `_process_single_patient_flow_by_id` (creates scoped sync Session) → `EnhancedFlowEngine` (uses hybrid _execute).
- The `flow_type` is not a direct column on `patient_flow_states` — always resolve via join: `patient_flow_states.flow_template_version_id → flow_template_versions.flow_kind_id → flow_kinds.kind_key`.

### What's fragile
- `response_processing.py` still uses raw `await self.db.execute()` — it will break with sync Session if the webhook response path goes through the same scoped session as daily flow processing.
- The hybrid `_resolve()` pattern is a bridge, not a final solution. If both async and sync callers need the same FlowCore instance simultaneously, race conditions could appear.

### Authoritative diagnostics
- `patient_flow_states.step_data` is the source of truth for flow progress — check `last_message_sent`, `current_flow_day`, `flow_kind`, `last_task_id`.
- `messages` table with `status` + `delivery_status` columns shows the send pipeline state.
- Celery worker logs with `Successfully sent scheduled message <id>` confirm WuzAPI delivery.

### What assumptions changed
- **Assumed:** FlowCore/EnhancedFlowEngine only receives AsyncSession → **Actually:** `process_daily_flows` creates a sync `Session` via `get_scoped_session()`, which is passed to `EnhancedFlowEngine`. The hybrid helpers bridge this.
- **Assumed:** `patient_flow_states.flow_type` is a direct column → **Actually:** flow type is resolved via the `flow_template_versions` → `flow_kinds` join chain. `normalize_flow_type(flow_state.flow_type)` works because the model has a hybrid property or the join is done lazily.
