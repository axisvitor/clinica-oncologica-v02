# M009: Substituição do Celery por Taskiq

**Gathered:** 2026-03-16
**Status:** Ready for planning

## Project Description

Migração do task queue do sistema oncológico de Celery para Taskiq. O Celery atualmente é o motor de todas as operações assíncronas críticas — envio de mensagens WhatsApp, processamento diário de fluxos, retry de falhas, sagas de onboarding, quiz sessions, alertas, follow-up, e 40+ tasks periódicas. O problema fundamental é que Celery é sync-first num codebase que é heavily async (FastAPI, AsyncSession, async SQLAlchemy), resultando em ~900 linhas de código de bridging (async_context_manager.py, async_helpers.py, run_async_in_celery(), hybrid _resolve/_execute helpers) que existem exclusivamente para contornar essa incompatibilidade.

Taskiq é async-native, tem integração first-class com FastAPI (TaskiqDepends compartilha dependency injection), usa Redis como broker (compatível com Dragonfly), tem SmartRetryMiddleware com exponential backoff + jitter, e LabelScheduleSource para scheduling periódico — cobrindo todas as capabilities de Celery usadas neste projeto sem a mismatch sync/async.

## Why This Milestone

M001–M008 construíram e provaram o pipeline oncológico ponta-a-ponta. Mas o Celery é a fonte de friction mais persistente no codebase: cada nova feature async que precisa rodar numa task requer bridging explícito. O M008 expôs isso severamente — a saga de onboarding, process_daily_flows, e o webhook handler todos precisaram de hybrid helpers para funcionar com sync Session no Celery worker. Migrar para Taskiq elimina essa friction permanentemente e simplifica todo o stack de tasks.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Subir o stack local e ver o worker Taskiq processando tasks contra Dragonfly
- Criar paciente → welcome message chega via Taskiq worker (não Celery)
- Executar process_daily_flows via Taskiq scheduler e ver mensagem chegar no WhatsApp
- Ver todas as 40+ tasks periódicas executando no schedule correto
- Verificar que Celery não existe mais no requirements.txt nem no runtime

### Entry point / environment

- Entry point: `taskiq worker` CLI + FastAPI lifespan + `taskiq scheduler` CLI
- Environment: local dev — Docker + PostgreSQL + Dragonfly + WuzAPI
- Live dependencies involved: Dragonfly (Redis-compatible broker), PostgreSQL, WuzAPI, Gemini AI

## Completion Class

- Contract complete means: tasks executam via Taskiq worker, retry funciona, schedule roda
- Integration complete means: pipeline M008 funciona end-to-end com Taskiq
- Operational complete means: worker + scheduler sobem, processam, e se recuperam de falhas

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- Worker Taskiq processa tasks reais (send_scheduled_message, process_daily_flows) contra Dragonfly
- Pipeline M008 funciona: create patient → welcome → daily flow → response → transition
- 40+ periodic tasks rodam no scheduler com timing equivalente ao Celery beat
- Celery + dependências transitivas (kombu, amqp, billiard, flower) removidos
- Bridge code removido (~900 linhas de async_context_manager, run_async_in_celery, etc.)
- Backend sobe sem nenhum import de celery no path

## Risks and Unknowns

- **Dragonfly compatibility** — Taskiq usa redis-py async. Dragonfly é drop-in Redis mas pode ter edge cases com Redis Streams ou PubSub. Precisa provar na S01.
- **self.retry() translation** — 15+ task files usam Celery bound task com self.retry(exc=e, countdown=...). Taskiq usa SmartRetryMiddleware com labels. A tradução precisa preservar o behavior exato (countdown, backoff, max_retries).
- **Beat schedule parity** — 40+ entries com mix de crontab e interval. LabelScheduleSource precisa cobrir todos os patterns.
- **Worker lifecycle** — Celery signals (worker_process_init, worker_process_shutdown) inicializam asyncio loops, session managers, Redis connections. Taskiq tem broker startup/shutdown hooks — precisa cobrir o mesmo setup.
- **Test adaptation** — Tasks que mockam Celery precisam ser adaptadas para Taskiq InMemoryBroker.
- **apply_async com ETA** — Alguns call sites usam `.apply_async(args=[...], eta=datetime)`. Taskiq precisa de um schedule source para delayed tasks.

## Existing Codebase / Prior Art

- `backend-hormonia/app/celery_app.py` — 477 linhas: Celery instance, beat_schedule (40+ entries), worker init/shutdown signals, run_async_in_celery helper
- `backend-hormonia/app/tasks/` — 35 task files, ~12,600 linhas total
- `backend-hormonia/app/tasks/base.py` — BaseTask com retry config, logging, DB session management
- `backend-hormonia/app/tasks/config.py` — TaskConfig dataclasses por domínio
- `backend-hormonia/app/task_queue.py` — Task queue abstraction layer (imports all task modules)
- `backend-hormonia/app/core/async_context_manager.py` — 457 linhas de bridging async
- `backend-hormonia/app/utils/async_helpers.py` — 430 linhas de helpers async
- `backend-hormonia/app/services/flow/core/operations.py` — Hybrid _resolve/_execute/_commit helpers (M008)

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions.

## Relevant Requirements

- R077 — Taskiq broker + scheduler substituem Celery
- R078 — Base task abstraction Taskiq-native
- R079 — Messaging tasks migradas
- R080 — Flow/saga tasks migradas
- R081 — Quiz/alert/follow-up/monitoring tasks migradas
- R082 — Schedule periódico com paridade total
- R083 — Call sites migrados
- R084 — Bridge code removido
- R085 — Celery + deps transitivas removidos
- R086 — Pipeline M008 ponta-a-ponta funciona

## Scope

### In Scope

- Setup do Taskiq broker + scheduler + FastAPI integration
- Base task abstraction com retry, logging, DB session via dependency injection
- Migração incremental de todas as task files (messaging → flow → quiz/alert/follow-up/monitoring)
- Migração de todos os call sites (.delay/.apply_async → .kiq)
- Migração do beat schedule completo para label-based scheduling
- Remoção do Celery e dependências transitivas
- Remoção do bridge code sync/async
- Verificação do pipeline M008 end-to-end

### Out of Scope / Non-Goals

- Dashboard polish (M010)
- Novas tasks ou capabilities — migração preserva paridade funcional exata
- Mudança de broker (Dragonfly fica)
- Otimização de performance das tasks (migração, não refactor)

## Technical Constraints

- Dragonfly em porta 6380 (não 6379) — configurado desde M008/S01
- Tasks usam mix de sync Session (get_scoped_session) e AsyncSession — Taskiq sendo async-native permite consolidar em AsyncSession
- `self.retry()` pattern com countdown/backoff aparece em 15+ files — precisa de tradução cuidadosa para SmartRetryMiddleware
- `.apply_async(eta=datetime)` aparece em call sites de scheduling — Taskiq precisa de delayed task support
- Worker init precisa: asyncio event loop, session manager, Redis connections, monitoring (mesmas que Celery signals fazem)
- Nenhum uso de Celery canvas primitives (chain/group/chord) — simplifica migração
- Nenhum uso de AsyncResult polling — simplifica migração

## Integration Points

- **Dragonfly** — broker para Taskiq (mesmo que Celery usava)
- **PostgreSQL** — DB sessions nas tasks (via dependency injection com TaskiqDepends)
- **WuzAPI** — envio de mensagens WhatsApp a partir de tasks
- **Gemini AI** — personalização de mensagens em flow tasks
- **FastAPI** — lifespan integration para broker startup/shutdown

## Open Questions

- **Broker type**: ListQueueBroker (simples, sem acknowledge) vs RedisStreamBroker (com acknowledge, mais robusto). Inclinar para ListQueueBroker pela simplicidade dado que tasks já têm retry próprio — validar em S01.
- **Delayed tasks (ETA)**: Taskiq não tem ETA nativo como Celery. Opções: (1) usar ScheduleSource para tasks com delay, (2) usar Redis TTL-based approach, (3) aceitar que tasks com ETA podem usar um schedule dinâmico. Resolver em S01.
