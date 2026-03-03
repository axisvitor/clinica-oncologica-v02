# Feature Research

**Domain:** Frontend Quality Overhaul + Google ADK Integration (v1.7)
**Researched:** 2026-03-03
**Confidence:** HIGH for frontend patterns (established ecosystem); MEDIUM for ADK integration specifics (ADK v1.26.0 + dependency constraints verified but OTel removal scope inferred from codebase inspection)

---

## Context

This research maps the feature landscape for v1.7, which targets two independent workstreams:

1. **Frontend Quality** — Review and fix both frontends (admin SPA: React 19 + Vite + shadcn/ui; quiz interface: Next.js 14 + React 18 + shadcn/ui) for dead code, API alignment, layout consistency, and code quality (lint/types).
2. **Google ADK Integration** — Remove OpenTelemetry (unblocking dependency conflict) and integrate Google ADK on top of the existing Pydantic AI agent stack.

These workstreams are nearly independent. Frontend quality has no dependency on ADK. ADK integration is purely backend.

**Existing stack relevant to this milestone:**
- Admin SPA: React 19, Vite 6, Tailwind v4, shadcn/ui (full Radix primitive set), TanStack Query v5, react-router-dom v6, Sentry, Firebase Auth, axios, vitest, Playwright
- Quiz interface: Next.js 14, React 18, Tailwind v4, shadcn/ui (pinned Radix versions), jest, msw
- Backend AI: 4 Pydantic AI agents (pydantic-ai-slim[google]), google-genai SDK, GeminiClient with circuit breaker + rate limiter + cache, PIISafeAgent mandatory wrapper
- OTel: opentelemetry-api/sdk + 4 instrumentation packages + 2 exporters — optional wrapper in `app/core/tracing.py` (already guarded by `try/except ImportError`)

---

## Feature Landscape

### Table Stakes — Frontend Quality (Users / Developers Expect These)

Features a well-maintained React/Next.js codebase must have. Missing = technical debt that blocks future development.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Zero unused npm dependencies | Package bloat slows install/build; security surface | LOW | Both frontends have full shadcn/ui Radix primitive set installed; many primitives may be unused. Use `knip` for project-wide detection; shadcn/ui docs explicitly say to remove unused `@radix-ui/react-*` packages. |
| Zero unused files and exports | Dead components add confusion, inflate bundle | MEDIUM | Admin SPA has pages like `HiveMindPage`, `EnhancedAnalyticsDashboard`, `PhysicianDashboard` — their backend endpoints need verification. `knip` traces from entry points; anything unreachable is flagged. |
| ESLint passing with zero errors | Prevents bad code reaching CI | LOW | Admin SPA: `eslint . --ext ts,tsx` (eslint v9 + typescript-eslint v8). Quiz: `next lint` (eslint v8 + eslint-config-next). Both configured. Run state unknown — may have suppressed errors. |
| TypeScript strict with zero `any` warnings | Type safety catches API contract mismatches at compile time | MEDIUM | Admin SPA: `tsc --noEmit`. Quiz: typescript v5.9. Both have tsconfig. Degree of `any` usage, `@ts-ignore`, and `as unknown as X` patterns unknown without audit. |
| API calls matching backend contracts | Frontend silently breaks when endpoint paths/payloads drift | MEDIUM | Admin SPA `lib/api-client/` has 10+ domain modules (auth, patients, analytics, admin, dashboard, tasks, hive-mind, etc.). `hive-mind.ts` calls `/api/v2/hive-mind/agents` — backend "hive mind" concept may not exist as a real API resource post-v1.2 AI rationalization. `ai-adapters.ts` maps AI insight types — must align with Pydantic AI agent output schemas. |
| Consistent error states and loading skeletons | Users expect graceful failure and loading UX | MEDIUM | Admin SPA has `LoadingStates.tsx`, `ErrorBoundary.tsx`, `ErrorFallback.tsx`, skeleton components — but consistency across pages is unverified. `AgentSwarm` component uses raw `useEffect` + `setInterval` instead of TanStack Query — inconsistent pattern. |
| No duplicate API client implementations | Multiple clients for same domain = divergent behavior | LOW | Admin SPA has `lib/api.ts`, `lib/api-client.ts`, `lib/client.ts`, AND `lib/api-client/` directory — potential duplication. `src/client.ts` at top level appears to be a stub. Needs consolidation audit. |

### Table Stakes — ADK Integration (Backend)

What must be true for ADK to be usable in this project.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| OTel packages removed from requirements.txt | ADK pulls its own OTel; running two OTel stacks causes `ValueError: Token was created in a different Context` errors in async code | MEDIUM | Current: 7 OTel packages in requirements.txt. `app/core/tracing.py` already has `try/except ImportError` mock fallback — designed for optional OTel. Removal primarily means: (1) remove from requirements.txt, (2) verify no `from opentelemetry import X` calls survive outside the guarded module, (3) update middleware_setup.py if any OTel middleware was registered. |
| google-adk installable alongside pydantic-ai-slim | pip can resolve both without conflict | MEDIUM | ADK v1.26.0 current (verified). ADK depends on google-genai (same as pydantic-ai-slim[google]). Version pinning between ADK and pydantic-ai-slim on google-genai may require careful version coordination. LOW confidence on exact version constraints without running pip resolve. |
| ADK Runner wired to at least one existing agent | Proof of integration; validates agent wrapping pattern | MEDIUM | ADK uses `Runner` + `InMemorySessionService` for stateless operation; or `DatabaseSessionService` for persistence. Existing Pydantic AI agents are callable functions — they need to be wrapped as ADK `FunctionTool` or `LlmAgent`. |
| PIISafeAgent contract preserved | LGPD Art. 46 — PII redaction must remain mandatory | LOW | ADK agent wrapping must invoke PIISafeAgent, not bypass it. CI guard `scripts/check_agent_run_calls.py` must still block direct `.run()` calls. ADK's `FunctionTool` wrapping a PIISafeAgent-guarded function naturally satisfies this. |

### Differentiators — Frontend Quality

Features that improve maintainability beyond the minimum viable cleanup.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| TanStack Query used consistently for all async data | Eliminates raw `useEffect` + `useState` polling; adds caching, deduplication, background refresh, optimistic updates | MEDIUM | `AgentSwarm.tsx` uses `setInterval` polling pattern (anti-pattern). `SystemHealth.tsx` likely same. Converting to `useQuery` with `refetchInterval` is the correct pattern. Admin SPA already has TanStack Query v5 + `OptimizedQueryProvider` — just apply it consistently. |
| Centralized query key factory (`queryKeys.ts`) | Prevents cache invalidation bugs from mismatched keys | LOW | Admin SPA already has `lib/query-keys.ts`. Verify all hooks use it rather than inline string keys. |
| Shared `apiClient` instance used everywhere | One auth token, one base URL, one interceptor chain | LOW | Admin SPA has `lib/api-client/` as the canonical client. Verify pages and hooks do not call `axios` directly or use `lib/api.ts` as a parallel client. |
| Layout consistency: page header / breadcrumb / card padding | Cross-page visual coherence reduces cognitive load for clinic staff | MEDIUM | Admin SPA has 20+ pages — visual consistency between `DashboardPage`, `PatientsPage`, `PhysicianDashboard`, `EnhancedAnalyticsDashboard`, etc. needs audit. `Breadcrumb.tsx` and `Header.tsx` exist but page-level patterns may diverge. |
| Zod validation schemas colocated with forms | Eliminates runtime field name mismatches between form and API payload | LOW | Admin SPA has `lib/validations/admin-schemas.ts`, `lib/validations/user-schemas.ts`. Patient form (`PatientForm.tsx`) uses `react-hook-form` + `@hookform/resolvers/zod` — check all forms follow this pattern. |
| React 19 ref-as-prop migration on shadcn components | React 19 deprecates `forwardRef`; shadcn/ui v1.x already removed it | LOW | Admin SPA on React 19 — if using shadcn/ui components installed before Feb 2025 update, they may still use `forwardRef`. Check `components.json` shadcn version and run `shadcn add` updates for stale primitives. Quiz interface on React 18 — no change needed. |

### Differentiators — ADK Integration

What ADK adds beyond the current Pydantic AI setup.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| ADK Session + Memory Service | Agents can carry conversational state across tool calls without explicit state threading in caller code | HIGH | Current Pydantic AI agents are stateless per-call. ADK `InMemorySessionService` adds within-session state; `DatabaseSessionService` could persist across sessions. Useful for multi-turn patient assessment flows. High complexity: requires ADK Runner integration into async FastAPI handlers. |
| ADK Sequential/Parallel/Loop workflow agents | Declarative multi-step agent pipelines without custom orchestration code | HIGH | Current flow orchestration uses direct async Python functions (~10-15 lines each). ADK workflow agents provide the same semantics with more overhead but better observability. Medium value for this codebase since direct functions already work well. |
| ADK Built-in Evaluation framework | Run automated test cases against agents with prompt/response fixture pairs | MEDIUM | Current: no agent evaluation pipeline. ADK's `adk eval` CLI runs scenarios and scores responses. Valuable for validating sentiment/empathy agent quality changes. |
| ADK Agent Registry + Skills API | Discover and compose agents dynamically; `load_skill_from_dir()` | HIGH | Overkill for 4 fixed-purpose agents. Future value if agent count grows. |
| ADK BigQuery Analytics plugin | Track agent usage, latency, error rates in BigQuery | HIGH | Project uses Railway + AWS RDS — no BigQuery. Not applicable. |

### Anti-Features — Frontend Quality

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Full UI redesign of admin SPA | "While we're in the code, improve the UX" | Out-of-scope per PROJECT.md: "Redesign de UI do frontend admin ou quiz interface — foco backend." Scope creep that blocks v1.7 delivery. | Stick to layout consistency (padding, spacing, card structure) without visual redesign. |
| Migrating quiz interface from Next.js 14 → 15 | Next.js 15 is available | Next.js 15 changes App Router behavior, Server Actions API, and React 19 opt-in mechanics. Migration is a separate workstream, not a quality fix. | Stay on Next.js 14. Fix quality within current version. |
| Adding Storybook for component catalog | Seems like a good practice | Adds significant tooling overhead and maintenance burden for a small team. Admin SPA has vitest + Playwright — component testing is covered. | Document component patterns in CLAUDE.md or a lightweight spec if needed. |
| Code splitting / bundle optimization | "Performance improvements" | Performance has not been identified as a user complaint. Premature optimization. Vite already does code splitting by default. | Let Vite handle it. Focus on correctness and dead code removal. |
| Replacing axios with native `fetch` | React 19 promotes `use(fetch(...))` | `TanStack Query + axios` is the established pattern already wired up. Switching HTTP clients is pure churn with zero functional benefit. | Keep axios. |
| Type-safe API generation from OpenAPI spec | "Eliminate manual type maintenance" | FastAPI does expose an OpenAPI schema, but wiring openapi-typescript code-gen into both frontends' CI is significant tooling work. Over-engineered for this team size and codebase maturity. | Hand-maintain types in `lib/api-client/types.ts`. Use `tsc --noEmit` as the quality gate. |

### Anti-Features — ADK Integration

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Replacing Pydantic AI agents entirely with ADK LlmAgent | "Consolidate on one framework" | Pydantic AI agents provide typed structured output — critical for PIISafeAgent LGPD compliance. ADK's output schema is less strict. Replacement would destabilize 4 tested agents and weaken type safety. | Wrap existing Pydantic AI agents as ADK FunctionTools. ADK orchestrates; Pydantic AI executes typed calls. |
| Using ADK for flow orchestration (replacing direct async Python) | "Better observability" | Direct async Python flow functions (10-15 lines each) already replaced LangGraph successfully in v1.2. Introducing ADK workflow agents adds framework overhead for no functional gain. The decision log explicitly notes "Direct async Python over ADK for flow orchestration — zero new dependencies." | Keep direct async Python flow functions. Use ADK only for agent-level coordination if needed. |
| Keeping OpenTelemetry alongside ADK | "Don't lose tracing" | ADK v1.26.0 manages its own OTel tracer. Two OTel SDK initializations in the same process cause `ValueError: Token was created in a different Context` on async context propagation — a known ADK/Langfuse conflict documented in multiple open issues. | Remove OTel; use Sentry (already installed) for error tracking. ADK's built-in tracing covers AI agent spans. |
| ADK Web UI / CLI deployment | "Use ADK's built-in server" | Project deploys on Railway/Cloud Run with FastAPI. ADK's web interface is a development tool, not a production runtime. | Use ADK as a Python library inside existing FastAPI handlers. |
| ADK RabbitMQ / BigQuery integrations | "Enterprise features" | Project has no RabbitMQ or BigQuery infrastructure. Adding dependencies for unused features. | Skip these ADK optional plugins. |

---

## Feature Dependencies

```
FRONTEND WORKSTREAM
-------------------

Dead Code Audit (knip)
    └──informs──> Unused npm package removal
    └──informs──> Unused file/component removal
    └──prerequisite for──> Layout consistency (know what pages exist and are reachable)

ESLint audit
    └──prerequisite for──> TypeScript strict audit (fix lint first, then type errors)

TypeScript strict audit
    └──prerequisite for──> API alignment audit (tsc catches contract mismatches)

API alignment audit
    └──depends on──> Dead code audit (don't align API calls for dead pages)
    └──may trigger──> Backend endpoint verification (does /api/v2/hive-mind exist?)

Layout consistency review
    └──depends on──> Dead code audit (only fix pages that are reachable)
    └──independent of──> API alignment (visual only)

BACKEND ADK WORKSTREAM
----------------------

OTel removal from requirements.txt
    └──prerequisite for──> google-adk installation (eliminates context conflict)
    └──verify──> app/core/tracing.py mock fallback still works
    └──verify──> no surviving bare `from opentelemetry import X` outside guarded module

google-adk installation
    └──depends on──> OTel removal
    └──may conflict with──> pydantic-ai-slim[google] on google-genai version (verify pip resolve)

ADK Runner wiring
    └──depends on──> google-adk installation
    └──wraps──> existing PIISafeAgent calls as FunctionTool
    └──must preserve──> PIISafeAgent LGPD wrapper (not bypass)

CROSS-WORKSTREAM
----------------

Frontend AI display (ai-adapters.ts, AIPredictionsPanel)
    └──depends on──> ADK agent output schema remaining compatible
    └──note──> If ADK changes response format vs current Pydantic AI, frontend type sync needed
```

### Dependency Notes

- **Dead code audit before layout work:** Running `knip` first prevents spending time fixing layout on unreachable pages. The admin SPA has `HiveMindPage`, `EnhancedAnalyticsDashboard`, `PhysicianDashboard`, `DLQDashboard` — reachability from routes must be confirmed before cleanup.
- **OTel removal before ADK install:** Installing google-adk while OTel SDK is active triggers async context errors in production. This is the blocker the PROJECT.md notes explicitly ("OTel removed to unblock ADK").
- **PIISafeAgent must survive ADK wrapping:** ADK's `FunctionTool` wraps a Python callable. The callable must be the PIISafeAgent-gated function, not the raw agent `.run()`. CI guard (`scripts/check_agent_run_calls.py`) must not need modification.
- **`hive-mind` API client module:** `lib/api-client/hive-mind.ts` calls `/api/v2/hive-mind/*` endpoints. Post v1.2 AI rationalization (LangGraph removed), whether these backend routes still exist is unknown. If they are tombstoned or never existed as a REST API, this is a dead API client module and should be removed.

---

## MVP Definition (v1.7 Scope)

### Launch With (v1.7 — both workstreams)

**Frontend Quality:**
- [ ] `knip` audit run on both frontends — unused files, exports, packages identified and removed
- [ ] ESLint errors: zero in admin SPA (`eslint . --ext ts,tsx`) and quiz (`next lint`)
- [ ] TypeScript: `tsc --noEmit` passing with zero errors in both frontends
- [ ] API client consolidation in admin SPA: single `lib/api-client/` as canonical; `lib/api.ts` and `lib/api-client.ts` at root removed or verified as shims
- [ ] `hive-mind.ts` API module: verified against actual backend routes or removed if endpoints do not exist
- [ ] TanStack Query used for data fetching in `AgentSwarm.tsx` and `SystemHealth.tsx` (replace raw `useEffect` + `setInterval`)
- [ ] Layout consistency: page-level padding, card structure, and breadcrumb usage verified consistent across all reachable admin pages

**ADK Integration:**
- [ ] OTel packages removed from `requirements.txt` (7 packages: api, sdk, 4 instrumentations, 2 exporters)
- [ ] `app/core/tracing.py` verified working with mock fallback (no live OTel)
- [ ] `google-adk` installed and pip resolve clean alongside `pydantic-ai-slim[google]`
- [ ] At least one existing Pydantic AI agent (e.g., sentiment agent) wrapped as ADK `FunctionTool` as proof-of-concept
- [ ] ADK Runner integration in a FastAPI handler (can be a new diagnostic endpoint, not in critical path)
- [ ] PIISafeAgent CI guard remains in place; ADK wrapping does not bypass it

### Add After Validation (v1.x)

- [ ] ADK `InMemorySessionService` for multi-turn patient assessment context (only if a use case emerges)
- [ ] ADK evaluation harness for agent quality regression testing
- [ ] Remaining Pydantic AI agents (humanize, variation, empathy) wrapped as ADK FunctionTools

### Future Consideration (v2+)

- [ ] ADK `DatabaseSessionService` backed by PostgreSQL for persistent agent memory
- [ ] ADK Agent Registry for dynamic agent discovery if agent count grows beyond 4
- [ ] Next.js upgrade (quiz interface) from 14 → 15 as a separate milestone

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| ESLint zero errors | MEDIUM (dev quality) | LOW | P1 |
| TypeScript zero errors | HIGH (prevents runtime bugs) | MEDIUM | P1 |
| Dead code removal (knip) | MEDIUM (bundle size, clarity) | LOW | P1 |
| API client consolidation | HIGH (prevents silent failures) | MEDIUM | P1 |
| hive-mind module verification/removal | HIGH (live API calls to possibly non-existent endpoints) | LOW | P1 |
| TanStack Query for all data fetching | MEDIUM (DX consistency) | LOW | P1 |
| Layout consistency | LOW (visual only) | MEDIUM | P2 |
| OTel removal | HIGH (ADK prerequisite) | MEDIUM | P1 |
| google-adk installation + pip resolve | HIGH (ADK prerequisite) | MEDIUM | P1 |
| One agent wrapped as ADK FunctionTool | MEDIUM (proof of concept) | MEDIUM | P1 |
| ADK evaluation harness | MEDIUM (quality gate) | HIGH | P2 |
| All 4 agents wrapped in ADK | LOW (incremental) | LOW | P2 |

**Priority key:**
- P1: Must have for v1.7 milestone close
- P2: Should have, add when possible within v1.7
- P3: Nice to have, future milestone

---

## Competitor / Ecosystem Analysis

Not applicable in traditional competitive sense. This is internal quality work. Ecosystem patterns that inform decisions:

| Pattern | Ecosystem Standard | This Project | Gap |
|---------|-------------------|--------------|-----|
| Dead code detection | `knip` (industry standard 2024-2026, recommended over ts-prune) | Not yet in CI | Add `npx knip` to both frontends |
| ESLint v9 flat config | Admin SPA already uses eslint v9 + typescript-eslint v8 | In place | Verify config is strict enough |
| TanStack Query v5 for async state | Standard for React data fetching; replaces SWR, Redux Toolkit Query for most use cases | Installed, partially used | Apply consistently to all data-fetching components |
| ADK v1.26.0 | Current production release (Feb 26, 2026); supports `InMemorySessionService`, `FunctionTool`, `LlmAgent`, workflow agents | Not yet installed | Install after OTel removal |
| Pydantic AI + ADK coexistence | ADK wraps Pydantic AI agents as FunctionTools — documented pattern; ADK uses Pydantic for its own output schemas | Planned | Implement wrapping; do not replace |
| shadcn/ui + Tailwind v4 | React 19 removes forwardRef; shadcn/ui updated Feb 2025; Tailwind v4 now stable | Admin SPA: Tailwind v4 + React 19 (up to date). Quiz: Tailwind v4 + React 18 | Admin SPA may have pre-update shadcn components |

---

## Sources

- [google/adk-python GitHub Releases](https://github.com/google/adk-python/releases) — v1.26.0 current (Feb 26, 2026); feature list HIGH confidence
- [Google ADK Documentation](https://google.github.io/adk-docs/) — LLM agents, sessions, memory, artifacts — HIGH confidence
- [Google ADK Issue #1670: OTel context error](https://github.com/google/adk-python/issues/1670) — async context conflict confirmed — HIGH confidence
- [Langfuse Issue #8316: ADK + OTel conflict](https://github.com/langfuse/langfuse/issues/8316) — context token created/detached in different context — HIGH confidence
- [Google ADK Issue #2792: OTel disable/extend support](https://github.com/google/adk-python/issues/2792) — no public API to disable ADK internal OTel — MEDIUM confidence
- [Knip official docs](https://knip.dev/) — dead code detection; Vite + Next.js plugins — HIGH confidence
- [Knip: dead code vs ts-prune](https://levelup.gitconnected.com/dead-code-detection-in-typescript-projects-why-we-chose-knip-over-ts-prune-8feea827da35) — why knip is the current standard — MEDIUM confidence
- [shadcn/ui React 19 docs](https://ui.shadcn.com/docs/react-19) — forwardRef removal, Tailwind v4 support — HIGH confidence
- [TanStack Query v5 TypeScript guide](https://tanstack.com/query/v5/docs/framework/react/typescript) — typed queries, AxiosError handling — HIGH confidence
- Codebase inspection: `frontend-hormonia/package.json` — React 19, Vite 6, TanStack v5, shadcn full Radix set
- Codebase inspection: `quiz-mensal-interface/package.json` — Next.js 14, React 18, Radix pinned versions
- Codebase inspection: `frontend-hormonia/src/lib/api-client/` — 10+ domain modules, hive-mind.ts
- Codebase inspection: `frontend-hormonia/src/components/hive-mind/AgentSwarm.tsx` — raw useEffect polling
- Codebase inspection: `backend-hormonia/requirements.txt` — 7 OTel packages, pydantic-ai-slim[google]
- Codebase inspection: `backend-hormonia/app/core/tracing.py` — optional OTel with mock fallback pattern

---

*Feature research for: Frontend Quality Overhaul + Google ADK Integration (oncology clinic v1.7)*
*Researched: 2026-03-03*
