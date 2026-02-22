# Roadmap: Clínica Oncológica — Refinamento para Produção

## Overview

Este roadmap leva o protótipo funcional a produção com pacientes oncológicos reais. O trabalho está organizado em 9 fases que seguem a cadeia de dependências do sistema: primeiro eliminar bloqueadores de segurança e compliance (fases 1-4), depois consolidar a arquitetura (fases 5-7), e finalmente racionalizar a camada de IA e implementar observabilidade real (fases 8-9). Cada fase entrega uma capacidade verificável e completa — nunca metade de uma funcionalidade.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Security Hardening** - Eliminar exposições de segurança que bloqueiam go-live com pacientes reais
- [ ] **Phase 2: LGPD Compliance** - Fechar gaps de auditoria e opt-out que criam risco regulatório ativo
- [ ] **Phase 3: Operational Stability** - Corrigir bugs que causam memory leaks, race conditions e CVEs ativos
- [ ] **Phase 4: AI Reliability** - Garantir que falhas de LangGraph/Gemini sejam visíveis e explícitas
- [ ] **Phase 5: Flow Consolidation** - Eliminar o dual flow system que causa divergência silenciosa de estado de pacientes
- [ ] **Phase 6: Async Hot Path Migration** - Migrar os três hot paths de banco de dados para AsyncSession
- [ ] **Phase 7: LGPD Key Rotation** - Implementar batch re-encryption para viabilizar rotação de chaves criptográficas
- [ ] **Phase 8: AI Rationalization** - Simplificar cinco grafos single-node e adicionar circuit breaker para Gemini
- [ ] **Phase 9: Observability** - Substituir métricas hardcoded por instrumentação real e corrigir WebSocket scaling

## Phase Details

### Phase 1: Security Hardening
**Goal**: O sistema não expõe dados de pacientes nem permite acesso não autorizado a endpoints de monitoramento
**Depends on**: Nothing (first phase)
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04
**Success Criteria** (what must be TRUE):
  1. Endpoints de monitoramento retornam 401 quando chamados sem token válido de usuário autenticado com role adequada
  2. O binário de produção não contém TEST_TOKEN_REGISTRY — `grep -r "TEST_TOKEN_REGISTRY" app/` retorna zero resultados fora de conftest
  3. A service account key do Firebase não existe como arquivo no working directory — está em env var ou Secret Manager
  4. Um deploy com `APP_ENABLE_DEBUG=True` falha na validação de configuração antes de aceitar tráfego
**Plans**: 3 plans (Wave 1 — all parallel)

Plans:
- [x] 01-01-PLAN.md — Replace placeholder monitoring auth with canonical get_admin_user + role check (SEC-01)
- [ ] 01-02-PLAN.md — Remove TEST_TOKEN_REGISTRY from production code + add Firebase key file startup guardrail (SEC-02, SEC-03)
- [ ] 01-03-PLAN.md — Add pydantic model_validator to block APP_ENABLE_DEBUG=True in production/staging (SEC-04)

### Phase 2: LGPD Compliance
**Goal**: O sistema possui trilha de auditoria persistente e imutável de deleções, responde ao opt-out imediatamente, e registra eventos de IA no audit log
**Depends on**: Phase 1
**Requirements**: LGPD-01, LGPD-02, LGPD-03
**Success Criteria** (what must be TRUE):
  1. Quando um paciente é deletado, um registro persiste na tabela `patient_deletion_audit` no PostgreSQL com timestamp, motivo e executor — o registro não desaparece com rotação de logs da Railway
  2. Quando um paciente envia "STOP" ou "PARAR" via WhatsApp, o sistema para o envio de mensagens imediatamente e registra a revogação de consentimento antes de qualquer mensagem subsequente ser enviada
  3. Eventos de IA (`AI_QUERY`, `AI_HUMANIZATION`, `AI_SENTIMENT`, `AI_FOLLOW_UP`) aparecem no `AuditEventType` enum e a migration Alembic foi aplicada no banco — o audit log registra chamadas Gemini
**Plans**: TBD

Plans:
- [ ] 02-01: Criar tabela patient_deletion_audit via Alembic migration + registrar evento antes da deleção (LGPD-01)
- [ ] 02-02: Implementar handler de opt-out WhatsApp (STOP/PARAR/CANCELAR) com revogação de consentimento (LGPD-02)
- [ ] 02-03: Adicionar AI event types ao AuditEventType enum + migration Alembic (LGPD-03)

### Phase 3: Operational Stability
**Goal**: O sistema não vaza event loops, o rate limiter é atômico, e python-jose está completamente removido do codebase
**Depends on**: Phase 1
**Requirements**: REL-01, REL-02, REL-03, ASYNC-04
**Success Criteria** (what must be TRUE):
  1. `grep -r "asyncio.run(" app/tasks/` retorna zero resultados — todas Celery tasks usam `async_to_sync`
  2. O rate limiter executa o Lua script atomicamente: dois requests simultâneos para o mesmo endpoint nunca ultrapassam o limite configurado sob carga paralela
  3. `grep -r "from jose" app/` retorna zero resultados — python-jose não está importado em nenhum módulo da aplicação
  4. `pip show python-jose` não retorna resultado no ambiente de produção — o pacote está removido das dependências
**Plans**: TBD

Plans:
- [ ] 03-01: Substituir asyncio.run() por async_to_sync em todas Celery tasks (ASYNC-04)
- [ ] 03-02: Implementar rate limiter atômico via Lua script Redis em rate_limit_core.py (REL-01)
- [ ] 03-03: Sweep e remoção de imports from jose + confirmar remoção do pacote (REL-02, REL-03)

### Phase 4: AI Reliability
**Goal**: Falhas de LangGraph e Gemini são visíveis, explícitas e capturadas pelo Sentry — nenhuma falha silenciosa entrega mensagens robóticas a pacientes
**Depends on**: Phase 1, Phase 3
**Requirements**: AI-01, AI-02
**Success Criteria** (what must be TRUE):
  1. Se LangGraph não está disponível na inicialização da aplicação, a aplicação falha com erro claro no startup em vez de aceitar tráfego e produzir mensagens sem humanização
  2. Quando uma chamada LangGraph retorna `None`, o sistema levanta `FeatureNotAvailableError` explícito que é capturado pelo Sentry — não há silent degradation entregando templates não humanizados
**Plans**: TBD

Plans:
- [ ] 04-01: Adicionar LangGraph startup health check no lifespan.py (AI-01)
- [ ] 04-02: Converter fallbacks None de LangGraph para FeatureNotAvailableError explícito (AI-02)

### Phase 5: Flow Consolidation
**Goal**: Existe exatamente um sistema canônico de flow state para pacientes — o dual flow system está eliminado e os dois sistemas não podem divergir
**Depends on**: Phase 3, Phase 4
**Requirements**: FLOW-01, FLOW-02, FLOW-03
**Success Criteria** (what must be TRUE):
  1. Um `FlowDispatcher` facade existe e roteia chamadas de flow baseado em feature flag — nenhum código chama `flow_core.py` ou `services/flow/core/manager.py` diretamente
  2. Novos pacientes são roteados exclusivamente para o sistema canônico escolhido via feature flag — a escolha está documentada e justificada
  3. Testes de integração cobrem o flow system unificado end-to-end: onboarding → avanço de flow → alert pipeline — os testes passam no CI
**Plans**: TBD

Plans:
- [ ] 05-01: Escolher sistema canônico + implementar FlowDispatcher facade com feature-flag routing (FLOW-01, FLOW-02)
- [ ] 05-02: Escrever testes de integração do flow unificado + alert pipeline end-to-end (FLOW-03)

### Phase 6: Async Hot Path Migration
**Goal**: Os três hot paths de banco de dados de maior throughput usam AsyncSession — o webhook handler, quiz response processing e flow advancement não bloqueiam o event loop
**Depends on**: Phase 5
**Requirements**: ASYNC-01, ASYNC-02, ASYNC-03, ASYNC-05
**Success Criteria** (what must be TRUE):
  1. `sequential_message_handler.py` usa AsyncSession em todas as 12 instâncias anotadas com `TODO(async-migration)` — nenhum `Session` síncrono dentro de handlers async
  2. `flow_core.py` usa AsyncSession nas 7 instâncias anotadas — avanço de flow não bloqueia o event loop sob carga
  3. `enhanced_quiz_service.py` usa AsyncSession nas 8 instâncias anotadas — processamento de respostas de quiz não bloqueia o event loop
  4. O saga orchestrator (compensation + steps) usa AsyncSession — operações de compensação de saga não criam risco de corrupção de dados por timeout
**Plans**: TBD

Plans:
- [ ] 06-01: Migrar sequential_message_handler.py para AsyncSession (12 instâncias) (ASYNC-01)
- [ ] 06-02: Migrar flow_core.py para AsyncSession (7 instâncias) (ASYNC-02)
- [ ] 06-03: Migrar enhanced_quiz_service.py para AsyncSession (8 instâncias) (ASYNC-03)
- [ ] 06-04: Migrar saga orchestrator (compensation + steps) para AsyncSession (ASYNC-05)

### Phase 7: LGPD Key Rotation
**Goal**: É possível realizar rotação de chaves criptográficas via Celery task sem perda de dados — batch re-encryption existe e é operacional
**Depends on**: Phase 5, Phase 6
**Requirements**: LGPD-04
**Success Criteria** (what must be TRUE):
  1. Uma Celery task de batch re-encryption existe e pode ser invocada com nova chave — ela processa registros em chunks sem timeout ou perda de dados
  2. A task pode ser interrompida e retomada sem corromper dados parcialmente re-encriptados — idempotência verificada por teste
**Plans**: TBD

Plans:
- [ ] 07-01: Implementar Celery task de batch re-encryption com chunked processing e idempotência (LGPD-04)

### Phase 8: AI Rationalization
**Goal**: Cinco grafos LangGraph single-node estão eliminados — o código AI é mais simples, e chamadas Gemini têm circuit breaker explícito
**Depends on**: Phase 4, Phase 5
**Requirements**: AI-03, AI-04
**Success Criteria** (what must be TRUE):
  1. Os grafos `humanization`, `sentiment`, `generation`, `question_variation` e `empathetic_follow_up` não existem mais como StateGraph compilados — as chamadas Gemini correspondentes passam diretamente por `GeminiClient.generate_content()`
  2. Um circuit breaker envolve chamadas Gemini — quando Gemini retorna 5xx ou timeout repetidamente, o circuit breaker abre e `FeatureNotAvailableError` é levantado em vez de retry infinito
**Plans**: TBD

Plans:
- [ ] 08-01: Substituir os 5 grafos single-node por chamadas diretas GeminiClient.generate_content() (AI-03)
- [ ] 08-02: Adicionar circuit breaker ao redor de chamadas Gemini usando CircuitBreaker existente (AI-04)

### Phase 9: Observability
**Goal**: Métricas refletem o comportamento real do sistema, o endpoint de disponibilidade do médico retorna slots reais, e o WebSocket funciona em múltiplas instâncias
**Depends on**: Phase 5, Phase 6
**Requirements**: OBS-01, OBS-02, OBS-03
**Success Criteria** (what must be TRUE):
  1. `avg_task_duration_seconds` não está hardcoded como 2.5 — o valor reflete a média real das últimas N execuções de tasks, calculada via rolling average no Redis
  2. `get_available_slots()` retorna slots reais baseados nos horários configurados do médico — o endpoint não retorna lista vazia silenciosamente
  3. O WebSocket dashboard funciona corretamente com duas instâncias da aplicação rodando simultaneamente — eventos de uma instância aparecem nos dashboards conectados à outra instância via Redis pub/sub
**Plans**: TBD

Plans:
- [ ] 09-01: Instrumentar Celery task completion times com rolling average em Redis (OBS-01)
- [ ] 09-02: Implementar get_available_slots() com lógica real de geração de slots (OBS-02)
- [ ] 09-03: Verificar e corrigir WebSocket scaling com Redis pub/sub para multi-instance (OBS-03)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9

Note: Phases 2 and 3 both depend only on Phase 1 and can be worked in parallel if desired.
Phase 8 can begin after Phase 4 + Phase 5 complete, independently of Phase 6-7.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Security Hardening | 2/3 | In Progress|  |
| 2. LGPD Compliance | 0/3 | Not started | - |
| 3. Operational Stability | 0/3 | Not started | - |
| 4. AI Reliability | 0/2 | Not started | - |
| 5. Flow Consolidation | 0/2 | Not started | - |
| 6. Async Hot Path Migration | 0/4 | Not started | - |
| 7. LGPD Key Rotation | 0/1 | Not started | - |
| 8. AI Rationalization | 0/2 | Not started | - |
| 9. Observability | 0/3 | Not started | - |

---
*Roadmap created: 2026-02-22*
*Last updated: 2026-02-22 after Phase 1 planning (3 plans created)*
