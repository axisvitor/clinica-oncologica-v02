# Project Research Summary

**Project:** Clinica Oncologica v02 — Healthcare WhatsApp Patient Monitoring
**Domain:** Oncology remote symptom tracking with AI-humanized questionnaires (production refinement)
**Researched:** 2026-02-22
**Confidence:** HIGH (stack and pitfalls grounded in direct codebase inspection; features confirmed against peer-reviewed clinical literature)

## Executive Summary

This is a production-refinement project, not a greenfield build. The prototype is functionally complete: WhatsApp delivery via Evolution API, LangGraph + Gemini AI humanization, Celery Beat with 38 periodic tasks, patient flow state machine, LGPD consent management, and a real-time dashboard. The research question is not "what to build" but "what must be hardened before real oncology patients use this system." The answer is unambiguous: seven critical gaps exist that are either compliance blockers (LGPD audit gaps, missing opt-out handling), security exposures (auth bypasses, test token in production binary), or reliability risks (sync-in-async blocking, dual flow divergence, LangGraph silent degradation). All seven must be resolved before the first patient.

The recommended approach is a two-phase refinement: Phase 1 addresses every blocker that is independent and actionable now — security fixes, LGPD compliance gaps, operational stability bugs. Phase 2 addresses larger architectural work that has dependencies on Phase 1 — consolidating the dual flow systems, migrating hot-path database calls to AsyncSession, implementing batch re-encryption. The existing stack (Python 3.13, FastAPI, LangGraph 1.0.9, Celery + Dragonfly, Gemini 2.0 Flash) is fundamentally sound and should not be replaced; what is needed is rationalization of over-engineered patterns (five single-node LangGraph graphs can become direct GeminiClient calls) and completion of half-finished migrations (the async migration, the flow consolidation).

The central risk is operational reliability in a clinical context. Oncology patients receiving impersonal robotic messages when LangGraph silently no-ops, missed quiz deliveries when Celery Beat crashes without HA, or data corruption from dual flow state divergence are not just UX problems — they are patient safety problems. The roadmap must treat the Phase 1 fixes as prerequisites for any v1 launch, not as technical debt to be addressed later.

---

## Key Findings

### Recommended Stack

The stack is well-chosen for this domain and should be retained as-is. The only structural change is rationalization of LangGraph usage: the five single-node AI graphs (`humanization`, `sentiment`, `generation`, `question_variation`, `empathetic_follow_up`) are over-engineered wrappers around single Gemini calls and should be replaced with direct `GeminiClient.generate_content()` calls. The two multi-node routing graphs (`flow_message_graph`, `flow_response_graph`) are legitimate LangGraph use cases and should be kept. LangGraph 1.0.9 (released 2026-02-19) is production-stable with official no-breaking-changes commitment until 2.0.

The primary stack debt is the SQLAlchemy sync/async split. The codebase uses FastAPI (async) with SQLAlchemy sync `Session` throughout — the worst possible configuration, delivering ~550 req/s where pure async would deliver ~1,400 req/s. The fix is targeted: migrate only the hot-path methods (webhook handler, quiz response processing, flow advancement) to `AsyncSession`. Celery tasks can legitimately keep sync sessions. The `asyncpg` driver is already in `requirements.txt` — infrastructure exists.

**Core technologies:**
- Python 3.13 + FastAPI 0.128+: Runtime and HTTP layer — optimal for 2025/2026, async-first, keep as-is
- SQLAlchemy 2.0 AsyncSession + asyncpg: Database access for hot paths — currently partially used; complete migration of Tier 1 paths
- LangGraph 1.0.9: Stateful multi-node flow orchestration only — keep flow_message and flow_response graphs; remove single-node wrappers
- Google Gemini 2.0 Flash: AI message humanization — $0.10/1M tokens, cost-optimal; keep with PII redaction always applied
- Celery 5.x + Dragonfly: Task queue and periodic scheduling — correct for 38 periodic tasks; Dragonfly is 100% Redis-compatible with 25x throughput advantage
- Evolution API v2: WhatsApp integration — acceptable for current scale; plan Cloud API migration path for >500 patients
- Firebase Auth: Authentication — no change needed; remove test bypass from production binary

### Expected Features

Research confirmed this is a production-readiness milestone. The feature landscape is defined by what must be fixed before first real patient, not what must be built from scratch. The system's competitive position (WhatsApp delivery + AI humanization + LGPD compliance + Portuguese-native) is unique and should not be diluted by scope creep.

**Must have before first real patient (P1 blockers):**
- Persistent LGPD deletion audit table — Art. 16/18 compliance; logs-only fails regulatory audit
- WhatsApp opt-out (STOP keyword) handling — LGPD Art. 18 and Meta policy; absence risks account suspension
- Fix placeholder auth on monitoring endpoints — publicly accessible metrics is a security breach
- Remove TEST_TOKEN_REGISTRY from production binary — debug bypass in production is an auditable risk
- AI event types in audit enum (AI_QUERY, AI_HUMANIZATION) — LGPD accountability principle
- LangGraph startup health check — silent no-op delivers robotic messages to cancer patients undetected
- Fix asyncio.run() to async_to_sync in Celery tasks — memory leak from new event loop per task invocation
- Rate limiter Lua script atomicity — race condition allows WhatsApp API burst violations causing account suspension
- python-jose import sweep — CVE-2024-23342; remaining imports cause silent runtime failures

**Should have within 30 days of first patient (P2):**
- Dual flow system consolidation — two parallel engines create invisible patient state divergence
- Sync-in-async hot path migration — webhook handler (12 TODOs), quiz service (8 TODOs), flow_core (7 TODOs)
- Physician availability slots implementation — endpoint currently returns empty list silently
- Batch re-encryption for key rotation — LGPD Art. 46; current state makes security incident unrecoverable
- WebSocket multi-instance scaling — Redis pub/sub manager exists; integration with WebSocket manager is the gap
- Real health metrics — avg_task_duration_seconds hardcoded at 2.5; misleads physicians

**Defer to v2 (after clinical validation):**
- Full AsyncSession migration (all 42+ methods) — large project, high regression risk
- Celery Beat HA with redbeat — justified only at >500 patients
- Multi-tenant architecture — separate product, requires full schema redesign
- EHR/HIS integration — out of scope per PROJECT.md; data portability via export satisfies LGPD Art. 18

**Anti-features (do not build):**
- Autonomous AI clinical recommendations — regulatory risk; AI role must remain strictly humanizer, never clinical decision-maker
- Real-time free-form WhatsApp chat — requires 24/7 clinical triage, out of scope
- Full AsyncSession big-bang migration — creates large regression risk; migrate hot paths only

### Architecture Approach

The architecture is layered correctly: FastAPI routers communicate only with the domain/services layer; the AI layer communicates through PII redaction before any Gemini call; Celery workers communicate with services, never directly with AI or repositories; all external integrations have facade classes (UnifiedWhatsAppService, GeminiOrchestrator, RedisManager). These boundaries are sound and must be maintained during refactoring.

The two architectural problems requiring resolution are the dual flow system and the sync-in-async split. The dual flow system consolidation should follow the Strangler Fig pattern: introduce a `FlowDispatcher` facade that routes to either system based on a feature flag, migrate new patients to the QW-021 system first, then tombstone the flat-file production system after 100% migration. The sync/async migration should be sequenced by throughput priority (webhook handler first, then quiz service, then flow_core), using Strategy B (proper AsyncSession) for Tier 1 paths and Strategy A (run_in_executor bridge) only as a documented temporary measure.

**Major components:**
1. FastAPI Application — HTTP routing, auth middleware, webhook handling, WebSocket manager; currently has auth placeholder gap in monitoring router
2. Flow Layer (dual — consolidation required) — production flat-file system (SQLAlchemy PatientFlowState, day-based) and QW-021 package (Pydantic FlowContext, step-based); must be unified via FlowDispatcher facade
3. AI Layer (LangGraph + Gemini) — 8 compiled graphs of which 5 are over-engineered; rationalize to 3 graphs + direct client calls; add startup health check
4. Celery Workers + Beat — 38 periodic tasks; asyncio.run() must be replaced with async_to_sync; Beat has no HA (redbeat needed at scale)
5. Infrastructure Core — RedisManager (singleton, circuit breaker, SSL), CircuitBreaker, LGPD services; missing Gemini circuit breaker is a gap
6. Data Stores — PostgreSQL/RDS (sync Session is the debt), Dragonfly (4 logical DBs, production-proven)

### Critical Pitfalls

1. **Sync-in-async as a gradual performance cliff** — 46 annotated sync DB calls inside async FastAPI handlers cause no errors in dev but cause cascading timeouts under concurrent patient load (~550 req/s vs ~1,400 req/s). Migrate hot paths (webhook handler, quiz service, flow_core) first using AsyncSession + asyncpg. Do not attempt all 46 at once.

2. **LangGraph silent no-op on import failure** — five `try/except ImportError: X = None` guards in graphs.py, runtime.py, and consensus.py mean LangGraph failures are invisible. Patients receive robotic template text with no error, no Sentry event. Fix: add startup health check in lifespan.py that verifies LangGraph functional before traffic arrives; convert None fallbacks to FeatureNotAvailableError.

3. **Dual flow system divergence creates invisible patient state corruption** — two parallel engines (flow_core.py and services/flow/core/manager.py) are independently tested but not integration-tested together. A patient can appear active in one system with a different state than the other. Fix: introduce FlowDispatcher facade first, write integration tests covering the seam, then migrate all patients to one canonical system before tombstoning the other. Never apply bug fixes to both systems simultaneously.

4. **asyncio.run() in Celery tasks leaks event loops** — flow_tasks.py:326 creates a new event loop per task invocation; over 38 periodic tasks, this causes memory growth followed by OOM kill. The fix (async_to_sync from asgiref) is already applied in response_tasks.py and helpers.py — standardize it everywhere. Grep for `asyncio.run(` in `app/tasks/`; must return zero results.

5. **LGPD audit gaps create regulatory exposure** — patient deletion events written only to application logs (Railway log rotation destroys them); AI event types absent from AuditEventType enum. ANPD has been very active since 2023 with BRL 98M in fines across 2023-2025. Fix: create patient_deletion_audit table via Alembic migration (write before deletion, not after); add AI_QUERY/AI_HUMANIZATION/AI_SENTIMENT/AI_FOLLOW_UP to AuditEventType enum with migration.

---

## Implications for Roadmap

Based on combined research, a two-phase structure is strongly recommended. The dependency chain is clear: security and compliance fixes have no dependencies and must come first; architectural refactoring (flow consolidation, async migration) depends on those foundations and is required before new functionality.

### Phase 1: Security, Compliance, and Stability

**Rationale:** Nine of the P1 blockers are independent of each other and each takes less than a day. None can be deferred — they are preconditions for exposing the system to real patients. The clinical liability and regulatory risk of going live without these outweigh any timeline pressure. LGPD enforcement is active; Evolution API account suspension is real; Celery task memory leaks compound over days.

**Delivers:** A system that is legally compliant (LGPD audit trail, opt-out handling), security-hardened (no auth bypasses, no debug code in production), and operationally stable (no event loop leaks, rate limiter atomic, LangGraph health-checked).

**Addresses (from FEATURES.md):** LGPD deletion audit table, WhatsApp opt-out handling, monitoring endpoint auth fix, TEST_TOKEN_REGISTRY removal, AI audit enum, LangGraph startup health check, asyncio.run() fix in Celery, rate limiter Lua script, python-jose sweep.

**Avoids (from PITFALLS.md):** LGPD audit gap (Pitfall 5), LangGraph silent no-op (Pitfall 2), Celery event loop leak (Pitfall 4), monitoring auth bypass (Security Mistakes section).

**Research flag:** Standard patterns — no additional research needed. Every fix is documented in codebase analysis with exact file locations and line numbers.

### Phase 2: Core Architectural Refactoring

**Rationale:** Dual flow consolidation and AsyncSession migration are the two largest technical risks to reliability at scale. Both have internal dependencies: AsyncSession migration must come before FlowDispatcher because the QW-021 system needs AsyncSession-capable repositories to be the migration target. Both are blocked on Phase 1 completing (specifically: asyncio.run() fix clears the way for consistent async patterns across the codebase).

**Delivers:** A single canonical flow system (no more dual-engine divergence), async database operations on all high-throughput paths (webhook, quiz, flow advancement), and batch re-encryption capability for LGPD key rotation.

**Uses (from STACK.md):** SQLAlchemy 2.0 AsyncSession with asyncpg driver (already in requirements.txt), Strangler Fig consolidation pattern, async_to_sync for Celery/async boundary.

**Implements (from ARCHITECTURE.md):** FlowDispatcher facade, AsyncSession in BaseRepository, FlowContextRepository with persistence to patient_flow_states table, Gemini circuit breaker (currently missing), shim integrity test in CI.

**Avoids (from PITFALLS.md):** Dual flow divergence (Pitfall 3), sync-in-async performance cliff (Pitfall 1), encryption key rotation gap (Pitfall 6), shim accumulation (Pitfall 7).

**Research flag:** Needs deeper research for AsyncSession migration scope. The specific query patterns in sequential_message_handler.py (12 TODOs), flow_core.py (7 TODOs), and enhanced_quiz_service.py (8 TODOs) require file-by-file analysis during planning to estimate migration effort accurately.

### Phase 3: Observability, Resilience, and Reliability

**Rationale:** After Phase 2 completes, the system has one canonical flow, async hot paths, and a compliance-complete audit trail. Phase 3 addresses the remaining operational gaps that become important as patient volume grows: real health metrics (not hardcoded stubs), physician dashboard accuracy, WebSocket multi-instance scaling, Celery Beat HA.

**Delivers:** A system that operators can trust to monitor and a dashboard that physicians can rely on. Physician availability slots become functional. Dashboard metrics reflect actual system behavior. Beat can survive a process restart without patient impact.

**Addresses (from FEATURES.md):** Hardcoded metrics stub removal, WebSocket scaling (Redis pub/sub integration), physician availability implementation, Celery Beat HA configuration (redbeat).

**Avoids (from PITFALLS.md):** WebSocket split-brain (Performance Traps section), Celery Beat SPOF (Performance Traps section), metrics collector DB spike (Performance Traps section).

**Research flag:** WebSocket multi-instance integration needs a focused spike. The `redis_pubsub_manager.py` exists but the gap between it and the WebSocket connection manager is not fully characterized in the codebase analysis.

### Phase 4: LangGraph Rationalization and AI Hardening

**Rationale:** The single-node LangGraph graph rationalization (replacing 5 graphs with direct GeminiClient calls) is deliberately deferred to Phase 4. The primary reason is risk management: touching the AI layer during Phases 1-3 would increase diff size and regression risk while more critical work is in progress. By Phase 4, the dual flow is resolved, the async foundation is solid, and the AI layer can be safely refactored. This phase also adds the Gemini circuit breaker (currently missing) and validates the PII redaction pipeline with integration tests.

**Delivers:** A simpler, more maintainable AI layer with fewer compiled graph instances, explicit Gemini circuit breaking, and verified PII redaction coverage.

**Uses (from STACK.md):** Direct GeminiClient.generate_content() for single AI calls, existing CircuitBreaker from app/resilience/circuit_breaker/ extended to cover Gemini.

**Research flag:** Standard patterns — LangGraph graph removal is well-understood (direct client calls); Gemini circuit breaker follows existing CircuitBreaker pattern in codebase.

### Phase Ordering Rationale

- Phase 1 before everything: security and compliance blockers have no dependencies and are preconditions for patient exposure.
- AsyncSession migration (Phase 2) before flow consolidation: the QW-021 system needs AsyncSession-capable repositories to be a viable migration target; running consolidation on the legacy sync path would be wasted effort.
- Observability (Phase 3) after architectural refactoring: meaningful metrics require a stable, single-flow system to report on; instrumentation of a system mid-refactoring produces misleading data.
- LangGraph rationalization (Phase 4) last: lowest risk, highest optionality; removing graph scaffolding is a cleanup, not a prerequisite.
- Do not build new clinical features (v2 scope) until the Phase 1 blockers are resolved and the Phase 2 architecture is stable.

### Research Flags

Phases needing deeper research during planning:
- **Phase 2 (AsyncSession migration scope):** Sequential_message_handler.py (12 TODOs), flow_core.py (7 TODOs), and enhanced_quiz_service.py (8 TODOs) require file-by-file analysis to produce accurate effort estimates. Query patterns vary; some may require significant restructuring.
- **Phase 3 (WebSocket multi-instance gap):** The exact integration point between redis_pubsub_manager.py and the WebSocket connection manager needs a focused code-reading spike before story creation.

Phases with standard, well-documented patterns (skip research-phase):
- **Phase 1 (Security and Compliance fixes):** Every item has exact file and line number from codebase analysis. Patterns (Alembic migration, FastAPI Depends, async_to_sync) are standard.
- **Phase 4 (LangGraph rationalization):** Removing StateGraph wrappers and calling GeminiClient directly is straightforward; the existing client API is well-documented in the codebase.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All recommendations grounded in direct codebase inspection + official docs. LangGraph overhead benchmarks are MEDIUM (community benchmarks, not official). |
| Features | HIGH | P1 blockers verified line-by-line in codebase. Clinical domain standards from peer-reviewed sources (Lancet, PMC, NCI). Anti-features grounded in clinical AI risk literature. |
| Architecture | HIGH | Component boundaries and dependency rules verified against actual code structure. Strangler Fig pattern is a well-established Microsoft Architecture pattern. AsyncSession performance benchmark (550 vs 1400 req/s) is MEDIUM confidence (single external source). |
| Pitfalls | HIGH | All critical pitfalls have specific file and line number evidence from codebase. LGPD enforcement data is from official ANPD and ICLG sources. LangGraph checkpoint CVE verified against cyberpress source. |

**Overall confidence:** HIGH

### Gaps to Address

- **Physician availability slots implementation scope:** Research confirmed the endpoint returns empty silently; the actual scheduling model (what constitutes an "available slot" in this clinic's context) is not documented in the codebase and needs product clarification during Phase 2 story creation.
- **Evolution API webhook signature validation:** Mentioned in architecture as required, but not verified as currently implemented in the webhook handler. Confirm presence or absence during Phase 1 story sizing.
- **LangGraph checkpoint CVE remediation status:** Verify that the current pinned version (>=1.0.7) includes the patched checkpoint library before Phase 4 LangGraph work begins.
- **Patient data export validation:** FEATURES.md notes the export endpoint exists in import_export.py but marks it as "validate it works." This is a LGPD Art. 18 portability requirement and should be confirmed during Phase 1.
- **AsyncSession migration effort estimate:** The 27 highest-priority TODOs across 3 files need a focused code reading to estimate query complexity before Phase 2 can be accurately sized.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `backend-hormonia/app/ai/langgraph/graphs.py`, `nodes_ai.py`, `runtime.py`, `consensus.py`
- Direct codebase inspection: `backend-hormonia/app/services/flow_core.py`, `app/services/flow/core/manager.py`
- Direct codebase inspection: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/CONCERNS.md`
- [SQLAlchemy 2.0 async documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) — AsyncSession patterns
- [SQLAlchemy 2.0 Major Migration Guide](https://docs.sqlalchemy.org/en/21/changelog/migration_20.html) — gradual migration strategy
- [LangGraph PyPI 1.0.9](https://pypi.org/project/langgraph/) — version, Python compatibility, release date
- [LangChain blog — LangGraph 1.0](https://blog.langchain.com/langchain-langgraph-1dot0/) — production readiness, adoption
- [Lancet Regional Health 2024 — 33 cancer centers](https://www.thelancet.com/journals/lanepe/article/PIIS2666-7762(24)00172-8/fulltext) — physician notification as key clinical factor
- [LGPD Enforcement: ANPD fines 2023-2025](https://www.compliancehub.wiki/breaches-and-fines-under-brazils-lei-geral-de-protecao-de-dados-lgpd-2/) — regulatory risk context
- [ICLG Brazil Data Protection 2025-2026](https://iclg.com/practice-areas/data-protection-laws-and-regulations/brazil) — LGPD current enforcement status
- [Microsoft Azure Architecture — Strangler Fig Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig) — flow consolidation approach

### Secondary (MEDIUM confidence)
- [Building High-Performance Async APIs with FastAPI, SQLAlchemy 2.0, asyncpg](https://leapcell.io/blog/building-high-performance-async-apis-with-fastapi-sqlalchemy-2-0-and-asyncpg) — 550 vs 1400 req/s benchmark
- [FastAPI + AsyncSQLAlchemy 2.0 modern patterns (Dec 2025)](https://dev-faizan.medium.com/fastapi-sqlalchemy-2-0-modern-async-database-patterns-7879d39b6843) — migration patterns
- [ZenML blog — LangGraph alternatives](https://www.zenml.io/blog/langgraph-alternatives) — ~14ms framework overhead benchmark
- [Dragonfly vs Redis 2025](https://martinuke0.github.io/posts/2025-12-11-dragonfly-vs-redis-a-practical-data-backed-comparison-for-2025/) — 25x throughput claim
- [Using Celery with FastAPI: event loop problem](https://medium.com/@termtrix/using-celery-with-fastapi-the-async-inside-tasks-event-loop-problem-and-how-endpoints-save-79e33676ade9) — asyncio.run() leak pattern
- [LLM Risks in Consumer Health, PMC12325106](https://pmc.ncbi.nlm.nih.gov/articles/PMC12325106/) — AI overtrust risk
- [WhatsApp chatbot breast cancer study, PMC6521209](https://pmc.ncbi.nlm.nih.gov/articles/PMC6521209/) — patient acceptance data

### Tertiary (LOW confidence)
- [LangGraph GitHub discussion #4595](https://github.com/langchain-ai/langgraph/discussions/4595) — single-node graph overhead; community discussion, no official benchmark
- [LangGraph GitHub issue #6709](https://github.com/langchain-ai/langgraph/issues/6709) — runtime-postgres missing from PyPI; needs re-verification if checkpointing is ever needed
- [Critical Flaw in LangGraph RCE via Deserialization](https://cyberpress.org/flaw-in-langgraph/) — checkpoint CVE; verify remediation status in pinned version before Phase 4

---
*Research completed: 2026-02-22*
*Ready for roadmap: yes*
