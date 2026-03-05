# Roadmap: Clinica Oncologica — Refinamento para Producao

## Milestones

- ✅ **v1.0 Foundations** — Phases 1-5 (shipped 2026-02-22)
- ✅ **v1.1 Architecture & Observability** — Phases 6-9 (shipped 2026-02-23)
- ✅ **v1.2 AI Framework Migration** — Phases 10-13 (shipped 2026-02-24)
- ✅ **v1.3 Flow Health & Cleanup** — Phases 14-19 (shipped 2026-02-26)
- ✅ **v1.4 AsyncSession & Test Stability** — Phases 20-28 (shipped 2026-02-28)
- ✅ **v1.5 Saga Orchestrator Deep Dive** — Phases 29-32 (shipped 2026-03-01)
- ✅ **v1.6 WuzAPI Migration** — Phases 33-39 (shipped 2026-03-03)
- ✅ **v1.7 Frontend Quality & ADK Integration** — Phases 40-43 (shipped 2026-03-05)
- 🚧 **v1.8 ADK Stability & Error Hardening** — Phases 44-47 (in progress)

## Phases

<details>
<summary>✅ v1.0-v1.7 (Phases 1-43) — SHIPPED</summary>

- [x] Phases 1-5 archived — `.planning/milestones/v1.0-ROADMAP.md`
- [x] Phases 6-9 archived — `.planning/milestones/v1.1-ROADMAP.md`
- [x] Phases 10-13 archived — `.planning/milestones/v1.2-ROADMAP.md`
- [x] Phases 14-19 archived — `.planning/milestones/v1.3-ROADMAP.md`
- [x] Phases 20-28 archived — `.planning/milestones/v1.4-ROADMAP.md`
- [x] Phases 29-32 archived — `.planning/milestones/v1.5-ROADMAP.md`
- [x] Phases 33-39 archived — `.planning/milestones/v1.6-ROADMAP.md`
- [x] Phases 40-43 archived — `.planning/milestones/v1.7-ROADMAP.md`

</details>

- [x] **Phase 44: ADK Runtime Controls** - Limites por invocacao e ciclo de vida de sessao ADK no endpoint canonico. (completed 2026-03-05)
- [ ] **Phase 45: ADK Tool Safety and Deterministic Errors** - Guardrails de tool e classificacao deterministica de falhas ADK. (verification gaps found 2026-03-05)
- [ ] **Phase 46: ADK Observability Baseline** - Metricas operacionais de latencia, throughput e erro por invocacao/agente.
- [ ] **Phase 47: ADK CI Smoke Gate** - Gate de CI que bloqueia deploy com regressao em trajetorias oncologicas criticas.

## Phase Details

### Phase 44: ADK Runtime Controls
**Goal**: Operadores conseguem controlar a execucao ADK por invocacao com limites previsiveis e sessao sob controle.
**Depends on**: Phase 43
**Requirements**: ADK-09, ADK-10
**Success Criteria** (what must be TRUE):
  1. Operador define `max_llm_calls` no `/api/v2/adk/run` e a invocacao encerra ao atingir o limite sem travar a API.
  2. Operador define timeout por invocacao e recebe falha classificada de timeout quando o limite e excedido.
  3. Operador cancela uma invocacao em andamento e confirma que o fluxo ADK para sem continuar processamento.
  4. Operador executa create/resume/close de sessao ADK e observa crescimento de estado dentro do limite configurado.
**Plans**: 3 plans

Plans:

- [x] 44-01: Extend the canonical ADK route contract and add application-owned session/invocation metadata storage
- [x] 44-02: Enforce timeout, LLM budget, and explicit cancellation at the runtime boundary
- [x] 44-03: Finalize bounded session-state behavior and lock regression coverage

### Phase 45: ADK Tool Safety and Deterministic Errors
**Goal**: Falhas e bloqueios ADK tornam-se seguros e deterministicos antes de qualquer efeito colateral de tool.
**Depends on**: Phase 44
**Requirements**: ADK-11, ADK-12
**Success Criteria** (what must be TRUE):
  1. Chamada de tool insegura e bloqueada por `before_tool_callback` antes da execucao da tool.
  2. Falhas ADK retornam exatamente uma classe deterministica entre `timeout`, `policy_block`, `tool_error` e `upstream_error`.
  3. O mesmo tipo de falha gera a mesma classe em repeticoes do mesmo cenario, sem cair em erro generico ambiguo.
**Plans**: 3 plans

Plans:

- [x] 45-01: Add the pre-tool safety guardrail and lock `policy_block` route/runtime regressions
- [x] 45-02: Replace ambiguous runtime fallback with deterministic `tool_error` / `upstream_error` classification
- [x] 45-03: Finalize repeated-scenario regressions and sync the Phase 45 validation map

### Phase 46: ADK Observability Baseline
**Goal**: Operacao consegue monitorar saude ADK em producao por invocacao e por agente sem depender de debug manual.
**Depends on**: Phase 45
**Requirements**: OBS-02
**Success Criteria** (what must be TRUE):
  1. Operador visualiza latencia de invocacao ADK para o endpoint `/api/v2/adk/run`.
  2. Operador visualiza throughput e taxa de erro ADK por agente em producao.
  3. Operador identifica aumento de falhas ADK via metricas sem precisar inspecionar logs brutos request a request.
**Plans**: TBD

### Phase 47: ADK CI Smoke Gate
**Goal**: Release so avanca quando trajetorias ADK criticas do dominio oncologico continuam estaveis no CI.
**Depends on**: Phase 46
**Requirements**: ADK-13
**Success Criteria** (what must be TRUE):
  1. Time executa smoke ADK de trajetorias oncologicas criticas no CI e recebe resultado pass/fail por cenario.
  2. Pipeline bloqueia deploy automaticamente quando qualquer cenario critico de smoke regressa.
  3. Pipeline segue para deploy quando todos os cenarios criticos passam sem necessidade de bypass manual.
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 44. ADK Runtime Controls | 3/3 | Complete    | 2026-03-05 |
| 45. ADK Tool Safety and Deterministic Errors | 3/3 | Gaps Found | - |
| 46. ADK Observability Baseline | 0/TBD | Not started | - |
| 47. ADK CI Smoke Gate | 0/TBD | Not started | - |

---

_Roadmap created: 2026-02-22_
_Last updated: 2026-03-05 — Phase 45 execution complete but verification found a runner-path policy gap; gap closure planning required_
