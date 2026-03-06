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
- **v1.8 ADK Stability & Error Hardening** — Phases 44-49 (gap closure in progress)

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
- [x] **Phase 45: ADK Tool Safety and Deterministic Errors** - Guardrails de tool e classificacao deterministica de falhas ADK. (gap closure in progress) (completed 2026-03-06)
- [x] **Phase 46: ADK Observability Baseline** - Metricas operacionais de latencia, throughput e erro por invocacao/agente. (completed 2026-03-06)
- [x] **Phase 47: ADK CI Smoke Gate** - Gate de CI que bloqueia deploy com regressao em trajetorias oncologicas criticas. (completed 2026-03-06)
- [x] **Phase 48: Phase 44 Verification Closeout** - Fechar cadeia de verificacao orfanada de ADK-09 e ADK-10 com artefato 44-VERIFICATION.md. (gap closure) (completed 2026-03-06)
- [ ] **Phase 49: ADK Real Runner & Staging Validation** - Validacao humana em ambiente staging do runner google-adk para ADK-11, ADK-12 e cancel multi-instancia ADK-09. (gap closure)

## Gap Closure Phases

### Phase 48: Phase 44 Verification Closeout
**Goal**: Fechar a cadeia de verificacao orfanada de ADK-09 e ADK-10 criando 44-VERIFICATION.md com evidencia cruzada de sumarios, codigo e testes.
**Depends on**: Phase 44
**Requirements**: ADK-09, ADK-10
**Gap Closure**: Closes orphaned requirements from v1.8 audit
**Success Criteria** (what must be TRUE):
  1. Full Phase 44 test suite runs green and evidence is captured.
  2. `44-VERIFICATION.md` exists with cross-referenced evidence from summaries, code, and tests.
  3. REQUIREMENTS.md marks ADK-09 and ADK-10 as Complete with checked boxes.
**Plans**: 1 plan

Plans:

- [ ] 48-01-PLAN.md — Run Phase 44 test suite, write 44-VERIFICATION.md with cross-referenced evidence, and update REQUIREMENTS.md

### Phase 49: ADK Real Runner & Staging Validation
**Goal**: Validar comportamento de seguranca e erro ADK em ambiente staging com google-adk real instalado.
**Depends on**: Phase 45, Phase 48
**Requirements**: ADK-11, ADK-12
**Gap Closure**: Closes human_needed verification and staging flow gaps from v1.8 audit
**Success Criteria** (what must be TRUE):
  1. Real google-adk runner blocks unsafe tool call and returns `policy_block` with no side effect.
  2. Real google-adk runner/bootstrap failure returns `upstream_error` with no fallback dispatch.
  3. Multi-instance cancel confirmation passes in staging topology (ADK-09).
  4. `45-VERIFICATION.md` updated from `human_needed` to `passed`.
**Plans**: TBD

---

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
**Plans**: 4 plans

Plans:

- [x] 45-01: Add the pre-tool safety guardrail and lock `policy_block` route/runtime regressions
- [x] 45-02: Replace ambiguous runtime fallback with deterministic `tool_error` / `upstream_error` classification
- [x] 45-03: Finalize repeated-scenario regressions and sync the Phase 45 validation map
- [x] 45-04: Close runner-path policy bypass — protect operator policy keys from tool-call context overwrite (gap closure)

### Phase 46: ADK Observability Baseline
**Goal**: Operacao consegue monitorar saude ADK em producao por invocacao e por agente sem depender de debug manual.
**Depends on**: Phase 45
**Requirements**: OBS-02
**Success Criteria** (what must be TRUE):
  1. Operador visualiza latencia de invocacao ADK para o endpoint `/api/v2/adk/run`.
  2. Operador visualiza throughput e taxa de erro ADK por agente em producao.
  3. Operador identifica aumento de falhas ADK via metricas sem precisar inspecionar logs brutos request a request.
**Plans**: 1/1 plans complete

Plans:

- [x] 46-01-PLAN.md — Add Prometheus metrics (Histogram, Counter, Gauge) and structured logging at the ADK runtime boundary

### Phase 47: ADK CI Smoke Gate
**Goal**: Release so avanca quando trajetorias ADK criticas do dominio oncologico continuam estaveis no CI.
**Depends on**: Phase 46
**Requirements**: ADK-13
**Success Criteria** (what must be TRUE):
  1. Time executa smoke ADK de trajetorias oncologicas criticas no CI e recebe resultado pass/fail por cenario.
  2. Pipeline bloqueia deploy automaticamente quando qualquer cenario critico de smoke regressa.
  3. Pipeline segue para deploy quando todos os cenarios criticos passam sem necessidade de bypass manual.
**Plans**: 1/1 plans complete

Plans:

- [x] 47-01-PLAN.md — Register adk_smoke pytest marker, create oncology tool smoke suite, and wire smoke-adk CI job as deploy gate

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 44. ADK Runtime Controls | 3/3 | Complete    | 2026-03-05 |
| 45. ADK Tool Safety and Deterministic Errors | 4/4 | Complete   | 2026-03-06 |
| 46. ADK Observability Baseline | 1/1 | Complete    | 2026-03-06 |
| 47. ADK CI Smoke Gate | 1/1 | Complete    | 2026-03-06 |
| 48. Phase 44 Verification Closeout | 1/1 | Complete   | 2026-03-06 |
| 49. ADK Real Runner & Staging Validation | 0/? | Planned | — |

---

_Roadmap created: 2026-02-22_
_Last updated: 2026-03-06 — Phase 48 planned (1 plan); gap closure phases 48-49 added after v1.8 audit_
