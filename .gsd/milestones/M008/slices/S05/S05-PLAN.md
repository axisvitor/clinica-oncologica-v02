# S05: Resposta do paciente e transição de fase

**Goal:** Paciente responde no WhatsApp, webhook processa e persiste resposta em `patient_flow_responses`. Transição onboarding → daily_follow_up funciona quando current_day atinge 16.
**Demo:** Paciente responde "Estou me sentindo bem" no WhatsApp, resposta aparece em `patient_flow_responses` com day_number e message_index corretos. Advance_patient_flow com force_day=16 transiciona flow_type para daily_follow_up.

## Must-Haves

- Webhook do WuzAPI entrega resposta do paciente pro backend
- `MessageWebhookHandler.process_message()` processa a resposta
- Row criada em `patient_flow_responses` com flow_state_id, day_number, message_index, response_text, responded_at
- Dual-write: resposta também em step_data do PatientFlowState
- `advance_patient_flow(patient_id, force_day=16)` transiciona flow_type de `onboarding` para `daily_follow_up`
- step_data.transitions registra a transição com timestamp e dia

## Proof Level

- This slice proves: integration + final-assembly
- Real runtime required: yes (todo o stack + WuzAPI + WhatsApp real)
- Human/UAT required: yes (enviar resposta pelo WhatsApp, verificar transição)

## Verification

- Query SQL: `SELECT * FROM patient_flow_responses WHERE patient_id = '<id>'` mostra resposta com contexto
- Query SQL: `SELECT flow_type, step_data->'transitions' FROM patient_flow_states WHERE patient_id = '<id>'` mostra transição
- Webhook logs mostram processamento da resposta
- Resposta do paciente processada sem erro no backend logs

## Observability / Diagnostics

- Runtime signals: webhook handler logs, response_processing logs, flow transition logs
- Inspection surfaces: `patient_flow_responses` table, `patient_flow_states.step_data`, backend logs
- Failure visibility: webhook error em logs, flow_state stuck em awaiting_response
- Redaction constraints: response_text pode conter dados sensíveis do paciente

## Integration Closure

- Upstream surfaces consumed: WuzAPI webhook → backend endpoint, patient_flow_states de S04, patient_flow_responses model de M007/S04
- New wiring introduced: webhook → dual-write → flow continuation → phase transition
- What remains before the milestone is truly usable end-to-end: nothing — this is the final slice

## Tasks

- [x] **T01: Webhook de resposta do paciente** `est:30m`
  - Why: sem webhook, respostas do paciente no WhatsApp nunca chegam ao sistema
  - Files: `backend-hormonia/app/services/webhook/handlers/message_handler.py`, `backend-hormonia/app/api/v2/routers/` (webhook endpoint)
  - Do: enviar mensagem de resposta pelo WhatsApp do número de teste. Verificar que webhook do WuzAPI entrega pro backend, MessageWebhookHandler.process_message() identifica o paciente, processa a resposta. Verificar que dual-write persiste em patient_flow_responses E step_data. Debugar e corrigir qualquer falha no caminho (phone matching, webhook routing, etc.).
  - Verify: row em patient_flow_responses com response_text correto, step_data atualizado
  - Done when: resposta "Estou me sentindo bem" enviada pelo WhatsApp aparece em patient_flow_responses com day_number e message_index corretos

- [x] **T02: Transição onboarding → daily_follow_up** `est:20m`
  - Why: provar que o sistema transiciona automaticamente de fase quando o dia atinge 16
  - Files: `backend-hormonia/app/services/flow/core/transitions.py`
  - Do: chamar `advance_patient_flow(patient_id, force_day=16)` via script Python ou API. Verificar que flow_type muda de `onboarding` para `daily_follow_up`, step_data.transitions registra a transição. Se possível, triggar process_daily_flows com current_day=16 e verificar que template de daily_follow_up é usado.
  - Verify: query SQL mostra flow_type='daily_follow_up', step_data contém transitions com from/to/timestamp
  - Done when: transição registrada, flow_type atualizado, template correto seria carregado para dia 16

## Files Likely Touched

- `backend-hormonia/app/services/webhook/handlers/message_handler.py`
- `backend-hormonia/app/services/enhanced_flow_engine_pkg/response_processing.py`
- `backend-hormonia/app/services/flow/core/transitions.py`
- `backend-hormonia/app/api/v2/routers/` (webhook endpoint)
