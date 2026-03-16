# S04: Criação de paciente → welcome → ciclo diário

**Goal:** Médico cria paciente via API, saga executa (create → flow → welcome → commit), welcome message chega no WhatsApp real. Trigger manual de `process_daily_flows` envia mensagem do dia com conteúdo do template.
**Demo:** Paciente criado, welcome message recebida no WhatsApp. Segundo trigger envia mensagem do dia 1 do onboarding com conteúdo clínico real personalizado por IA.

## Must-Haves

- `POST /api/v2/patients` cria paciente com doctor_id, phone, name
- Saga completa 4 steps: create_patient → initialize_flow → send_welcome → commit
- Welcome message chega no WhatsApp real do número de teste
- PatientFlowState criado com flow_type=onboarding, status=active
- Trigger manual de `process_daily_flows` processa o paciente e envia mensagem do dia
- Mensagem do dia chega no WhatsApp com conteúdo do template (personalizado se Gemini ativo)

## Proof Level

- This slice proves: integration + operational
- Real runtime required: yes (todo o stack + WuzAPI)
- Human/UAT required: yes (verificar mensagens no telefone)

## Verification

- Query SQL: `SELECT id, name, flow_state FROM patients WHERE phone_hash IS NOT NULL` mostra paciente ativo
- Query SQL: `SELECT patient_id, flow_type, status, current_step FROM patient_flow_states WHERE status = 'active'` mostra flow state
- Query SQL: `SELECT content, status, direction FROM messages WHERE patient_id = '<id>' ORDER BY created_at` mostra welcome + daily message
- Mensagem welcome e mensagem do dia recebidas no WhatsApp (verificação visual)

## Observability / Diagnostics

- Runtime signals: saga logs (step 1-4), process_daily_flows logs, send_scheduled_message logs
- Inspection surfaces: `patient_flow_states` table, `messages` table, `patient_onboarding_sagas` table
- Failure visibility: saga error em `patient_onboarding_sagas.error_details`, task failure em Celery logs
- Redaction constraints: phone number encriptado em `patients.phone_encrypted`

## Tasks

- [x] **T01: Criar paciente via API e provar saga completa** `est:40m`
  - Why: este é o caminho crítico — se a saga não completar, o paciente nunca recebe nada
  - Files: `backend-hormonia/app/api/v2/routers/patients/crud.py`, `backend-hormonia/app/orchestration/saga_orchestrator/`
  - Do: autenticar como médico, criar paciente via `POST /api/v2/patients` com phone do número de teste. Verificar que saga completa (4 steps), PatientFlowState é criado com flow_type=onboarding e status=active, welcome message é registrada em `messages` e entregue via Celery → WuzAPI → WhatsApp. Debugar e corrigir qualquer falha no caminho.
  - Verify: welcome message recebida no WhatsApp, PatientFlowState exists, saga status=completed
  - Done when: paciente criado, flow state ativo, welcome message no telefone

- [x] **T02: Trigger manual de process_daily_flows e mensagem do dia** `est:30m`
  - Why: prova que o ciclo diário funciona — template loader carrega conteúdo, IA personaliza, WuzAPI envia
  - Files: `backend-hormonia/app/tasks/flows/batch_tasks.py`, `backend-hormonia/app/tasks/flows/flow_tasks.py`
  - Do: chamar `process_daily_flows` manualmente via Celery (`celery -A app.celery_app call app.tasks.flows.flow_tasks.process_daily_flows`) ou via script Python. Verificar que o paciente criado em T01 recebe mensagem do dia com conteúdo do template. Se day=0 e welcome já foi enviada, pode precisar ajustar current_day. Verificar que step_data é atualizado com last_message_sent.
  - Verify: mensagem do dia chega no WhatsApp, `messages` table tem novo registro, step_data atualizado
  - Done when: mensagem diária recebida no telefone com conteúdo clínico real

## Files Likely Touched

- `backend-hormonia/app/api/v2/routers/patients/crud.py`
- `backend-hormonia/app/orchestration/saga_orchestrator/`
- `backend-hormonia/app/tasks/flows/batch_tasks.py`
- `backend-hormonia/app/tasks/flows/flow_tasks.py`
- `backend-hormonia/app/services/patient/flow_service.py`
