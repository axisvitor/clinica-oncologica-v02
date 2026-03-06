---
gsd_state_version: 1.0
milestone: v1.8
milestone_name: ADK Stability & Error Hardening
current_plan: 0/TBD planned
status: ready_to_plan
stopped_at: Completed Phase 46 verification
last_updated: "2026-03-06T01:54:05Z"
last_activity: 2026-03-06 - Completed Phase 46 verification and marked OBS-02 complete
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 8
  completed_plans: 8
  percent: 75
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-05)

**Core value:** Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.
**Current focus:** Planejar a Phase 47 para transformar a cobertura ADK estabilizada em gate de CI que bloqueia regressao antes do deploy.

## Current Position

Milestone: v1.8 ADK Stability & Error Hardening
Phase: 47 of 47 (ADK CI Smoke Gate) - next phase after Phase 46 completed on 2026-03-06
Plan: not started
Current Plan: 0/TBD planned
Total Plans in Phase: TBD
Status: Ready to plan
Last Activity: 2026-03-06 - Completed Phase 46 verification and marked OBS-02 complete

Progress: [████████░░] 75%

## Performance Metrics

| Milestone | Phases | Plans | Timeline |
|-----------|--------|-------|----------|
| v1.0-v1.7 (shipped) | 43 | 179 | 2026-02-22 -> 2026-03-05 |
| v1.8 (in progress) | 4 | 8 | 2026-03-05 -> present |
| Phase 45 P01 | 41min | 2 tasks | 5 files |
| Phase 45 P02 | 7min | 2 tasks | 5 files |
| Phase 45 P03 | 10min | 2 tasks | 5 files |
| Phase 45 P04 | 4m | 2 tasks | 3 files |
| Phase 46 P01 | 8m | 2 tasks | 4 files |

## Accumulated Context

### Decisions

- [Phase 44]: Persist ADK session and invocation metadata in an application-owned Redis-first store with process-local fallback for host compatibility.
- [Phase 44]: Normalize runtime terminal outcomes to explicit operator-facing statuses (`success`, `closed`, `cancelled`, `timeout`, `limit_exceeded`).
- [Phase 44]: Prune low-priority session state before rejecting oversized resumes so high-value clinical context survives bounded-state enforcement.
- [v1.8 roadmap]: Fases derivadas apenas dos requisitos v1.8 (ADK-09..13, OBS-02).
- [v1.8 roadmap]: Ordem por dependencia de capacidade: runtime -> safety/errors -> observability -> CI gate.
- [v1.8 roadmap]: Cobertura 100% validada com mapeamento 1:1 de requisito para fase.
- [v1.7 roadmap]: Phase 40 and Phase 42 can run in parallel (no shared code between backend ADK and frontend admin); sequential ordering chosen to keep plans focused
- [v1.7 roadmap]: ADK split into two phases (40: foundation/safety, 41: wiring) to enforce PIISafeADKWrapper + CI guard gate before any patient data reaches ADK
- [v1.7 roadmap]: Phase 43 depends on Phase 42 (tooling decisions — ESLint major, Prettier config pattern — made once in admin SPA then mirrored to quiz)
- [v1.7 research]: OTel removal target is instrumentation packages only (not opentelemetry-api/sdk core); ADK re-introduces OTel core as transitive dep at its own version range
- [v1.7 research]: HiveMind LangGraph dead code (LANGGRAPH_ONLY enum value + _process_with_langgraph method) is a live production crash risk — must be removed in Phase 41
- [v1.6]: WuzAPIClient uses aiohttp; hard cut with no dual-provider mode; Evolution tombstoned after Phase 36
- [Phase 40]: Used python:3.13-slim container for ADK compatibility gate because host python3.13 was unavailable.
- [Phase 40]: Kept protobuf pin and updated rationale for retained Google/ADK dependency compatibility.
- [Phase 40]: Added CeleryIntegration explicitly in setup_sentry() to preserve FastAPI->Celery trace correlation post-OTel cleanup.
- [Phase 40]: Mirror PIISafeAgent safety contract in PIISafeADKWrapper.safe_run before ADK wiring
- [Phase 40]: Keep AIDeps typing via TYPE_CHECKING to avoid runtime import side effects during package import
- [Phase 40]: Keep one CI guard script for pydantic-ai and ADK direct-run policy
- [Phase 40]: Add optional scan-root argument so guard regression tests can target tmp fixtures
- [Phase 41]: Keep ADK execution behind PIISafeADKWrapper by delegating wrapper _invoke_adk to runtime helper.
- [Phase 41]: Normalize all tool and runtime responses to stable {status, result} payloads for downstream endpoint wiring.
- [Phase 41]: Removed LANGGRAPH_ONLY mode and _process_with_langgraph path entirely to eliminate unsupported crash-prone execution.
- [Phase 41]: Added source-level and import-level regression tests to permanently guard against LangGraph tombstone symbol reintroduction.
- [Phase 41]: Kept /api/v2/adk/run as a thin router that always delegates execution through PIISafeADKWrapper.safe_run.
- [Phase 41]: Standardized ADK endpoint response as {status, tool_name, session_id, output} with request_source metadata in wrapper context.
- [Phase 41]: Build deterministic single-tool Agent instances so requested tool_name maps to exactly one FunctionTool in Runner mode
- [Phase 41]: Preserve host compatibility by keeping direct-handler fallback when ADK runtime is unavailable
- [Phase 42]: Use semi:false and singleQuote:true as the admin SPA formatting baseline with Prettier
- [Phase 42]: Keep eslint-config-prettier as the final tseslint.config entry to disable formatting conflicts
- [Phase 42]: Kept Hive Mind frontend client surface limited to /health and /agents to match live backend endpoints and avoid guaranteed 404 routes.
- [Phase 42]: Confirmed ADMIN-03 duplicate-call audit: WhatsAppService uses /api/v2/whatsapp/* while apiClient modules do not call WhatsApp endpoints, so no endpoint deduplication was required.
- [Phase 42]: Kept Hive Mind query keys scoped to ['hive-mind','agents'] and ['hive-mind','health'] to keep TanStack Query cache segments explicit and stable.
- [Phase 42]: Preserved existing loading/error/content UI while replacing manual interval polling with useQuery refetchInterval for both Hive Mind widgets.
- [Phase 42-admin-spa-quality]: Kept recharts as intentional knip false positive due to dynamic import usage.
- [Phase 42-admin-spa-quality]: Checkpoint Task 2 was finalized from explicit user approval before docs/state closeout.
- [Phase 42-admin-spa-quality]: Render WhatsAppDashboard directly in WhatsAppPage so routed users see WuzAPI connection state immediately
- [Phase 42-admin-spa-quality]: Use connectRef indirection in MetricsWebSocket reconnect callback to satisfy react-hooks dependency rules without lint suppression
- [Phase 42-admin-spa-quality]: Checkpoint closure required explicit approved signal before plan closeout.
- [Phase 42-admin-spa-quality]: Continuation honored prior Task 1 commit and resumed from Task 2 without rework.
- [Phase 42-admin-spa-quality]: Removed all five knip-flagged unused dependencies instead of preserving dead-path imports.
- [Phase 42-admin-spa-quality]: Replaced axios/Radix-dependent code paths with local implementations to keep gates green post-prune.
- [Phase 43-quiz-interface-quality]: Kept React/React DOM on 18.3.x with Next 15 to avoid ecosystem peer conflicts while upgrading lint/framework baselines.
- [Phase 43-quiz-interface-quality]: Migrated to ESLint 9 flat config through FlatCompat and kept eslint-config-prettier as the final entry.
- [Phase 43-quiz-interface-quality]: Kept Jest on jsdom but enabled node export conditions to resolve MSW v2 node entrypoints.
- [Phase 43-quiz-interface-quality]: Added dedicated test polyfill bootstrap loaded before msw/node server import for stable MSW v2 interceptors.
- [Phase 43-quiz-interface-quality]: Validate quiz API payloads at boundaries with zod and friendly ApiError fallbacks.
- [Phase 43-quiz-interface-quality]: Keep 43-03 scoped to locked core files; defer pre-existing cross-app React type collisions to follow-up plan.
- [Phase 43]: Localize quiz toast store dependency to avoid cross-app runtime/type coupling
- [Phase 43]: Reuse shared quiz shell class constants across route and component wrappers for consistent layout semantics
- [Phase 43]: Kept quiz submit boundary parsing strict and aligned test/MSW mocks to required is_last_question and session_status fields.
- [Phase 43]: Preserved destructive toast assertions only in explicit error paths while restoring success/completion flow assertions.
- [Phase 43]: Use quiz-local copies of shadcn/radix UI primitives instead of source-level cross-app bridges to keep a single React type universe.
- [Phase 43]: Add ownership tests that assert local import boundaries so bridge regressions fail fast in CI.
- [Phase 45]: Policy decisions are driven by explicit tool_policy metadata at the runtime boundary instead of tool-local validation or model-text parsing.
- [Phase 45]: Once the ADK runner path starts, failures no longer silently fall through to direct handler execution.
- [Phase 45]: Keep tool safety decisions at the runtime boundary — ADK runner execution and direct-handler fallback now share the same deterministic policy verdict.
- [Phase 45]: Forward normalized tool_policy metadata from PIISafeADKWrapper — Safety stays explicit in request context instead of being inferred inside tool handlers.
- [Phase 45]: Wrap tool-dispatch exceptions with explicit ADKToolExecutionError metadata so runtime classification never parses raw exception strings.
- [Phase 45]: Treat any failure after the ADK runner path starts as deterministic classification instead of falling through to direct-handler execution.
- [Phase 45]: Phase 45-03 locked final deterministic regressions through test-only coverage because the existing runtime already passed the expanded repeated-scenario suite.
- [Phase 45]: Phase 45-03 keeps real google-adk regression coverage conditional in validation and defers CI smoke gating to Phase 47.
- [Phase 45]: Runner callback policy evaluation restores operator-owned required-context paths before evaluating required_context_keys.
- [Phase 45]: ADK tool dispatch preserves operator tool_policy, policy, and required_context_keys metadata while still allowing non-policy context merges for approved executions.
- [Phase 46]: Keep ADK observability on the default Prometheus registry so the existing `/metrics` exporter surfaces new series without extra wiring.
- [Phase 46]: Record only low-cardinality labels (`tool_name`, `status`) in metrics and keep `invocation_id`/`session_id` exclusively in structured logs.
- [Phase 46]: Measure latency at the `run_adk_tool` boundary so session resolution, policy checks, and terminal runtime paths all contribute to invocation timing.

### Pending Todos

- Nenhum todo pendente para a Phase 46.

### Blockers/Concerns

- Validacao local ainda pula os testes de integracao com `google-adk` real quando o pacote nao esta instalado; manter o follow-up de staging documentado em `45-VALIDATION.md`.
- Phase 40: ADK pip resolution with pydantic-ai-slim[google] in Python 3.13 is MEDIUM confidence — first task of Phase 40 must run dry-run install and document resolved versions before touching requirements.txt
- Phase 40: PIISafeADKWrapper hook point (ADK before_model_callback vs call-site) needs spike in ADK v1.26.0 source before implementation
- Phase 42: hive-mind.ts frontend module disposition (keep vs remove) depends on whether /api/v2/hive-mind/* routes exist in current backend router — verify in Phase 42 plan

## Session Continuity

**Last session:** 2026-03-06T00:54:30.875Z
**Stopped At:** Completed 45-04-PLAN.md
**Resume File:** None
