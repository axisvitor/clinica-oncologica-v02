# Pitfalls Research

**Domain:** Brownfield frontend quality overhaul (React 19 + Next.js 14) + Google ADK integration into existing Pydantic AI stack + OTel removal — v1.7 milestone
**Researched:** 2026-03-03
**Confidence:** HIGH (verified against codebase, ADK v1.26.0 release notes, and confirmed GitHub issues)

---

## Critical Pitfalls

### Pitfall 1: ADK Reintroduces OTel as a Transitive Dependency After "Removal"

**What goes wrong:**
The team removes all `opentelemetry-*` packages from `requirements.txt` to unblock ADK integration. ADK is then installed. ADK v1.24.0+ itself declares `opentelemetry-api>=1.36.0` and `opentelemetry-sdk>=1.36.0` as its own direct dependencies (ADK uses OTel for its own built-in tracing). The OTel packages return as transitive dependencies, now at a version range ADK controls — not the project. The instrumentation packages (`opentelemetry-instrumentation-fastapi`, `-sqlalchemy`, `-redis`, `-httpx`) are gone, but the core API/SDK is back. The result is a partial, unconfigured OTel install that no one intentionally set up, where `app/core/tracing.py` still exists with the full `DistributedTracer` class but now acts on ADK-imported OTel rather than nothing. The "relaxed version constraints" note in ADK v1.24.0 release notes ("Update OpenTelemetry dependency versions to relax version constraints for opentelemetry-api and opentelemetry-sdk") confirms OTel was NOT removed from ADK — only version pinning was loosened.

**Why it happens:**
Removing OTel from `requirements.txt` removes it from your explicit requirements but not from the installed environment if a peer package pulls it back. ADK's OTel dependency is not optional — it is used for ADK's own tracing of agent execution. Developers assume that removing explicit pins = removing the library.

**How to avoid:**
1. After installing ADK in isolation: `pip install google-adk && pip show opentelemetry-api opentelemetry-sdk`. If they appear, document that OTel is ADK-managed transitive dep — not your explicit dep.
2. Change the strategy: do NOT remove OTel core API/SDK. Remove only the *instrumentation packages* (`opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-sqlalchemy`, `opentelemetry-instrumentation-redis`, `opentelemetry-instrumentation-httpx`) and the OTLP exporters. These are the packages that add overhead and conflict — not the core.
3. Tombstone or convert `app/core/tracing.py` to a no-op shim. The two callers confirmed in the codebase (`message_service.py` L26 and `unified_whatsapp_service.py` L51) only use `get_tracer()` to set `self.tracer` — replacing with `MockTracer()` always requires zero API changes and zero risk.
4. Remove the `@trace(name="send_message_impl", attributes={"service": "wuzapi"})` decorator from `message_service.py` line 574 — it is the only active `@trace` decorator outside of `tracing.py` itself.

**Warning signs:**
- `pip check` shows `opentelemetry-api` conflicts after ADK install
- `opentelemetry.context ValueError: Token was created in a different Context` appears in Celery logs — documented ADK+ParallelAgent issue (github.com/google/adk-python/issues/860)
- `TypeError: BaseModel.model_dump() missing 1 required positional argument: 'self'` from ADK + OTel + Pydantic output_schema interaction (github.com/google/adk-python/issues/3884)

**Phase to address:**
OTel removal phase — MUST audit transitive deps before finalizing removal list. No OTel package should be removed without verifying ADK's requirements.

---

### Pitfall 2: PIISafeAgent Bypass When ADK Tools Call Pydantic AI Agents

**What goes wrong:**
Google ADK agents use `@tool` decorators and callback hooks to call external code. If a developer wires an ADK tool to invoke one of the four existing Pydantic AI agents (sentiment, humanize, variation, empathy) by passing `agent.run()` directly inside the tool function, the CI guard (`scripts/check_agent_run_calls.py`) may not detect this. The guard does static AST scanning for `.run(` on agent instances — ADK tool invocations that use indirect references, lambdas, or class methods may escape detection. Patient oncology data (CPF, name, diagnosis, treatment) reaches Gemini without PII redaction — a LGPD Art. 46 violation.

**Why it happens:**
ADK has its own agent execution model. Developers integrating ADK naturally use ADK-idiomatic patterns. The PIISafeAgent constraint is documented in `base.py` and MEMORY.md but is not structurally enforced in ADK-specific wiring code until someone extends the CI guard for ADK call patterns.

**How to avoid:**
1. Define every ADK tool as a plain async wrapper function that calls `PIISafeAgent._safe_run()` — never pass the Pydantic AI agent object directly to ADK's `FunctionTool` or `AgentTool`.
2. Extend `scripts/check_agent_run_calls.py` to also scan for `.run(` inside functions decorated with any ADK tool decorator pattern.
3. Add an integration test: invoke an ADK tool with a synthetic PHI payload (fake CPF, fake name). Assert that the PII redaction log line (`[PIISafeAgent]`) appears in the log output before the Gemini API call.
4. Use ADK's `before_tool_callback` to add a secondary PII check as defense-in-depth.
5. Apply PIISafeAgent BEFORE wiring, not as a retrofit — the PIISafeAgent CI guard was added in v1.2 precisely because retrofitting is hard.

**Warning signs:**
- CI guard passes but production structured logs show Gemini calls without the `[PIISafeAgent]` prefix
- Patient names or CPF numbers appear raw in Sentry error payload breadcrumbs
- ADK `tool_response` field in ADK session state contains patient identifiers

**Phase to address:**
ADK integration phase — the CI guard extension must be a prerequisite task, not a follow-up.

---

### Pitfall 3: Evolution API Dead Code Remains in Production Frontend Build

**What goes wrong:**
The WhatsApp hard cut to WuzAPI completed in v1.6 on the backend, but the frontend still ships Evolution API dead code. Confirmed in codebase:
- `WhatsAppDashboard.tsx` lines 62-76: `const [isEvolutionEnabled, setIsEvolutionEnabled] = useState(false)` and `VITE_ENABLE_EVOLUTION` check
- `WhatsAppDashboard.tsx` lines 183-195: renders "Evolution API disabled" placeholder visible to physicians
- `env-validator.ts` and `runtime-config.ts`: reference `VITE_ENABLE_EVOLUTION`
- `types/api-wave2.ts`: auto-generated October 2025, may contain Evolution-specific type shapes
- `AdminSettingsTab.tsx`: likely contains Evolution API settings fields

These dead branches add bundle weight, confuse future developers about provider state, and show misleading "Evolution API disabled" text to clinic physicians rather than WuzAPI connection status.

**Why it happens:**
Backend migrations are executed without synchronised frontend cleanup. v1.6 WuzAPI migration was documented as backend-only; "frontend foco backend" was an explicit scope constraint.

**How to avoid:**
1. Audit all `VITE_ENABLE_EVOLUTION` references as the first task in the frontend cleanup phase: `grep -r "VITE_ENABLE_EVOLUTION" frontend-hormonia/src/`.
2. Remove the feature flag and all conditional branches — there is no "disabled Evolution" state in the new system. The correct state is WuzAPI, always connected.
3. Replace `WhatsAppDashboard.tsx` Evolution placeholder with a WuzAPI-specific QR/status card that calls the WuzAPI instance status endpoint.
4. Remove Evolution-specific type definitions from `types/api-wave2.ts` — check what is actually consumed by the UI.
5. Remove Evolution settings fields from `AdminSettingsTab.tsx`.

**Warning signs:**
- `grep -r "VITE_ENABLE_EVOLUTION"` returns results in `src/` (currently confirmed)
- WhatsApp page shows "Enable it by setting VITE_ENABLE_EVOLUTION=true" — physicians see this message
- `WhatsAppService.ts` has methods pointing to `/evolution/` path prefixes

**Phase to address:**
Frontend dead code removal phase — prioritize WhatsApp feature area first due to physician UX impact.

---

### Pitfall 4: HiveMind Service Calls Tombstoned LangGraph Code

**What goes wrong:**
`app/services/hive_mind_integration.py` contains `IntegrationMode.LANGGRAPH_ONLY` (line 31) and `_process_with_langgraph()` (line 473). LangGraph was tombstoned in v1.2 — 9 modules in `app/ai/langgraph/` raise `ImportError` on import. If HiveMind service is instantiated and an external caller (the frontend HiveMind page, Celery Beat, or a future ADK orchestrator) triggers `LANGGRAPH_ONLY` mode, it crashes with `ImportError` from the tombstone.

The frontend `HiveMindPage.tsx` is actively routed in `routeDefinitions.tsx`. The `/hive-mind` router is registered in `api/v2/router.py` (confirmed: line 107). The endpoint is accessible in production — this is not dead frontend code guarded by a feature flag.

**Why it happens:**
HiveMind integration was written to bridge the old multi-mode system. The tombstoning of LangGraph removed the implementation but not the dead `IntegrationMode` enum value or the method that references it. The enum value has no callers at present, but it is a maintenance hazard if ADK integration adds a new orchestration path.

**How to avoid:**
1. Remove `LANGGRAPH_ONLY` from the `IntegrationMode` enum.
2. Delete `_process_with_langgraph()` method from `HiveMindIntegrationService`.
3. Determine the purpose and value of `HiveMindPage.tsx`. If it shows ADK-style multi-agent status, keep it and update to use ADK concepts. If it is purely legacy orchestration UI, remove the route.
4. Consider this a prerequisite for ADK integration — HiveMind is the natural landing zone for ADK wiring.

**Warning signs:**
- `grep -n "LANGGRAPH_ONLY\|_process_with_langgraph" backend-hormonia/app/services/hive_mind_integration.py` returns results (currently confirmed)
- HiveMind API endpoint returns 500 in production if called with a non-default integration mode

**Phase to address:**
Frontend dead code phase or ADK integration phase — clean up LangGraph references before wiring ADK to HiveMind service.

---

### Pitfall 5: Sentry Trace Correlation Breaks After OTel Instrumentation Removal

**What goes wrong:**
The system has `sentry-sdk[fastapi]>=1.38.0` installed. When OTel instrumentation packages (`opentelemetry-instrumentation-fastapi`, `-sqlalchemy`) are present, Sentry may use OTel context propagation headers (`traceparent`) to correlate FastAPI request traces with Celery task traces. After removing the instrumentation packages, if Sentry's context propagation relied on OTel's `W3CTraceContextPropagator`, request-to-task correlation in Sentry may break — showing separate isolated transactions instead of parent-child spans.

Note: Sentry does NOT require OTel for its own tracing. `sentry-sdk[fastapi]` includes its own FastAPI middleware that injects Sentry transaction IDs. However, if the project team had configured Sentry to read OTel's `traceparent` header instead of Sentry's own `sentry-trace` header, correlation breaks at the boundary.

**Why it happens:**
OTel and Sentry can interoperate through OpenTelemetry's `sentry-sdk` OTel integration. If this interop was configured, removing OTel instrumentation breaks the bridge. The `monitoring/sentry.ts` in the frontend has `beforeSend` filters — verifying those survive an OTel context change is non-trivial without explicit testing.

**How to avoid:**
1. Sample one production request BEFORE OTel removal: find a patient flow in Sentry and note the Sentry transaction tree depth (FastAPI root → Celery task → result).
2. After OTel removal, sample the same flow type and compare the transaction tree. If it is shallower or broken, Sentry was relying on OTel context propagation.
3. Fix: ensure `sentry-sdk[fastapi]` `FastApiIntegration` and `CeleryIntegration` are explicitly enabled in Sentry config — these provide trace correlation without OTel.
4. The two files that import from `tracing.py` (`message_service.py`, `unified_whatsapp_service.py`) do not affect Sentry directly — they only affect the `DistributedTracer` mock. Converting them to no-ops has zero Sentry impact.

**Warning signs:**
- Sentry transactions for `/api/v2/*` show as isolated (no Celery child spans) after OTel removal
- Railway Celery task logs lose `trace_id` field that previously matched FastAPI request trace ID
- Sentry "Performance" tab shows significantly fewer distributed traces

**Phase to address:**
OTel removal phase — validate Sentry observability explicitly before removing instrumentation packages, not as a post-hoc assumption.

---

### Pitfall 6: React Strict Mode Double-Invocation Breaks Quiz Session Initialization

**What goes wrong:**
The `quiz-mensal-interface` uses Next.js 13+ which enables React Strict Mode by default since v13.5.1. The `useQuizSession` hook already guards against this with a `useRef`-based double-execution guard (documented in the hook's JSDoc: "React Strict Mode protection (prevents double execution)"). If any refactoring during the quality pass removes this guard — perhaps because it looks like unnecessary complexity — the quiz session init fires twice.

The backend session init creates a cryptographic token and sets an HttpOnly cookie. A double-init either: (a) creates two sessions for the same patient, consuming two one-time-use tokens, or (b) the second init attempt fails because the token was consumed, leaving the patient stuck on an error screen. In either case, the patient's oncology follow-up quiz is disrupted.

**Why it happens:**
Developers cleaning "complex" hooks often simplify by removing guards they don't understand. The `useRef` guard looks like React antipattern boilerplate until you remove it and see the impact in development mode. Strict Mode is invisible in production (it is a development-only double-render), so removing the guard passes CI but breaks patient-facing behavior in development.

**How to avoid:**
1. Before the quality pass, add a block comment above the `useRef` guard in `useQuizSession.ts` explaining its purpose with explicit reference to React Strict Mode double-invoke behavior.
2. Add a unit test that renders the hook twice in quick succession (simulating Strict Mode) and asserts the API is called exactly once.
3. Run the quiz app in `next dev` (Strict Mode active) after any hook refactoring and monitor network tab for exactly one `POST /quiz/session` call.

**Warning signs:**
- Two `POST /quiz/session` API calls appear in browser DevTools network tab on page load in development
- Patients report "quiz link already used" immediately after clicking their link
- `useRef` guard removed from `useQuizSession.ts` during cleanup

**Phase to address:**
Quiz frontend quality phase — add the Strict Mode protection test before touching the hook.

---

### Pitfall 7: date-fns v3 vs v4 API Divergence Between Frontends

**What goes wrong:**
The admin SPA (`frontend-hormonia`) uses `date-fns v3.x` (`"date-fns": "^3.6.0"`). The quiz interface (`quiz-mensal-interface`) uses `date-fns v4.x` (`"date-fns": "4.1.0"`). Between v3 and v4, date-fns introduced breaking API changes — `format` function signatures changed, timezone handling changed, and some utilities were renamed or removed.

During a frontend quality consolidation pass, a developer copies a date formatting utility from the admin SPA (v3 API) to the quiz interface (expecting v4 API), or vice versa. The code compiles without errors (TypeScript types are broadly compatible) but renders dates incorrectly at runtime — showing wrong year, wrong format, or incorrect timezone offset for Brazilian patients (UTC-3 / America/Sao_Paulo).

**Why it happens:**
Both frontends use shadcn/ui with Tailwind, both use date-fns — they look like the same stack. The minor version difference is easy to miss in `package.json` comparisons. TypeScript doesn't always catch date-fns API misuse because the types are backward-compatible at the function signature level.

**How to avoid:**
1. In the quality consolidation phase, standardize both frontends on the same date-fns version. Upgrade the admin SPA to v4 (or pin quiz to v3) as a deliberate decision.
2. Any shared date formatting logic must live in a single package or be written explicitly for each frontend's version.
3. All date displays referencing patient appointment dates must be tested against `America/Sao_Paulo` timezone, not UTC. Brazilian oncology patient appointments use São Paulo local time.

**Warning signs:**
- Dates in admin SPA show differently from the same dates in quiz interface for the same patient
- `format(new Date(), 'dd/MM/yyyy')` returns different results between the two frontends despite same input
- Any copy-paste of date utilities between the two frontends without version check

**Phase to address:**
Frontend quality consolidation phase — standardize date-fns version first before any date utility sharing.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep `app/core/tracing.py` as-is, just remove OTel from requirements.txt | Zero code change | ADK pulls OTel back as transitive dep; tracing.py becomes permanently ambiguous dead code with unclear activation state | Never — convert to no-op shim or tombstone after ADK install verification |
| Leave `VITE_ENABLE_EVOLUTION` flag "false by default" in frontend config | No frontend changes needed | Engineers expect dual-provider mode to exist; flag pollutes env validator and runtime-config; physicians see "Evolution API disabled" message | Never — hard delete all Evolution references |
| Running ADK alongside Pydantic AI without extending PIISafeAgent CI guard | Fast integration path | Patient oncology data (CPF, diagnosis, treatment) can reach Gemini API unredacted; LGPD Art. 46 violation | Never for any data from patient records |
| Skipping TypeScript strict mode in the quality pass | Fewer immediate type errors | Type holes hide API contract mismatches between frontend and backend; unsafe `any` types grow | Only if strict mode was never enabled before — do not introduce a new disable |
| Using `// @ts-ignore` on type errors from stale `api-wave2.ts` types | Quick compilation fix | API misalignment becomes invisible; stale type definitions cause runtime 404s and silent data loss | Never — fix the type definition to match the actual backend contract |
| Leaving `IntegrationMode.LANGGRAPH_ONLY` in hive_mind_integration.py | No enum changes | Any caller using that mode gets an ImportError from tombstoned LangGraph; no valid code path exists | Never — remove dead enum values when the implementation is tombstoned |
| Creating a new ADK `GeminiClient` instance instead of reusing existing `app/ai/client.py` | Simpler ADK setup | Two Gemini SDK instances with independent rate limit state and circuit breakers; rate limit budget split unpredictably | Never — reuse existing `GeminiClient` via shared configuration |

## Integration Gotchas

Common mistakes when connecting ADK to the existing Pydantic AI + google-genai stack.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| ADK + Pydantic AI agents | Passing Pydantic AI agent object as ADK `AgentTool` or `FunctionTool` directly | Wrap each Pydantic AI agent call in a plain async function decorated as an ADK tool; `PIISafeAgent._safe_run()` lives inside that wrapper |
| ADK + GeminiClient | Creating a new `google-genai` client instance in ADK agent configuration | Reuse the `GeminiClient` from `app/ai/client.py` via shared API key and model name — two client instances split the rate limit budget and each has its own circuit breaker |
| ADK + AsyncSession | ADK framework callbacks may be called synchronously | Use `async_to_sync()` (established codebase pattern from Celery tasks) if ADK requires sync callbacks that need DB access; never pass `AsyncSession` to a sync callback |
| ADK + Circuit Breaker | Not wrapping ADK `runner.run_async()` in the existing circuit breaker | Import `aiobreaker` circuit breaker from `app/resilience/circuit_breaker/` and wrap the ADK runner call — ADK can fail with network errors, Gemini errors, or quota errors |
| ADK + OTel re-import | Removing all OTel from requirements.txt and assuming ADK works without it | Pin ADK version in requirements.txt, run `pip install google-adk && pip freeze` to confirm actual transitive dep tree before finalizing removal list |
| Frontend + WuzAPI endpoints | Calling backend endpoints that matched Evolution API paths (e.g., `/evolution/`) | Compare `frontend-hormonia/src/services/whatsapp/WhatsAppService.ts` endpoint paths against active routes in `api/v2/router.py`; update mismatched paths |
| Frontend types + backend contract | Using `types/api-wave2.ts` (auto-generated Oct 2025) without verifying current backend Pydantic models | Re-generate or manually audit `api-wave2.ts` types against current v2 OpenAPI output (`/api/v2/openapi.json`) before cleanup |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| ADK agent sessions not explicitly closed | Memory growth in long-running FastAPI process; ADK session context accumulates state | Use `async with` context manager or explicit `session.close()` in a `finally` block around ADK runner calls | At >100 concurrent patients in active follow-up flows |
| React Query cache not invalidated on admin focus | Physician sees stale patient data from another session's cache in multi-tab usage | Add `refetchOnWindowFocus: true` for patient-facing queries; use per-session query keys for sensitive data | Immediately visible when physician uses multiple browser tabs |
| Virtualisation components on pages with <50 items | `react-window` and `react-virtualized-auto-sizer` in quiz history or alerts (likely <20 items) add complexity with no performance benefit | Remove virtualisation from low-item pages; keep only for patient list (100+ records) | Never breaks performance, but adds unnecessary complexity that makes quality cleanup harder |
| Stale mocks in `frontend-hormonia/src/mocks/` silencing real API contract errors | Tests pass against mocked responses while production calls different endpoints or gets different shapes | Audit mock files against actual backend responses using the test `normalizers.ts` patterns; confirm mock shapes match live API | Immediately at any backend endpoint change that mocks don't reflect |

## Security Mistakes

Domain-specific security issues for oncology patient data.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging patient name or CPF in browser console during API debugging | LGPD violation; console accessible to browser extensions and XSS | Use `createLogger` from `lib/logger.ts` (already sanitizes PII); never call `console.log(patient)` or `console.log(response.data)` with raw patient objects |
| ADK tool output containing patient clinical data persisted in ADK session state | ADK session state may be written to disk, memory dumps, or ADK's built-in storage service in ways the team doesn't control | Apply PII redaction via `PIISafeAgent` BEFORE any data enters ADK tool results; use `before_tool_callback` as secondary filter |
| Removing Sentry's `beforeSend` filter during the monitoring cleanup pass | Patient names appearing in Sentry breadcrumbs, error payloads, and session replay | The `SentryMonitoring` class in `monitoring/sentry.ts` already has `beforeSend` filters — verify they survive any Sentry configuration refactor; never remove them |
| Switching quiz session state storage from HttpOnly cookies to `localStorage` | XSS can steal session token; quiz sessions represent patient oncology health interactions | Quiz already uses HttpOnly cookies correctly per `use-quiz-session.ts` — do not change this during the quality pass; it is the secure architecture |
| New ADK API endpoint missing audit log | LGPD Art. 37 requires processing activity records for health data | Every new API route that invokes ADK agents must call the existing `AuditService` — add this at route handler level, not as an afterthought in a follow-up story |
| ADK agent output rendered to admin UI without output escaping | ADK processes patient messages, which may contain injection strings | Escape all ADK agent output before rendering to any HTML context; `DOMPurify` is already installed in the admin SPA (`"dompurify": "^3.3.0"`) |

## UX Pitfalls

Frontend-specific UX mistakes for the oncology admin context.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Removing the Evolution "disabled" banner without replacing with WuzAPI status | Physicians have zero visibility into WhatsApp system health; the most critical infrastructure for patient follow-up has no status indicator | Replace Evolution placeholder in `WhatsAppDashboard.tsx` with a WuzAPI connection status card showing: instance status, last-seen timestamp, QR code state if disconnected |
| Dead Evolution settings fields in AdminSettingsTab | Physician or admin tries to toggle "Evolution API" settings and gets no response; confusing UI state | Remove all Evolution-related settings fields from `AdminSettingsTab.tsx` |
| 501 responses showing as infinite loading state | When backend returns 501 (unsupported feature, e.g., WuzAPI contact sync), frontend spinner runs forever | Map HTTP 501 to explicit "Feature not available" UI state — the `FeatureNotAvailableError` pattern is established in the backend; align the frontend |
| Inconsistent Sao Paulo timezone display between admin SPA and quiz interface | Same appointment time shows differently in both UIs for the same patient | Standardize timezone handling in both frontends: `America/Sao_Paulo` UTC-3; verify `date-fns` timezone functions use the correct locale and zone after v3→v4 alignment |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **OTel removal:** Confirm whether `pip show opentelemetry-api` returns "not found" OR document that ADK re-imported it and clarify that instrumentation packages are the real removal target — never leave the OTel state ambiguous.
- [ ] **ADK integration:** Verify `scripts/check_agent_run_calls.py` detects direct `.run()` calls inside ADK `@tool`-decorated functions — test with a synthetic file.
- [ ] **PIISafeAgent in ADK path:** Integration test with synthetic PHI input asserts the PII redaction log line appears before Gemini API call in every ADK-invoked agent path.
- [ ] **Evolution dead code removed:** `grep -r "VITE_ENABLE_EVOLUTION\|Evolution API\|EvolutionAPI" frontend-hormonia/src/` returns zero results.
- [ ] **HiveMind LangGraph cleaned:** `grep -n "LANGGRAPH_ONLY\|_process_with_langgraph" backend-hormonia/app/services/hive_mind_integration.py` returns zero results.
- [ ] **Quiz Strict Mode guard preserved:** `useQuizSession.ts` unit test passes simulating double-invocation; API called exactly once.
- [ ] **Sentry correlation intact post-OTel-removal:** Sentry transaction tree for one sampled patient flow request shows same parent-child span depth before and after OTel instrumentation package removal.
- [ ] **TypeScript clean in both frontends:** `tsc --noEmit` exits 0 in both `frontend-hormonia/` and `quiz-mensal-interface/` with strict mode enabled.
- [ ] **date-fns version aligned:** Both frontends declare the same major version of date-fns; no copy-paste of date utilities across frontends without version verification.
- [ ] **ADK session lifecycle:** ADK runner sessions are explicitly closed in all code paths including exception paths; no session accumulation under load.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| ADK re-pulls OTel at conflicting version | MEDIUM | Pin ADK to exact tested version; document OTel as ADK-managed transitive dep; remove your own OTel pins from requirements.txt and let ADK's declared range govern |
| PIISafeAgent bypassed in production ADK call | HIGH | Immediately deploy hotfix wrapping the ADK tool in `PIISafeAgent._safe_run()`; notify DPO per LGPD Art. 48 if patient PHI reached Gemini unredacted; audit Gemini API request logs for the exposure window |
| Quiz double-session from Strict Mode guard removal | LOW | Rollback the hook change that removed the `useRef` guard; add the missing test; redeploy |
| Evolution dead code causes physician confusion | LOW | Remove `VITE_ENABLE_EVOLUTION` flag; remove Evolution UI sections; rebuild and deploy frontend; no backend changes needed |
| Sentry loses correlation after OTel removal | MEDIUM | Ensure `sentry-sdk[fastapi]` `FastApiIntegration` and `CeleryIntegration` are explicitly registered in Sentry init; verify `traces_sample_rate > 0`; Sentry does not require OTel for its own tracing |
| HiveMind endpoint crashes on LANGGRAPH_ONLY mode | LOW | Remove dead enum value; redeploy backend; no data loss since the mode was unreachable safely |
| date-fns API mismatch causes incorrect dates in UI | LOW | Identify the cross-version copy-paste; standardize on one version; test with São Paulo timezone edge case (DST boundary) |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| ADK reintroduces OTel as transitive dep | OTel removal phase — audit transitive deps first | `pip show opentelemetry-api` state is known and documented before any requirements.txt changes |
| PIISafeAgent bypass via ADK tools | ADK integration phase — extend CI guard before any agent wiring | CI fails on a test file with direct `agent.run()` inside an ADK `@tool` function |
| ADK tool output leaks PHI to session state | ADK integration phase | Integration test with synthetic PHI in tool input asserts redaction in ADK session output |
| Evolution API dead code in frontend | Frontend dead code removal phase — WhatsApp area first | `grep -r "VITE_ENABLE_EVOLUTION"` returns zero results in `frontend-hormonia/src/` |
| HiveMind references tombstoned LangGraph | Frontend dead code or ADK integration phase | `grep -n "LANGGRAPH_ONLY"` returns zero results in `hive_mind_integration.py` |
| Sentry trace correlation breaks post-OTel removal | OTel removal phase — validate Sentry before and after | Sentry transaction tree for one sampled flow intact after instrumentation package removal |
| React Strict Mode double-init in quiz | Quiz quality phase | `useQuizSession` unit test with double-invocation simulation; API called exactly once |
| date-fns version divergence between frontends | Frontend quality consolidation phase | Both frontends declare same date-fns major version; `tsc --noEmit` clean |
| 501 responses showing as infinite loading | Frontend quality phase | HTTP 501 response renders "Feature not available" state, not spinner |
| ADK session not closed causing memory growth | ADK integration phase | ADK runner usage wrapped in `async with` or `finally` block; load test shows stable memory |

## Sources

- Google ADK v1.26.0 CHANGELOG: "Update OpenTelemetry dependency versions to relax version constraints" — confirms OTel is NOT removed, only pinning widened — [https://github.com/google/adk-python/blob/main/CHANGELOG.md](https://github.com/google/adk-python/blob/main/CHANGELOG.md)
- Google ADK v1.26.0 releases page — [https://github.com/google/adk-python/releases](https://github.com/google/adk-python/releases)
- GitHub Issue: `TypeError: BaseModel.model_dump()` with ADK + OTel + Pydantic output_schema — [https://github.com/google/adk-python/issues/3884](https://github.com/google/adk-python/issues/3884)
- GitHub Issue: OTel context ValueError with ADK ParallelAgent (google/adk-python #860) — [https://github.com/google/adk-python/issues/860](https://github.com/google/adk-python/issues/860)
- GitHub Issue: OTel context detach errors in ADK (google/adk-python #1670) — [https://github.com/google/adk-python/issues/1670](https://github.com/google/adk-python/issues/1670)
- GitHub Issue: Pydantic AI + OTel import crash on Lambda (pydantic/pydantic-ai #2985) — [https://github.com/pydantic/pydantic-ai/issues/2985](https://github.com/pydantic/pydantic-ai/issues/2985)
- OTel + Protobuf version conflict documentation — [https://github.com/open-telemetry/opentelemetry-python/issues/4563](https://github.com/open-telemetry/opentelemetry-python/issues/4563)
- Google ADK Safety documentation (PII and callbacks) — [https://google.github.io/adk-docs/safety/](https://google.github.io/adk-docs/safety/)
- React 19 release notes and Strict Mode behavior — [https://react.dev/blog/2024/12/05/react-19](https://react.dev/blog/2024/12/05/react-19)
- LGPD compliance checklist — [https://captaincompliance.com/education/lgpd-compliance-checklist/](https://captaincompliance.com/education/lgpd-compliance-checklist/)
- Codebase: `backend-hormonia/app/core/tracing.py` — OPENTELEMETRY_AVAILABLE guard and MockTracer fallback (HIGH confidence — direct file read)
- Codebase: `frontend-hormonia/src/features/whatsapp/WhatsAppDashboard.tsx` lines 62-76, 183-195 — Evolution API dead code confirmed (HIGH confidence — direct file read)
- Codebase: `backend-hormonia/app/services/hive_mind_integration.py` lines 31, 217-218 — LangGraph dead code in active service confirmed (HIGH confidence — direct file read)
- Codebase: `quiz-mensal-interface/hooks/use-quiz-session.ts` — Strict Mode protection guard confirmed present (HIGH confidence — direct file read)
- Codebase: `backend-hormonia/requirements.txt` lines 116-134 — 9 explicit OTel package declarations confirmed (HIGH confidence — direct file read)
- Codebase: confirmed OTel callers: only `app/integrations/whatsapp/services/message_service.py` (line 26, 314, 574) and `app/services/unified_whatsapp_service.py` (line 51, 142) (HIGH confidence — grep confirmed)

---
*Pitfalls research for: Clinica Oncologica v02 — v1.7 Frontend Quality & ADK Integration milestone*
*Researched: 2026-03-03*
