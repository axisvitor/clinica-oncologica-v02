# Architecture Research

**Domain:** ADK stability/error hardening inside existing DDD FastAPI + Celery + Gemini + WhatsApp backend
**Researched:** 2026-03-05
**Confidence:** HIGH (codebase integration points), MEDIUM (ADK runtime/session behavior based on official docs), LOW (production-volume bottlenecks without live telemetry)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            API LAYER (FastAPI)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  /api/v2/adk/run                                                            │
│      │                                                                      │
│      ├── Request validation (ADKRunRequest)                                 │
│      ├── Auth/role guard (align with AI routers)                            │
│      └── ADKExecutionService (NEW facade)                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                      APPLICATION / DOMAIN AI SERVICES                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  ADKExecutionService (NEW)                                                   │
│      ├── PIISafeADKWrapper (existing safety boundary)                       │
│      ├── ADKRuntimeAdapter (NEW around run_adk_tool)                        │
│      ├── ADKErrorMapper (NEW: typed error taxonomy)                         │
│      └── ADKMetricsEmitter (NEW: latency/throughput/error)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                    AI INFRASTRUCTURE / INTEGRATION LAYER                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  app/ai/adk/runtime.py (MOD)                                                 │
│      ├── Runner + Agent + FunctionTool path                                 │
│      ├── SessionService strategy (InMemory -> Database via flag)             │
│      └── Deterministic fallback to direct handler                             │
│                                                                             │
│  app/ai/adk/tools.py (MOD) -> GeminiDomainClient -> GeminiClient             │
│  app/ai/adk/wrapper.py (MOD) -> sanitize_prompt_text_for_external_ai         │
├─────────────────────────────────────────────────────────────────────────────┤
│                        DATA + OPERATIONS LAYER                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  PostgreSQL (optional ADK session persistence)                               │
│  Redis/Dragonfly (existing cache/rate-limit/queue infra)                    │
│  Sentry + structured logs (post-OTel observability baseline)                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `ADKExecutionService` (NEW) | Single orchestrator for ADK calls from API/workers; owns control flow and failure semantics | Application-service facade under `app/services/ai/` |
| `PIISafeADKWrapper` (MOD) | Mandatory redaction boundary and output PII scan | Keep wrapper model already used in `app/ai/adk/wrapper.py` |
| `ADKRuntimeAdapter` (NEW) | Isolate Runner/function-tool execution details from routers | Thin adapter around `run_adk_tool` with typed exceptions |
| `ADKErrorMapper` (NEW) | Map runtime/integration errors to stable API and monitoring categories | Dataclass/Enum error taxonomy + mapper functions |
| `ADKMetricsEmitter` (NEW) | Emit ADK-specific latency/throughput/error metrics + breadcrumbs | Extend `app/services/ai/metrics.py` pattern + Sentry tags |
| `/api/v2/adk/run` router (MOD) | Transport concerns only (validation/auth/response shape) | Keep thin router; delegate execution to service |

## Recommended Project Structure

```
backend-hormonia/app/
├── api/v2/routers/
│   └── adk.py                         # MOD: auth + service delegation + error mapping
├── ai/adk/
│   ├── runtime.py                     # MOD: no silent exception swallowing
│   ├── tools.py                       # MOD: tool-level timeout/context contracts
│   ├── wrapper.py                     # MOD: structured event hooks
│   └── session_service.py             # NEW: session backend strategy
├── services/ai/
│   ├── adk_execution_service.py       # NEW: orchestration facade
│   ├── adk_errors.py                  # NEW: typed error taxonomy
│   ├── adk_observability.py           # NEW: metrics + breadcrumbs emitter
│   └── metrics.py                     # MOD: add ADK metric dimensions
├── schemas/v2/
│   └── adk.py                         # MOD: stable error envelope + trace metadata
└── tests/
    ├── api/v2/test_adk.py             # MOD: HTTP contract + auth + error mapping
    └── unit/
        ├── test_adk_tools_runtime.py  # MOD: fallback/runner/error paths
        └── test_adk_stability.py       # NEW: hardening regressions
```

### Structure Rationale

- **`services/ai/adk_*`:** hardening logic belongs in application services, not routers or low-level runtime internals.
- **`ai/adk/session_service.py`:** session backend choice is infrastructure detail; keeps runtime testable and switchable.
- **`schemas/v2/adk.py`:** contract must be explicit and versioned at API boundary for rollback-safe changes.

## Architectural Patterns

### Pattern 1: Service-Facade Stability Boundary

**What:** All ADK entrypoints (HTTP now, Celery later) call one application service that owns retries, fallbacks, and telemetry.
**When to use:** Any new ADK caller path to avoid policy drift.
**Trade-offs:** Adds one layer, but removes duplicated error handling and keeps rollback simple.

**Example:**
```python
result = await adk_execution_service.execute(
    prompt=payload.prompt,
    tool_name=payload.tool_name,
    caller="api_v2_adk",
    context=payload.context,
)
```

### Pattern 2: Typed Error Taxonomy (Not String Matching)

**What:** Normalize runtime failures into explicit classes (`ADKToolUnsupported`, `ADKRunnerTimeout`, `ADKSessionError`, `ADKGuardrailViolation`).
**When to use:** Router responses, metrics labels, alert routing, runbooks.
**Trade-offs:** Upfront mapping work, but prevents silent regressions and brittle log parsing.

**Example:**
```python
except ADKRunnerTimeout as exc:
    raise HTTPException(status_code=504, detail=to_public_error(exc))
```

### Pattern 3: Session Backend Strategy

**What:** Runtime asks a strategy provider for `InMemorySessionService` (default) or `DatabaseSessionService` (flagged rollout).
**When to use:** Move from single-process ephemeral sessions to durable multi-instance continuity.
**Trade-offs:** DB-backed sessions improve resiliency but add migration and operational overhead.

## Data Flow

### Request Flow (API path)

```
POST /api/v2/adk/run
    ↓
ADK router (validate + auth + request_id)
    ↓
ADKExecutionService.execute(...)
    ↓
PIISafeADKWrapper.safe_run(...)
    ↓
ADKRuntimeAdapter.run(...) -> run_adk_tool(...)
    ↓
Runner(FunctionTool) OR direct handler fallback
    ↓
GeminiDomainClient method -> GeminiClient.generate_content
    ↓
Normalize result/error -> emit metrics -> ADKRunResponse
```

### Request Flow (Celery path, future integration)

```
Celery task (sync Session world)
    ↓
async_to_sync(ADKExecutionService.execute)
    ↓
same ADK stability pipeline as API
    ↓
task result + structured failure category for retries/DLQ
```

### Key Data Flows

1. **Control-flow hardening:** router and worker callers stop invoking wrapper/runtime directly; all paths go through one service facade.
2. **Error-flow hardening:** runtime exceptions become typed categories before crossing API/task boundary.
3. **Observability flow:** each ADK execution emits `status`, `error_category`, `tool_name`, `latency_ms`, `caller` consistently.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-1k users | InMemory sessions acceptable; prioritize correctness and observability consistency |
| 1k-100k users | Switch ADK session strategy to DB-backed sessions; add timeout budgets + backpressure gates |
| 100k+ users | Split ADK execution into dedicated worker pool/queue and isolate model-intensive tool classes |

### Scaling Priorities

1. **First bottleneck:** opaque failures from mixed runtime exceptions; fix via typed taxonomy + stable envelopes.
2. **Second bottleneck:** session continuity across instances; fix via `DatabaseSessionService` strategy rollout.

## Anti-Patterns

### Anti-Pattern 1: Silent exception swallowing in runtime

**What people do:** catch broad exception in runner path and `pass` to fallback.
**Why it's wrong:** hides root cause, blocks alerts, and produces false-success behavior.
**Do this instead:** catch, classify, emit telemetry, then fallback only for explicitly allowed categories.

### Anti-Pattern 2: Router owns business recovery logic

**What people do:** add retries/fallbacks directly inside `app/api/v2/routers/adk.py`.
**Why it's wrong:** impossible to reuse safely in Celery path and creates policy drift.
**Do this instead:** keep router thin; centralize in `ADKExecutionService`.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Google ADK (`Runner`, `Agent`, `FunctionTool`, `SessionService`) | Wrapped by `ADKRuntimeAdapter` | Keep ADK-specific API out of router layer |
| Gemini via `GeminiDomainClient` | Tool handlers only | Preserve existing resilience stack in `GeminiClient` |
| Sentry | Structured tags + exception capture from service layer | Post-OTel baseline for ADK incident visibility |
| PostgreSQL | Optional `DatabaseSessionService` backend | Roll out with feature flag and additive schema migration |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `api/v2/routers/adk.py` -> `services/ai/adk_execution_service.py` | Direct async call | Router remains transport-only |
| `services/ai/adk_execution_service.py` -> `ai/adk/wrapper.py` | Direct async call | Mandatory LGPD gate before runtime |
| `wrapper.py` -> `runtime.py` | Typed request object | No raw dict contracts across this boundary |
| `runtime.py` -> `tools.py` | Registry lookup + context propagation | Deterministic tool dispatch per `tool_name` |
| `tools.py` -> `GeminiDomainClient` | Existing domain client methods | Reuse stable typed agent behavior |
| Celery tasks -> `ADKExecutionService` | `async_to_sync` bridge | Keep worker sync-session model unchanged |

## New vs Modified Modules (Concrete Scope)

| Module | Action | Why |
|--------|--------|-----|
| `app/services/ai/adk_execution_service.py` | NEW | Single control plane for ADK stability policy |
| `app/services/ai/adk_errors.py` | NEW | Shared error taxonomy for API + worker + alerts |
| `app/services/ai/adk_observability.py` | NEW | Unified ADK metrics/log/sentry emission |
| `app/ai/adk/session_service.py` | NEW | Backend strategy for session durability rollout |
| `app/api/v2/routers/adk.py` | MOD | Add auth parity, trace context, service delegation |
| `app/ai/adk/runtime.py` | MOD | Remove silent catch-all behavior; emit typed failures |
| `app/ai/adk/wrapper.py` | MOD | Keep safety gate + attach structured telemetry hooks |
| `app/ai/adk/tools.py` | MOD | Tighten context contract, timeout/validation, deterministic errors |
| `app/schemas/v2/adk.py` | MOD | Add stable error envelope (`code`, `message`, `retryable`) |
| `backend-hormonia/tests/*adk*` | MOD/NEW | Lock failure semantics and rollback-safe contracts |

## Recommended Build Order (Risk-Reducing + Rollback-Safe)

1. **Stabilize contracts first (no behavior change):** add error taxonomy + response envelope + trace metadata in schemas/tests; keep legacy runtime path active.
2. **Introduce service facade behind feature flag:** implement `ADKExecutionService` and route existing endpoint through it; fallback to current execution when flag off.
3. **Harden runtime internals:** refactor `runtime.py` to classify errors and stop silent swallowing; keep explicit allowed fallback categories only.
4. **Add observability parity:** emit ADK latency/throughput/error metrics and Sentry tags from service layer; add smoke alerts before widening rollout.
5. **Worker integration after API stability:** add Celery caller adapter (`async_to_sync`) only after API path metrics show stable error budget.
6. **Session durability rollout:** add `DatabaseSessionService` strategy as opt-in; start shadow mode, then gradual enablement; keep `InMemorySessionService` rollback switch.
7. **Finalize runbook + rollback switches:** document flags, thresholds, known error classes, and one-command rollback path.

### Rollback Safety Rules

- Keep `AI_ADK_STABILITY_ENABLED` (new flag) default-off until metrics baseline is healthy.
- Preserve current `/api/v2/adk/run` contract shape during migration; add fields additively only.
- Keep runtime fallback path until at least one full release cycle of stable error/latency metrics.
- Treat session persistence migration as additive and reversible (strategy flag, no destructive schema cutover).

## Sources

- Codebase inspection (HIGH):
  - `backend-hormonia/app/api/v2/routers/adk.py`
  - `backend-hormonia/app/ai/adk/runtime.py`
  - `backend-hormonia/app/ai/adk/tools.py`
  - `backend-hormonia/app/ai/adk/wrapper.py`
  - `backend-hormonia/app/schemas/v2/adk.py`
  - `backend-hormonia/scripts/check_agent_run_calls.py`
  - `backend-hormonia/tests/api/v2/test_adk.py`
  - `backend-hormonia/tests/unit/test_adk_tools_runtime.py`
  - `backend-hormonia/app/config/settings/integrations.py`
  - `backend-hormonia/app/core/setup/sentry.py`
- Official ADK docs (MEDIUM):
  - Sessions and `SessionService` implementations: https://google.github.io/adk-docs/sessions/session/
  - Function tool behavior and return normalization: https://google.github.io/adk-docs/tools-custom/function-tools/
  - ADK docs index/release navigation: https://google.github.io/adk-docs/

---
*Architecture research for: Clinica Oncologica v1.8 ADK Stability & Error Hardening*
*Researched: 2026-03-05*
