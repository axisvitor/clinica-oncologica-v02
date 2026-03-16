# S04: Criação de paciente → welcome → ciclo diário — UAT

**Milestone:** M008
**Written:** 2026-03-16

## UAT Type

- UAT mode: mixed (live-runtime + human-experience)
- Why this mode is sufficient: The slice proves real message delivery to WhatsApp — DB verification confirms pipeline success, but final human confirmation that messages arrived on the phone is required for full UAT.

## Preconditions

1. Stack running: backend on `:8000` (health green), Celery worker connected to Dragonfly (`:6380`), Postgres on `:5434` with `hormonia_dev` at Alembic head
2. WuzAPI running on `:8081` with WhatsApp number connected (verified by S02)
3. Templates seeded: `flow_kinds` has `onboarding`, `flow_template_versions` has active version with 9 steps (verified by S03)
4. Admin user seeded and login functional (verified by S01)
5. At least one doctor user exists in the DB (used as `doctor_id` for patient creation)

## Smoke Test

Run this SQL and confirm at least one patient with `flow_state=active` and messages with `status=sent`:

```sql
SELECT p.name, p.flow_state, 
       (SELECT count(*) FROM messages m WHERE m.patient_id = p.id AND m.status = 'sent') AS sent_messages
FROM patients p
WHERE p.flow_state = 'active'
ORDER BY p.created_at DESC LIMIT 5;
```

Expected: at least one row with `flow_state=active` and `sent_messages >= 2`.

## Test Cases

### 1. Patient creation via API creates active flow

1. Authenticate as doctor: `POST /api/v2/auth/login` with admin credentials
2. Create patient: `POST /api/v2/patients` with `{"name": "UAT Test Patient", "phone": "+5511999990001", "treatment_type": "hormonioterapia"}`
3. Query saga: `SELECT status, current_step FROM patient_onboarding_saga ORDER BY created_at DESC LIMIT 1`
4. **Expected:** Saga `status=COMPLETED`, `current_step=4`
5. Query patient: `SELECT flow_state FROM patients WHERE name LIKE '%UAT Test%'`
6. **Expected:** `flow_state=active`
7. Query flow state:
   ```sql
   SELECT pfs.status, pfs.current_step, fk.kind_key
   FROM patient_flow_states pfs
   JOIN flow_template_versions ftv ON ftv.id = pfs.flow_template_version_id
   JOIN flow_kinds fk ON fk.id = ftv.flow_kind_id
   WHERE pfs.patient_id = '<patient_id>';
   ```
8. **Expected:** `status=active`, `current_step=1`, `kind_key=onboarding`

### 2. Welcome message is persisted and dispatched

1. Query messages for the patient created in test 1:
   ```sql
   SELECT left(content, 80), status, direction, delivery_status
   FROM messages WHERE patient_id = '<patient_id>' ORDER BY created_at;
   ```
2. **Expected:** At least one `outbound` message with `status=sent` and `delivery_status=sent`
3. If message is `pending`, dispatch manually: call `send_scheduled_message.delay('<message_id>')` from a Python shell with env vars loaded
4. Wait 10 seconds, re-query
5. **Expected:** `status=sent`, `delivery_status=sent`

### 3. process_daily_flows sends day-1 onboarding message

1. Run from Python shell (with backend env vars loaded):
   ```python
   from asgiref.sync import async_to_sync
   from app.tasks.flows.flow_tasks import process_daily_flows_async
   result = async_to_sync(process_daily_flows_async)(10)
   print(result)
   ```
2. **Expected:** `processed_count >= 1`, `success_count >= 1`, `error_count = 0`
3. Query messages:
   ```sql
   SELECT left(content, 120), status, delivery_status, 
          message_metadata->>'flow_context' AS flow_ctx
   FROM messages WHERE patient_id = '<patient_id>' 
   ORDER BY created_at DESC LIMIT 1;
   ```
4. **Expected:** Latest message has `status=sent`, content is AI-personalized (not raw template), `flow_context` contains `"flow_day": 1, "flow_type": "onboarding"`

### 4. step_data and scheduling updated after daily processing

1. Query flow state step_data:
   ```sql
   SELECT step_data->>'last_message_sent' AS last_sent,
          step_data->>'current_flow_day' AS flow_day,
          step_data->>'flow_kind' AS flow_kind,
          step_data->>'last_task_id' AS task_id,
          next_scheduled_at::timestamp(0) AS next_sched
   FROM patient_flow_states WHERE patient_id = '<patient_id>';
   ```
2. **Expected:**
   - `last_sent` is today's ISO timestamp
   - `flow_day = 1`
   - `flow_kind = onboarding`
   - `task_id` is a UUID
   - `next_sched` is tomorrow at 9:00 AM (or next template day)

### 5. WhatsApp delivery confirmation (human verification)

1. Check the WhatsApp app on the test phone number
2. **Expected:** Two messages from the system:
   - Welcome message: "Olá [name], bem-vindo(a) à Clínica Hormonia! Seu cadastro foi realizado com sucesso..."
   - Day 1 onboarding message: AI-personalized content about treatment introduction
3. Messages should be in Portuguese, clinical in tone, and personalized to the patient name

## Edge Cases

### Already-sent message today (idempotency)

1. Run `process_daily_flows_async(10)` a second time on the same day
2. **Expected:** Result shows `status=skipped`, `reason=Message already sent today` for the patient
3. No duplicate message in the `messages` table

### Patient with no active flow

1. Create a patient without triggering the saga (e.g., direct DB insert with `flow_state=inactive`)
2. Run `process_daily_flows_async(10)`
3. **Expected:** Patient is not processed (not in active flows list)

### Saga failure compensation

1. If saga fails at step 2 (initialize_flow), check `patient_onboarding_saga.status`
2. **Expected:** `status=COMPENSATED` with `error_message` describing the failure
3. Patient should not have an active flow state

## Failure Signals

- Saga `status=COMPENSATED` with `error_type` populated — saga step failed and rolled back
- Message `status=pending` persisting for >30 seconds after dispatch — Celery worker not processing or WuzAPI not reachable
- `process_daily_flows` returns `error_count > 0` — check `errors` array for `ChunkedIteratorResult`, `MissingGreenlet`, or session-related errors
- `delivery_status=failed` in messages table — WuzAPI rejected the send (check WuzAPI logs on port 8081)
- `patient_flow_states.status` is not `active` after saga — check saga `error_details` JSONB

## Requirements Proved By This UAT

- R070 — Patient creation → welcome message on WhatsApp: saga completes, welcome delivered
- R071 — Daily onboarding cycle works end-to-end: template loaded, AI personalizes, WuzAPI delivers

## Not Proven By This UAT

- R072 — Patient response capture via webhook (S05 scope)
- R073 — Automatic transition from onboarding to daily_follow_up at day 16 (S05 scope)
- Celery beat automatic scheduling of process_daily_flows (manual trigger used)
- Multi-day progression (only day 1 proven; day 2+ requires waiting or day manipulation)

## Notes for Tester

- The test phone number must be the one connected to WuzAPI in S02. Check `WHATSAPP_WUZAPI_BASE_URL` in `.env`.
- If `process_daily_flows` returns "Message already sent today", the patient already received today's message. Wait until tomorrow or create a new patient.
- The daily message content is AI-personalized by Gemini — exact wording will vary between runs but should be clinically grounded in the day 1 template content.
- Celery beat is NOT running — all dispatch is manual via `send_scheduled_message.delay()` or `process_daily_flows_async()`.
- The `patient_flow_states.flow_type` column does not exist directly — always join through `flow_template_versions → flow_kinds` to get `kind_key`.
