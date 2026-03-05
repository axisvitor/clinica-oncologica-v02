# Project Research Summary

**Project:** Clinica Oncologica v1.8 - ADK Stability and Error Hardening
**Domain:** Brownfield healthcare backend hardening (FastAPI + Celery + Gemini + Google ADK) with LGPD-safe observability
**Researched:** 2026-03-05
**Confidence:** HIGH

## Executive Summary

This project is a production oncology follow-up platform where ADK is already integrated, but still needs stability hardening before it is a dependable operational path. The research converges on one clear recommendation: treat ADK as an orchestration/runtime layer inside the existing FastAPI and Celery architecture, not as a parallel platform. Keep typed Pydantic AI flows, keep one API surface (`/api/v2/adk/run`), and harden execution with explicit runtime budgets, guardrails, typed errors, and telemetry.

Experts build this class of system by centralizing control flow in one application service, instrumenting all runtime boundaries, and forcing deterministic failure behavior. The proposed architecture follows that pattern via a new `ADKExecutionService` facade, typed error taxonomy, consistent correlation IDs across API -> worker -> ADK, and a unified Sentry + Prometheus + structured logging baseline. This approach minimizes policy drift and keeps rollback safe in a mature brownfield system.

The highest risks are privacy leakage, untraceable incidents, and unsafe retry behavior. The mitigation is explicit and phaseable: enforce INFO-only production logging and redaction, propagate mandatory correlation keys end-to-end, classify retryable vs non-retryable errors, and rollout via shadow/canary with instant rollback. Big-bang rollout and broad debug logging are explicitly unsafe for this healthcare domain.

## Key Findings

### Recommended Stack

The stack recommendation is conservative: keep `google-adk==1.26.0` as runtime, standardize on `sentry-sdk==2.54.0`, and use Prometheus as the primary metrics plane (`prometheus-client==0.24.1` with optional `prometheus-fastapi-instrumentator==7.1.0`). For logging, use `structlog==25.5.0` and/or `python-json-logger==4.0.0` only through one consistent pipeline.

Critical requirement: one Sentry initialization path for API and workers (`app/core/setup/sentry.py`) with parity on tags/release/environment. Reintroducing OTel or splitting telemetry stacks is a direct anti-pattern for this milestone.

**Core technologies:**
- `google-adk==1.26.0`: stable ADK runner/session/callback surface already aligned with codebase
- `sentry-sdk==2.54.0`: end-to-end exception and trace continuity across FastAPI and Celery
- `prometheus-client==0.24.1`: SLO metrics for ADK latency, throughput, and error categories
- `prometheus-fastapi-instrumentator==7.1.0`: standardized HTTP baseline metrics on ADK routes
- `structlog==25.5.0`: structured, correlation-first operational logs at runtime boundaries

### Expected Features

Feature research is strongly aligned with the architecture proposal: stabilize runtime behavior first (P1), then add rollout intelligence and richer quality gates (P2), then move to durable session sophistication (P3).

**Must have (table stakes):**
- Runtime limits per invocation (`max_llm_calls`, timeout, cancellation)
- Standardized ADK error taxonomy and API mapping
- Tool guardrails via `before_tool_callback` for high-risk actions
- Observability baseline with invocation IDs, latency/error/throughput metrics
- CI smoke/eval gate for critical oncology trajectories

**Should have (competitive):**
- Policy-as-code guardrail library reusable across ADK tools
- Progressive rollout controls (shadow/canary/rollback)
- Expanded safety/quality eval rubric and operator runbook automation

**Defer (v2+):**
- Database-backed persistent ADK sessions as default
- Advanced cross-agent security plugin stack beyond current callback guardrails

### Architecture Approach

The architecture should introduce a strict stability boundary: all ADK callers route through `ADKExecutionService`, which composes PII-safe wrapper, runtime adapter, error mapper, and observability emitter. Routers remain transport-only. Runtime internals stop swallowing broad exceptions and only fallback on explicitly allowed categories.

**Major components:**
1. `ADKExecutionService` - orchestration control plane for API and future Celery callers
2. `ADKRuntimeAdapter` + `session_service` strategy - isolates runner/tool/session implementation details
3. `ADKErrorMapper` + `adk_observability` - typed failure semantics plus unified metrics/log/sentry emission

### Critical Pitfalls

1. **PHI leakage in diagnostics** - enforce INFO-only prod logging, redaction before logs/Sentry, scoped diagnostic mode only
2. **Broken correlation chain** - require and propagate `request_id`, `celery_task_id`, `adk_invocation_id`, `adk_session_id`, `flow_id`
3. **Duplicate patient messaging from retries** - add idempotency ledger and retry policy tied to error class
4. **Callback/tool contract drift after ADK upgrades** - pin ADK version and gate upgrades with callback contract tests
5. **Error taxonomy collapse to generic 500s** - implement explicit error classes with HTTP/retry/alert/runbook mapping

## Implications for Roadmap

Based on combined research, recommended phase structure is 4 phases.

### Phase 1: Guardrails and Error Contracts
**Rationale:** Safety and deterministic failure behavior are prerequisites for everything else.
**Delivers:** runtime budgets, typed error taxonomy, `ADKExecutionService` facade, callback guardrail enforcement, stable API error envelope.
**Addresses:** P1 features (runtime limits, error mapping, tool guardrails).
**Avoids:** PHI leakage, callback drift, taxonomy collapse.

### Phase 2: Observability Baseline and Correlation
**Rationale:** After contracts stabilize, make incidents diagnosable before rollout expansion.
**Delivers:** unified Sentry init, Prometheus ADK metrics, route instrumentation, mandatory correlation keys API -> Celery -> ADK, cardinality controls.
**Uses:** `sentry-sdk`, `prometheus-client`, optional instrumentator, structured logging pipeline.
**Avoids:** untriageable incidents, metric-cardinality explosion, blind spots after fallback paths.

### Phase 3: Runtime Hardening and Controlled Worker Adoption
**Rationale:** Only after observability is trustworthy should retries/fallbacks/session strategy be widened.
**Delivers:** idempotent retry semantics for outbound messaging, explicit retryable/non-retryable policies, Celery caller parity via service facade, flagged session backend strategy rollout.
**Implements:** architecture patterns for shared API/worker control plane and rollback-safe session migration.
**Avoids:** duplicate patient messages, session loss on restarts, inconsistent worker error handling.

### Phase 4: Progressive Rollout and Operationalization
**Rationale:** Healthcare safety requires staged enablement with measurable gates, not big-bang launch.
**Delivers:** shadow/canary controls, rollback switches, alert thresholds, runbook automation, release gates tied to eval and SLOs.
**Addresses:** P2 differentiators and operational maturity.
**Avoids:** production-wide regressions from internal hardening changes.

### Phase Ordering Rationale

- Contracts before telemetry avoids measuring unstable failure semantics.
- Telemetry before scaling/worker expansion avoids debugging in the dark.
- Worker/session expansion after idempotency and taxonomy avoids patient-impact regressions.
- Rollout controls last ensures changes are already observable, classifiable, and reversible.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3:** durable session backend migration details (schema/version compatibility, retention governance, replay diagnostics).
- **Phase 4:** shadow/canary threshold design and auto-rollback criteria tuned to oncology workflow risk.

Phases with standard patterns (skip research-phase):
- **Phase 1:** runtime budgets, typed errors, callback guardrails are well documented in ADK docs and current code patterns.
- **Phase 2:** Sentry/FastAPI/Celery and Prometheus instrumentation patterns are mature and directly supported by official docs.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions and integration patterns backed by PyPI + official Sentry/Prometheus/ADK docs; codebase integration points are explicit. |
| Features | HIGH | ADK table-stakes validated by official runtime/callback/session/eval docs; prioritization is internally consistent. |
| Architecture | MEDIUM-HIGH | Strong codebase alignment and clear boundaries; production-volume bottlenecks remain partially inferred without live telemetry. |
| Pitfalls | HIGH | Risks are concrete for healthcare runtime ops and mapped to specific prevention/verification actions. |

**Overall confidence:** HIGH

### Gaps to Address

- **Live-scale performance envelope:** no direct production benchmark data for ADK path under sustained load; add early load + queue-depth validation gates in planning.
- **Session governance decisions:** TTL, retention classing, and deletion workflows for durable ADK sessions need explicit legal/ops approval before broad rollout.
- **ADK upgrade discipline:** maintain a lightweight compatibility matrix between callback contracts and pinned ADK versions to prevent silent drift.

## Sources

### Primary (HIGH confidence)

- Google ADK docs (runtime config, callbacks, sessions, eval, safety, logging): https://google.github.io/adk-docs/
- Sentry Python docs (FastAPI/Celery integrations, data scrubbing): https://docs.sentry.io/platforms/python/
- Prometheus Python client docs: https://prometheus.github.io/client_python/
- PyPI package metadata: `google-adk`, `google-genai`, `sentry-sdk`, `prometheus-client`, `prometheus-fastapi-instrumentator`
- Project research files: `.planning/research/STACK.md`, `.planning/research/FEATURES.md`, `.planning/research/ARCHITECTURE.md`, `.planning/research/PITFALLS.md`

### Secondary (MEDIUM confidence)

- OpenAI production best practices (cross-vendor operational heuristics): https://platform.openai.com/docs/guides/production-best-practices
- ADK Python release notes/changelog context: https://github.com/google/adk-python/releases

### Tertiary (LOW confidence)

- None required for roadmap-critical decisions; current recommendations rely on official vendor docs and direct project-context analysis.

---
*Research completed: 2026-03-05*
*Ready for roadmap: yes*
