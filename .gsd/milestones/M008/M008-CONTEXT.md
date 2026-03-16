# M008: Onboarding Real de Pacientes — Ponta a Ponta

**Gathered:** 2026-03-16
**Status:** Ready for planning

## Project Description

Prova ponta-a-ponta do fluxo completo de acompanhamento oncológico: desde subir o stack local até o paciente receber mensagens reais no WhatsApp e responder livremente. O sistema tem toda a mecânica construída (M001–M007), mas nunca foi exercitado contra o stack real rodando localmente com WuzAPI real.

## Why This Milestone

M001–M007 construíram pipeline resiliente, auth canônica, cleanup estrutural, editor de templates, personalização IA, armazenamento de respostas e resumo mensal. Tudo provado por testes unitários e de integração. Mas o caminho completo "médico cria paciente → paciente recebe mensagem no WhatsApp → responde → fluxo avança" nunca foi exercitado contra serviços reais. Sem essa prova, o sistema é um protótipo sofisticado — não uma ferramenta clínica funcional.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Subir o stack local com um comando (Postgres + Dragonfly + backend + Celery + WuzAPI)
- Criar um paciente no dashboard e ver a welcome message chegar no WhatsApp real
- Executar process_daily_flows e ver a mensagem do dia chegar no WhatsApp
- Responder livremente no WhatsApp e ver a resposta persistida no sistema
- Verificar que o fluxo transiciona de onboarding para daily follow-up no dia 16

### Entry point / environment

- Entry point: dashboard web (médico) + WhatsApp (paciente) + API backend + Celery worker
- Environment: local dev — Docker + PostgreSQL + Dragonfly + WuzAPI
- Live dependencies involved: WuzAPI (WhatsApp real), PostgreSQL, Dragonfly, Gemini AI (chave disponível)

## Completion Class

- Contract complete means: stack sobe, migrations rodam, templates existem, health checks verdes
- Integration complete means: welcome message chega no WhatsApp real, resposta do paciente volta via webhook
- Operational complete means: ciclo diário funciona via trigger de process_daily_flows, transição de fase ocorre

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- Médico cria paciente no dashboard → welcome message chega no WhatsApp real do número de teste
- Trigger de process_daily_flows → mensagem do dia com conteúdo do template chega no WhatsApp
- Paciente responde livremente no WhatsApp → resposta aparece em patient_flow_responses com contexto de fluxo
- Transição onboarding (dia ≤15) → daily_follow_up (dia 16) funciona sem intervenção manual

## Risks and Unknowns

- **Setup do WuzAPI com QR code** — processo manual que depende do número conectar. Se o número não parear, o milestone trava.
- **Webhook routing** — WuzAPI precisa enviar webhooks de volta pro backend. Em ambiente local, isso requer que WuzAPI e backend se alcancem na rede (docker network ou localhost).
- **kind_key mismatch** — seed migration usa `initial_15_days`, migration posterior normaliza pra `onboarding`. Se o Alembic head não estiver atualizado, o template loader não encontra templates.
- **Celery beat schedule** — `process_daily_flows` precisa de schedule configurado ou trigger manual. Se o beat não estiver rodando, mensagens diárias não saem automaticamente.
- **Env vars inconsistentes** — 292 variáveis no .env.example. Configuração errada de qualquer uma pode bloquear silenciosamente.

## Existing Codebase / Prior Art

- `backend-hormonia/docker-compose.yml` — Dragonfly + API + Worker (sem WuzAPI)
- `backend-hormonia/app/orchestration/saga_orchestrator/` — Saga de criação de paciente (4 steps: create → flow → welcome → commit)
- `backend-hormonia/app/tasks/flows/batch_tasks.py` — `process_daily_flows` e `_process_single_patient_flow`
- `backend-hormonia/app/services/flow/core/transitions.py` — `determine_flow_type()`: dia ≤15 → ONBOARDING, dia 16-45 → DAILY_FOLLOW_UP
- `backend-hormonia/app/integrations/wuzapi/client.py` — `WuzAPIClient` com `send_text()`, `send_media()`
- `backend-hormonia/app/integrations/wuzapi/mock.py` — `MockWuzAPIClient` para testes sem WuzAPI real
- `backend-hormonia/app/services/webhook/handlers/message_handler.py` — `MessageWebhookHandler.process_message()` para respostas do paciente
- `backend-hormonia/alembic/versions/9b4e2d1c7f66_sync_canonical_flow_templates_from_snapshots.py` — Migration que lê snapshots markdown e popula templates com conteúdo clínico real
- `backend-hormonia/app/templates/arquivo/db_snapshot/FLUXO HORMON[IA] - 1 A 15 [DB].md` — 15 dias de conteúdo de onboarding (mensagens multi-step com send_mode e expects_response)
- `backend-hormonia/app/templates/arquivo/db_snapshot/Fluxo HORMON[IA] - 16 A 45 [DB].md` — Conteúdo daily follow-up dias 16-45
- `backend-hormonia/app/services/patient/flow_service.py` — `PatientFlowService.initialize_default_flow()` e `activate_patient()`
- `frontend-hormonia/src/features/patients/dialogs/` — `CreatePatientDialog`, `PatientForm`, `usePatientForm` — UI de criação de paciente existente

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions.

## Relevant Requirements

- R067 — Stack local roda ponta-a-ponta
- R068 — WuzAPI conectado e enviando mensagens reais
- R069 — Templates de onboarding (15 dias) com conteúdo clínico real
- R070 — Criação de paciente → welcome message no WhatsApp
- R071 — Ciclo diário de onboarding funciona ponta-a-ponta
- R072 — Resposta do paciente chega e persiste via webhook
- R073 — Transição automática onboarding → daily follow-up verificada
- R074 — Templates de daily follow-up (dia 16-45) com conteúdo

## Scope

### In Scope

- Setup e documentação do stack local (Postgres + Dragonfly + backend + Celery + WuzAPI)
- Conexão do WuzAPI com número de teste real
- Verificação e seeding de templates de onboarding e daily follow-up
- Prova de criação de paciente → welcome message real
- Prova de ciclo diário via process_daily_flows
- Prova de webhook de resposta do paciente
- Prova de transição de fase onboarding → daily follow-up
- Fix de bugs encontrados no caminho

### Out of Scope / Non-Goals

- Quiz mensal ponta-a-ponta (R075) — ciclo de 30+ dias impraticável neste milestone
- Deploy em produção/staging (R076) — milestone separado
- Override de template por paciente (R064) — deferred
- Polimento do dashboard do médico — M009
- Personalização profunda do conteúdo IA — calibração já provada em M007/S04

## Technical Constraints

- WuzAPI roda via Docker e precisa de número WhatsApp conectado via QR code (processo manual do usuário)
- Backend usa psycopg (não psycopg2) — DATABASE_URL precisa de `postgresql+psycopg://`
- Dragonfly é drop-in Redis — usa mesma biblioteca `redis` do Python
- Templates vivem no banco via `FlowTemplateVersion` — migration `9b4e2d1c7f66` lê snapshots markdown e popula
- `determine_flow_type()` usa regra fixa: dia ≤15 → ONBOARDING, dia 16-45 → DAILY_FOLLOW_UP, dia >45 → QUIZ_MENSAL
- Flow kinds no banco precisam ter `kind_key` = `onboarding`, `daily_follow_up`, `quiz_mensal` (não `initial_15_days`)

## Integration Points

- **WuzAPI** — envio de mensagens (send_text/send_media) e recebimento de webhooks (respostas do paciente)
- **PostgreSQL** — todas as tabelas do sistema (patients, patient_flow_states, flow_kinds, flow_template_versions, patient_flow_responses, messages, notifications)
- **Dragonfly** — cache de sessão, rate limiting, estado de follow-up, template cache
- **Celery** — `process_daily_flows` task, `send_scheduled_message` task, welcome message via saga
- **Gemini AI** — personalização de mensagens (API key disponível)

## Open Questions

- Qual porta o WuzAPI vai usar localmente vs. backend (ambos default 8080) — resolver no setup
- Se Celery beat precisa de schedule explícito ou se process_daily_flows é chamado manualmente durante prova — resolver em S04
