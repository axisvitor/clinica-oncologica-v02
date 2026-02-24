# Requirements: Clinica Oncologica v1.2 — AI Framework Migration

**Defined:** 2026-02-23
**Core Value:** Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.

## v1.2 Requirements

Requirements for AI framework migration. Each maps to roadmap phases.

### Preparation & Scope

- [x] **PREP-01**: Developer can see a complete import graph of all LangGraph/LangChain dependencies across the codebase (audit)
- [x] **PREP-02**: System installs pydantic-ai-slim[google,retries] without conflicts on Python 3.13
- [x] **PREP-03**: Consensus graph and all associated code are deleted (0 callers, confirmed dead code)

### Agent Implementation

- [x] **AGENT-01**: SentimentAgent analyzes patient responses returning typed SentimentResult (sentiment, confidence, emotional_indicators, medical_concerns, requires_attention, key_themes, suggested_follow_up) via PromptedOutput
- [ ] **AGENT-02**: HumanizeAgent transforms flow templates into natural conversation messages preserving question count and placeholders
- [ ] **AGENT-03**: VariationAgent generates question variations avoiding 88% word overlap with recent interactions
- [ ] **AGENT-04**: EmpathyAgent generates empathetic follow-up messages based on sentiment analysis
- [x] **AGENT-05**: All 4 agents enforce PII/PHI redaction before every Gemini call via PIISafeAgent wrapper (LGPD Art. 46)
- [x] **AGENT-06**: All 4 agents validate output via @result_validator decorators reconnecting existing guardrails (banned patterns, prompt leak detection, length validation)
- [ ] **AGENT-07**: GeminiDomainClient methods delegate to new Pydantic AI agents via shim pattern (zero breaking changes to callers)
- [ ] **AGENT-08**: 50-scenario output regression test suite passes comparing old GeminiClient vs new agent outputs

### Flow Orchestration Replacement

- [ ] **FLOW-01**: flow_message_graph replaced by async Python function (load_flow_context → dispatch_send_mode)
- [ ] **FLOW-02**: flow_response_graph replaced by async Python function (load_response_context → dispatch_response_continuation)
- [ ] **FLOW-03**: LangGraph, langchain-core packages removed from requirements.txt
- [ ] **FLOW-04**: Redis LangGraph checkpoint keys purged via migration script (PHI data, LGPD compliance)
- [ ] **FLOW-05**: app/ai/langgraph/ directory tombstoned (runtime.py, nodes.py, state.py, graphs.py, _invoke.py, prompts.py)

### SDK Migration & Cleanup

- [ ] **SDK-01**: GeminiClient._initialize_model() migrated from ChatGoogleGenerativeAI (langchain-google-genai) to google-genai SDK directly
- [ ] **SDK-02**: langchain-google-genai package removed from requirements.txt (last LangChain dependency)
- [ ] **SDK-03**: All Celery tasks calling AI agents use agent.run_sync() (not async_to_sync wrapper) to avoid event loop closure errors

## v1.3 Requirements (Deferred)

### ADK Orchestration

- **ADK-01**: Google ADK installed after issue #3615 (google-adk-core lightweight install) is resolved
- **ADK-02**: Flow orchestration migrated from async Python to ADK SequentialAgent/ParallelAgent
- **ADK-03**: ADK BaseAgent custom implementations for deterministic flow nodes (no LLM calls)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Google ADK installation in v1.2 | 3 irresolvable dependency conflicts (OTel cap, FastAPI bundling, Pydantic 2.11+ failures) |
| New AI capabilities (triagem, tendencias) | Same logic better tech — nao expandir escopo AI |
| Frontend changes | Backend-only migration, zero UI impact |
| Full AsyncSession migration (42+ methods) | Carried tech debt from v1.1, outside migration scope |
| 60+ files >500 lines splitting | Carried tech debt, outside migration scope |
| CrewAI / Vercel AI SDK | CrewAI: 3-10 LLM calls per task + tool hallucination bug; AI SDK: no Python version |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PREP-01 | Phase 10 | Complete |
| PREP-02 | Phase 10 | Complete |
| PREP-03 | Phase 10 | Complete |
| AGENT-01 | Phase 11 | Complete |
| AGENT-02 | Phase 11 | Pending |
| AGENT-03 | Phase 11 | Pending |
| AGENT-04 | Phase 11 | Pending |
| AGENT-05 | Phase 11 | Complete |
| AGENT-06 | Phase 11 | Complete |
| AGENT-07 | Phase 11 | Pending |
| AGENT-08 | Phase 11 | Pending |
| FLOW-01 | Phase 12 | Pending |
| FLOW-02 | Phase 12 | Pending |
| FLOW-03 | Phase 12 | Pending |
| FLOW-04 | Phase 12 | Pending |
| FLOW-05 | Phase 12 | Pending |
| SDK-01 | Phase 13 | Pending |
| SDK-02 | Phase 13 | Pending |
| SDK-03 | Phase 13 | Pending |

**Coverage:**
- v1.2 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-23*
*Last updated: 2026-02-23 — traceability table confirmed against ROADMAP.md phases 10-13*
