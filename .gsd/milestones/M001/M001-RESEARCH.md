# M001 Research

**Milestone:** Bulletproof Flow Pipeline  
**Source basis:** `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/phases/51-flow-recovery/51-RESEARCH.md`, and completed phase summaries for phases 50-53.

## Executive Summary

This milestone hardens the WhatsApp flow pipeline so silent failures become either automatic recovery actions or visible operator signals. The legacy planning material shows four tightly connected workstreams:

1. **Reliability** — recover from context mismatches, retry failed sends/follow-ups, and make day advancement atomic.
2. **Recovery** — detect stuck `awaiting_response` flows and provide both automatic and manual intervention paths.
3. **Observability** — expose health counts, stall alerts, AI fallback metrics, and correlation tracing.
4. **Verification** — prove the full webhook -> gate -> continuation -> send pipeline with integration tests.

The project is a mature brownfield healthcare backend, so the correct approach is to extend existing FastAPI, Celery, SQLAlchemy, and structured-logging patterns rather than introduce new infrastructure.

## What the Old Research Established

### Existing architectural constraints

- **API routes use AsyncSession**; **Celery workers stay on sync Session** by design.
- **WuzAPI is the sole WhatsApp provider** after the Evolution hard cut.
- **LGPD constraints remain mandatory**, so logs/alerts/traces must stay structured and privacy-aware.
- **Flow state is already persisted in `PatientFlowState.step_data`**, which is the right place to read/write recovery and observability markers.

### Reusable implementation patterns

- **Celery retry tasks** should follow the existing `async_to_sync`/scoped-session pattern already used in the codebase.
- **Stuck-flow detection** should query JSON/step-data markers directly instead of introducing a new persistence table.
- **Admin extension APIs** should follow the established `admin_extensions` router pattern with admin auth, rate limiting, and audit logging.
- **Correlation tracing** should reuse the existing correlation ContextVar rather than introduce a second trace primitive.
- **Observability surfaces** should stay lightweight: Prometheus metrics, structured warnings, and optional webhook fan-out.

## Milestone Scope by Slice

### S01 — Pipeline Reliability

Close the silent-failure gaps in the flow engine:
- bounded recovery for sequential-gate context mismatch,
- Celery retry for failed outbound sends,
- retry for deferred follow-ups,
- atomic + verified day advancement,
- fail-fast day_config validation.

### S02 — Flow Recovery

Add bounded stuck-flow detection and recovery:
- periodic Celery Beat sweep,
- resend/day-advance recovery decision,
- max-attempt guardrails,
- admin reset/advance/unstick endpoints,
- visibility into failed flow operations.

### S03 — Flow Observability

Make the pipeline operator-visible:
- flow health counts,
- stall alerting,
- AI fallback metrics,
- correlation ID propagation from ingress through downstream flow handling.

### S04 — Pipeline Verification

Lock the milestone with integration coverage:
- webhook ingress + sequential continuation,
- mismatch reset behavior,
- config validation behavior,
- stuck-flow detection and recovery,
- outbound/follow-up retry success and exhaustion paths.

## Key Risks and Guardrails

- **Duplicate patient actions:** recovery/retry paths must stay idempotent.
- **Race conditions:** re-check flow state before acting when recovery and inbound responses may overlap.
- **Silent regressions:** every deterministic fallback or stall path should produce either state markers, metrics, or logs.
- **Operational drift:** keep all work inside current FastAPI/Celery/WuzAPI boundaries instead of introducing parallel orchestration.

## Ready-to-Execute Guidance

When working inside this milestone, prefer:
- `PatientFlowState.step_data` markers over new tables,
- existing admin-extension patterns over bespoke routers,
- existing Celery task conventions over custom retry runners,
- structured logs + Prometheus counters over ad hoc print/debug paths,
- focused integration tests that exercise real service seams while mocking only external boundaries.

## Bottom Line

The migrated milestone should be understood as a **production hardening milestone for the WhatsApp flow pipeline** — not a generic migration bucket. Its planning artifacts are about making patient-flow failures recoverable, visible, and test-verified within the project's existing backend architecture.
