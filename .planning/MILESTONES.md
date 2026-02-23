# Milestones

## v1.0 Refinamento para Producao (Shipped: 2026-02-22)

**Phases completed:** 5 phases, 13 plans, 28 tasks
**Git range:** `dd00b23c..b265da2c` (38 commits)
**Files changed:** 72 files, +2,057 / -11,371 lines (net -9,314 LOC)
**Timeline:** 2026-02-22

**Key accomplishments:**
- Monitoring endpoints locked down with canonical session-based auth; test token registry removed from production; Firebase key guardrail; debug flag validation (SEC-01..04)
- LGPD audit trail: immutable `patient_deletion_audit` table with PostgreSQL RULE immutability; WhatsApp opt-out handler (STOP/PARAR/CANCELAR); AI audit event types (LGPD-01..03)
- Celery tasks migrated from `asyncio.run()` to `async_to_sync`; atomic Lua sliding window rate limiter; python-jose fully eliminated and replaced by PyJWT (REL-01..03, ASYNC-04)
- LangGraph startup health check + centralized `invoke_langgraph_graph()` wrapper eliminating silent None fallbacks with explicit FeatureNotAvailableError (AI-01, AI-02)
- Dual flow system eliminated: FlowDispatcher facade with patient-type feature-flag routing + QW-021 full code deletion (~11k LOC removed); 5 integration tests covering unified flow (FLOW-01..03)

**Known Gaps (deferred to v1.1):**
- LGPD-04: Batch re-encryption for key rotation
- AI-03, AI-04: Single-node graph simplification + Gemini circuit breaker
- ASYNC-01..03, ASYNC-05: Hot path AsyncSession migration (webhook, flow, quiz, saga)
- OBS-01..03: Real metrics instrumentation, physician slot generation, WebSocket scaling

**Archive:** `.planning/milestones/v1.0-ROADMAP.md`, `.planning/milestones/v1.0-REQUIREMENTS.md`

---


## v1.1 Architecture & Observability (Shipped: 2026-02-23)

**Phases completed:** 4 phases, 10 plans, 20 tasks
**Git range:** `48923d96..d2a54201` (30+ commits)
**Files changed:** 69 files, +5,919 / -1,255 lines (net +4,664)
**Timeline:** 2026-02-22 → 2026-02-23

**Key accomplishments:**
- Async hot paths unblocked: all 35 `TODO(async-migration)` annotations resolved across webhook handler, flow engine, quiz service, and saga orchestrator — event loop no longer blocked under load (ASYNC-01..03, ASYNC-05)
- LGPD key rotation enabled: batch re-encryption Celery task with dual-key pattern, chunked processing, and Redis idempotency markers allows safe cryptographic key rotation (LGPD-04)
- AI layer simplified: 5 single-node LangGraph StateGraph wrappers eliminated — all AI generation calls go directly through `GeminiClient.generate_content()` (AI-03)
- Circuit breaker canonicalized: Gemini circuit-open path raises `FeatureNotAvailableError` with correct graph_name/operation attributes (AI-04)
- Real observability metrics: hardcoded 2.5s replaced with Redis rolling average; physician availability returns real 30-min slots (OBS-01, OBS-02)
- WebSocket multi-instance fixed: 3 method name mismatches in `RedisPubSubManager` corrected for cross-instance delivery (OBS-03)

**Known Gaps (deferred):**
- Full AsyncSession migration (42+ remaining methods in 65+ files) — hot paths cover ~80% throughput
- Physician availability hours model — hardcoded Mon-Fri 08:00-17:00 for v1.1, real preferences table needed
- 60+ files >500 lines still need splitting

**Archive:** `.planning/milestones/v1.1-ROADMAP.md`, `.planning/milestones/v1.1-REQUIREMENTS.md`

---

