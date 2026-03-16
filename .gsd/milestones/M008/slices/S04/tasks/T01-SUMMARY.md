---
id: T01
parent: S04
milestone: M008
provides:
  - Patient creation via POST /api/v2/patients with saga completing 4 steps
  - PatientFlowService hybrid sync/async support for saga path
  - Welcome message persisted and dispatched via Celery worker → WuzAPI → WhatsApp
  - PatientFlowState created with flow_type=onboarding, status=active
key_files:
  - backend-hormonia/app/services/patient/flow_service.py
  - backend-hormonia/app/api/v2/routers/patients/crud.py
  - backend-hormonia/app/domain/patient/onboarding/coordinator.py
key_decisions:
  - Adapt PatientFlowService to support AsyncSession in saga onboarding path via hybrid helpers
  - Refresh/reload patient after saga commit to avoid MissingGreenlet in serialization
patterns_established:
  - Hybrid sync/async execution helpers (_resolve, _execute, _commit) for mixed session types
observability_surfaces:
  - SQL: patient_onboarding_saga (status, current_step, error_message, error_type)
  - SQL: patients (flow_state, current_day)
  - SQL: patient_flow_states (status, current_step, step_data)
  - SQL: messages (status, delivery_status, sent_at)
  - Runtime logs: saga step completion in backend uvicorn logs
  - Runtime logs: send_scheduled_message in celery worker logs
duration: 40m (executed within T02 session)
verification_result: passed
completed_at: 2026-03-16 16:58 GMT-3
blocker_discovered: false
---

# T01: Criar paciente via API e provar saga completa

**Paciente criado via POST /api/v2/patients, saga completa 4 steps (create → flow → welcome → commit), welcome message enviada via Celery worker → WuzAPI → WhatsApp real.**

## What Happened

T01 was executed as part of the T02 session because the T01 executor crashed before completing. The T02 executor found no patient in the database and had to create one to proceed.

The critical bug discovered was that `PatientFlowService.initialize_default_flow()` received an `AsyncSession` from the onboarding saga but called synchronous `.query()` / `.flush()` / `.commit()` methods. This broke the `initialize_flow` step with `AttributeError: 'AsyncSession' object has no attribute 'query'`.

Fix applied in `flow_service.py`: hybrid sync/async execution helpers that detect session type and await when needed. The same pattern was applied to `activate_patient()`, `pause_patient()`, and `delete_flow()`.

After the fix, the saga completed all 4 steps:
1. `create_patient` — patient persisted with `flow_state=active`
2. `initialize_flow` — PatientFlowState created with `status=active`, `current_step=1`
3. `send_welcome` — welcome message created in `messages` table with `status=pending`
4. `commit` — saga marked `COMPLETED`, `current_step=4`

Welcome dispatched manually via `send_scheduled_message.delay()` and confirmed `status=sent` in DB.

## Verification

- Saga: `patient_onboarding_saga.status = COMPLETED`, `current_step = 4`
- Patient: `patients.flow_state = active`, `current_day = 1`
- Flow: `patient_flow_states.status = active`, `current_step = 1`, `flow_kind = onboarding`
- Welcome: `messages.status = sent`, `delivery_status = sent`, `sent_at` populated
- Unit tests: `test_patient_flow_service_async.py` — 3 tests PASS

## Diagnostics

- Check saga status: `SELECT id, patient_id, status, current_step, error_message FROM patient_onboarding_saga ORDER BY created_at DESC LIMIT 5`
- Check flow state: `SELECT pfs.patient_id, fk.kind_key, pfs.status, pfs.current_step FROM patient_flow_states pfs JOIN flow_template_versions ftv ON ftv.id = pfs.flow_template_version_id JOIN flow_kinds fk ON fk.id = ftv.flow_kind_id WHERE pfs.status = 'active'`
- Check messages: `SELECT id, left(content, 80), status, delivery_status FROM messages WHERE patient_id = '<id>' ORDER BY created_at`
- Celery worker logs: grep for `Successfully sent scheduled message`
