# Project Research Summary

**Project:** Clinica Oncologica v1.7 — Frontend Quality Overhaul + Google ADK Integration
**Domain:** Brownfield SPA/Next.js quality cleanup + Python AI framework expansion (React 19 / Next.js 14 / FastAPI + Google ADK)
**Researched:** 2026-03-03
**Confidence:** HIGH (OTel/ADK conflict verified from github issues + pyproject.toml; frontend gaps verified from codebase inspection), MEDIUM (ADK integration scope — install-time pip resolution needs real-environment confirmation)

---

## Executive Summary

v1.7 is a dual-workstream milestone with two nearly independent tracks: a frontend quality overhaul across both frontends (admin SPA and quiz interface) and a backend AI framework expansion via Google ADK. The two tracks share one critical cross-cutting concern — ADK integration on the backend must not be attempted before OpenTelemetry instrumentation packages are removed, because ADK v1.26.0 bundles its own OTel context manager and running two OTel stacks in the same async Python process produces non-deterministic `ValueError: Token was created in a different Context` crashes. Once OTel instrumentation is removed, ADK can be installed cleanly alongside the existing Pydantic AI agents without replacing them.

The recommended approach treats OTel removal as its own phase rather than a sub-task of ADK integration. The frontend workstream runs in parallel: the admin SPA has confirmed dead code from the v1.6 WuzAPI migration (Evolution API feature flags, settings fields, and type definitions that no longer have a backend counterpart), stale AI provider references (OpenAI/LangChain comments that survived the v1.2 AI rationalization), and inconsistent data-fetching patterns (raw `useEffect` polling instead of TanStack Query). The quiz interface needs ESLint alignment with the admin SPA's ESLint 9 flat config and has a missing test dependency (`identity-obj-proxy`). Both frontends need Prettier added. None of these frontend tasks block or depend on the ADK work.

The primary risk in this milestone is LGPD compliance. ADK integration introduces a new AI call path that must be protected by PII redaction equivalent to the existing `PIISafeAgent` wrapper. The CI guard (`scripts/check_agent_run_calls.py`) must be extended to cover ADK tool call patterns before any ADK agent processes patient data. On the frontend, Evolution API dead code creates active physician UX confusion — clinicians see "Evolution API disabled" on the WhatsApp dashboard instead of WuzAPI connection status. This is the highest-priority frontend cleanup item because it affects clinical workflow visibility.

---

## Key Findings

### Recommended Stack

The stack changes for v1.7 are surgical: remove 9 OTel packages, add one Python package (`google-adk>=1.26.0,<2.0.0`), and add tooling to both frontends (Prettier + ESLint integrations). The underlying stack — FastAPI + AsyncSession + Celery + Dragonfly + Pydantic AI + google-genai — is unchanged. ADK sits alongside Pydantic AI at a different abstraction level: Pydantic AI handles typed, structured AI calls; ADK provides Runner, Session, and multi-step agent orchestration primitives for new scenarios not currently covered by the four existing agents.

The critical subtlety in the OTel removal is that ADK re-imports OTel as a transitive dependency. The removal target is the seven *instrumentation* packages (`opentelemetry-instrumentation-fastapi`, `-sqlalchemy`, `-redis`, `-httpx`) and the OTLP exporter packages — not the OTel core API/SDK, which ADK will re-introduce at a version range it controls (`>=1.36.0,<1.39.0`). The existing `app/core/tracing.py` mock fallback path is already written and all callers (`message_service.py`, `unified_whatsapp_service.py`) use `get_tracer()` which transparently returns a no-op mock when OTel instrumentation is absent. The file should be converted to a tombstone after ADK install is confirmed.

**Core technologies (changes for v1.7):**
- `google-adk>=1.26.0,<2.0.0`: Multi-step agent orchestration, Runner, SessionService — sits alongside existing Pydantic AI agents
- `prettier>=3.5.0`: Code formatting enforced via lint-staged pre-commit in both frontends — absent today, causing silent drift
- `eslint-config-prettier + eslint-plugin-prettier`: Bridges ESLint 9 flat config (admin SPA) and Prettier — required companion packages
- `eslint-plugin-jsx-a11y>=6.10.0`: Accessibility lint for admin SPA (patient-facing oncology data demands a11y enforcement)
- `next@^15.3.0` (quiz): Unlocks ESLint 9 flat config support in quiz interface — aligns toolchains across monorepo
- `identity-obj-proxy@^3.0.0` (quiz): Already referenced in jest config but missing from devDependencies — breaks CSS module tests

**Packages to remove (backend):**
- `opentelemetry-instrumentation-fastapi/sqlalchemy/redis/httpx` + `opentelemetry-exporter-otlp` + `opentelemetry-exporter-otlp-proto-http` + `opentelemetry-proto` (7 lines from requirements.txt)

### Expected Features

v1.7 has two feature categories: quality corrections (removing what should not exist) and new capability additions (ADK). The quality corrections are the larger scope.

**Must have (table stakes — P1):**
- Evolution API dead code fully removed from admin SPA — physicians currently see "Evolution API disabled" banner on the WhatsApp dashboard; this affects clinical workflow visibility
- `hive-mind.ts` API module verified or removed — calls `/api/v2/hive-mind/*` endpoints that may not exist post-v1.2 AI rationalization; live 404s in production are worse than dead code
- OTel instrumentation packages removed from requirements.txt — blocks ADK install; confirmed runtime conflict
- `google-adk` installed and pip resolve confirmed clean — proof that google-genai version range satisfies both ADK and pydantic-ai-slim[google]
- ESLint zero errors in both frontends, TypeScript `tsc --noEmit` clean in both frontends
- `AgentSwarm.tsx` and `SystemHealth.tsx` converted from raw `useEffect` polling to TanStack Query `useQuery` with `refetchInterval`
- API client consolidation in admin SPA: single canonical `lib/api-client/`; `lib/api.ts` legacy monolith verified or removed

**Should have (differentiators — P2):**
- At least one Pydantic AI agent wrapped as an ADK `FunctionTool` as proof-of-concept — validates the integration pattern without destabilizing all four agents
- Layout consistency audit across admin SPA pages — padding, card structure, breadcrumb usage
- Prettier enforced via pre-commit in both frontends — prevents formatting drift silently accumulating

**Defer to v1.x / v2+:**
- ADK `InMemorySessionService` for multi-turn patient assessment context (only if a multi-turn use case emerges)
- ADK evaluation harness for agent quality regression testing
- Remaining 3 Pydantic AI agents wrapped as ADK FunctionTools (after first one validated)
- Next.js upgrade for quiz if not being done in this milestone — not essential for quality fixes
- ADK `DatabaseSessionService` backed by PostgreSQL for persistent agent memory
- MSW v2 upgrade in quiz interface (breaking API change — dedicate a separate story)

### Architecture Approach

The system architecture is a layered monolith with a well-established feature-slice frontend and a DDD-structured FastAPI backend. Frontend quality work does not change any API contracts — it corrects internal frontend consistency and removes dead branches. ADK integration adds a new module (`app/ai/adk/`) alongside the existing AI stack without modifying any existing file in `app/ai/agents/`.

The key architectural constraint is the PIISafeAgent boundary. Every AI invocation that touches patient data must pass through `PIISafeAgent._safe_run()` (or an equivalent wrapper) for LGPD Art. 46 PII redaction. This boundary exists today for the four Pydantic AI agents and is enforced by CI lint. ADK introduces a new invocation path that bypasses the existing lint guard unless the guard is explicitly extended. The `PIISafeADKWrapper` must implement the same PII sanitization pattern as `PIISafeAgent` and must be introduced before any ADK tool processes real patient data.

**Major components (v1.7 changes):**
1. `app/ai/adk/` (NEW) — ADK module: `runner.py`, `wrapper.py` (PIISafeADKWrapper), `agents/` directory; no modifications to existing `app/ai/agents/`
2. `app/core/tracing.py` (TOMBSTONE) — converts to `raise ImportError` stub after ADK install confirms mock-only path works
3. `frontend-hormonia/src/features/whatsapp/WhatsAppDashboard.tsx` (REWORK) — remove Evolution gate; wire to WuzAPI status endpoints
4. `frontend-hormonia/src/lib/api-client/` (AUDIT) — consolidate; verify hive-mind module against live backend routes
5. `quiz-mensal-interface/` (TOOLING) — add Prettier, align ESLint to v9 flat config via Next.js 15 upgrade

### Critical Pitfalls

1. **ADK reintroduces OTel as a transitive dependency** — removing OTel from requirements.txt while installing ADK leaves OTel as an ADK-managed transitive dep at a version range the project no longer controls. The correct strategy: remove only the *instrumentation* packages, not the core API/SDK. After ADK install, run `pip show opentelemetry-api` and document whether it is present. The goal is to eliminate the instrumentation context conflicts, not to have zero OTel packages installed. Tombstone `app/core/tracing.py` to prevent future ambiguity.

2. **PIISafeAgent bypass via ADK tool functions** — if a developer passes a Pydantic AI agent object directly to an ADK `FunctionTool` and calls `agent.run()` inside the tool function, the CI guard (`scripts/check_agent_run_calls.py`) may not detect it through indirect references or lambda patterns. Patient oncology data reaches Gemini unredacted — LGPD Art. 46 violation. Prevention: extend the CI guard to scan for `.run()` inside ADK `@tool`-decorated functions before writing any agent wiring code. Add an integration test with synthetic PHI input that asserts the PII redaction log line appears before every Gemini API call through the ADK path.

3. **Evolution API dead code actively confusing physicians** — `WhatsAppDashboard.tsx` renders "Evolution API disabled" text to clinic physicians (confirmed in codebase lines 183-195). This is not dormant dead code — it is active UI producing wrong information. Priority: remove the `VITE_ENABLE_EVOLUTION` gate entirely and replace with WuzAPI connection status. `grep -r "VITE_ENABLE_EVOLUTION" frontend-hormonia/src/` must return zero results before this phase is complete.

4. **HiveMind service references tombstoned LangGraph** — `hive_mind_integration.py` contains `IntegrationMode.LANGGRAPH_ONLY` and `_process_with_langgraph()` which will crash with `ImportError` from the LangGraph tombstones if invoked. The HiveMind endpoint is actively routed in production (`api/v2/router.py` line 107) and `HiveMindPage.tsx` is in `routeDefinitions.tsx`. This is a live production crash risk, not latent dead code. Remove both the enum value and the method before wiring ADK to HiveMind.

5. **React Strict Mode double-invocation breaks quiz session init** — The `useQuizSession` hook has a `useRef` guard preventing double-execution under React Strict Mode. If this guard is removed during quality cleanup (it looks like unnecessary complexity), the session init fires twice in development: either two sessions are created for one patient or the second attempt fails with "token already used," leaving patients stuck. Prevention: add a unit test simulating double-invocation before touching the hook. The guard must be documented with a comment explaining its purpose before cleanup begins.

6. **Sentry trace correlation may break after OTel removal** — if `sentry-sdk[fastapi]` was configured to use OTel's `traceparent` header for request-to-task correlation, removing OTel instrumentation breaks the correlation. Prevention: sample one production request in Sentry BEFORE OTel removal to baseline the transaction tree depth. After removal, verify same tree depth. Ensure `FastApiIntegration` and `CeleryIntegration` are explicitly registered — Sentry does not require OTel for its own tracing.

---

## Implications for Roadmap

Based on combined research, a 4-phase structure is recommended. Frontend workstream (Phases 2 and 3) can run in parallel with backend ADK workstream (Phase 1), because they touch entirely separate codebases. Phase 4 (validation) gates all workstreams.

### Phase 1: OTel Removal and ADK Foundation

**Rationale:** OTel instrumentation removal is the only strict blocker for ADK integration. It must be its own phase because removing OTel packages has observable side effects (Sentry correlation must be validated, `app/core/tracing.py` must be handled, and the transitive dep question must be answered). Installing ADK in the same step would make it impossible to isolate which change caused any regression. Doing OTel removal first, validating it, then installing ADK in the same phase as a second step produces a clean install state.
**Delivers:** 7 OTel instrumentation packages removed from requirements.txt; `app/core/tracing.py` converted to a no-op shim or tombstone; Sentry transaction correlation validated (baseline before, confirmed after); `google-adk>=1.26.0` installed and pip resolve documented; `app/ai/adk/` module scaffolded with `PIISafeADKWrapper`; CI guard (`check_agent_run_calls.py`) extended to detect ADK tool `.run()` patterns; at least one Pydantic AI agent wrapped as ADK FunctionTool (proof-of-concept).
**Addresses:** OTel removal (table stakes), google-adk installation (table stakes), PIISafeAgent contract preserved (table stakes).
**Avoids:** OTel transitive dep reintroduction (Pitfall 1), PIISafeAgent bypass (Pitfall 2), dual OTel context crashes.

### Phase 2: Admin SPA Frontend Quality

**Rationale:** Admin SPA quality work is independent of backend ADK work and can run in parallel with Phase 1. It is prioritized over the quiz interface because it has physician-facing broken UX (Evolution API banner), live production crash risk (HiveMind LangGraph dead code), and potentially dead API calls to non-existent endpoints (hive-mind.ts module). These are active problems, not latent debt.
**Delivers:** Evolution API dead code fully removed (WhatsAppDashboard, AdminSettingsTab, env-validator, runtime-config, api-wave2.ts Evolution types); `grep -r "VITE_ENABLE_EVOLUTION"` returns zero results; WuzAPI connection status card replacing Evolution placeholder; `hive-mind.ts` module verified against live backend routes or removed; `IntegrationMode.LANGGRAPH_ONLY` and `_process_with_langgraph()` removed from hive_mind_integration.py; stale AI provider references removed (OpenAI/LangChain type fields and comments); API client consolidation (`lib/api.ts` legacy monolith resolved); `AgentSwarm.tsx` and `SystemHealth.tsx` converted to TanStack Query; type duplication between `src/types/` and `src/lib/types/` resolved.
**Uses:** Existing `apiClient` WuzAPI endpoints; TanStack Query v5 already installed; existing TypeScript strict config.
**Avoids:** Evolution dead code confusing physicians (Pitfall 3), HiveMind LangGraph crash (Pitfall 4), HTTP 404 from dead API client calls.

### Phase 3: Frontend Tooling and Quiz Quality

**Rationale:** Both frontends need Prettier added. The quiz interface has a separate set of quality issues (ESLint 8 vs 9 inconsistency, missing test dependency, `useQuizSession` Strict Mode guard risk). These are lower urgency than Phase 2 (no active physician-facing issues) and can run in parallel with Phase 1 but depend on Phase 2 completing (to avoid duplicate work on shared frontend tooling decisions).
**Delivers:** Prettier configured in both frontends with `.prettierrc`; `eslint-config-prettier` and `eslint-plugin-prettier` added to both frontends; `eslint-plugin-jsx-a11y` added to admin SPA; `identity-obj-proxy` added to quiz devDependencies; Next.js upgraded to 15.x in quiz (enables ESLint 9 flat config); `useQuizSession.ts` Strict Mode guard documented and unit-tested before any refactoring; `tsc --noEmit` passing in both frontends; zero ESLint errors in both frontends; lint-staged updated to run `prettier --write` on staged files.
**Implements:** Monorepo toolchain consistency (single ESLint major version, shared Prettier config pattern).
**Avoids:** Quiz Strict Mode double-invocation (Pitfall 5), date-fns version divergence from copy-paste between frontends (standardize on one version in this phase), 501 responses showing as infinite loading state.

### Phase 4: Validation and CI Gate

**Rationale:** Cross-cutting verification that all v1.7 deliverables are complete and integrated. This is not a follow-on cleanup — it is a gate. The "Looks Done But Isn't" checklist from PITFALLS.md must be exhaustively verified. CI must pass cleanly on both frontend and backend changes together.
**Delivers:** All PITFALLS.md "Looks Done But Isn't" checklist items verified; ADK integration test with synthetic PHI input confirming PII redaction log line appears before Gemini API call; `grep -r "VITE_ENABLE_EVOLUTION"` and `grep -n "LANGGRAPH_ONLY"` both return zero; `tsc --noEmit` and `eslint` clean in both frontends; `pip check` clean with ADK installed; Sentry transaction tree confirmed intact; date-fns version aligned across both frontends; ADK session lifecycle verified closed in all exception paths.

### Phase Ordering Rationale

- Phase 1 and Phases 2+3 in parallel: No shared code between backend ADK work and frontend quality work. Parallel execution reduces total wall time.
- Phase 1 OTel removal before ADK install: ADK install with OTel instrumentation present produces async context crashes; the removal must be deployed and validated first.
- Phase 2 before Phase 3: Admin SPA has active physician UX issues and a live production crash risk (HiveMind) that outprioritize quiz tooling work.
- Phase 4 as a gate after all other phases: Validation items depend on all prior deliverables being in place; running validation incrementally during earlier phases reduces final verification burden.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (ADK pip resolution):** `google-genai` version range compatibility between ADK v1.26.0 and `pydantic-ai-slim[google]` is MEDIUM confidence. Must run `pip install google-adk pydantic-ai-slim[google] --dry-run` in a clean environment and inspect the resolved versions before committing the requirements.txt change. If there is a conflict, version pinning may be needed.
- **Phase 1 (PIISafeADKWrapper design):** ADK's `before_model_callback` hook vs pre-processing at the calling site for PII sanitization — the correct integration point is not fully documented in ADK v1.26.0 docs. A spike to read ADK source code for callback ordering is recommended before implementing `PIISafeADKWrapper`.
- **Phase 2 (hive-mind.ts backend routes):** Whether `/api/v2/hive-mind/*` endpoints exist in the current backend router is UNKNOWN. Must verify `api/v2/router.py` and all sub-routers before deciding to keep or remove `hive-mind.ts`. If the routes exist and serve ADK-based content, the frontend module stays. If they are tombstoned, remove the module.

Phases with standard patterns (research-phase not needed):
- **Phase 1 (OTel package removal):** The exact 7 packages to remove are documented in STACK.md and PITFALLS.md with verification steps. Standard requirements.txt edit with known callers.
- **Phase 2 (Evolution dead code removal):** All file locations and line numbers confirmed via codebase inspection. Deterministic grep-verify completion criteria.
- **Phase 3 (Prettier + ESLint setup):** Well-documented pattern for ESLint 9 flat config + Prettier. Installation commands and config templates are in STACK.md.
- **Phase 4 (validation):** PITFALLS.md "Looks Done But Isn't" checklist provides explicit pass/fail criteria for every item. No novel verification patterns needed.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | OTel/ADK conflict verified from 3 github issues (adk-python #860, #1670, #2792) + pyproject.toml. Frontend tooling gaps verified from direct package.json inspection. ADK version pinning and pip resolution is MEDIUM until real install test runs. |
| Features | HIGH | Frontend dead code locations verified by direct file reads (specific line numbers confirmed). ADK feature scope (FunctionTool wrapping pattern) is HIGH confidence from official ADK docs. hive-mind.ts backend route existence is the one unverified gap. |
| Architecture | HIGH | Direct codebase inspection of all affected files. PIISafeAgent pattern fully understood. `app/ai/adk/` placement is a clean additive design with no modifications to existing modules. The OTel mock fallback path in `tracing.py` is already written and working. |
| Pitfalls | HIGH | All 7 critical pitfalls grounded in direct codebase evidence (specific file paths and line numbers) or confirmed github issue reports. LGPD violation scenarios mapped to specific articles. React Strict Mode guard confirmed present in `useQuizSession.ts`. |

**Overall confidence:** HIGH

### Gaps to Address

- **google-adk pip resolution with pydantic-ai-slim[google]:** Must verify google-genai version transitive compatibility in a clean Python 3.13 environment before finalizing requirements.txt change. Run `pip install google-adk pydantic-ai-slim[google] 2>&1 | grep -i "error\|conflict"` as the first task of Phase 1. If conflict: pin google-genai explicitly to the ADK-compatible range.

- **HiveMind backend route existence:** `lib/api-client/hive-mind.ts` calls `/api/v2/hive-mind/*` endpoints. Whether these routes exist in the current `api/v2/router.py` and sub-routers must be verified before Phase 2 begins. If they exist and are active, the hive-mind frontend module should be updated (not removed) when ADK is wired in Phase 1. If they are tombstoned or never registered, remove the frontend module in Phase 2.

- **ADK `before_model_callback` vs call-site PII sanitization:** The correct hook point for `PIISafeADKWrapper` needs a one-task spike reading ADK v1.26.0 source code. `before_model_callback` fires before every model call, which is the desired behavior, but its exact signature and whether it can access and modify the prompt content needs confirmation.

- **date-fns version standardization decision:** Admin SPA uses date-fns v3; quiz uses date-fns v4. Phase 3 must make a deliberate choice (upgrade admin to v4, or pin quiz to v3) before any date utility code is shared. The decision should be documented in the story before any code changes.

---

## Sources

### Primary (HIGH confidence)

- `google/adk-python` pyproject.toml — exact OTel version constraints `>=1.36.0,<1.39.0`: https://github.com/google/adk-python/blob/main/pyproject.toml
- `google-adk` PyPI page — v1.26.0, Python >=3.10: https://pypi.org/project/google-adk/
- ADK issue #1670 — "Failed to detach context" OTel conflict (Jun 2025): https://github.com/google/adk-python/issues/1670
- ADK issue #2792 — No public API to disable ADK internal OTel (open as of Aug 2025): https://github.com/google/adk-python/issues/2792
- ADK issue #860 — OTel context ValueError with ADK ParallelAgent (May 2025): https://github.com/google/adk-python/issues/860
- ADK CHANGELOG v1.26.0 — "relax OTel version constraints" (confirms OTel is NOT removed from ADK): https://github.com/google/adk-python/blob/main/CHANGELOG.md
- Codebase: `backend-hormonia/requirements.txt` — 9 explicit OTel package lines confirmed
- Codebase: `backend-hormonia/app/core/tracing.py` — `OPENTELEMETRY_AVAILABLE = False` mock fallback path confirmed
- Codebase: `frontend-hormonia/src/features/whatsapp/WhatsAppDashboard.tsx` lines 62-76, 183-195 — Evolution API dead code confirmed
- Codebase: `backend-hormonia/app/services/hive_mind_integration.py` lines 31, 473 — LangGraph dead references in active service confirmed
- Codebase: `quiz-mensal-interface/hooks/use-quiz-session.ts` — Strict Mode protection guard confirmed present
- Codebase: `frontend-hormonia/package.json` — ESLint 9, vitest 3.2.4, no Prettier confirmed
- Codebase: `quiz-mensal-interface/package.json` — Next.js 14, ESLint 8 legacy, msw v1, missing identity-obj-proxy confirmed
- Codebase: `frontend-hormonia/src/lib/api-client/hive-mind.ts` — calls `/api/v2/hive-mind/*` confirmed

### Secondary (MEDIUM confidence)

- ADK Sessions documentation: https://google.github.io/adk-docs/sessions/session/
- ADK Safety documentation (PII and callbacks): https://google.github.io/adk-docs/safety/
- Next.js ESLint 9 flat config support in Next.js 15: https://github.com/vercel/next.js/discussions/54238
- Prettier 3.x + ESLint 9 flat config setup pattern: https://leandroaps.medium.com/setting-up-eslint-and-prettier-in-a-react-19-project-with-vite-using-eslint-9-326147501971
- shadcn/ui React 19 + forwardRef migration: https://ui.shadcn.com/docs/react-19

### Tertiary (informational)

- ADK issue #3884 — `TypeError: BaseModel.model_dump()` with ADK + OTel + Pydantic output_schema: https://github.com/google/adk-python/issues/3884
- Langfuse issue #8316 — ADK + OTel conflict: https://github.com/langfuse/langfuse/issues/8316
- React 19 Strict Mode behavior: https://react.dev/blog/2024/12/05/react-19
- LGPD Art. 46 compliance checklist: https://captaincompliance.com/education/lgpd-compliance-checklist/

---

*Research completed: 2026-03-03*
*Ready for roadmap: yes*
