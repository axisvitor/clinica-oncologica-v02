# M009: Substituição do Celery por Taskiq

**Vision:** Eliminar a friction sync/async permanente do codebase migrando de Celery para Taskiq — async-native, FastAPI-integrated, Redis-backed — com paridade funcional total: todas as tasks, schedules, retries, e o pipeline M008 ponta-a-ponta funcionando sem nenhum código de bridging.

## Success Criteria

- Worker Taskiq processa tasks reais contra Dragonfly (6380) e responde a health checks
- `send_scheduled_message` envia mensagem real via Taskiq worker → WuzAPI → WhatsApp
- `process_daily_flows` executa via Taskiq e entrega mensagem personalizada ao paciente
- Todas as 40+ periodic tasks rodam no Taskiq scheduler com timing equivalente ao Celery beat
- Pipeline M008 completo funciona: create patient → welcome → daily flow → response → transition
- Celery, kombu, amqp, billiard, flower removidos de requirements.txt
- Bridge code removido: async_context_manager.py, run_async_in_celery(), ~900 linhas
- Backend + worker sobem sem Celery no import path

## Key Risks / Unknowns

- Dragonfly compatibility com Taskiq Redis broker — edge cases com Streams/PubSub
- self.retry() translation — 15+ files usam bound task retry com countdown, precisa mapeamento para SmartRetryMiddleware
- Beat schedule parity — 40+ entries com mix de crontab e interval
- apply_async(eta=datetime) — Taskiq não tem ETA nativo, precisa alternativa
- Worker lifecycle initialization — session managers, Redis connections, monitoring

## Proof Strategy

- Dragonfly compat → retirar em S01 provando que broker envia/recebe tasks via Dragonfly
- self.retry translation → retirar em S02 provando que send_scheduled_message retry funciona com SmartRetryMiddleware
- Beat schedule parity → retirar em S04 provando que todas as 40+ tasks estão no scheduler
- apply_async(eta=) → retirar em S02 provando alternativa para delayed task dispatch
- Pipeline e2e → retirar em S06 provando o pipeline M008 completo via Taskiq

## Verification Classes

- Contract verification: tasks executam e retornam resultado, scheduler dispara no timing correto, retry respeita backoff
- Integration verification: WuzAPI envia mensagem real via task Taskiq, flow engine processa via worker
- Operational verification: worker + scheduler sobem e se comunicam com Dragonfly, lifecycle hooks funcionam
- UAT / human verification: mensagem chega no WhatsApp real (verificação visual pelo usuário)

## Milestone Definition of Done

This milestone is complete only when all are true:

- Taskiq worker + scheduler rodam contra Dragonfly e processam todas as tasks
- Todas as 40+ periodic tasks estão no schedule com timing equivalente
- Pipeline M008 funciona end-to-end: create patient → welcome → daily flow → response → transition
- Celery + dependências transitivas removidos de requirements.txt
- Bridge code removido (~900 linhas)
- Backend + worker sobem sem Celery no import path
- Testes existentes passam (adaptados para Taskiq)
- Success criteria verificados por exercício real contra stack local

## Requirement Coverage

- Covers: R077, R078, R079, R080, R081, R082, R083, R084, R085, R086
- Partially covers: none
- Leaves for later: R064 (override por paciente — deferred), R087 (dashboard polish — M010)
- Orphan risks: none

## Slices

- [x] **S01: Taskiq broker + base task + FastAPI integration** `risk:high` `depends:[]`
  > After this: worker Taskiq processa task de teste via Dragonfly, SmartRetryMiddleware funciona, scheduler roda com LabelScheduleSource, FastAPI lifespan integra broker startup/shutdown, health check reporta worker status.

- [x] **S02: Messaging tasks migradas** `risk:high` `depends:[S01]`
  > After this: send_scheduled_message.kiq() envia mensagem real via WuzAPI, process_scheduled_messages roda no scheduler, retry_failed_messages funciona com SmartRetryMiddleware, DLQ processing migrado. Celery e Taskiq coexistem — apenas messaging usa Taskiq.

- [x] **S03: Flow/saga tasks migradas** `risk:high` `depends:[S01,S02]`
  > After this: process_daily_flows executa via Taskiq worker com async nativo (sem bridge), saga_retry funciona, stuck_detection roda periodicamente, flow_automation e monthly_tasks migrados.

- [x] **S04: Quiz/alert/follow-up/monitoring migradas + schedule completo** `risk:medium` `depends:[S01]`
  > After this: todas as tasks de quiz, alertas, follow-up, LGPD, audit, webhook DLQ, e monitoring migradas. Schedule completo com todas as 40+ entries no Taskiq scheduler com timing correto.

- [x] **S05: Celery removal + bridge cleanup** `risk:medium` `depends:[S02,S03,S04]`
  > After this: celery, kombu, amqp, billiard, flower removidos de requirements.txt. celery_app.py deletado. async_context_manager.py, run_async_in_celery(), e bridge code removidos (~900 linhas). Backend sobe sem nenhum import de celery.

- [ ] **S06: Verificação integrada ponta-a-ponta** `risk:low` `depends:[S05]`
  > After this: pipeline M008 completo verificado via Taskiq: create patient → welcome → daily flow → response → transition. Testes existentes passam. Stack local roda end-to-end sem Celery.

## Boundary Map

### S01 → S02

Produces:
- `app/taskiq_broker.py` — Taskiq broker instance (ListQueueBroker or RedisStreamBroker) configured with Dragonfly URL
- `SmartRetryMiddleware` configured com default retry, backoff, jitter
- `RedisAsyncResultBackend` para result storage
- `LabelScheduleSource` + `TaskiqScheduler` para periodic tasks
- FastAPI lifespan integration (broker startup/shutdown)
- Base task pattern: dependency injection para DB sessions via `TaskiqDepends`
- `taskiq-redis`, `taskiq`, `taskiq-fastapi` em requirements.txt
- Worker CLI command: `taskiq worker app.taskiq_broker:broker`
- Scheduler CLI command: `taskiq scheduler app.taskiq_broker:scheduler`

Consumes:
- nothing (first slice)

### S01 → S03

Produces:
- Same as S01 → S02

Consumes:
- nothing (first slice)

### S01 → S04

Produces:
- Same as S01 → S02

Consumes:
- nothing (first slice)

### S02 → S03

Produces:
- `send_scheduled_message` como Taskiq task com `.kiq()` dispatch
- Pattern estabelecido para tradução de `self.retry()` → SmartRetryMiddleware labels
- Pattern para `.apply_async(eta=datetime)` → delayed dispatch

Consumes from S01:
- Taskiq broker, retry middleware, scheduler, DB session dependency

### S02 → S05

Produces:
- Messaging tasks operando inteiramente via Taskiq (sem Celery)
- Call sites de messaging migrados para `.kiq()`

Consumes from S01:
- Broker + middleware + scheduler

### S03 → S05

Produces:
- Flow/saga tasks operando via Taskiq (sem Celery)
- process_daily_flows usando async nativo (sem hybrid bridge)

Consumes from S01:
- Broker + middleware + scheduler
Consumes from S02:
- send_scheduled_message como Taskiq task (flow tasks chamam messaging tasks)

### S04 → S05

Produces:
- Quiz/alert/follow-up/monitoring tasks operando via Taskiq
- Schedule completo com todas as 40+ entries

Consumes from S01:
- Broker + middleware + scheduler

### S05 → S06

Produces:
- Celery completamente removido (requirements, imports, celery_app.py)
- Bridge code removido (async_context_manager, run_async_in_celery)
- Backend sobe sem Celery

Consumes from S02:
- Messaging tasks operando via Taskiq
Consumes from S03:
- Flow/saga tasks operando via Taskiq
Consumes from S04:
- Quiz/alert/follow-up/monitoring tasks operando via Taskiq

### S06 (terminal)

Produces:
- Pipeline M008 verificado end-to-end via Taskiq
- Prova de paridade funcional completa

Consumes from S05:
- Stack limpo sem Celery, todas as tasks via Taskiq
