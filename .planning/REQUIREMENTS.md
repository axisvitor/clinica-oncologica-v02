# Requirements: Clinica Oncologica v1.8

**Defined:** 2026-03-05
**Core Value:** Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.

## v1 Requirements

### ADK Runtime

- [x] **ADK-09**: Operador pode aplicar limites de execucao ADK por invocacao (`max_llm_calls`, timeout e cancelamento) no endpoint `/api/v2/adk/run`.
- [x] **ADK-10**: Operador pode executar ciclo de vida de sessao ADK (create/resume/close) com crescimento de estado controlado.

### ADK Safety & Errors

- [ ] **ADK-11**: Operador pode bloquear chamadas de tool inseguras via validacao `before_tool_callback` antes de efeitos colaterais.
- [ ] **ADK-12**: Operador pode classificar falhas ADK em classes deterministicas (`timeout`, `policy_block`, `tool_error`, `upstream_error`).

### Observability

- [x] **OBS-02**: Operador pode monitorar latencia, throughput e taxa de erro ADK em producao por invocacao e agente.

### Quality Gates

- [x] **ADK-13**: Time pode bloquear deploy quando trajetorias smoke ADK de fluxos oncologicos criticos regressam no CI.

## Future Requirements (Deferred)

### Observability

- **OBS-01**: Definir replacement de observabilidade pos-OTel com padrao unico de instrumentacao
- **OBS-03**: Propagar correlation IDs obrigatorios (`request_id`, `celery_task_id`, `adk_invocation_id`, `adk_session_id`, `flow_id`) em toda cadeia API -> Celery -> ADK

### ADK Runtime/Contracts

- **ADK-14**: Mapear taxonomia de erro ADK para envelope HTTP padronizado no endpoint `/api/v2/adk/run`
- **ADK-15**: Definir politica retryable/non-retryable com idempotencia para chamadas ADK com side effects
- **ADK-ADV-01**: Habilitar session service persistente em banco para continuidade multi-step
- **ADK-ADV-02**: Expandir evaluation harness ADK com rubrica de seguranca/qualidade para go/no-go de release

## Out of Scope

| Feature | Reason |
|---------|--------|
| Biblioteca completa policy-as-code para tools | Diferenciador de fase posterior; primeiro estabilizar guardrail minimo `before_tool_callback` |
| Canary/shadow rollout com auto-rollback | Requer baseline de metricas e thresholds maduros; adiar para operacao avancada |
| Automacao de runbook por classe de erro | Depende da taxonomia + alertas consolidados em producao |
| ADK substituir agentes Pydantic AI tipados | Contrato tipado atual e obrigatorio para seguranca/estabilidade clinica |
| Persistencia de sessoes ADK como padrao default | Precisa de governanca de retencao/LGPD antes de ampliar escopo |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ADK-09 | Phase 44 / Phase 48 (gap closure) | Complete |
| ADK-10 | Phase 44 / Phase 48 (gap closure) | Complete |
| ADK-11 | Phase 45 / Phase 49 (gap closure) | Pending |
| ADK-12 | Phase 45 / Phase 49 (gap closure) | Pending |
| OBS-02 | Phase 46 | Complete |
| ADK-13 | Phase 47 | Complete |

**Coverage:**
- v1 requirements: 6 total
- Mapped to phases: 6
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-05*
*Last updated: 2026-03-06 — Phase 48 verification closeout completed; ADK-09/10 restored to Complete and Phase 49 remains pending*
