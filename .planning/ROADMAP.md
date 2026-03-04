# Roadmap: Clinica Oncologica — Refinamento para Producao

## Milestones

- ✅ **v1.0 Foundations** — Phases 1-5 (shipped 2026-02-22)
- ✅ **v1.1 Architecture & Observability** — Phases 6-9 (shipped 2026-02-23)
- ✅ **v1.2 AI Framework Migration** — Phases 10-13 (shipped 2026-02-24)
- ✅ **v1.3 Flow Health & Cleanup** — Phases 14-19 (shipped 2026-02-26)
- ✅ **v1.4 AsyncSession & Test Stability** — Phases 20-28 (shipped 2026-02-28)
- ✅ **v1.5 Saga Orchestrator Deep Dive** — Phases 29-32 (shipped 2026-03-01)
- ✅ **v1.6 WuzAPI Migration** — Phases 33-39 (shipped 2026-03-03)
- 🚧 **v1.7 Frontend Quality & ADK Integration** — Phases 40-43 (in progress)

## Phases

<details>
<summary>✅ v1.0 Foundations (Phases 1-5) — SHIPPED 2026-02-22</summary>

- [x] Phase 1: Security Hardening (3/3 plans) — completed 2026-02-22
- [x] Phase 2: LGPD Compliance (3/3 plans) — completed 2026-02-22
- [x] Phase 3: Operational Stability (3/3 plans) — completed 2026-02-22
- [x] Phase 4: AI Reliability (2/2 plans) — completed 2026-02-22
- [x] Phase 5: Flow Consolidation (2/2 plans) — completed 2026-02-22

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 Architecture & Observability (Phases 6-9) — SHIPPED 2026-02-23</summary>

- [x] Phase 6: Async Hot Path Migration (4/4 plans) — completed 2026-02-23
- [x] Phase 7: LGPD Key Rotation (1/1 plan) — completed 2026-02-23
- [x] Phase 8: AI Rationalization (2/2 plans) — completed 2026-02-23
- [x] Phase 9: Observability (3/3 plans) — completed 2026-02-23

Full details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

<details>
<summary>✅ v1.2 AI Framework Migration (Phases 10-13) — SHIPPED 2026-02-24</summary>

- [x] Phase 10: Preparation & Scope (4/4 plans) — completed 2026-02-24
- [x] Phase 11: Agent Implementation (4/4 plans) — completed 2026-02-24
- [x] Phase 12: Flow Orchestration Replacement (3/3 plans) — completed 2026-02-24
- [x] Phase 13: SDK Migration & Cleanup (5/5 plans) — completed 2026-02-24

Full details: `.planning/milestones/v1.2-ROADMAP.md`

</details>

<details>
<summary>✅ v1.3 Flow Health & Cleanup (Phases 14-19) — SHIPPED 2026-02-26</summary>

- [x] Phases 14-19 archived — full details: `.planning/milestones/v1.3-ROADMAP.md`

</details>

<details>
<summary>✅ v1.4 AsyncSession & Test Stability (Phases 20-28) — SHIPPED 2026-02-28</summary>

- [x] Phase 20: Schema Fix (1/1 plan) — completed 2026-02-26
- [x] Phase 21: Async Foundation (5/5 plans) — completed 2026-02-26
- [x] Phase 22: Critical Async Fixes (3/3 plans) — completed 2026-02-27
- [x] Phase 23: Service Migration (9/9 plans) — completed 2026-02-27
- [x] Phase 24: API Routers — Auth / Patients / Flow (7/7 plans) — completed 2026-02-27
- [x] Phase 25: API Routers — Messages / Quiz (5/5 plans) — completed 2026-02-27
- [x] Phase 26: API Routers — Analytics / Admin / System / Remaining (16/16 plans) — completed 2026-02-27
- [x] Phase 27: Test Stability (6/6 plans) — completed 2026-02-28
- [x] Phase 28: Async Session Gap Closure (2/2 plans) — completed 2026-02-28

Full details: `.planning/milestones/v1.4-ROADMAP.md`

</details>

<details>
<summary>✅ v1.5 Saga Orchestrator Deep Dive (Phases 29-32) — SHIPPED 2026-03-01</summary>

- [x] Phase 29: Saga Module Audit (3/3 plans) — completed 2026-02-28
- [x] Phase 30: Flow Integration Trace (4/4 plans) — completed 2026-03-01
- [x] Phase 31: Compensation Integrity (2/2 plans) — completed 2026-03-01
- [x] Phase 32: Test Coverage (5/5 plans) — completed 2026-03-01

Full details: `.planning/milestones/v1.5-ROADMAP.md`

</details>

<details>
<summary>✅ v1.6 WuzAPI Migration (Phases 33-39) — SHIPPED 2026-03-03</summary>

- [x] Phases 33-39 archived — full details: `.planning/milestones/v1.6-ROADMAP.md`

</details>

### 🚧 v1.7 Frontend Quality & ADK Integration (In Progress)

**Milestone Goal:** Corrigir qualidade dos dois frontends (admin SPA + quiz mensal) e integrar Google ADK no backend desbloqueado pela remocao do OpenTelemetry.

- [x] **Phase 40: OTel Removal & ADK Foundation** - Remove OTel instrumentation, install ADK, scaffold PIISafeADKWrapper with CI guard (completed 2026-03-03)
- [x] **Phase 41: ADK Agent Integration** - Wire Pydantic AI agents as ADK FunctionTools, configure ADK Runner endpoint, remove HiveMind LangGraph dead code (gap closure in progress) (completed 2026-03-04)
- [ ] **Phase 42: Admin SPA Quality** - Remove Evolution dead code, consolidate API client, migrate polling to TanStack Query, enforce lint/formatting
- [ ] **Phase 43: Quiz Interface Quality** - Add Prettier, upgrade Next.js 15, align ESLint 9, fix missing deps, improve type coverage

## Phase Details

### Phase 40: OTel Removal & ADK Foundation
**Goal**: OTel instrumentation packages removed and ADK installed cleanly — the pip conflict that blocked ADK since v1.2 is resolved, Sentry correlation verified intact, and the LGPD-compliant PIISafeADKWrapper exists before any patient data can reach ADK
**Depends on**: Phase 39 (v1.6 complete)
**Requirements**: ADK-01, ADK-02, ADK-03, ADK-04, ADK-05
**Success Criteria** (what must be TRUE):
  1. `pip check` returns no errors with google-adk and pydantic-ai-slim[google] installed together in Python 3.13
  2. Sentry captures FastAPI and Celery transactions with the same tree depth as before OTel removal (baseline sampled, post-removal confirmed)
  3. `app/core/tracing.py` is tombstoned — importing it raises ImportError and callers fall back to no-op mock without any code change
  4. `app/ai/adk/wrapper.py` exists with PIISafeADKWrapper that redacts PII before every ADK Gemini call, tested with synthetic PHI input
  5. CI lint (`check_agent_run_calls.py`) blocks direct `.run()` calls inside ADK tool functions and the test suite confirms this with a failing fixture
**Plans**: 3 plans
Plans:
- [ ] 40-01-PLAN.md — Validate ADK dependency compatibility, remove OTel instrumentation, and tombstone tracing with Sentry CeleryIntegration
- [ ] 40-02-PLAN.md — Scaffold PIISafeADKWrapper package and verify synthetic PHI sanitization behavior
- [x] 40-03-PLAN.md — Extend CI guard to block direct ADK run calls with regression fixture coverage (completed 2026-03-03)

### Phase 41: ADK Agent Integration
**Goal**: At least one Pydantic AI agent is callable as an ADK FunctionTool via a live FastAPI endpoint, the ADK Runner is operational, and all LangGraph dead code in hive_mind_integration.py is removed — no live production crash risk from LangGraph tombstones
**Depends on**: Phase 40
**Requirements**: ADK-06, ADK-07, ADK-08
**Success Criteria** (what must be TRUE):
  1. `GET /api/v2/adk/run` (or equivalent) returns a valid response with at least one Pydantic AI agent wrapped as an ADK FunctionTool
  2. The ADK Runner processes a request end-to-end: receives input, calls PIISafeADKWrapper, returns output — verifiable via integration test with synthetic data
  3. `grep -n "LANGGRAPH_ONLY\|_process_with_langgraph" backend-hormonia/app/services/hive_mind_integration.py` returns zero results
  4. The HiveMind service no longer crashes at import time — running `python -c "from app.services.hive_mind_integration import HiveMindService"` succeeds without ImportError
**Plans**: 4 plans
Plans:
- [x] 41-01-PLAN.md — Wrap sentiment/humanize/variation/empathy as ADK tools and implement wrapper runtime invocation
- [x] 41-02-PLAN.md — Expose `/api/v2/adk/run` endpoint with schema and integration tests through PIISafeADKWrapper
- [x] 41-03-PLAN.md — Remove HiveMind LangGraph dead code paths and add regression/import safety checks
- [ ] 41-04-PLAN.md — Gap closure: replace plain handler dispatch with real ADK FunctionTool + Runner primitives (ADK-06, ADK-07)

### Phase 42: Admin SPA Quality
**Goal**: The admin SPA shows accurate WuzAPI connection status to physicians (no "Evolution API disabled" banner), all API calls hit real backend endpoints, and the codebase passes ESLint and TypeScript checks cleanly
**Depends on**: Phase 39 (v1.6 complete — can run in parallel with Phases 40-41)
**Requirements**: ADMIN-01, ADMIN-02, ADMIN-03, ADMIN-04, ADMIN-05, ADMIN-06, ADMIN-07, ADMIN-08
**Success Criteria** (what must be TRUE):
  1. `grep -r "VITE_ENABLE_EVOLUTION" frontend-hormonia/src/` returns zero results and the WhatsApp dashboard shows WuzAPI connection status instead of an Evolution placeholder
  2. `tsc --noEmit` exits with code 0 in the admin SPA with zero type errors
  3. `eslint .` exits with zero errors in the admin SPA (warnings acceptable, errors must be zero)
  4. AgentSwarm.tsx and SystemHealth.tsx fetch data via TanStack Query `useQuery` with `refetchInterval` — no raw `useEffect` polling loops remain in those components
  5. `knip` (or equivalent unused-package audit) reports zero unused npm packages in the admin SPA after cleanup
**Plans**: TBD

### Phase 43: Quiz Interface Quality
**Goal**: The quiz interface has aligned tooling with the admin SPA (same ESLint major, Prettier enforced), all test dependencies are present, and the codebase passes TypeScript and ESLint checks cleanly
**Depends on**: Phase 42 (tooling decisions made for admin SPA apply here)
**Requirements**: QUIZ-01, QUIZ-02, QUIZ-03, QUIZ-04, QUIZ-05, QUIZ-06, QUIZ-07
**Success Criteria** (what must be TRUE):
  1. `prettier --check .` exits with code 0 in the quiz interface (all files formatted)
  2. Next.js version is 15.x and `npm run build` succeeds without errors
  3. `tsc --noEmit` exits with code 0 in the quiz interface with zero type errors
  4. `eslint .` exits with zero errors in the quiz interface using ESLint 9 flat config
  5. `npm test` passes in the quiz interface — `identity-obj-proxy` and `msw` v2 are present and CSS module tests no longer fail
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-5. Foundations | v1.0 | 13/13 | Complete | 2026-02-22 |
| 6-9. Architecture & Observability | v1.1 | 10/10 | Complete | 2026-02-23 |
| 10-13. AI Framework Migration | v1.2 | 16/16 | Complete | 2026-02-24 |
| 14-19. Flow Health & Cleanup | v1.3 | 31/31 | Complete | 2026-02-26 |
| 20-28. AsyncSession & Test Stability | v1.4 | 54/54 | Complete | 2026-02-28 |
| 29-32. Saga Orchestrator Deep Dive | v1.5 | 14/14 | Complete | 2026-03-01 |
| 33-39. WuzAPI Migration | v1.6 | 21/21 | Complete | 2026-03-03 |
| 40. OTel Removal & ADK Foundation | 3/3 | Complete    | 2026-03-03 | - |
| 41. ADK Agent Integration | 4/4 | Complete   | 2026-03-04 | - |
| 42. Admin SPA Quality | v1.7 | 0/TBD | Not started | - |
| 43. Quiz Interface Quality | v1.7 | 0/TBD | Not started | - |

---
*Roadmap created: 2026-02-22*
*Last updated: 2026-03-04 — Phase 41 gap closure plan added (41-04)*
