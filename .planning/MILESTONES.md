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

