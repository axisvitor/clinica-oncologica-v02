# S05: Resposta do paciente e transição de fase — UAT

**Milestone:** M008
**Written:** 2026-03-16

## UAT Type

- UAT mode: mixed (artifact-driven unit tests + live-runtime verification)
- Why this mode is sufficient: Unit tests prove code paths and boundary logic (42 tests green). Live-runtime UAT proves real WhatsApp → webhook → database → transition chain against the running stack. Both are needed because the code-path tests alone cannot prove the WuzAPI webhook delivers real messages to the pipeline.

## Preconditions

1. Full stack running: backend (localhost:8000), Celery worker, PostgreSQL (hormonia_dev on port 5434), Dragonfly (port 6380)
2. WuzAPI running on port 8081 with WhatsApp number connected (QR code paired)
3. At least one patient created with an active flow (from S04 — POST /api/v2/patients with real WhatsApp phone)
4. Patient has received at least one message (welcome or daily) so there is a `current_flow_day` and `current_day_message_index` in step_data
5. Access to the test WhatsApp phone to send a response message

## Smoke Test

Send a text message "Oi" from the test WhatsApp phone (the patient's number) to the WuzAPI-connected number. Check backend logs for `WuzAPI: created inbound message` and `WuzAPI: persisted flow response`. If both appear, the pipeline is working.

## Test Cases

### 1. Patient response persisted via webhook

1. Identify the test patient's ID from the database: `SELECT id, phone_hash FROM patients LIMIT 5;`
2. Check the patient's current flow state: `SELECT id, flow_type, current_step, step_data->'current_flow_day' as flow_day, step_data->'current_day_message_index' as msg_idx FROM patient_flow_states WHERE patient_id = '<patient_id>' AND status = 'active';`
3. From the test phone (patient's WhatsApp), send the message: "Estou me sentindo bem hoje"
4. Wait 5-10 seconds for webhook processing
5. Check backend logs for structured processing messages
6. **Expected:** Backend logs show:
   - `WuzAPI inbound message from <phone>: id=<msg_id> text_len=26`
   - `WuzAPI: created inbound message <uuid> for patient <patient_id>`
   - `WuzAPI: persisted flow response for patient <patient_id> (day=<N>, msg_idx=<M>)`
   - `WuzAPI: sequential continuation result for patient <patient_id>: status=<status>`

### 2. Response row exists in patient_flow_responses

1. After test case 1, query the database:
   ```sql
   SELECT id, flow_state_id, day_number, message_index, response_text, responded_at, prompt_message_id, response_message_id
   FROM patient_flow_responses
   WHERE patient_id = '<patient_id>'
   ORDER BY responded_at DESC
   LIMIT 5;
   ```
2. **Expected:** At least one row with:
   - `response_text` = "Estou me sentindo bem hoje"
   - `day_number` matches the patient's current_flow_day
   - `message_index` matches current_day_message_index
   - `flow_state_id` is not NULL and matches the active flow state
   - `responded_at` is within the last few minutes

### 3. Dual-write to step_data

1. After test case 1, query step_data:
   ```sql
   SELECT
     step_data->'responses_by_message' as responses,
     step_data->'last_response' as last_resp
   FROM patient_flow_states
   WHERE patient_id = '<patient_id>'
   AND status = 'active';
   ```
2. **Expected:**
   - `responses_by_message` contains a key like `day_N_msg_M` with `response_text`, `timestamp`, `flow_day`, `flow_kind`
   - `last_response` contains `response_message_id` and `timestamp` and `text_length`

### 4. Outgoing message echo is skipped

1. Send a message FROM the system to the patient (trigger process_daily_flows or send a manual message)
2. Check backend logs
3. **Expected:** WuzAPI echoes the outgoing message back to the webhook, but logs show `WuzAPI Message: skipping own message id=<id>` and the message is NOT persisted as an inbound patient response

### 5. Transition onboarding → daily_follow_up at day 16

1. Check current flow state:
   ```sql
   SELECT id, flow_type, current_step, step_data->'flow_kind' as kind, step_data->'transitions' as transitions
   FROM patient_flow_states
   WHERE patient_id = '<patient_id>' AND status = 'active';
   ```
2. Run advance_patient_flow with force_day=16 via Python shell or management command:
   ```python
   # In a Python shell with backend context:
   import asyncio
   from app.services.flow_core import FlowCore
   # ... setup db session, create FlowCore instance ...
   result = await flow_core.advance_patient_flow(patient_id, force_day=16)
   print(result)
   ```
   Or via the API if there is an admin endpoint for flow advancement.
3. **Expected:** Result dict contains:
   - `status: "success"`
   - `transitioned: True`
   - `flow_type: "daily_follow_up"`
   - `previous_flow_type: "onboarding"`
   - `current_day: 16`
4. Verify in database:
   ```sql
   SELECT flow_type, step_data->'flow_kind' as kind, step_data->'transitions' as transitions, step_data->'current_flow_day' as day
   FROM patient_flow_states
   WHERE patient_id = '<patient_id>' AND status = 'active';
   ```
5. **Expected:**
   - `flow_type` = "daily_follow_up"
   - `step_data.flow_kind` = "daily_follow_up"
   - `step_data.transitions` contains at least one entry with `from_flow: "onboarding"`, `to_flow: "daily_follow_up"`, `at_day: 16`, and a valid `timestamp`
   - `step_data.current_flow_day` = 16

### 6. Patient without active flow stores as general_chat

1. Find or create a patient that has NO active flow state (e.g., flow was completed or paused)
2. Send a WhatsApp message from that patient's number
3. **Expected:**
   - Backend logs show `WuzAPI: no active flow for patient <id>, message stored as general_chat`
   - A message row is created in the `messages` table with metadata containing `"context": "general_chat"`
   - NO row is created in `patient_flow_responses`

## Edge Cases

### Unknown phone number sends message

1. Send a WhatsApp message from a phone number not registered as any patient
2. **Expected:** Backend logs show `WuzAPI message: patient not found for phone` and response is `{"status": "skipped", "reason": "patient_not_found"}`

### Duplicate message (idempotency)

1. Note: WuzAPI may send the same webhook event twice
2. **Expected:** Second delivery returns `{"status": "duplicate"}` and does NOT create a second response row

### Opt-out keyword

1. Send "PARAR" or "CANCELAR" or "STOP" from a patient's WhatsApp
2. **Expected:** Response is `{"status": "opt_out_processed"}` and the patient's messaging consent is revoked

## Failure Signals

- Backend logs show `WuzAPI message processing failed: ...` — indicates pipeline error
- Backend logs show `WuzAPI: sequential continuation failed` — indicates flow engine error after response persistence
- No row in `patient_flow_responses` after sending a message — webhook pipeline is broken
- `flow_type` still "onboarding" after force_day=16 — transition logic is broken
- `step_data.transitions` is empty after force_day=16 — transition recording is broken
- Backend returns 403 on webhook — HMAC validation issue (check WHATSAPP_WUZAPI_WEBHOOK_SECRET matches WuzAPI config)
- Backend returns 500 on webhook — import or runtime error in processing pipeline

## Requirements Proved By This UAT

- R072 — Patient response arrives via WhatsApp, webhook processes it, row exists in patient_flow_responses with correct day_number, message_index, flow_state_id
- R073 — advance_patient_flow(force_day=16) transitions onboarding→daily_follow_up, step_data.transitions records the transition with from/to/timestamp/at_day

## Not Proven By This UAT

- Celery beat automatic scheduling of process_daily_flows (requires cron/beat config not in M008 scope)
- Quiz mensal transition at day 46+ (out of M008 scope per R075)
- Multi-patient concurrent response processing (single-patient test only)
- Long-term flow progression across 15+ real days (accelerated via force_day only)

## Notes for Tester

- The test phone must be the same number used for the patient created in S04. Check `phone_hash` in patients table against the known phone.
- WuzAPI webhook URL must be configured to point to the backend's `/webhooks/wuzapi` endpoint. Verify with: `curl http://localhost:8081/api/getwebhook` (or similar WuzAPI admin endpoint).
- If no messages appear in logs after sending from WhatsApp, check: (1) WuzAPI container is running, (2) webhook URL is correct, (3) HMAC secret matches between WuzAPI and backend .env.
- The `force_day=16` approach is a shortcut for testing transition without waiting 16 real days. In production, `calculate_patient_day()` computes the actual day from `started_at`.
- After transition, running `process_daily_flows` should use daily_follow_up templates (day 16+) instead of onboarding templates.
