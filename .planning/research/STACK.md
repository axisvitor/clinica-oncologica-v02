# Stack Research

**Domain:** Healthcare WhatsApp patient monitoring with AI-humanized questionnaires (refinement/production readiness)
**Researched:** 2026-02-22
**Confidence:** HIGH (core framework choices), MEDIUM (LangGraph trade-offs), HIGH (DB templates verdict)

---

## Executive Verdict: What to Keep, Change, or Add

| Component | Status | Action |
|-----------|--------|--------|
| Python 3.13 + FastAPI + Pydantic v2 | Keep | Optimal for 2025/2026 |
| SQLAlchemy sync Session | Problematic | Migrate hot paths to AsyncSession |
| LangGraph (flow orchestration graphs) | Keep | Justified for stateful multi-step flows |
| LangGraph (single-node AI graphs) | Overengineered | Replace with direct async Gemini calls |
| Celery + Celery Beat | Keep | Right tool for 38 periodic tasks at this scale |
| Dragonfly (Redis-compatible) | Keep | Production-proven, 100% API-compatible |
| Evolution API (WhatsApp) | Monitor | Unofficial protocol risk; plan Cloud API migration path |
| Google Gemini 2.0 Flash | Keep | Cost-optimal for healthcare message humanization |
| Templates in database | Keep | Correct pattern; optimize retrieval with caching |
| Firebase Auth | Keep | No change needed |

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.13 | Runtime | Latest stable with JIT improvements; already in use |
| FastAPI | >=0.128.0 | HTTP API | Async-first, Pydantic v2 native, production-proven |
| Pydantic v2 | >=2.12.5 | Validation + settings | 5-50x faster than v1; already migrated |
| SQLAlchemy 2.0 | >=2.0.45 | ORM | AsyncSession available; sync session is the debt |
| Alembic | >=1.14.1 | Migrations | Standard Python ORM migration tool |
| Uvicorn | >=0.39.0 | ASGI server | Correct for FastAPI production |
| Celery | >=5.6.2 | Task queue + periodic scheduler | The right tool for 38 periodic tasks requiring distributed execution, retries, and DLQ |
| Dragonfly | Latest stable | Redis-compatible broker/cache | 25x throughput vs Redis, 100% redis-py compatible, production-deployed by thousands of companies |
| LangGraph | 1.0.9 | Stateful flow orchestration only | Use only for graphs with conditional edges, multiple nodes, or state persistence requirements |
| Google Gemini 2.0 Flash | Latest via langchain-google-genai | AI message humanization | $0.10/1M input tokens; sub-second latency; cost-optimal for this volume |
| Evolution API | v2 | WhatsApp integration | Currently integrated; acceptable for prototype/early production; plan migration path |

### The LangGraph Decision: When to Use vs When Not To

This is the central question of this research. The answer is nuanced: **the current codebase uses LangGraph in two fundamentally different ways, and only one is justified.**

#### Justified Use: Multi-node Stateful Flow Graphs

`build_flow_message_graph` and `build_flow_response_graph` are legitimately complex:
- Conditional routing (`_route_after_load`, `_route_after_response_load`)
- Multiple nodes with business logic (`load_flow_context` → `dispatch_send_mode`)
- State carries patient context, flow state IDs, message indexes, send modes
- External dependency injection via `config["configurable"]["handler"]`
- Awaiting-response state management across async operations

For these graphs, LangGraph's value is real: explicit state typing, testable nodes, and the graph structure itself documents the routing logic. **Keep these as LangGraph graphs.**

Confidence: HIGH — verified against actual code and LangGraph 1.0 production-readiness claims.

#### Overengineered Use: Single-Node AI Graphs

`build_humanization_graph`, `build_sentiment_graph`, `build_generation_graph`, `build_question_variation_graph`, `build_empathetic_follow_up_graph` are all this pattern:

```
START → single_node → END
```

Each is a single async function call wrapped in `StateGraph(AIState)` boilerplate. The `@lru_cache` on the compiled graph shows awareness of overhead. These graphs have:
- No conditional edges
- No routing decisions
- No state persistence across calls
- No multi-actor coordination

**Benchmark data**: LangGraph adds ~14ms framework overhead per invocation vs ~3-6ms for direct calls. For a single humanization call (already dominated by Gemini latency of 300-800ms), this is negligible in absolute terms — but architecturally, wrapping a single async function in a StateGraph is pure complexity with no benefit.

**Recommendation: Replace single-node graphs with direct async Gemini calls via the existing `GeminiClient`.** The `GeminiClient.generate_content()` abstraction already handles retry, output profiles, and PII redaction. The graph infrastructure for these is dead weight.

Migration is low-risk: the compiled graphs are `@lru_cache`'d, so callers just invoke them once. Replace callers to call `client.generate_content(prompt, profile=...)` directly.

Confidence: HIGH — based on actual code analysis + LangGraph overhead benchmarks.

#### LangGraph 1.0 Production Status

LangGraph reached 1.0 in October 2025 (current version 1.0.9 released 2026-02-19). The 1.0 release:
- Commits to no breaking changes until 2.0
- Supports Python 3.10–3.13
- Durable execution with checkpointing (not relevant here — you use `@lru_cache` not persistent checkpointers)
- Production adoption: Uber, LinkedIn, Klarna

**Known issue**: `langgraph-runtime-postgres` package is missing from PyPI (as of early 2026), blocking PostgreSQL backend. This is not relevant to the current use — the codebase uses in-memory compiled graphs without checkpointing.

### The Async Migration Decision

The codebase has 42+ methods annotated `# TODO(async-migration)` because SQLAlchemy sync `Session` is used throughout while FastAPI runs on asyncio. The pattern `await asyncio.to_thread(lambda: db.query(...).first())` is correct but suboptimal — it offloads sync blocking I/O to a thread pool, which consumes threads and adds latency.

**What the research says**: The combination of FastAPI + SQLAlchemy 2.0 AsyncSession + asyncpg is the established 2025 production pattern for high-performance APIs. The migration path is:
1. `create_async_engine` with `asyncpg` dialect
2. `async_sessionmaker` providing `AsyncSession`
3. FastAPI dependencies yield `AsyncSession` per request
4. All `.query()` calls become `await session.execute(select(Model)...)`

**Verdict for this project**: Full migration is the correct long-term direction but is a large project (165+ sync call sites in 65+ files per project notes). The pragmatic approach for production readiness:
- **Hot paths** (request handlers that call the database): migrate to AsyncSession first
- **Celery tasks**: these run outside FastAPI's event loop and can legitimately use sync Session with run_sync() — no migration needed
- **LangGraph flow nodes**: already use `asyncio.to_thread()` correctly as a bridge; clean up with AsyncSession when migrating the hot paths

### The Templates-in-Database Decision

**Verdict: Keep templates in database. This is the correct approach.**

Rationale:
- WhatsApp message templates for healthcare follow-up need to be updated by clinic staff without code deployments (new treatment protocols, seasonal messaging, physician preference)
- AI humanization requires the template as structured input to the Gemini prompt — the template is data, not logic
- Database storage enables per-flow-kind, per-day configuration (exactly what `day_config` provides)
- Versioning and audit trail are possible with DB-stored templates (important for LGPD compliance)

**What to optimize**: Template retrieval is currently synchronous (SQLAlchemy sync query). Templates are stable data that changes infrequently. Add a Redis-backed cache layer with TTL (30-60 minutes) to eliminate DB round-trips on every message send. The `RedisManager` infrastructure already exists.

The pattern: `get_day_config(flow_kind, day_number)` should check Redis first, fallback to DB, write to Redis on miss.

Confidence: HIGH — based on actual code analysis + WhatsApp healthcare best practices.

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| langchain-google-genai | >=2.1.12 | Gemini API access via LangChain | Required for current Gemini integration; consider migrating to `google-genai` SDK directly if removing LangChain |
| google-genai | Latest | Google's official async Gemini SDK | Use if removing LangChain overhead; `from google import genai` |
| asyncpg | >=0.30.0 | Async PostgreSQL driver | Required for AsyncSession migration; already in requirements |
| psycopg[binary] | >=3.2.13 | Sync PostgreSQL driver | Keep for Celery tasks and Alembic migrations |
| tenacity | >=8.2.3 | Retry with exponential backoff | Keep; used for Gemini API retries |
| aiobreaker | >=1.2.0 | Async circuit breaker | Keep; existing resilience pattern |
| httpx | >=0.28.1 | Async HTTP client | Keep; Evolution API calls |
| fakeredis | >=2.20.0 | In-memory Redis for tests | Keep; essential for fast test isolation |
| pytest-asyncio | >=0.23.0 | Async test support | Keep; asyncio_mode=auto configured |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| Black (py313) | Code formatter | Line-length=120; already configured |
| ruff | Linter (F rules) | Minimal config; consider enabling more rules for production readiness |
| mypy | Type checking | Currently non-blocking (`|| true`); should be blocking for production |
| bandit | Security scanning | Keep; important for healthcare data |
| pytest-cov | Coverage reporting | Target 80%+ on core domain, saga, and AI paths |

---

## Alternatives Considered

| Category | Current/Recommended | Alternative | Why Not Alternative |
|----------|---------------------|-------------|---------------------|
| AI Orchestration (multi-node flows) | LangGraph 1.0.9 | CrewAI, OpenAI Agents SDK | LangGraph is optimal for deterministic stateful flows with conditional routing; CrewAI is for role-based multi-agent; OpenAI SDK is OpenAI-specific |
| AI Orchestration (single AI calls) | Direct GeminiClient.generate_content() | LangGraph single-node graph | No benefit from graph abstraction for linear single-call patterns; removes ~14ms overhead and complexity |
| Background tasks | Celery 5.x + Celery Beat | Dramatiq, RQ, APScheduler | Celery is correct for 38 periodic tasks requiring distributed execution, retry, DLQ, and multi-broker support; alternatives lack this combination |
| Redis-compatible store | Dragonfly | Redis (OSS), Valkey | Dragonfly is 100% API-compatible with zero migration cost; 25x throughput advantage; production-proven |
| WhatsApp integration | Evolution API (current) | WhatsApp Cloud API (Meta official) | Cloud API has official support, SLAs, compliance path; Evolution API uses unofficial Baileys protocol with ban/disconnect risk |
| LLM provider | Google Gemini 2.0 Flash | OpenAI GPT-4o-mini, Claude Haiku | Gemini Flash is cost-optimal ($0.10/1M input tokens) and Google provides native LangChain integration; switching requires re-testing prompt behavior |
| ORM | SQLAlchemy 2.0 async | SQLModel, Tortoise ORM | SQLAlchemy 2.0 is the mature standard; already integrated; AsyncSession is the migration target |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Single-node LangGraph graphs for AI calls | Adds boilerplate, ~14ms overhead, complexity with zero benefit for linear single-call patterns | Direct `GeminiClient.generate_content()` call |
| `asyncio.run()` inside async context | Creates nested event loop; known bug in this codebase | `await` or `asyncio.to_thread()` for sync code |
| SQLAlchemy `db.query()` in FastAPI request handlers | Blocks event loop thread; causes concurrency degradation under load | `AsyncSession` with `await session.execute(select(...))` |
| `redis.keys()` in any context | O(N) blocking scan freezes Redis; already documented in project | `scan_iter(match=pattern, count=100)` |
| `langgraph-checkpoint-postgres` (PyPI missing) | `langgraph-runtime-postgres` package is missing from PyPI as of early 2026 | In-memory compiled graphs with `@lru_cache` (current approach) or custom checkpoint implementation |
| LangGraph Platform / LangGraph Cloud | Paid, managed; overkill for this scale and usage | Self-hosted compiled graphs with `@lru_cache` |
| APScheduler | Removed from project correctly; creates in-process scheduling that doesn't scale across workers | Celery Beat (already in use) |
| Evolution API without fallback | Unofficial Baileys protocol can result in account bans; no SLA | Add WhatsApp Cloud API as fallback for critical messages |

---

## Stack Patterns by Context

**For AI message humanization (single LLM call):**
- Call `GeminiClient.generate_content(prompt, profile=MESSAGE_HUMANIZED)` directly
- No LangGraph wrapper needed
- Already structured correctly in `nodes_ai.py` — just remove the graph scaffolding

**For flow orchestration (stateful, multi-step):**
- Keep LangGraph with `StateGraph`, `@lru_cache` compiled graph
- The flow_message_graph and flow_response_graph are valid uses
- Do not add persistent checkpointing until `langgraph-runtime-postgres` is stable on PyPI

**For database operations in FastAPI request handlers:**
- Use `AsyncSession` from `async_sessionmaker`
- Inject via FastAPI `Depends(get_async_db_session)`
- The existing `base_v2.py` repository pattern should be adapted to `AsyncSession`

**For database operations in Celery tasks:**
- Celery workers have their own event loop per task
- Sync `Session` is acceptable here; use `asyncio.run()` only at the top level of a task, never nested
- Alternatively, use `asyncpg` directly for async operations in tasks

**For template retrieval (templates in DB):**
- Add Redis cache layer in `_get_day_config()`:
  ```python
  cache_key = f"day_config:{flow_kind}:{day_number}"
  cached = await redis_manager.get(cache_key)
  if cached:
      return json.loads(cached)
  config = db.query(FlowTemplate)...
  await redis_manager.setex(cache_key, 1800, json.dumps(config))
  return config
  ```

---

## Production Readiness Gaps (Current Stack)

These are not stack replacements — they are the production-readiness work needed with the existing stack:

| Gap | Severity | Action |
|-----|----------|--------|
| 42+ sync-in-async methods blocking event loop | HIGH | Migrate FastAPI request-path methods to AsyncSession; Celery tasks are lower priority |
| Single-node LangGraph graphs (5 graphs) | MEDIUM | Replace with direct GeminiClient calls; reduces complexity and marginal overhead |
| Evolution API unofficial protocol risk | MEDIUM | Acceptable for current scale; document migration path to Cloud API for >500 patients |
| mypy non-blocking in CI | MEDIUM | Enable type checking as CI gate; healthcare code should be type-safe |
| Template retrieval uncached | LOW | Add Redis TTL cache in `_get_day_config()`; reduces DB load on every message send |
| Dual flow systems (production vs QW-021) | MEDIUM | Consolidate to production `flow_core.py` system; QW-021 is low-production-use per project notes |

---

## Version Compatibility

| Package | Version | Compatible With | Notes |
|---------|---------|-----------------|-------|
| LangGraph | 1.0.9 | Python 3.10–3.13, langgraph-prebuilt | Pin minor version; `langgraph-prebuilt==1.0.2` had breaking change without proper constraints (GitHub issue #6363) |
| langchain-google-genai | >=2.1.12 | langchain-core >=1.2.7 | Google officially partners with LangChain; stable integration |
| SQLAlchemy | >=2.0.45 | asyncpg >=0.30.0 | asyncpg 0.29.0+ may have issues with `create_async_engine`; test before pinning |
| Celery | >=5.6.2 | redis >=6.4.0, Dragonfly | Dragonfly is 100% Redis protocol compatible; no changes needed |
| Pydantic v2 | >=2.12.5 | FastAPI >=0.128.0 | Already on v2; do not mix v1 validators |
| redis (client) | >=6.4.0 | Dragonfly, SSL | Uses `ssl_context` for Dragonfly TLS; keep |

---

## Installation

```bash
# Core (already installed — for documentation purposes)
pip install fastapi uvicorn[standard] pydantic[email] pydantic-settings sqlalchemy alembic

# AI stack
pip install langchain-core langchain-google-genai langgraph

# Database drivers
pip install psycopg[binary] asyncpg

# Task queue
pip install celery redis

# Resilience
pip install tenacity aiobreaker httpx

# Auth / Security
pip install firebase-admin pyjwt cryptography passlib[bcrypt] argon2-cffi

# Observability
pip install sentry-sdk[fastapi] opentelemetry-sdk prometheus-client structlog

# Dev tools
pip install -U pytest pytest-asyncio pytest-cov fakeredis pytest-mock black ruff mypy bandit
```

---

## Sources

- LangGraph PyPI — version 1.0.9, release date 2026-02-19, Python 3.10–3.13 supported: https://pypi.org/project/langgraph/
- LangChain blog — LangGraph 1.0 production readiness, Uber/LinkedIn/Klarna adoption: https://blog.langchain.com/langchain-langgraph-1dot0/
- ZenML blog — LangGraph alternatives comparison, framework overhead benchmarks (~14ms for LangGraph): https://www.zenml.io/blog/langgraph-alternatives
- Dragonfly vs Redis 2025 — 25x throughput, production deployment data: https://martinuke0.github.io/posts/2025-12-11-dragonfly-vs-redis-a-practical-data-backed-comparison-for-2025/
- Dragonfly official — scaling and performance vs Redis: https://www.dragonflydb.io/blog/scaling-performance-redis-vs-dragonfly
- Google AI pricing — Gemini 2.0 Flash: $0.10/1M input, $0.40/1M output: https://ai.google.dev/gemini-api/docs/pricing
- Evolution API risks — unofficial Baileys protocol production issues: https://wasenderapi.com/blog/evolution-api-problems-2025-issues-errors-best-alternative-wasenderapi
- FastAPI + AsyncSQLAlchemy 2.0 patterns 2025: https://dev-faizan.medium.com/fastapi-sqlalchemy-2-0-modern-async-database-patterns-7879d39b6843
- LangGraph GitHub issue #6363 — prebuilt version constraint: https://github.com/langchain-ai/langgraph/issues/6363
- LangGraph GitHub issue #6709 — runtime-postgres missing from PyPI: https://github.com/langchain-ai/langgraph/issues/6709
- Celery production patterns 2025: https://judoscale.com/blog/choose-python-task-queue
- Actual codebase analysis: `backend-hormonia/app/ai/langgraph/graphs.py`, `nodes.py`, `nodes_ai.py`

---

*Stack research for: Healthcare WhatsApp patient monitoring — refinement/production readiness*
*Researched: 2026-02-22*
