# Milestones

## v1.6 WuzAPI Migration (Shipped: 2026-03-03)

**Delivered:** Evolution API was fully replaced by WuzAPI across inbound, outbound, config/session, and test/CI flows with a hard-cut provider migration.

**Phases completed:** 7 phases, 21 plans, 42 tasks

**Git range:** `885816d3..9ee0cdb4` (99 commits)
**Files changed:** 132 files, +16,433 / -7,093 lines (net +9,340 LOC)
**Timeline:** 2026-03-01 → 2026-03-03

**Key accomplishments:**
- WuzAPI client foundation shipped with token auth, retries, rate limiting, circuit breaker, media encoding, and mock factory (`CLI-01..06`).
- WuzAPI webhook stack implemented with raw-body HMAC validation, payload extraction, Redis idempotency, LGPD opt-out handling, and LID DLQ routing (`WH-01..06`).
- Outbound message paths fully migrated to WuzAPI and Evolution code tombstoned across Stack A/Stack B with import-level kill switches (`OUT-01..04`, `CLEAN-01..06`).
- Regression gates added for webhook fixtures, STOP-to-send-guard E2E, and source-level Evolution import checks (`TEST-01..05`).
- Audit findings M-1/M-2 closed in Phase 39 by aligning webhook secret lookup with settings and returning explicit HTTP 501 for unsupported contacts sync.

**Known Gaps (tech debt, non-blocking):**
- Live-provider verification still required for production confidence: real WuzAPI send/media, real webhook HMAC delivery, QR pairing UX, and LID DLQ observability.

**Archive:** `.planning/milestones/v1.6-ROADMAP.md`, `.planning/milestones/v1.6-REQUIREMENTS.md`, `.planning/milestones/v1.6-MILESTONE-AUDIT.md`

---

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


## v1.2 AI Framework Migration (Shipped: 2026-02-24)

**Phases completed:** 4 phases, 16 plans, 32 tasks
**Git range:** `279193d4..88f64d35` (72 commits)
**Files changed:** 131 files, +13,411 / -5,731 lines (net +7,680 LOC)
**Timeline:** 2026-02-24

**Key accomplishments:**
- 4 typed Pydantic AI agents shipped (Sentiment, Humanize, Variation, Empathy) with mandatory PII redaction via PIISafeAgent wrapper and CI enforcement (LGPD Art. 46) (AGENT-01..08)
- LangGraph fully decommissioned: 9 modules tombstoned, 3 LangChain packages removed from requirements, Redis checkpoint PHI keys purged with LGPD audit logging (FLOW-01..05)
- GeminiClient migrated from ChatGoogleGenerativeAI (langchain-google-genai) to google-genai SDK directly, preserving all resilience patterns (SDK-01, SDK-02)
- 2 LangGraph StateGraphs replaced by direct async Python functions (10-15 lines each), zero graph overhead (FLOW-01, FLOW-02)
- Celery-safe sync bridge: PIISafeAgent run_sync handles closed/missing event loops, 100-call sequential load test, all Celery AI paths wired to explicit sync entrypoints (SDK-03)
- Permanent CI gates: AST-based LangChain import blocker and Celery AI sync wiring validator prevent regression

**Known Gaps (deferred):**
- Google ADK installation deferred to v1.3 (irresolvable dependency conflicts)
- Full AsyncSession migration (42+ remaining methods) — hot paths cover ~80% throughput
- 60+ files >500 lines still need splitting
- Physician availability hours model — hardcoded defaults
- PromptedOutput validation confidence against gemini-2.5-flash is MEDIUM

**Archive:** `.planning/milestones/v1.2-ROADMAP.md`, `.planning/milestones/v1.2-REQUIREMENTS.md`

---


## v1.3 Flow Health & Cleanup (Shipped: 2026-02-26)

**Phases completed:** 6 phases, 31 plans, 62 tasks

**Git range:** `3ee3967d..a086cf67` (123 commits)
**Files changed:** 198 files, +21,525 / -16,053 lines (net +5,472 LOC)
**Timeline:** 2026-02-24 → 2026-02-26

**Key accomplishments:**
- Flow control repaired end-to-end: pause semantics standardized on `state_data.paused`, auto-resume now follows `auto_resume_at`, and cancel flow revokes queued work safely (FIX-01..03)
- Data integrity stabilized: missing quiz templates now fail soft, cycle math/constants unified across services, and failed messages are visible via DLQ retry monitoring (FIX-04..07)
- Dead code reduced with ImportError tombstones: 5 legacy flow packages/files removed from active runtime paths (~4,550 LOC) while preserving migration guidance (DEAD-01..05)
- Core flow layer decomposed: `_flow_functions.py`, `flow_core.py`, and `flow_management.py` split into focused modules with compatibility shims for existing imports (SPLIT-05..07)
- Service and saga layers completed: `sequential_message_handler`, `enhanced_flow_engine`, `flow_dashboard`, `flow_monitoring`, `saga/orchestrator`, `saga/compensation`, and `flow_integrity` split under maintained interfaces (SPLIT-01..04, SPLIT-08..10)

**Known Gaps (deferred):**
- Milestone archived without `v1.3-MILESTONE-AUDIT.md` (run `/gsd-audit-milestone` post-archive if formal verification record is required)
- Full AsyncSession migration (42+ remaining methods)
- Physician availability preferences model
- PromptedOutput validation confidence for `gemini-2.5-flash`

**Archive:** `.planning/milestones/v1.3-ROADMAP.md`, `.planning/milestones/v1.3-REQUIREMENTS.md`

---


## v1.4 AsyncSession & Test Stability (Shipped: 2026-02-28)

**Phases completed:** 9 phases, 54 plans, 108 tasks
**Git range:** `a1960486..cf3c404a` (199 commits)
**Lines changed:** +24,168 / -3,665 (net +20,503 LOC)
**Timeline:** 2026-02-26 → 2026-02-28 (3 days)

**Key accomplishments:**
- Alerts schema repaired: `alerts.type` column mapping fixed + PostgreSQL schema guard in test fixtures, unblocking the full test suite (SCHEMA-01, SCHEMA-02)
- Async foundation established: canonical `get_async_db`, DualSessionMixin, async engine (pool_size=5), backward-compat shims, and CI guard blocking AsyncSession in Celery tasks (FOUND-01..04)
- All 7 shared service groups migrated to AsyncSession: patient, quiz, analytics, communication, auth/session, infrastructure, and flow_monitoring — all support dual-mode Session/AsyncSession via DI (CRIT-01..03, SVC-01..07)
- Full API router migration complete: all 46+ router files across 9 groups (auth, patient, flow, message, quiz, analytics, admin, system, remaining) use `get_async_db` — zero `Depends(get_db)` in any request handler (API-01..09)
- Test stability achieved: SyncToAsyncSessionAdapter supports full AsyncSession contract (begin_nested, delete, add, scalars, get), pagination test fixed, source-level regression tests lock out sync DB regressions (TEST-01..03)
- Audit gaps closed: Phase 28 added awaitable wrappers to test adapters and migrated enhanced_reports.py to `get_async_db`

**Known Gaps (deferred):**
- Full Celery task async conversion (workers run in separate processes; sync Session is correct)
- 50+ files >500 lines needing split
- Physician availability preferences model (hardcoded Mon-Fri 08-17)
- Google ADK integration (dependency conflicts)
- Runtime API contract parity human verification (Phase 25)
- DualSessionMixin orphaned (services use inline Session|AsyncSession typing)

**Archive:** `.planning/milestones/v1.4-ROADMAP.md`, `.planning/milestones/v1.4-REQUIREMENTS.md`, `.planning/milestones/v1.4-MILESTONE-AUDIT.md`

---


## v1.5 Saga Orchestrator Deep Dive (Shipped: 2026-03-01)

**Phases completed:** 4 phases, 14 plans, 28 tasks
**Git range:** `30f26611..c4865c6d` (53 commits)
**Lines changed:** +7,225 / -59 (net +7,166 LOC)
**Timeline:** 2026-02-28 → 2026-03-01 (2 days)

**Key accomplishments:**
- Saga orchestrator made async-safe with dual-session DB adapters; SagaDBAdapterMixin extracted keeping orchestrator under 500-LOC contract; Pydantic v2 step serialization fixed (AUDIT-01..04)
- Two independent onboarding paths traced end-to-end across 15+ handoffs with parameter/return/session contract verification; FlowDispatcher classified as compatibility surface (TRACE-01..04)
- Pause/resume/cancel semantics fully traced and verified: three pause implementations compared, cancel confirmed independent from saga compensation lifecycle (TRACE-02, TRACE-03)
- Compensation integrity proven: every active step mapped to handler, reverse-order rollback (4->3->1) verified, flush-only transaction boundaries and idempotency guards tested (COMP-01..04)
- 40+ new tests covering saga happy path, per-handler compensation rollback, timeout/concurrency/retry exhaustion, shim export parity, and flow lifecycle (TEST-01..05)
- Documentation-code contract parity enforced through gap closure for TRACE-01/TRACE-03 and compensation hard-delete contract (Phases 30, 32)

**Known Gaps (deferred):**
- `AuditLog.severity` select error in admin stats router (pre-dates v1.4)
- Dual pause-key divergence (`paused` vs `flow_paused`) classified MEDIUM
- Saga performance profiling under concurrent load (PERF-01)
- Saga execution OpenTelemetry tracing (OBS-01)
- Saga state cleanup/archival (DATA-01)

**Archive:** `.planning/milestones/v1.5-ROADMAP.md`, `.planning/milestones/v1.5-REQUIREMENTS.md`

---
