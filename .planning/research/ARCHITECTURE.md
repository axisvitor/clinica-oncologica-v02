# Architecture Research

**Domain:** Healthcare WhatsApp monitoring — Frontend quality overhaul + Google ADK integration
**Researched:** 2026-03-03
**Confidence:** HIGH (direct codebase inspection + official ADK release notes)

---

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTENDS (Firebase Hosting)              │
├──────────────────────────┬──────────────────────────────────┤
│  frontend-hormonia        │  quiz-mensal-interface           │
│  React 19 + Vite          │  Next.js 14 + React 18          │
│  shadcn/ui (Radix)        │  shadcn/ui (Radix)              │
│  TanStack Query v5        │  fetch + CSRF in RAM            │
│  Firebase Auth + sessions │  HttpOnly cookies               │
│  WS real-time             │  Direct API (no proxy)          │
└──────────┬───────────────┴──────────────────────────────────┘
           │  HTTPS + session cookie
           ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI v2 (Railway)                       │
│  DDD: API -> Domain -> Services -> Infrastructure           │
│  All routers: AsyncSession                                   │
│  Middleware: CORS, LGPD, Security, CSRF, Cache, Compress    │
├────────────────────┬────────────────────────────────────────┤
│  AI Layer (v1.2)   │  WhatsApp Layer (v1.6)                 │
│  GeminiDomainClient│  WuzAPI (Go/whatsmeow) -- hard cut     │
│  4 PydanticAI agents│  No Evolution fallback                │
│  PIISafeAgent guard │  unified_whatsapp_service.py          │
│  google-genai SDK  │  webhook HMAC validation               │
├────────────────────┴────────────────────────────────────────┤
│  Saga Orchestrator         │  FlowDispatcher (facade)        │
│  Async-safe dual-session   │  Direct async Python functions  │
│  Compensation + trace      │  pause/resume/cancel            │
├─────────────────────────────────────────────────────────────┤
│  Celery Beat (38 tasks)    │  Dragonfly (Redis-compat)       │
│  Sync Session (by design)  │  4 DBs: broker/cache/sess/rl   │
└─────────────────────────────────────────────────────────────┘
│  PostgreSQL (AWS RDS)                                        │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Status |
|-----------|---------------|--------|
| `frontend-hormonia` | Admin SPA -- physicians, patients, flows, monitoring | Needs quality pass |
| `quiz-mensal-interface` | Patient quiz via short link -- HttpOnly cookie session | Needs quality pass |
| `GeminiClient` | Raw Gemini calls: rate limit, circuit breaker, cache, PII redact | Stable |
| `GeminiDomainClient` | Domain methods: humanize, sentiment, variation, empathy | Stable |
| `PIISafeAgent` | LGPD wrapper around all Pydantic AI agent `.run()` calls | Stable, CI-enforced |
| `app/core/tracing.py` | OTel wrapper with mock fallback -- the only OTel import file | Removal target |
| OTel block in requirements.txt | 7 opentelemetry-* packages + protobuf>=5 | Removal target |
| `FlowDispatcher` | Stable facade routing enrollments; callers never see flow internals | Stable |
| `SagaOrchestrator` | Async-safe compensation, dual-session, 40+ tests | Stable |

---

## Frontend Architecture: admin SPA (frontend-hormonia)

### Current Structure

```
frontend-hormonia/src/
├── app/
│   ├── providers/         # AuthContext (Firebase + session)
│   ├── routes/            # routeConfig, routeDefinitions, AdminRoutes.lazy
│   └── styles/
├── components/
│   ├── auth/              # ProtectedRoute, ReAuthenticationModal
│   ├── common/            # FileUpload, LoadingStates
│   ├── error/             # ErrorBoundary
│   ├── hive-mind/         # AgentSwarm, SystemHealth (legacy UI)
│   ├── layout/            # Layout, Sidebar, Header, Breadcrumb, Nav
│   ├── monitoring/        # SystemStatus
│   └── ui/                # shadcn/ui primitives
├── config/
│   └── mock.config.ts     # Mock mode toggle
├── contexts/
│   └── AuthContext.tsx
├── features/              # Domain-sliced features (20+ slices)
│   ├── admin/             # AdminDashboard, UsersTab, AuditLogViewer
│   ├── ai/                # AIChatInterface, AIAnalyticsDashboard, etc.
│   ├── analytics/         # AIPredictionsPanel, TrendAnalysisChart
│   ├── auth/              # ProtectedRoute, ReAuthenticationModal
│   ├── dashboard/         # MetricCard, Charts, RecentActivity
│   ├── flow-designer/     # Canvas, Nodes, Properties, Validator
│   ├── flows/             # FlowsTable, FlowAnalyticsDashboard
│   ├── monitoring/        # SystemStatus
│   ├── patients/          # PatientsTable, PatientDetail, AI analysis
│   ├── settings/          # SettingsSection, sidebar, sections
│   ├── templates/         # template management
│   └── whatsapp/          # WhatsAppDashboard, instances, messages
├── hooks/                 # 30+ hooks split across api/, admin/, auth/
├── lib/
│   ├── api-client/        # Modular: auth, patients, analytics, admin...
│   ├── api-client.ts      # Backward compat shim
│   ├── api.ts             # Legacy file (check for actual callers)
│   ├── types/             # api.ts (re-export barrel, 526 lines)
│   └── [utils, logger, flow-engine, mappers, react-query...]
├── mocks/                 # 7 mock data files (patients, flows, alerts...)
├── monitoring/            # sentry.ts
├── pages/                 # 20 page-level components (mixed routing)
├── services/
│   ├── firebase-auth.ts   # Firebase + session management
│   └── whatsapp/          # WhatsAppService.ts (wraps apiClient)
└── types/                 # 15 type files: api.ts, shared, auth, medico...
```

### Key Frontend Issues Identified

**Dead Code -- Evolution API (fully tombstoned backend since v1.6):**
- `features/whatsapp/WhatsAppDashboard.tsx` -- gated on `VITE_ENABLE_EVOLUTION=true`; always shows "disabled" state since backend no longer supports it. Entire dashboard is effectively dead UI.
- `features/admin/tabs/AdminSettingsTab.tsx:203` -- Evolution API URL form field still visible in admin settings.
- `lib/env-validator.ts:266` -- still validates `VITE_ENABLE_EVOLUTION` and `VITE_EVOLUTION_API_URL`.
- `lib/runtime-config.ts:51-52` -- Evolution fields still in type definition and defaults.

**Stale AI Provider References:**
- `config.ts:248-250` -- JSDoc comments reference `VITE_OPENAI_API_KEY` and `VITE_LANGCHAIN_API_KEY` (backend is Gemini-only since v1.2; these env vars are never read).
- `types/api.ts:766` -- `AIConfig.openai_model` field (backend has no OpenAI integration; field is dead).
- `lib/types/api.ts` -- eight `@deprecated` re-export markers indicating consolidation is incomplete.

**Type Duplication:**
- `src/types/api.ts` (884 lines) + `src/lib/types/api.ts` (526-line re-export barrel) + 15 other type files create confusion about canonical type source.
- `lib/api-client/types.ts` defines `AIInsight`, `AIInsights`, `AIRecommendations` and is imported alongside `types/api.ts:AIInsight` in some components.

**Mock Layer Drift:**
- `src/mocks/` and `src/lib/mock-api-handler.ts` are used only when `enableMockApi` flag is set in dev. Mock data shapes have not been updated since v1.3-v1.6 API changes.

**API Alignment:**
- `lib/api-client/patients.ts:384` has comment `REMOVED: Medical History, Appointments, Documents` -- client was pruned but some page-level components may still attempt removed endpoints.
- `WhatsAppService.ts` wraps `apiClient` for WuzAPI endpoints but `WhatsAppDashboard` still models Evolution API instance lifecycle (connected/QR states differ in WuzAPI).

---

## Frontend Architecture: quiz-mensal-interface

### Current Structure

```
quiz-mensal-interface/
├── app/
│   ├── api/health/         # Next.js API route for health check
│   ├── quiz/               # Quiz pages (page.tsx, monthly/page.tsx)
│   ├── globals.css
│   ├── layout.tsx
│   └── page.tsx            # Root -- redirects to /quiz
├── components/
│   ├── error/              # ErrorBoundary
│   ├── quiz/               # QuizSkeleton, ResumeQuizDialog, question types
│   ├── quiz-interface.tsx  # Main quiz UI component
│   ├── theme-provider.tsx
│   └── ui/                 # shadcn/ui primitives
├── hooks/
│   ├── use-quiz-session.ts  # Gold master: URL token -> HttpOnly cookie -> CSRF in RAM
│   ├── use-mobile.ts
│   └── use-toast.ts
├── lib/
│   └── api-client.ts       # Direct fetch (no proxy), CSRF in RAM, auto-retry
├── tests/                  # (coverage/ also present)
└── types/quiz.ts           # QuizSession, QuizSubmitResponse
```

### Quiz Architecture Pattern

The quiz uses a stateless security model that bypasses a Next.js API proxy layer:

```
Patient clicks short link --> URL contains ?token=xxx
    |
    v
useQuizSession hook:
  1. Exchange URL token for session (POST /api/v2/quiz/sessions/init)
  2. Backend sets HttpOnly cookie (QuizSession UUID)
  3. CSRF token returned in response body --> stored in RAM (XSS immune)
  4. URL cleaned (removes ?token from address bar)
    |
    v
All subsequent calls use: credentials: 'include' + X-CSRF-Token header
```

Key constraint: quiz talks directly to FastAPI backend at `NEXT_PUBLIC_QUIZ_PUBLIC_API_URL`. No Next.js server-side proxy exists. Only `/api/health` is a Next.js API route.

---

## Backend AI Architecture

### Current AI Stack

```
GeminiDomainClient (extends GeminiClient)
    |
    +-- humanize_flow_message()      -> HumanizeAgent (PIISafeAgent)
    +-- generate_varied_question()   -> VariationAgent (PIISafeAgent)
    +-- analyze_response_sentiment() -> SentimentAgent (PIISafeAgent)
    +-- create_empathetic_follow_up()-> EmpathyAgent (PIISafeAgent)
           |
           +-- PIISafeAgent._safe_run()
                   +-- sanitize_prompt_text_for_external_ai()  <- PII/PHI redaction (LGPD)
                   +-- GoogleModel(deps.model_name) via pydantic-ai
                   +-- agent.run(safe_prompt, model=model, deps=deps)

GeminiClient.generate_content()  <- For non-agent calls (templates, raw text)
    +-- PII redaction
    +-- Rate limit (Redis sliding window, fallback in-process)
    +-- Circuit breaker (get_ai_circuit_breaker())
    +-- Semantic cache (Redis, SHA-256 hash keyed)
    +-- Guardrail validation (OutputKind: MESSAGE, JSON, RAW)
    +-- Retry with exponential backoff
```

### ADK Integration Architecture

**What ADK is:** Google Agent Development Kit v1.26.0 (Feb 26, 2026) -- framework for building, evaluating, and deploying multi-agent pipelines using Gemini. Ships with OTel integration as an internal dependency.

**Why OTel must be removed first:**
ADK bundles `opentelemetry-*` as a hard dependency and manages its own OTel context internally. Running ADK alongside the current explicit OTel instrumentation causes `ValueError: Token was created in a different Context` in async generators -- confirmed in adk-python issue #860 (May 2025) and #1670 (Jun 2025). Issue #2792 confirms no public API exists to disable ADK's internal OTel tracing. The only clean resolution is to let ADK own the OTel layer by removing the explicit OTel packages.

**OTel removal scope (backend only -- well-isolated):**

The codebase has already designed for graceful OTel removal. `app/core/tracing.py` wraps all OTel imports in a `try/except ImportError` block and provides complete mock implementations when OTel is not installed. Callers of `get_tracer()` get a no-op mock tracer transparently.

Files to change in `requirements.txt` (remove):
```
opentelemetry-api
opentelemetry-sdk
opentelemetry-instrumentation-fastapi
opentelemetry-instrumentation-sqlalchemy
opentelemetry-instrumentation-redis
opentelemetry-instrumentation-httpx
opentelemetry-exporter-otlp
opentelemetry-exporter-otlp-proto-http
opentelemetry-proto
```

Files that need no code changes after package removal (callers of mock tracer):
- `app/integrations/whatsapp/services/message_service.py` -- uses `get_tracer()`, `@trace` decorator; both become no-ops
- `app/services/unified_whatsapp_service.py` -- uses `self.tracer = get_tracer()`; becomes no-op

`setup_tracing()` in application startup calls `instrument_fastapi()` etc., all of which are already safe no-ops when OTel is absent. No startup code changes needed.

**ADK integration points with existing AI stack:**

The 4 Pydantic AI agents (humanize, sentiment, variation, empathy) are NOT replaced by ADK. They are stable, CI-guarded, and satisfy their specific typed operations. ADK is an additional module for new agentic capabilities not currently covered.

```
EXISTING (keep as-is)                  NEW (ADK adds)
------------------------------------   ---------------------------------
GeminiClient.generate_content()        ADK LlmAgent
  template rendering, raw generation     multi-step reasoning tasks

PIISafeAgent + 4 Pydantic AI agents    ADK Runner + Session
  humanize, sentiment, variation,        agent lifecycle management
  empathy (typed, structured output)     state persistence across turns

FlowDispatcher -> direct async fns     ADK orchestration (optional path)
  enrollment flow control                complex multi-agent scenarios
```

**ADK module placement:**

```
backend-hormonia/app/ai/
├── agents/          # Existing: 4 PIISafe Pydantic AI agents (unchanged)
│   ├── base.py
│   ├── deps.py
│   ├── humanize_agent.py
│   ├── sentiment_agent.py
│   ├── variation_agent.py
│   └── empathy_agent.py
├── adk/             # NEW: ADK integration module
│   ├── __init__.py
│   ├── runner.py    # ADK Runner setup, session management
│   ├── wrapper.py   # PIISafeADKWrapper (mirrors PIISafeAgent pattern)
│   └── agents/      # ADK-specific agent definitions
├── client.py        # Unchanged
├── client_domain.py # Unchanged
└── pii_redaction.py # Unchanged (shared by both layers)
```

---

## Data Flow Changes (v1.7)

### Frontend Quality Work -- Data Flow Unchanged

Frontend quality improvements (dead code removal, API alignment, type consolidation, layout consistency) do not change API contracts. The request flow remains:

```
Admin user action
    |
    v
React component -> feature hook -> apiClient.[domain].[method]()
    |
    v
ApiClientCore.request()  -- auth headers, CSRF, retry, error mapping
    |
    v
FastAPI /api/v2/[resource]  -- AsyncSession, auth dep, LGPD middleware
    |
    v
Domain service -> PostgreSQL (RDS)
    |
    v
Response -> normalized (normalizers.ts) -> TanStack Query cache -> component
```

What changes during quality pass (data flow perspective):
- `WhatsAppDashboard` Evolution API gate removed; component shows WuzAPI connection state directly using existing WuzAPI admin endpoints.
- `AdminSettingsTab` Evolution URL field removed; settings form simplified.
- Stale type fields (`openai_model` in `AIConfig`) removed from TS types; no backend impact.
- Mock data shapes updated to match current API response schemas where drift exists.

### ADK Data Flow (new path)

```
New agentic endpoint called (e.g., POST /api/v2/ai/adk/assess)
    |
    v
FastAPI router (AsyncSession context)
    |
    v
app/ai/adk/runner.py
    +-- PIISafeADKWrapper.run(patient_text)
            +-- sanitize_prompt_text_for_external_ai()  <- mandatory PII redaction
            +-- ADK Runner dispatches to LlmAgent
            +-- ADK internal OTel span (ADK manages its own context)
    |
    v
Structured result returned to router -> response
```

---

## Architectural Patterns

### Pattern 1: PIISafeAgent Wrapper (existing -- MUST extend to ADK)

**What:** All Gemini/AI calls go through a wrapper that sanitizes PII before sending to external AI. CI lint script `scripts/check_agent_run_calls.py` blocks direct `agent.run()` calls outside the wrapper.

**When to use:** Any AI invocation that may receive patient data -- name, CPF, phone, medical notes.

**Trade-offs:** Small overhead per call (regex scan + hash log), but mandatory for LGPD Art. 46 compliance. Non-negotiable.

```python
class PIISafeAgent:
    async def _safe_run(self, prompt: str, deps: AIDeps, *, operation: str) -> Any:
        safe_prompt = sanitize_prompt_text_for_external_ai(prompt)  # mandatory
        result = await self._agent.run(safe_prompt, model=model, deps=deps)
        return result
```

ADK extension needed: Any ADK-managed agent that processes patient text needs equivalent PII sanitization before the ADK Runner dispatches to Gemini. Implement via ADK `before_model_callback` hook or pre-process at the calling site.

### Pattern 2: Modular API Client (existing frontend pattern)

**What:** `lib/api-client/` is split by domain (patients, auth, analytics, admin, etc.) and composed into the `apiClient` singleton in `index.ts`. Domain modules are independently importable.

**When to use:** All new API endpoints are added to the relevant domain module, not inline in components.

**Trade-offs:** Good separation but `index.ts` is large due to inline type imports. `lib/api.ts` is a legacy monolith -- callers should migrate to `lib/api-client/`.

### Pattern 3: Feature Slice (existing frontend pattern)

**What:** `features/[domain]/` contains the feature's components, hooks, and local utils. Shared components go in `components/`. Shared cross-feature hooks go in `hooks/`.

**When to use:** New feature work and refactoring should respect this boundary. Domain-specific logic does not belong in `components/`.

**Trade-offs:** 20+ feature slices; some have 1-2 files (minor over-slicing in `features/monitoring/`, `features/analytics/`). Acceptable for this project size.

### Pattern 4: Dual-Mode Session (existing backend -- DO NOT CHANGE)

**What:** API routers use `AsyncSession` via `get_async_db`. Celery tasks use sync `Session` via `get_db`. Services accept `db: Any` and operate with either.

**When to use:** All new router code uses `get_async_db`. All new Celery task code uses sync `get_db`. This is a design contract enforced by CI guard `scripts/check_async_isolation.py`.

**ADK relevance:** If ADK agents are called from FastAPI routes (HTTP-triggered), they run in the async context and do not touch the DB session. If called from Celery tasks, they need a sync bridge (`async_to_sync` pattern already used elsewhere).

---

## Integration Points

### Frontend Integration Points for Quality Work

| Integration Point | Current State | Required Change |
|-------------------|--------------|----------------|
| `WhatsAppDashboard` | Gated on `VITE_ENABLE_EVOLUTION=true`; always shows disabled state | Remove gate; wire to WuzAPI status/QR endpoints via existing `apiClient` |
| `AdminSettingsTab:203` | Evolution API URL form field present | Remove field and its validation |
| `lib/env-validator.ts:266` | Validates `VITE_ENABLE_EVOLUTION`, `VITE_EVOLUTION_API_URL` | Remove both entries |
| `lib/runtime-config.ts:51-52` | Evolution fields in type + defaults | Remove from type definition and defaults object |
| `types/api.ts:AIConfig` | `openai_model: string` field | Remove or rename to `gemini_model` |
| `config.ts` comments | References `VITE_OPENAI_API_KEY`, `VITE_LANGCHAIN_API_KEY` | Update docs to Gemini-only |
| `lib/types/api.ts` @deprecated exports | 8 re-exports marked deprecated | Decide: consolidate into `types/api.ts` or keep barrel explicitly |
| Mock data shapes | May have drifted from v1.3-v1.6 API changes | Sync with backend response schemas |

### Backend Integration Points for ADK Integration

| Integration Point | Current State | Required Change |
|-------------------|--------------|----------------|
| `requirements.txt` OTel block | 7 OTel packages pinned | Remove all 7; add `google-adk>=1.26.0` |
| `app/core/tracing.py` | Tries real OTel, falls back to mocks on ImportError | Remove real OTel try-imports; keep mock-only path (already written) |
| `unified_whatsapp_service.py` | `self.tracer = get_tracer()` | No code change needed; mock tracer stays |
| `integrations/whatsapp/services/message_service.py` | Uses `get_tracer()`, `@trace` decorator | No code change needed; decorators become no-ops |
| `app/ai/` directory | 4 Pydantic AI agents + GeminiClient | ADD `app/ai/adk/` alongside -- no modifications to existing files |
| New ADK endpoints | Not yet defined | New router `app/api/v2/routers/ai/adk.py` (if HTTP-triggered) |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `frontend-hormonia` <-> FastAPI | HTTPS REST + WebSocket (wss://) | No changes to contract during quality pass |
| `quiz-mensal-interface` <-> FastAPI | HTTPS REST direct (no proxy) | No changes; quiz is stable |
| `GeminiDomainClient` <-> `PIISafeAgent` | Direct method calls | Stable; ADK does not touch this |
| ADK agents <-> `PIISafeAgent` pattern | New `PIISafeADKWrapper` needed | Must implement PII sanitization at ADK boundary |
| `app/core/tracing.py` <-> callers | Mock tracer interface (no-op) | After OTel removal, callers get no-ops automatically |
| Celery tasks <-> ADK | Sync bridge if needed | Use `async_to_sync` pattern (same as existing Celery AI calls) |

---

## Build Order for v1.7

The dependency structure dictates this ordering:

**Phase A -- Backend OTel removal (blocker for ADK, no frontend impact):**
1. Remove 7 OTel packages from `requirements.txt`
2. Verify `app/core/tracing.py` compiles with mock-only path (`OPENTELEMETRY_AVAILABLE = False`)
3. Confirm `unified_whatsapp_service.py` and `message_service.py` still import without error
4. Run existing test suite to confirm no regressions

**Phase B -- ADK integration (depends on Phase A):**
1. Add `google-adk>=1.26.0` to `requirements.txt`
2. Create `app/ai/adk/` module with `PIISafeADKWrapper`
3. Define ADK agent(s) for new capability scope
4. Add new router endpoint(s) if HTTP-triggered; or Celery bridge if task-triggered
5. Verify ADK's OTel context operates without conflict (no context detach errors in logs)

**Phase C -- Frontend quality: admin SPA (independent of A/B):**
1. Remove Evolution API dead code (WhatsAppDashboard gate, AdminSettingsTab field, env-validator, runtime-config)
2. Update `WhatsAppDashboard` to model WuzAPI lifecycle (QR pairing, connected, disconnected)
3. Clean stale AI provider references (types, config comments)
4. Audit and sync mock data shapes with current API response schemas
5. Consolidate type duplication (`src/types/` vs `src/lib/types/`)
6. Fix lint issues, type errors, ESLint suppressions

**Phase D -- Frontend quality: quiz (independent of A/B/C):**
1. Audit `quiz-mensal-interface` for dead code and type coverage gaps
2. Verify mock data shapes
3. Layout consistency pass
4. Run TypeScript strict check (`noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`)

Phases C and D can run in parallel with A and B since they touch separate codebases with no shared code.

---

## Anti-Patterns

### Anti-Pattern 1: Parallel OTel + ADK

**What people do:** Install `google-adk` without removing existing `opentelemetry-*` packages.

**Why it's wrong:** ADK's internal OTel tracer conflicts with existing instrumentation. `ValueError: Token was created in a different Context` appears at runtime in async generators -- hard to debug, non-deterministic. ADK has no public API to disable its internal OTel (issue #2792, open as of 2025-08).

**Do this instead:** Remove all 7 OTel packages from `requirements.txt` first. `app/core/tracing.py` already has a mock fallback path -- callers are safe after removal with zero code changes.

### Anti-Pattern 2: Direct Gemini calls in ADK agents without PII sanitization

**What people do:** Write ADK agents that accept patient records directly in the prompt string.

**Why it's wrong:** Violates LGPD Art. 46. The CI guard `scripts/check_agent_run_calls.py` blocks `agent.run()` outside `PIISafeAgent`, but ADK agents bypass this guard unless explicitly extended.

**Do this instead:** Add `sanitize_prompt_text_for_external_ai()` at the ADK integration boundary, either via ADK `before_model_callback` hook or at the calling site. Implement `PIISafeADKWrapper` that mirrors `PIISafeAgent`.

### Anti-Pattern 3: Adding new API calls inline in React components

**What people do:** Call `fetch('/api/v2/...')` or `apiClient.core.request()` directly inside a component's `useEffect`.

**Why it's wrong:** Bypasses error normalization, retry logic, auth header injection, and TanStack Query caching. Creates duplicate loading/error state management.

**Do this instead:** Add the call to the relevant domain module in `lib/api-client/`, expose it via a typed hook in `hooks/`, and use TanStack Query for cache/loading/error state.

### Anti-Pattern 4: Modifying existing Pydantic AI agents for ADK compatibility

**What people do:** Refactor `HumanizeAgent`, `SentimentAgent`, etc. to run under ADK orchestration.

**Why it's wrong:** These 4 agents are stable, fully tested, and CI-guarded. They solve specific typed output problems well. ADK is an addition for new scenarios -- not a migration target for existing agents.

**Do this instead:** Keep existing agents unchanged. `app/ai/adk/` covers new agentic scenarios that were previously impossible or ad-hoc.

---

## Scaling Considerations

The system serves a single oncology clinic. Architecture scaling is not a concern for v1.7. Relevant operational considerations:

| Concern | Current Approach | v1.7 Impact |
|---------|-----------------|-------------|
| AI latency | Circuit breaker + rate limit + Redis cache | ADK adds its own retry; do not double-retry at the outer layer |
| PII compliance | PIISafeAgent + CI lint guard | Must extend to ADK boundary before any patient data flows through ADK |
| OTel context conflicts | Currently blocks ADK adoption | OTel removal unblocks ADK; no other scaling impact |
| Frontend bundle size | Firebase lazy-loaded, React.lazy routes | Dead code removal reduces bundle; no regressions expected |

---

## Sources

- Direct codebase inspection (HIGH confidence -- 2026-03-03):
  - `backend-hormonia/app/ai/client.py` -- GeminiClient full implementation
  - `backend-hormonia/app/ai/client_domain.py` -- GeminiDomainClient 4 domain methods
  - `backend-hormonia/app/ai/agents/base.py` -- PIISafeAgent pattern
  - `backend-hormonia/app/core/tracing.py` -- OTel mock fallback design
  - `backend-hormonia/requirements.txt` -- 7 OTel packages + AI deps
  - `frontend-hormonia/src/lib/api-client/` -- modular API client
  - `frontend-hormonia/src/features/whatsapp/WhatsAppDashboard.tsx` -- Evolution gate
  - `frontend-hormonia/src/config.ts` -- stale OpenAI/LangChain comments
  - `frontend-hormonia/src/types/api.ts` -- `openai_model` field
  - `frontend-hormonia/src/lib/env-validator.ts` -- Evolution env validation
  - `quiz-mensal-interface/hooks/use-quiz-session.ts` -- gold master quiz security pattern
  - `quiz-mensal-interface/lib/api-client.ts` -- direct fetch, no proxy
- [google/adk-python Releases](https://github.com/google/adk-python/releases) -- v1.26.0 (Feb 26, 2026) confirmed latest; OTel bundled as internal dep (MEDIUM confidence via WebFetch)
- [ADK issue #860](https://github.com/google/adk-python/issues/860) -- OTel context conflict in async generators (confirmed May 2025)
- [ADK issue #1670](https://github.com/google/adk-python/issues/1670) -- Failed to detach context with dual OTel (confirmed Jun 2025)
- [ADK issue #2792](https://github.com/google/adk-python/issues/2792) -- No public API to disable internal OTel tracing (open issue Aug 2025)
- [pydantic-ai PyPI](https://pypi.org/project/pydantic-ai/) -- v1.x current; compatible with ADK as separate packages (not conflicting)

---

*Architecture research for: Clinica Oncologica v1.7 -- Frontend Quality + ADK Integration*
*Researched: 2026-03-03*
