# M008: Onboarding Real de Pacientes - Ponta a Ponta

**Vision:** Provar que o sistema de acompanhamento oncológico funciona de verdade: médico cria paciente no dashboard, paciente recebe mensagens no WhatsApp real, responde livremente, e o fluxo avança automaticamente do onboarding ao daily follow-up — tudo rodando localmente contra serviços reais.

## Success Criteria

- Stack local (Postgres + Dragonfly + backend + Celery worker + WuzAPI) sobe e responde health checks
- WuzAPI conectado com número real envia mensagem de teste que chega no WhatsApp
- Templates de onboarding (15 dias) e daily follow-up (dia 16-45) existem no banco com conteúdo clínico real
- Médico cria paciente no dashboard e welcome message chega no WhatsApp real
- `process_daily_flows` envia mensagem do dia correto pro WhatsApp do paciente
- Paciente responde livremente no WhatsApp e a resposta é persistida em `patient_flow_responses` com contexto de fluxo
- Transição automática de onboarding para daily_follow_up funciona no dia 16

## Key Risks / Unknowns

- WuzAPI setup com QR code é manual e pode falhar se número não parear — risco de bloqueio
- Webhook routing entre WuzAPI → backend em ambiente Docker local — precisa de rede correta
- kind_key mismatch (`initial_15_days` vs `onboarding`) se Alembic head não estiver atualizado
- Celery beat schedule pode não existir para `process_daily_flows` — precisa trigger manual ou configuração
- 292 env vars — configuração inconsistente pode bloquear silenciosamente

## Proof Strategy

- Stack setup → retirar em S01 provando que backend responde `/health` e Celery worker conecta ao broker
- WuzAPI real → retirar em S02 provando que `send_text()` entrega mensagem no WhatsApp de teste
- Templates → retirar em S03 provando que `EnhancedTemplateLoader.get_message_for_day()` retorna conteúdo para todos os dias de onboarding e daily follow-up
- Welcome + ciclo diário → retirar em S04 provando que create_patient saga entrega welcome e `process_daily_flows` entrega mensagem do dia
- Resposta + transição → retirar em S05 provando que webhook persiste resposta e `advance_patient_flow` transiciona no dia 16

## Verification Classes

- Contract verification: health check endpoints, template loader retorna conteúdo, flow_kinds existem no banco
- Integration verification: WuzAPI envia/recebe real, saga cria paciente e envia welcome, webhook processa resposta
- Operational verification: Celery worker processa tasks, process_daily_flows executa sem erro, transição de fase funciona
- UAT / human verification: mensagem chega no WhatsApp real (verificação visual pelo usuário)

## Milestone Definition of Done

This milestone is complete only when all are true:

- Stack local (backend + Celery + Dragonfly + Postgres + WuzAPI) roda e se comunica
- WuzAPI conectado com número real, enviando e recebendo mensagens
- Templates de onboarding (15 dias) e daily follow-up (dia 16-45) existem no banco com conteúdo clínico
- Paciente criado pelo médico recebe welcome message no WhatsApp real
- Mensagem diária do fluxo chega no WhatsApp via process_daily_flows
- Resposta livre do paciente é capturada pelo webhook e persistida em patient_flow_responses
- Transição automática de onboarding para daily_follow_up funciona no dia 16
- Success criteria verificados por exercício real contra o stack local

## Requirement Coverage

- Covers: R067, R068, R069, R070, R071, R072, R073, R074
- Partially covers: none
- Leaves for later: R064 (override por paciente — deferred), R075 (quiz mensal ponta-a-ponta), R076 (deploy)
- Orphan risks: none

## Slices

- [x] **S01: Stack local rodando** `risk:high` `depends:[]`
  > After this: backend responde health check, Celery worker conecta ao Dragonfly, Postgres tem schema atualizado via Alembic, .env configurado. Provado por curl ao health endpoint e logs do worker.

- [x] **S02: WuzAPI conectado e enviando** `risk:high` `depends:[S01]`
  > After this: WuzAPI rodando via Docker com número de teste conectado, e uma mensagem de teste enviada via API chega no WhatsApp real. Provado por mensagem recebida no telefone.

- [x] **S03: Templates clínicos semeados** `risk:medium` `depends:[S01]`
  > After this: flow_kinds `onboarding`, `daily_follow_up`, `quiz_mensal` existem no banco, templates de onboarding (15 dias) e daily follow-up (dia 16-45) têm conteúdo clínico real com send_mode e expects_response corretos. Provado por query SQL e EnhancedTemplateLoader.

- [x] **S04: Criação de paciente → welcome → ciclo diário** `risk:high` `depends:[S01,S02,S03]`
  > After this: médico cria paciente via API (ou dashboard), saga executa 4 steps, welcome message chega no WhatsApp real. Trigger de process_daily_flows envia mensagem do dia com conteúdo personalizado. Provado por mensagens recebidas no telefone.

- [x] **S05: Resposta do paciente e transição de fase** `risk:medium` `depends:[S04]`
  > After this: paciente responde no WhatsApp, webhook processa resposta, row existe em patient_flow_responses com day_number e message_index corretos. Transição onboarding → daily_follow_up funciona quando current_day atinge 16. Provado por query SQL e comportamento observado.

## Boundary Map

### S01 → S02

Produces:
- Backend rodando em `localhost:8000` com health check verde
- Dragonfly rodando em `localhost:6379`
- Postgres com schema atualizado (`alembic upgrade head`)
- `.env` configurado com DATABASE_URL, REDIS_URL, e variáveis base
- docker-compose funcional para serviços dependentes

Consumes:
- nothing (first slice)

### S01 → S03

Produces:
- Postgres com schema atualizado incluindo tabelas `flow_kinds`, `flow_template_versions`
- Alembic head aplicado incluindo migration `9b4e2d1c7f66` que sincroniza templates dos snapshots

Consumes:
- nothing (first slice)

### S01 → S04

Produces:
- Backend + Celery worker operacionais
- Postgres + Dragonfly disponíveis
- Env vars de IA (AI_GEMINI_API_KEY) e WhatsApp configurados

Consumes:
- nothing (first slice)

### S02 → S04

Produces:
- WuzAPI rodando e conectado com número real
- URL do WuzAPI configurada em WHATSAPP_WUZAPI_BASE_URL
- Token do WuzAPI configurado em WHATSAPP_WUZAPI_TOKEN
- Webhook URL do WuzAPI apontando pro backend para respostas
- Prova de envio: `WuzAPIClient.send_text()` entrega mensagem real

Consumes from S01:
- Backend rodando (para receber webhooks)
- Env vars configurados

### S03 → S04

Produces:
- `flow_kinds` com kind_key `onboarding`, `daily_follow_up`, `quiz_mensal` no banco
- `flow_template_versions` com steps JSONB contendo conteúdo clínico real, send_mode, expects_response
- `EnhancedTemplateLoader.get_message_for_day(flow_type, day)` retorna conteúdo para todos os dias

Consumes from S01:
- Postgres com schema atualizado

### S04 → S05

Produces:
- Paciente criado no banco com `flow_state=ACTIVE` e `PatientFlowState` inicializado
- Welcome message enviada e registrada na tabela `messages`
- `process_daily_flows` executado com sucesso para o paciente
- Mensagem do dia entregue no WhatsApp real
- `step_data` com `last_message_sent`, `current_flow_day`, metadados de envio

Consumes from S01:
- Stack operacional
Consumes from S02:
- WuzAPI real conectado
Consumes from S03:
- Templates com conteúdo real

### S05 (terminal)

Produces:
- Resposta do paciente persistida em `patient_flow_responses` com `flow_state_id`, `day_number`, `message_index`, `response_text`, `responded_at`
- Webhook de resposta processado corretamente pelo `MessageWebhookHandler`
- Transição de `FlowType.ONBOARDING` para `FlowType.DAILY_FOLLOW_UP` ocorre quando `current_day >= 16`
- `step_data.transitions` registra a transição com timestamp e dia

Consumes from S04:
- Paciente ativo com fluxo em andamento
- Mensagem enviada que gerou espera de resposta (`expects_response=True`)
