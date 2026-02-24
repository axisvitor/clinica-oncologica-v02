# Roadmap: Clinica Oncologica — Refinamento para Producao

## Milestones

- ✅ **v1.0 Foundations** — Phases 1-5 (shipped 2026-02-22)
- ✅ **v1.1 Architecture & Observability** — Phases 6-9 (shipped 2026-02-23)
- 🚧 **v1.2 AI Framework Migration** — Phases 10-13 (in progress)

## Phases

<details>
<summary>✅ v1.0 Foundations (Phases 1-5) — SHIPPED 2026-02-22</summary>

- [x] Phase 1: Security Hardening (3/3 plans) — completed 2026-02-22
- [x] Phase 2: LGPD Compliance (3/3 plans) — completed 2026-02-22
- [x] Phase 3: Operational Stability (3/3 plans) — completed 2026-02-22
- [x] Phase 4: AI Reliability (2/2 plans) — completed 2026-02-22
- [x] Phase 5: Flow Consolidation (2/2 plans) — completed 2026-02-22

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 Architecture & Observability (Phases 6-9) — SHIPPED 2026-02-23</summary>

- [x] Phase 6: Async Hot Path Migration (4/4 plans) — completed 2026-02-23
- [x] Phase 7: LGPD Key Rotation (1/1 plan) — completed 2026-02-23
- [x] Phase 8: AI Rationalization (2/2 plans) — completed 2026-02-23
- [x] Phase 9: Observability (3/3 plans) — completed 2026-02-23

Full details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

### 🚧 v1.2 AI Framework Migration (In Progress)

**Milestone Goal:** Substituir LangGraph por Pydantic AI, eliminando overhead de orquestracao mantendo as mesmas 4 operacoes AI com melhor type safety, PII safety, e output guardrails explicitos.

- [x] **Phase 10: Preparation & Scope** - Audit LangGraph imports, install pydantic-ai, delete consensus (dead code) (completed 2026-02-24)
- [x] **Phase 11: Agent Implementation** - Implement 4 typed pydantic-ai agents with PIISafeAgent wrapper, guardrails, and shim (completed 2026-02-24)
- [x] **Phase 12: Flow Orchestration Replacement** - Replace 2 LangGraph graphs with async Python, remove LangGraph packages, purge Redis checkpoints (completed 2026-02-24)
- [x] **Phase 13: SDK Migration & Cleanup** - Migrate GeminiClient from ChatGoogleGenerativeAI to google-genai SDK, validate Celery async bridge (completed 2026-02-24)

## Phase Details

### Phase 10: Preparation & Scope
**Goal**: The codebase is ready for agent implementation — all LangGraph import dependencies are mapped, pydantic-ai is installed without conflicts, and dead code (consensus system) is deleted
**Depends on**: Nothing (first v1.2 phase)
**Requirements**: PREP-01, PREP-02, PREP-03
**Success Criteria** (what must be TRUE):
  1. Developer can run `LANGGRAPH_AUDIT=1 python -c "import app.main"` and see a printed list of every file that imports from langgraph, langchain_core, or langchain_google_genai (import audit complete)
  2. `pip install pydantic-ai-slim[google,retries]>=1.63.0,<2.0.0` succeeds in the project virtualenv on Python 3.13 with zero dependency conflicts
  3. `consensus.py` and `consensus_manager.py` files no longer exist in the codebase and `grep -r "consensus" app/ai/` returns zero results
  4. All files in `app/agents/` (DDD service components) have a one-line scope comment confirming they contain no LLM calls and are not migration targets
**Plans**: 4 plans

Plans:
- [ ] 10-01-PLAN.md — LangGraph import audit + pydantic-ai-slim installation
- [ ] 10-02-PLAN.md — Consensus system deletion + app/agents/ scope annotation
- [ ] 10-03-PLAN.md — Gap closure part 1: annotate shared/patient app/agents modules
- [ ] 10-04-PLAN.md — Gap closure part 2: annotate communication modules + run full annotation audit

### Phase 11: Agent Implementation
**Goal**: All 4 AI operations (humanize, sentiment, variation, empathy) are delivered by typed pydantic-ai agents with mandatory PII redaction, reconnected output guardrails, and a feature-flag shim that callers cannot distinguish from the old interface
**Depends on**: Phase 10
**Requirements**: AGENT-01, AGENT-02, AGENT-03, AGENT-04, AGENT-05, AGENT-06, AGENT-07, AGENT-08
**Success Criteria** (what must be TRUE):
  1. SentimentAgent returns a fully-populated `SentimentResult` with all 7 fields (sentiment, confidence, emotional_indicators, medical_concerns, requires_attention, key_themes, suggested_follow_up) on every invocation — downstream alert logic never encounters a KeyError
  2. Every agent invocation passes patient data through `sanitize_prompt_text_for_external_ai()` before calling Gemini — confirmed by CI lint rule that blocks direct `.run()` calls outside `PIISafeAgent`
  3. Banned patterns, prompt leak markers, character length bounds, and Brazilian Portuguese punctuation rules fire as `@result_validator` decorators on each agent — identical guardrail assertions to the old `GeminiClient.generate_content()` path
  4. `GeminiDomainClient` callers (`flow_core.py`, `flow_service.py`, `enhanced_flow_engine.py`) receive responses with identical signatures when `AI_FRAMEWORK` feature flag is toggled — zero breaking changes observable at call sites
  5. The 50-scenario output regression test suite passes with all guardrail assertions satisfied and agent outputs compared against old GeminiClient baseline
**Plans**: 4 plans

Plans:
- [ ] 11-01-PLAN.md — PIISafeAgent base class + AIDeps dataclass + app/ai/agents/ scaffold
- [ ] 11-02-PLAN.md — SentimentAgent with PromptedOutput(SentimentResult) + output_validator guardrails
- [ ] 11-03-PLAN.md — HumanizeAgent + VariationAgent + EmpathyAgent implementation
- [ ] 11-04-PLAN.md — GeminiDomainClient shim with AI_FRAMEWORK feature flag + 50-scenario regression suite

### Phase 12: Flow Orchestration Replacement
**Goal**: LangGraph is completely removed from the codebase — the 2 flow routing graphs are replaced by direct async Python functions, all LangGraph packages are uninstalled, and Redis checkpoint keys (PHI data) are purged and logged as a LGPD compliance event
**Depends on**: Phase 11
**Requirements**: FLOW-01, FLOW-02, FLOW-03, FLOW-04, FLOW-05
**Success Criteria** (what must be TRUE):
  1. `flow_message_graph` callers invoke a direct async Python function that executes `load_flow_context → dispatch_send_mode` with no LangGraph runtime involved — `AI_FLOW_FRAMEWORK` flag routes between old and new paths
  2. `flow_response_graph` callers invoke a direct async Python function that executes `load_response_context → dispatch_response_continuation` — same behavior, zero graph overhead
  3. `requirements.txt` no longer contains `langgraph`, `langchain-core`, `langchain-google-genai`, or `google-ai-generativelanguage` — confirmed by a single clean `pip check` run
  4. `scan_iter` on Dragonfly DB 0 returns zero results for `langgraph:checkpoint:*` keys — purge executed, purge count logged as a LGPD data deletion event in the audit record
  5. Every file in `app/ai/langgraph/` raises `ImportError` with a migration message when imported — directory tombstoned, not deleted
**Plans**: 3 plans

Plans:
- [ ] 12-01-PLAN.md — Direct async flow functions + AI_FLOW_FRAMEWORK feature flag + caller migration to helpers.py
- [ ] 12-02-PLAN.md — Inline function bodies into helpers.py/_flow_functions.py + remove LangGraph packages from requirements.txt
- [ ] 12-03-PLAN.md — Tombstone app/ai/langgraph/ directory + Redis checkpoint PHI purge script (LGPD)

### Phase 13: SDK Migration & Cleanup
**Goal**: The last LangChain reference in the entire backend is eliminated — GeminiClient initializes directly via the google-genai SDK, Celery tasks use agent.run_sync() to avoid event loop closure errors, and zero LangChain imports remain anywhere
**Depends on**: Phase 12
**Requirements**: SDK-01, SDK-02, SDK-03
**Success Criteria** (what must be TRUE):
  1. `GeminiClient._initialize_model()` creates a `google.genai.Client` instance directly — no `ChatGoogleGenerativeAI`, no `HumanMessage` from langchain-core anywhere in `client.py`
  2. `langchain-google-genai` is absent from `requirements.txt` and `pip check` passes — confirmed by `grep -r "langchain" requirements.txt` returning zero results
  3. All Celery tasks that call AI agents use `agent.run_sync()` directly — a 100-task sequential load test completes without `RuntimeError: Event loop is closed` errors
**Plans**: 3 plans

Plans:
- [ ] 13-01-PLAN.md — GeminiClient + PatientSummaryService migrated to google-genai SDK
- [ ] 13-02-PLAN.md — Collapse feature-flag shims, purge all langchain references, permanent CI gate
- [ ] 13-03-PLAN.md — PIISafeAgent._safe_run_sync() Celery bridge + 100-task load test

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Security Hardening | v1.0 | 3/3 | Complete | 2026-02-22 |
| 2. LGPD Compliance | v1.0 | 3/3 | Complete | 2026-02-22 |
| 3. Operational Stability | v1.0 | 3/3 | Complete | 2026-02-22 |
| 4. AI Reliability | v1.0 | 2/2 | Complete | 2026-02-22 |
| 5. Flow Consolidation | v1.0 | 2/2 | Complete | 2026-02-22 |
| 6. Async Hot Path Migration | v1.1 | 4/4 | Complete | 2026-02-23 |
| 7. LGPD Key Rotation | v1.1 | 1/1 | Complete | 2026-02-23 |
| 8. AI Rationalization | v1.1 | 2/2 | Complete | 2026-02-23 |
| 9. Observability | v1.1 | 3/3 | Complete | 2026-02-23 |
| 10. Preparation & Scope | 4/4 | Complete    | 2026-02-24 | - |
| 11. Agent Implementation | 4/4 | Complete    | 2026-02-24 | - |
| 12. Flow Orchestration Replacement | 3/3 | Complete    | 2026-02-24 | - |
| 13. SDK Migration & Cleanup | 3/3 | Complete   | 2026-02-24 | - |

---
*Roadmap created: 2026-02-22*
*Last updated: 2026-02-23 — v1.2 AI Framework Migration phases 10-13 added*
