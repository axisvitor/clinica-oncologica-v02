# Feature Research

**Domain:** ADK stabilization + runtime hardening for production oncology AI backend
**Researched:** 2026-03-05
**Confidence:** HIGH for ADK runtime/session/guardrail features (official ADK docs); MEDIUM for cross-vendor "production table stakes" patterns (official OpenAI production guidance + ADK guidance)

## Feature Landscape

### Table Stakes (Users Expect These)

Features production teams expect for stable ADK-backed agent execution. Missing these means recurring incidents.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Deterministic ADK runtime budgets (`RunConfig.max_llm_calls`, run timeouts) | Prevents runaway loops, quota burn, and hung requests | MEDIUM | New requirement on top of existing ADK route foundation. Use strict per-endpoint defaults and fail-fast error mapping. Depends on existing Gemini rate limiter/circuit breaker to avoid cascading failures. |
| Standardized ADK error taxonomy + HTTP mapping | Ops and callers need predictable failure classes (timeout, policy_block, tool_error, upstream_error) | MEDIUM | New contract layer in wrapper/runtime/endpoint path. Depends on existing FastAPI exception handling, structured logging, and Sentry integration. |
| Tool-call guardrails before execution (`before_tool_callback`) | Production agents must validate tool args and auth context before side effects | MEDIUM | ADK callback pattern is explicit for policy enforcement. Reuse existing PIISafe wrappers and LGPD rules as deterministic preconditions. |
| Session lifecycle correctness (create/resume/delete, bounded state growth) | Multi-turn stability requires clean session management and predictable memory behavior | MEDIUM | ADK SessionService is a core runtime primitive; production needs explicit retention/cleanup policy. Depends on existing patient flow IDs and current backend identity model. |
| ADK observability baseline (invocation IDs, latency/error/throughput metrics, structured logs) | Incident response needs traceability per invocation and per tool call | MEDIUM | ADK relies on developer-configured logging; add explicit metric emission at wrapper + endpoint boundaries. Depends on existing logging/Sentry/monitoring endpoints. |
| ADK smoke/eval regression gate in CI | Agent regressions are non-deterministic without scenario-based tests and trajectory checks | MEDIUM | ADK eval supports trajectory and response criteria; wire minimal critical-path fixtures into direct-run CI guard flow. Depends on existing CI guardrails and typed agent outputs. |

### Differentiators (Competitive Advantage)

Features that move beyond minimum stability and materially improve safety/operations.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Policy-as-code guardrail library for tools | Reusable safety rules across all ADK tools (PII, role, allowed actions) with low drift | HIGH | Implement as shared callbacks/plugins rather than per-tool ad hoc checks. Builds on existing PIISafeAgent/PIISafeADKWrapper contracts. |
| Progressive rollout controls for ADK path (shadow/canary/rollback flag) | Reduces blast radius for runtime changes and model/tool upgrades | HIGH | Keep existing production path as fallback while ADK hardening matures. Depends on current feature-flag and deployment workflow discipline. |
| Persistent session backend with migration discipline (`DatabaseSessionService`) | Survives restarts and enables resilient multi-turn care journeys | HIGH | ADK supports DB-backed sessions; requires schema migration governance and retention policy. Depends on existing PostgreSQL ops and async DB expertise. |
| Safety+quality evaluation pack (hallucination/safety/tool-use rubrics) tied to release criteria | Converts subjective "agent quality" into objective go/no-go gates | HIGH | Extend basic CI smoke into graded eval profiles for oncology workflows and escalation prompts. Depends on existing test infrastructure and domain fixtures. |
| Operator runbook automation (auto-classify incidents, suggested remediation by error class) | Faster MTTR and fewer repeated on-call decisions | MEDIUM | Attach runbook links/actions to standardized error codes and alert payloads. Depends on new error taxonomy and existing alerting endpoints. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Replacing typed Pydantic agents with raw ADK LlmAgent everywhere | "Single framework" simplification | Loses proven typed-output safety contracts already used in production and increases regression risk in clinical messaging | Keep typed Pydantic AI agents as execution core; use ADK for runtime orchestration, sessions, callbacks, and evals |
| Launching ADK web/API server as parallel production surface | "Fastest path to ADK endpoints" | Duplicates existing FastAPI contract, auth, and observability paths; introduces split operational model | Embed ADK Runner inside existing FastAPI `/api/v2/adk/run` and keep one production API surface |
| Unlimited session retention and full transcript persistence by default | "Better debugging/history" | High LGPD/privacy and storage risk; worsens incident blast radius | Enforce retention windows, redaction-at-ingest, and scoped artifact storage |
| Enabling experimental runtime features (for example CFC) in critical care path early | "More capability quickly" | Experimental runtime behavior raises stability risk during hardening phase | Keep to stable ADK runtime settings first; isolate experiments behind non-critical flags |
| Big-bang ADK migration of all flows/tools in one milestone | "Finish migration once" | High failure domain; difficult root-cause isolation during incidents | Incremental rollout: harden one critical path, then expand by tool/agent cohort |

## Feature Dependencies

```text
Existing PIISafeAgent/PIISafeADKWrapper
    └──required for──> Tool-call guardrails (before_tool_callback)
                            └──required for──> Standardized error taxonomy (policy_block vs runtime_error)

Existing ADK route foundation (/api/v2/adk/run)
    └──required for──> Runtime budgets + timeout controls
                            └──required for──> Observability baseline (latency/error/throughput)
                                                    └──required for──> Alerting + runbook automation

Existing structured logging + Sentry
    └──required for──> Error taxonomy adoption
                            └──required for──> Incident classification and MTTR tracking

Existing CI direct-run guards + typed agent tests
    └──required for──> ADK smoke/eval regression gate
                            └──enables──> Progressive rollout (canary/shadow with confidence)

Session lifecycle correctness
    └──prerequisite for──> Persistent session backend adoption
```

### Dependency Notes

- **Runtime budgets require existing resilience controls:** `max_llm_calls` bounds ADK loops, but production stability still depends on the current Gemini circuit breaker/rate limiter for upstream fault containment.
- **Error taxonomy depends on shared logging context:** without existing structured logs + Sentry tags, error classes are not actionable for operators.
- **Guardrails should extend, not replace, PIISafe wrappers:** ADK callbacks enforce runtime policy checks; PIISafe remains mandatory for LGPD-sensitive content handling.
- **Persistent sessions should come after lifecycle hygiene:** adopt DB-backed session persistence only after create/resume/delete semantics and retention limits are proven.

## MVP Definition

### Launch With (v1)

- [ ] Runtime hard limits enabled for every ADK invocation path (`max_llm_calls`, timeout, cancellation behavior) — prevents runaway execution
- [ ] Stable ADK error contract and HTTP/status mapping implemented — enables reliable caller behavior and incident triage
- [ ] `before_tool_callback` validation for high-risk tools (PII-bearing and side-effecting operations) — prevents unsafe tool invocation
- [ ] ADK observability baseline live (latency p95, throughput, error rate, invocation/tool correlation IDs) — supports on-call diagnosis
- [ ] CI ADK smoke/eval suite for critical oncology prompts and tool trajectories — blocks known regressions before deploy

### Add After Validation (v1.x)

- [ ] Rollout controls (shadow/canary + automatic rollback triggers) — add when baseline error budget is measurable
- [ ] Expanded rubric-based evaluation (hallucination/safety/tool-use quality) — add after initial deterministic checks stabilize
- [ ] Operator runbook automation tied to error taxonomy — add once alert quality is consistent

### Future Consideration (v2+)

- [ ] Database-backed persistent ADK sessions for longitudinal interactions — defer until retention/governance policy is fully approved
- [ ] Reusable cross-agent security plugin stack (judge/model-armor style controls) — defer until current callback guardrails are mature

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Runtime budgets and cancellation semantics | HIGH | MEDIUM | P1 |
| Error taxonomy + API contract mapping | HIGH | MEDIUM | P1 |
| Tool-call guardrails (before callbacks) | HIGH | MEDIUM | P1 |
| ADK observability baseline | HIGH | MEDIUM | P1 |
| CI smoke/eval regression gate | HIGH | MEDIUM | P1 |
| Progressive rollout controls | HIGH | HIGH | P2 |
| Runbook automation | MEDIUM | MEDIUM | P2 |
| Persistent DB session backend | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must-have for ADK stabilization milestone
- P2: Should-have after baseline stability is proven
- P3: Defer until operational maturity and governance readiness

## Competitor / Ecosystem Feature Analysis

| Feature Pattern | ADK Guidance | Broader Production Guidance | Recommended Approach Here |
|-----------------|-------------|-----------------------------|---------------------------|
| Runtime bounds | `RunConfig.max_llm_calls` and validated runtime config | Production guidance emphasizes cost/latency/rate-limit control | Enforce hard per-route budgets with fail-fast defaults |
| Guardrails | Callbacks/plugins for policy enforcement and tool validation | Safety best practices emphasize proactive misuse prevention | Implement callback-based policy-as-code on top of PIISafe wrappers |
| Observability | ADK logging is developer-configured; callbacks integrate tracing tools | Production guidance emphasizes monitoring and incident diagnosis | Keep FastAPI-native telemetry as source of truth; enrich with ADK invocation metadata |
| Evaluation | ADK eval supports trajectory + response + safety criteria | Production guidance recommends formal eval loops pre-release | Start with deterministic smoke + trajectory checks, then add rubric/safety criteria |
| Session persistence | In-memory for dev; DB/managed services for production continuity | Production systems require resilience across restarts | Start with lifecycle correctness, then adopt DB session backend incrementally |

## Sources

- Google ADK docs (home): https://google.github.io/adk-docs/ (HIGH)
- ADK Runtime Config (`max_llm_calls`, streaming, validation): https://google.github.io/adk-docs/runtime/runconfig/ (HIGH)
- ADK Callback patterns and reliability guidance: https://google.github.io/adk-docs/callbacks/design-patterns-and-best-practices/ (HIGH)
- ADK Sessions and SessionService backends: https://google.github.io/adk-docs/sessions/session/ (HIGH)
- ADK Observability logging model: https://google.github.io/adk-docs/observability/logging/ (HIGH)
- ADK Evaluation framework and criteria: https://google.github.io/adk-docs/evaluate/ (HIGH)
- ADK Safety and Security best practices: https://google.github.io/adk-docs/safety/ (HIGH)
- ADK API Server usage/reference: https://google.github.io/adk-docs/runtime/api-server/ (HIGH)
- OpenAI Production best practices (cross-vendor production patterns): https://platform.openai.com/docs/guides/production-best-practices (MEDIUM)
- Project context: `.planning/PROJECT.md` (HIGH)

---
*Feature research for: ADK stability + runtime hardening (v1.8 oncology backend milestone)*
*Researched: 2026-03-05*
