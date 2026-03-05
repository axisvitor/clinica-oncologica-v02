# Stack Research

**Domain:** ADK stability, runtime error diagnosis, and post-OTel production observability
**Researched:** 2026-03-05
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `google-adk` | `1.26.0` | ADK runtime alignment (Agent/Runner/FunctionTool/SessionService) | Already integrated in this codebase; current ADK docs emphasize callbacks + standard logging hooks for execution diagnostics, so keep ADK as the single agent runtime surface. |
| `sentry-sdk` | `2.54.0` | Error diagnostics, trace continuity, and incident triage | Current code has fragmented Sentry setup; move to one Sentry stack version and use FastAPI + Celery integration so ADK failures are visible end-to-end (API trigger -> worker task -> ADK call). |
| `prometheus-client` | `0.24.1` | Metrics backend for latency/throughput/error SLOs | Already present and stable; best fit for replacing removed OTel metrics path without introducing a second telemetry model. |
| `prometheus-fastapi-instrumentator` | `7.1.0` | Low-friction HTTP baseline metrics for FastAPI routes | Add to standardize HTTP metrics for `/api/v2/adk/run` and reduce custom-middleware blind spots; keep custom business metrics for ADK tool-level telemetry. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sentry-sdk[integrations]` | `2.54.0` | `FastApiIntegration`, `CeleryIntegration`, `SqlalchemyIntegration`, `RedisIntegration` | Use in a single initializer only (`app/core/setup/sentry.py`) and ensure worker process initialization is explicit at Celery startup. |
| `structlog` | `25.5.0` | Structured ADK logs with correlation IDs | Use for ADK runtime boundary logs (tool name, session_id, user_id hash, status, duration_ms, error_type) in `app/ai/adk/runtime.py` and `app/ai/adk/wrapper.py`. |
| `python-json-logger` | `4.0.0` | JSON formatter for centralized log ingestion | Use if log shipping expects strict JSON and you keep stdlib logging handlers; do not duplicate with parallel formatter pipelines. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `promtool` (Prometheus CLI) | Validate alert/recording rules for ADK SLOs | Add to CI for metrics rule linting before deploy (operational stability gate). |
| Sentry issue alerts + metric alerts | Incident routing for ADK regressions | Configure alerts on `adk_tool_run_failed_total`, p95 ADK latency, and ADK endpoint 5xx spikes. |

## Installation

```bash
# Core changes
pip install "sentry-sdk==2.54.0" "prometheus-fastapi-instrumentator==7.1.0"

# Optional logging alignment updates
pip install "structlog==25.5.0" "python-json-logger==4.0.0"
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `sentry-sdk 2.54.0` centralized setup | Keep multiple Sentry setup modules (`app/monitoring/sentry_config.py`, `app/core/monitoring_config.py`, `app/core/setup/sentry.py`) | Never in production; only temporarily during refactor branch if you are actively deleting duplicates. |
| `prometheus-client` + optional instrumentator | Rebuild observability around a new APM vendor | Only if organization-level mandate exists; otherwise adds migration risk during ADK stabilization milestone. |
| ADK callbacks + structured logs for diagnosis | Ad-hoc `try/except` + plain string logs | Only for throwaway debugging; not acceptable for production diagnosis workflows. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Re-introducing OpenTelemetry packages/instrumentors | This milestone explicitly replaces post-OTel observability path; reintroducing OTel recreates dependency and operational complexity you just removed. | Sentry + Prometheus + structured logs. |
| Adding Langfuse/LangSmith/ML observability platform now | Extra ingestion pipeline and governance overhead during stability hardening; not required for immediate ADK runtime diagnosis goals. | First harden ADK telemetry with existing stack; revisit after SLOs are stable. |
| Parallel correlation middleware libraries (e.g., `asgi-correlation-id`) | Codebase already has correlation/request ID handling; adding another source creates inconsistent IDs across logs/metrics/errors. | Keep current correlation model and propagate IDs through ADK context + Celery headers. |
| Multiple Sentry init paths in runtime | Causes inconsistent sampling/filtering and hard-to-debug missing events. | One Sentry initializer and one worker bootstrap hook. |

## Stack Patterns by Variant

**If ADK calls stay API-synchronous (`/api/v2/adk/run`):**
- Instrument endpoint-level metrics via `prometheus-fastapi-instrumentator` and tool-level counters in `app/ai/adk/runtime.py`.
- Capture ADK exceptions in Sentry with tags: `tool_name`, `adk_session_id`, `request_source`.

**If ADK execution moves into Celery tasks:**
- Initialize Sentry in worker startup (Celery signal), not only API startup.
- Propagate correlation/request IDs into task headers and emit same IDs in ADK logs.

**If debugging an active production ADK incident:**
- Raise ADK logger to `INFO`/`DEBUG` only for scoped loggers (`google_adk.*`, `app.ai.adk.*`) and time-box it.
- Do not enable global DEBUG because ADK docs note verbose prompt-level logging at DEBUG can expose sensitive content.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `google-adk==1.26.0` | `google-genai==1.66.0` | Current PyPI versions are compatible; keep both within `<2.0.0` major line. |
| `sentry-sdk==2.54.0` | `fastapi>=0.79.0` and `celery>=4.4.7` | Supported by Sentry Python integration docs; matches this codebase (FastAPI/Celery already present). |
| `prometheus-fastapi-instrumentator==7.1.0` | `prometheus-client==0.24.1` | Instrumentator uses prometheus client under the hood; avoid duplicate metric names with custom exporters. |

## Integration Points in This Codebase

| Area | File(s) | Stack Impact |
|------|---------|-------------|
| ADK runtime boundary | `backend-hormonia/app/ai/adk/runtime.py` | Add latency/error/throughput counters around `run_adk_tool`, Runner path, fallback path, and tool dispatch result normalization. |
| PII-safe ADK wrapper | `backend-hormonia/app/ai/adk/wrapper.py` | Add structured logs + Sentry breadcrumbs for sanitization fail/block, output PII warnings, and operation tags. |
| ADK endpoint | `backend-hormonia/app/api/v2/routers/adk.py` | Add route metrics and request-source tags; ensure response includes correlation identifiers for support triage. |
| Monitoring bootstrap | `backend-hormonia/app/core/monitoring_setup.py` and `backend-hormonia/app/core/setup/sentry.py` | Consolidate to one Sentry init path; remove duplicate/legacy init flows from `app/monitoring/sentry_config.py` and `app/core/monitoring_config.py`. |
| Worker telemetry | `backend-hormonia/app/tasks/celery_metrics.py` | Add ADK-specific task labels/status dimensions and ensure Sentry worker initialization occurs at process start. |

## Migration Notes (Concrete Changes)

1. **Unify Sentry initialization first**
   - Keep `app/core/setup/sentry.py` as canonical.
   - Stop initializing Sentry from multiple modules to prevent split sampling/filter behavior.

2. **Add ADK-specific Prometheus metrics next**
   - Required minimums: `adk_tool_run_total{tool,status}`, `adk_tool_run_duration_seconds{tool}`, `adk_runner_fallback_total{reason}`.
   - Wire in `runtime.py` and `adk.py` endpoint path.

3. **Introduce HTTP auto-instrumentation carefully**
   - If adding `prometheus-fastapi-instrumentator`, disable overlapping HTTP metric names from custom middleware/exporters to avoid collision.

4. **Worker parity**
   - Ensure Celery worker has the same Sentry release/environment/tags as API process.
   - Confirm ADK-related task errors appear in Sentry with trace continuity.

## Sources

- PyPI: `google-adk` current version (`1.26.0`) - https://pypi.org/pypi/google-adk/json (HIGH)
- PyPI: `google-genai` current version (`1.66.0`) - https://pypi.org/pypi/google-genai/json (HIGH)
- ADK docs: Function Tools and Runner usage patterns - https://google.github.io/adk-docs/tools-custom/function-tools/ (HIGH)
- ADK docs: Callback lifecycle hooks (before/after agent/model/tool) - https://google.github.io/adk-docs/callbacks/types-of-callbacks/ (HIGH)
- ADK docs: Logging model and DEBUG sensitivity notes - https://google.github.io/adk-docs/observability/logging/ (HIGH)
- PyPI: `sentry-sdk` current version (`2.54.0`) - https://pypi.org/pypi/sentry-sdk/json (HIGH)
- Sentry docs: FastAPI integration behavior/options - https://docs.sentry.io/platforms/python/integrations/fastapi/ (HIGH)
- Sentry docs: Celery integration + worker init guidance - https://docs.sentry.io/platforms/python/integrations/celery/ (HIGH)
- PyPI: `prometheus-client` current version (`0.24.1`) - https://pypi.org/pypi/prometheus-client/json (HIGH)
- Prometheus Python client docs - https://prometheus.github.io/client_python/ (HIGH)
- PyPI: `prometheus-fastapi-instrumentator` current version (`7.1.0`) - https://pypi.org/pypi/prometheus-fastapi-instrumentator/json (MEDIUM)
- Project code references for integration points:
  - `backend-hormonia/app/ai/adk/runtime.py`
  - `backend-hormonia/app/ai/adk/wrapper.py`
  - `backend-hormonia/app/api/v2/routers/adk.py`
  - `backend-hormonia/app/core/setup/sentry.py`
  - `backend-hormonia/app/core/monitoring_setup.py`
  - `backend-hormonia/app/monitoring/sentry_config.py`
  - `backend-hormonia/app/core/monitoring_config.py`
  - `backend-hormonia/app/tasks/celery_metrics.py`

---
*Stack research for: v1.8 ADK stability/error hardening milestone*
*Researched: 2026-03-05*
