# Architecture Research

**Domain:** Healthcare WhatsApp AI messaging — oncology patient monitoring with LangGraph + FastAPI
**Researched:** 2026-02-22
**Confidence:** HIGH (based on direct codebase inspection + verified external patterns)

---

## Standard Architecture

### System Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                         CLIENT SURFACES                                │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐    │
│  │  Admin SPA       │  │  Quiz Next.js    │  │  WhatsApp        │    │
│  │  React 19 + Vite │  │  (short-link)    │  │  (Evolution API) │    │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘    │
└───────────┼─────────────────────┼────────────────────  ┼─────────────┘
            │                     │                       │
┌───────────▼─────────────────────▼───────────────────────▼─────────────┐
│                    FastAPI Application (main.py)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  API v2     │  │  Auth +     │  │  Webhook    │  │  WebSocket  │  │
│  │  Routers    │  │  LGPD Mware │  │  Handlers   │  │  Manager    │  │
│  └──────┬──────┘  └─────────────┘  └──────┬──────┘  └──────┬──────┘  │
│         │                                  │                │         │
│  ┌──────▼──────────────────────────────────▼────────────────▼──────┐  │
│  │                      Domain / Services Layer                     │  │
│  │  ┌────────────┐  ┌────────────┐  ┌─────────────┐               │  │
│  │  │  FlowCore  │  │  Saga      │  │  AI Layer   │               │  │
│  │  │  (prod)    │  │  Orchestr. │  │  LangGraph  │               │  │
│  │  └────────────┘  └────────────┘  └─────────────┘               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                      Infrastructure / Core                       │  │
│  │  RedisManager · CircuitBreaker · SessionManager · LGPD Services  │  │
│  └────────────────────────────┬─────────────────────────────────────┘  │
└───────────────────────────────┼────────────────────────────────────────┘
                                │
┌───────────────────────────────▼────────────────────────────────────────┐
│               Background Processing (Celery + Dragonfly)               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │ Flow Tasks   │  │ Quiz Tasks   │  │ Saga Retry   │  (38 beat tasks) │
│  │ Messaging    │  │ LGPD / Audit │  │ Monitoring   │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
└────────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼────────────────────────────────────────┐
│                          Data Stores                                   │
│  ┌──────────────────┐  ┌──────────────────────────────────────────┐   │
│  │ PostgreSQL/RDS   │  │ Dragonfly (Redis-compatible)             │   │
│  │ (ORM: sync SA)   │  │ DB0=broker DB1=cache DB2=sess DB3=rate  │   │
│  └──────────────────┘  └──────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| FastAPI routers (api/v2) | HTTP request routing, input validation, response serialization | Domain/services layer, schemas |
| FlowCore + FlowService (prod) | Day-based patient treatment flow progression, SQLAlchemy state | FlowStateRepository, WhatsApp, AI layer |
| FlowManager (QW-021) | Step-based flow execution engine with Pydantic contexts | FlowEngine, FlowValidator, integrations |
| AI Layer (langgraph/) | LangGraph graphs for humanization, sentiment, empathetic follow-up | Gemini via gemini_orchestrator, PII redaction |
| SagaOrchestrator | Distributed patient onboarding transaction with compensation | Redis distributed lock, all domain services |
| UnifiedWhatsAppService | Canonical messaging facade over Evolution API | Evolution API client, DLQ |
| RedisManager | Singleton Redis/Dragonfly client with pooling + circuit breaker | All layers that need Redis |
| Celery workers | Async background tasks: messaging, flows, quiz, saga retry | All services, Dragonfly broker |
| Celery Beat | 38 periodic tasks for flows, quizzes, alerts, reports | All task modules |

---

## Current LangGraph Integration Assessment

### What's Actually There

The codebase has **8 LangGraph graphs**, each compiled with `@lru_cache(maxsize=1)` and a Redis-backed `RedisCheckpointer` (with in-memory `MemorySaver` fallback):

| Graph | Nodes | Purpose |
|-------|-------|---------|
| `flow_message_graph` | load_flow_context → dispatch_send_mode | Route outbound message type |
| `flow_response_graph` | load_response_context → dispatch_response_continuation | Route inbound response handling |
| `humanization_graph` | humanize | Single-node: Gemini humanizes template text |
| `sentiment_graph` | sentiment | Single-node: Gemini sentiment classification |
| `generation_graph` | generate | Single-node: Gemini generic generation |
| `question_variation_graph` | question_variation | Single-node: Gemini question variant generation |
| `empathetic_follow_up_graph` | empathetic_follow_up | Single-node: Gemini empathetic message generation |

**Key Observation:** 5 of 8 graphs are single-node pipelines. Each graph compiles full LangGraph infrastructure (StateGraph, checkpointer, instrumentation wrapper) for what is functionally one `await llm.invoke(prompt)` call.

### Is LangGraph the Right Choice Here?

**Verdict: KEEP with rationalization, not replace.**

The architecture as-is is over-structured for single-node use cases but defensible because:

1. **The infrastructure is already invested and working.** LangGraph is installed, the Redis checkpointer is production-quality, `instrument_node` wraps all nodes with structured logging, and `guarded imports` provide degraded-mode operation. Ripping this out would introduce more risk than benefit.

2. **The 2-node routing graphs (flow_message, flow_response) ARE legitimate LangGraph use cases** — conditional branching on state, different execution paths.

3. **The single-node graphs are over-engineered but harmless at current scale.** The `@lru_cache` means graph compilation happens exactly once per process. The per-invocation overhead is the checkpointer write, which is a single Redis `setex`. At the throughput this system handles (oncology clinic, not WhatsApp at scale), this is negligible.

4. **Future expansion will benefit from the structure.** Adding retry logic, fallback nodes, or streaming would require no graph architecture changes.

**What to fix instead of replacing:**
- Convert `try/except ImportError` silent fallbacks to startup health check assertions (fail fast, not silent no-op)
- Add a `FeatureNotAvailableError` path for when LangGraph is missing rather than returning `None`
- Consider merging the 5 single-node AI graphs into one `unified_ai_graph` with routing based on `AIState.operation` — reduces compiled graph count from 8 to 3

---

## Dual Flow System Consolidation Strategy

### The Problem: Two Parallel Systems

```
Production System (flat files)              QW-021 System (package)
────────────────────────────────            ──────────────────────────────
app/services/flow_core.py                   app/services/flow/core/manager.py
app/services/flow_service.py                app/services/flow/core/engine.py
app/services/enhanced_flow_engine.py        app/services/flow/core/state_machine.py
app/services/flow_management.py             app/services/flow/core/context.py

SQLAlchemy PatientFlowState (ORM)           Pydantic FlowContext (in-memory)
Day-based progression                       Step-based progression
High production usage                       Low production usage
```

**The migration docstring in `flow_core.py` already names the intent correctly:** the organized `app.services.flow` package (QW-021) IS the intended consolidation target. The flat-file system is the legacy system.

### Recommended Consolidation: Strangler Fig Applied Internally

**Phase approach — do not do a big-bang rewrite:**

**Phase A (Preparation):** Make QW-021 system feature-complete.
- The QW-021 `FlowManager` already has lifecycle, error handlers, event broadcast, templates, integrations, and analytics sub-packages.
- Identify what the production flat-file system does that QW-021 does NOT yet cover — primarily the `PatientFlowState` SQLAlchemy persistence path.
- Add `AsyncSession`-aware persistence to `FlowContextRepository` so it can write to the same `patient_flow_states` table.

**Phase B (Facade + Routing):** Introduce a single `FlowDispatcher` facade that routes calls to either system based on a feature flag.
```python
# New: app/services/flow_dispatcher.py
class FlowDispatcher:
    def __init__(self, use_new: bool = False):
        self._new = FlowManager(db)  # QW-021
        self._old = FlowService(db)  # flat-file production

    async def advance_flow(self, patient_id, ...):
        if self._use_new_system:
            return await self._new.advance(...)
        return await self._old.advance(...)
```
- All callers (webhook handlers, Celery tasks, API routers) talk to `FlowDispatcher` only.
- Set `use_new=False` initially. Zero functional change.

**Phase C (Gradual Migration):** Enable the new system for new patients first. The QW-021 `FlowContext` is step-based — ensure it writes the `PatientFlowState` SQLAlchemy record for backward compatibility with dashboards and reporting.

**Phase D (Decommission):** When 100% of active patients are on the new system, tombstone the flat-file modules (`flow_core.py`, `enhanced_flow_engine.py`, etc.) using the existing tombstone pattern.

### Build Order Implications

The consolidation depends on `AsyncSession` migration for the QW-021 path (the flat-file system works with sync sessions; the new system should not inherit that).

**Recommended sequence:**
1. AsyncSession migration (hot paths) → removes sync-in-async blockers
2. FlowContextRepository gets AsyncSession support
3. FlowDispatcher facade introduced
4. Migration activated incrementally

---

## Sync-in-Async Migration Strategy

### The Problem

42+ methods annotated `# TODO(async-migration)` in 9 files block the FastAPI event loop with synchronous SQLAlchemy `Session` calls inside `async def` functions. **Performance impact is measured at ~550 req/s vs ~1400 req/s** for identical hardware (WebSearch verified).

### Recommended Approach: Phase by Throughput Priority, Not File Size

**Do not migrate all 42 methods in one sprint.** Migrate by impact.

**Tier 1 — Event Loop Killers (highest concurrency paths):**
These sit directly in async FastAPI request paths or Celery worker hot loops:

| File | Methods | Impact |
|------|---------|--------|
| `flow/sequential_message_handler.py` | 12 | Every inbound WhatsApp message |
| `flow_core.py` | 7 | Flow advance on message receipt |
| `enhanced_quiz_service.py` | 8 | Quiz response processing |
| `services/webhook/handlers/` (implied) | — | All inbound Evolution API webhooks |

**Tier 2 — Background Task Paths (less critical but still important):**

| File | Methods | Impact |
|------|---------|--------|
| `flow_alerts.py` | 5 | Alert generation in Celery workers |
| `flow_dashboard.py` | 4 | Dashboard data updates |
| `saga_orchestrator/compensation.py` | 5 | Saga rollback (high risk if event-loop blocked during distributed transaction) |
| `saga_orchestrator/steps.py` | 3 | Saga execution |

**Tier 3 — Lower Priority:**

| File | Methods | Impact |
|------|---------|--------|
| `firebase_user_sync_service.py` | 5 | Async sync task |
| `data_integrity_monitoring.py` | 5 | Monitoring job |

### Migration Pattern

**Two valid intermediate strategies exist:**

**Strategy A — run_in_executor (quick, safe, imperfect):**
```python
# Before: blocks event loop
def _load_patient_flow(self, patient_id: UUID) -> PatientFlowState:
    return self.db.query(PatientFlowState).filter(...).first()

# After: wraps in thread pool, unblocks event loop
async def _load_patient_flow(self, patient_id: UUID) -> PatientFlowState:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: self.db.query(PatientFlowState).filter(...).first()
    )
```
- Pros: Minimal code change per method, backward compatible
- Cons: Creates thread pool churn, does NOT give full async throughput gains, introduces risks with session lifecycle across thread boundaries

**Strategy B — AsyncSession (proper, higher change volume):**
```python
# Requires create_async_engine + AsyncSession throughout
async def _load_patient_flow(self, patient_id: UUID) -> PatientFlowState:
    result = await self.db.execute(
        select(PatientFlowState).where(PatientFlowState.patient_id == patient_id)
    )
    return result.scalar_one_or_none()
```
- Pros: Full performance gains (~1400 req/s), clean async, works with modern SQLAlchemy 2.0 patterns
- Cons: Requires query syntax migration throughout touched files

**Recommendation:** Use Strategy B for Tier 1 paths (they're the ones that matter). Use Strategy A as a short-term bridge for Tier 2-3 if timeline is constrained. **Never apply Strategy A to the Saga orchestrator** — session lifecycle across thread boundaries during compensation is a data integrity risk. Migrate the Saga to proper `AsyncSession` or leave it synchronous and wrap the entire saga invocation in `run_in_executor`.

### Celery Worker Compatibility

Celery workers are **synchronous by design**. The existing `asyncio.run()` / `async_to_sync` inconsistency is a real bug (identified in CONCERNS.md). The correct pattern is:

```python
# Correct: in Celery tasks that call async services
from asgiref.sync import async_to_sync

@celery_app.task
def send_scheduled_message(patient_id: str) -> None:
    async_to_sync(_send_message_async)(patient_id)  # correct
    # NOT: asyncio.run(_send_message_async(patient_id))  — leaks event loop
```

**When `AsyncSession` is introduced, Celery tasks must use a separate sync session factory** — the async session cannot be used in sync Celery worker context without `run_until_complete`.

The recommended pattern for dual-use code (called from both FastAPI and Celery):
```python
# Service method is sync, accepting session as parameter
def advance_flow_sync(db: Session, patient_id: UUID) -> FlowResult: ...

# Async wrapper for FastAPI routes
async def advance_flow(db: AsyncSession, patient_id: UUID) -> FlowResult:
    # Uses AsyncSession
    ...

# Celery task uses sync version directly
@celery_app.task
def advance_flow_task(patient_id: str) -> None:
    with SyncSession() as db:
        advance_flow_sync(db, UUID(patient_id))
```

---

## Component Boundaries — What Talks to What

### Strict Boundaries (must not be crossed)

```
AI Layer  →  Domain Services ONLY (never → Repositories directly)
AI Layer  →  PII Redaction (always, before Gemini calls)
Routers   →  Domain/Services ONLY (never → Repositories directly)
Celery    →  Services ONLY (never → AI Layer directly — use service method that wraps AI)
```

### Data Flow Direction

```
Inbound WhatsApp message:
  Evolution Webhook → FastAPI /webhook → WebhookHandler
    → FlowDispatcher.handle_response()
      → [new] FlowManager.process_step() OR [old] FlowCore.advance_day()
        → AI Layer (sentiment graph) if response classification needed
        → FlowStateRepository (persist state)
        → UnifiedWhatsAppService (send next message if needed)
          → AI Layer (humanization graph) → Gemini → PII-redacted response
          → Evolution API client

Outbound scheduled message:
  Celery Beat → messaging task
    → FlowDispatcher.get_next_message()
      → Template DB lookup
        → AI Layer (humanization graph) → Gemini
          → UnifiedWhatsAppService → Evolution API
```

### Layer Dependency Rules (dependency inversion respected)

```
api/ → domain/ → services/ → repositories/ → models/
                ↘ core/ (infrastructure: redis, auth, logging)
ai/ → services/ai/ → integrations/gemini_orchestrator
                   ↘ core/redis_manager (for checkpointing)
orchestration/ → services/ + repositories/ + core/distributed_lock
tasks/ → services/ (NEVER → api/)
```

---

## Architectural Patterns to Follow

### Pattern 1: Facade over External Integrations

**What:** All external service calls go through a single facade class. Nothing calls Evolution API, Gemini, or Firebase directly.
**When:** Any integration with a third-party API.
**Why:** Enables circuit breaking, retry, DLQ, and swap-out testing without touching callers.

Current implementations:
- `UnifiedWhatsAppService` (Evolution API facade)
- `GeminiOrchestrator` (Gemini facade, called by AI layer)
- `RedisManager` (Redis/Dragonfly facade)

**Extend this pattern to:** If a second AI provider is ever needed, add it as a `BaseAIProvider` with a factory, similar to `RedisManager`'s singleton pattern.

### Pattern 2: Repository Pattern with Typed Base

**What:** All DB access through typed repository classes. No raw `db.query()` outside of repositories.
**When:** Any data model access.

```python
# Correct
patient = await patient_repo.get_by_id(patient_id)

# Wrong — never do this in a service or router
patient = db.query(Patient).filter(Patient.id == patient_id).first()
```

**Important during async migration:** Repositories must be migrated to accept `AsyncSession` — the base class `BaseRepository` in `repositories/base.py` is the correct single point of change.

### Pattern 3: Tombstone Dead Code, Shim Old Locations

**What:** When retiring a module, replace with `raise ImportError` docstring (tombstone) or thin re-export shim. Never delete silently.
**When:** Any consolidation step (flow system, middleware, auth).
**Why:** Silent import failures are invisible bugs. Tombstones fail fast with a clear message.

```python
# Tombstone pattern (module no longer used)
"""
TOMBSTONE — [Module Name] (2026-XX-XX)
Replaced by: [canonical location]
Reason: [why replaced]
"""
raise ImportError(
    "[Module Name] has been removed. Use [canonical] instead."
)

# Shim pattern (old location kept for backward compatibility)
from app.canonical.module import MyClass  # noqa: F401  # shim
```

### Pattern 4: LangGraph Graphs as Cached Pipelines

**What:** Compile LangGraph graphs once with `@lru_cache`, use Redis checkpointer with MemorySaver fallback.
**When:** Any AI pipeline invocation.

```python
@lru_cache(maxsize=1)
def get_humanization_graph() -> Any:
    return build_humanization_graph()

# Caller
graph = get_humanization_graph()
result = await graph.ainvoke(state, config=build_graph_config(thread_id=patient_id))
```

**Improvement needed:** Add a startup health check that calls `get_humanization_graph()` and catches `RuntimeError("LangGraph is not installed")` — convert from silent `None` fallback to explicit startup failure.

### Pattern 5: Circuit Breaker Around External I/O

**What:** Wrap all calls to Evolution API, Gemini, Dragonfly with the `CircuitBreaker` from `app/resilience/circuit_breaker/`.
**When:** Any call that can fail and cause cascading timeouts.

The `RedisManager` already wraps Redis calls. The `UnifiedWhatsAppService` uses DLQ for failed deliveries. The AI layer currently does NOT have a circuit breaker for Gemini calls — this is a gap.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Raw `asyncio.run()` in Celery Tasks

**What people do:** `asyncio.run(my_async_service())` inside a Celery task function.
**Why it's wrong:** Creates and destroys a new event loop on every task invocation, leaking resources and causing "Event loop already running" errors on repeated calls.
**Do this instead:** `async_to_sync(my_async_service)()` from `asgiref.sync`.

### Anti-Pattern 2: SQLAlchemy `Session.query()` Inside `async def`

**What people do:** Call `self.db.query(Model).filter(...).first()` inside an `async def` function.
**Why it's wrong:** Blocks the FastAPI/uvicorn event loop. Under concurrent load, all simultaneous requests queue behind the blocking DB call.
**Do this instead:** Use `AsyncSession` with `await session.execute(select(Model).where(...))`.

### Anti-Pattern 3: `redis.keys("pattern:*")`

**What people do:** Use `redis_client.keys("*")` for cache invalidation or inspection.
**Why it's wrong:** Blocks the Redis server for the duration of the scan on large key sets. O(N) blocking operation.
**Do this instead:** `redis_client.scan_iter(match="pattern:*", count=100)` — lazy, non-blocking.

Already enforced in `RedisManager`; must be validated during any new Redis-touching code in the codebase.

### Anti-Pattern 4: Feature Flag Buried in Service Constructor

**What people do:** `FlowDispatcher(use_new=True)` hardcoded at call site.
**Why it's wrong:** Cannot be changed at runtime without deploying.
**Do this instead:** Read from `settings.FLOW_SYSTEM` env var in the constructor. Can be toggled in Railway without a redeploy.

### Anti-Pattern 5: Guarded Imports with `None` Fallback for Critical Features

**What people do:**
```python
try:
    from langgraph.graph import StateGraph
except ImportError:
    StateGraph = None  # silently degrades
```
**Why it's wrong:** When LangGraph is missing (misdeployment, broken package), message humanization silently does nothing instead of failing visibly. Patients receive un-humanized robotic messages without any alert.
**Do this instead:** Validate at startup in `app/core/lifespan.py` — raise `RuntimeError` if LangGraph is absent in production.

---

## Recommended Refactoring Order

The order matters because of dependencies between work items:

```
1. Security fixes (placeholder auth, LGPD audit persistence)
   ─── No dependencies, unblocks compliance. Do first.

2. Bug fixes (asyncio.run() → async_to_sync, physician availability stub)
   ─── No dependencies. Low risk. Do early.

3. AsyncSession migration — Tier 1 paths (webhook handler, sequential_message_handler)
   ─── Prerequisite for: flow consolidation (QW-021 needs async-capable repos)
   ─── Prerequisite for: full performance gains

4. Flow consolidation (FlowDispatcher facade + strangler fig)
   ─── Depends on: AsyncSession in FlowContextRepository
   ─── Prerequisite for: decommissioning flat-file flow system

5. AI audit enum + batch re-encryption
   ─── Depends on: nothing critical. Can run parallel to 3-4.
   ─── Prerequisite for: LGPD compliance sign-off

6. Large file splits (auth_dependencies.py, flow_monitoring.py, etc.)
   ─── Depends on: 3 (async migration) because split files will be re-organized
   ─── No external dependency otherwise

7. Shim removal + dead code cleanup
   ─── Depends on: 4 (flow consolidation complete), 6 (splits done)
   ─── Must verify no callers remain before tombstoning
```

---

## Scaling Considerations

| Scale | What Breaks First | Fix |
|-------|------------------|-----|
| Current (prototype) | sync-in-async event loop blocking | AsyncSession migration (Tier 1 paths) |
| ~500 concurrent patients | Celery Beat SPOF | redbeat distributed lock (multiple Beat instances) |
| ~2000 concurrent patients | WebSocket manager in-memory state | Move connection registry to Redis pub/sub (redis_pubsub_manager.py already exists) |
| ~5000+ patients | Single Dragonfly instance as sole cache+broker+sessions | Separate Dragonfly instances per role; circuit breakers already in place provide degraded-mode operation |

### Scaling Priority

1. **First bottleneck:** Sync SQLAlchemy blocking event loop under concurrent webhook + request load. Fix with AsyncSession on hot paths.
2. **Second bottleneck:** Celery Beat single instance. Fix with `redbeat` (minimal change: add redbeat to requirements, configure URL, deploy multiple Beat containers).
3. **Third bottleneck:** WebSocket in-memory connection registry breaks multi-pod deploy. `redis_pubsub_manager.py` already exists — integration with WebSocket manager is the gap.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Evolution API (WhatsApp) | `UnifiedWhatsAppService` facade + HTTP client | DLQ for failed deliveries; webhook signature validation |
| Google Gemini | `GeminiOrchestrator` facade + LangGraph nodes | PII redaction always applied before call; circuit breaker missing — gap |
| Firebase Auth | `auth_dependencies.py` token verification | TEST_TOKEN_REGISTRY bypass must be removed from production binary |
| Dragonfly/Redis | `RedisManager` singleton with 4 logical DBs | Circuit breaker already present; SSL in production |
| Sentry | Initialized at lifespan in `core/setup/sentry.py` | Structured logging context propagated |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| FastAPI ↔ Celery | Dragonfly message queue (broker) | Celery tasks defined in `app/tasks/`; called via `.delay()` or `.apply_async()` |
| FastAPI ↔ WebSocket clients | Redis Pub/Sub via `redis_pubsub_manager.py` | Multi-instance safe in theory; WebSocket manager integration incomplete |
| AI Layer ↔ Services | Direct Python function calls | LangGraph graphs called synchronously from services (no queue); LangGraph nodes are synchronous too — acceptable |
| Saga ↔ Redis | Distributed lock via `core/distributed_lock.py` | Must maintain lock during full saga execution; blocking sync calls in steps risk lock expiry |

---

## Sources

- Direct codebase inspection: `backend-hormonia/app/ai/langgraph/graphs.py`, `runtime.py`, `nodes_ai.py`, `state.py`
- Direct codebase inspection: `backend-hormonia/app/services/flow_core.py`, `app/services/flow/core/manager.py`
- Direct codebase inspection: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/CONCERNS.md`
- [FastAPI SQLAlchemy async performance: ~1400 req/s async vs ~550 req/s sync](https://leapcell.io/blog/building-high-performance-async-apis-with-fastapi-sqlalchemy-2-0-and-asyncpg) — MEDIUM confidence (WebSearch, single source)
- [LangGraph production FastAPI template patterns](https://github.com/wassim249/fastapi-langgraph-agent-production-ready-template) — MEDIUM confidence (WebSearch)
- [Strangler Fig Pattern for internal service consolidation](https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig) — HIGH confidence (official Azure Architecture docs)
- [SQLAlchemy asyncio documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) — HIGH confidence (official SQLAlchemy docs)
- [async_to_sync vs asyncio.run Celery pattern](https://medium.com/@neverwalkaloner/fastapi-with-async-sqlalchemy-celery-and-websockets-1b40cd9528da) — MEDIUM confidence (WebSearch, community source)
- [LangGraph overhead for single-node graphs](https://github.com/langchain-ai/langgraph/discussions/4595) — LOW confidence (community discussion, no official benchmark)

---

*Architecture research for: Healthcare WhatsApp AI Messaging — Oncology Patient Monitoring*
*Researched: 2026-02-22*
