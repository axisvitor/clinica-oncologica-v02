---
phase: 46
slug: adk-observability-baseline
status: passed
verified_on: 2026-03-05
requirements:
  - OBS-02
verifier: Codex
---

# Phase 46 Verification

## Verdict

Phase 46 is **passed**. The repository now exposes ADK latency, throughput, error-rate, and in-flight metrics on the default Prometheus registry, and the canonical `/api/v2/adk/run` path records those signals plus structured invocation logs at the runtime boundary.

## Must-Have Checks

| Check | Requirement | Result | Evidence |
|---|---|---|---|
| `/metrics` exposes the default Prometheus registry used by ADK metrics | OBS-02 | Pass | `backend-hormonia/app/api/v2/metrics.py:7-21`; `backend-hormonia/app/ai/adk/metrics.py:14-31` |
| ADK invocation latency is recorded per `tool_name` and `status` | OBS-02 | Pass | `backend-hormonia/app/ai/adk/metrics.py:14-19`; `backend-hormonia/app/ai/adk/runtime.py:148-157`; `backend-hormonia/tests/unit/test_adk_metrics.py:36-47`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:1198-1260` |
| ADK throughput and error-rate signals are aggregated per `tool_name` and `status` | OBS-02 | Pass | `backend-hormonia/app/ai/adk/metrics.py:21-25`; `backend-hormonia/app/ai/adk/runtime.py:126-343`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:1263-1351` |
| Operators can detect failure spikes without inspecting raw logs request by request | OBS-02 | Pass | `backend-hormonia/app/ai/adk/metrics.py:21-25`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:1263-1351`; local registry check showed ADK series on the default registry |
| Structured log line is emitted for each invocation with `tool_name`, `status`, `duration_ms`, `invocation_id`, and `session_id` | OBS-02 | Pass | `backend-hormonia/app/ai/adk/metrics.py:34-61`; `backend-hormonia/tests/unit/test_adk_metrics.py:61-78` |
| In-flight gauge increments during execution and returns to baseline on completion | OBS-02 | Pass | `backend-hormonia/app/ai/adk/metrics.py:64-71`; `backend-hormonia/app/ai/adk/runtime.py:215-217`; `backend-hormonia/app/ai/adk/runtime.py:341-343`; `backend-hormonia/tests/unit/test_adk_tools_runtime.py:1354-1393` |

## Requirement Coverage

| Requirement | Status | Notes |
|---|---|---|
| OBS-02 | Pass | The canonical ADK execution path now emits Prometheus metrics and structured logs with coverage for success, timeout, policy-block, unsupported-tool, and tool-error outcomes. Because `/metrics` serves `generate_latest()` from the default registry, the new ADK series are exposed without extra exporter wiring. |

## Evidence

### 1. The canonical `/api/v2/adk/run` path reaches the instrumented boundary

- The API route at `backend-hormonia/app/api/v2/routers/adk.py:13-48` continues to route requests through `PIISafeADKWrapper.safe_run(...)`.
- The wrapper delegates to `run_adk_tool(...)` at `backend-hormonia/app/ai/adk/wrapper.py:154`.
- The instrumented runtime boundary in `backend-hormonia/app/ai/adk/runtime.py:126-343` records metrics for unsupported-tool errors, cancel/session early returns, and every terminal execution outcome.

### 2. Prometheus series are defined on the default registry and exposed by `/metrics`

- `backend-hormonia/app/ai/adk/metrics.py:14-31` defines:
  - `adk_invocation_duration_seconds`
  - `adk_invocations_total` (counter sample family appears as `adk_invocations` in `REGISTRY.collect()`)
  - `adk_invocations_in_flight`
- `backend-hormonia/app/api/v2/metrics.py:13-21` returns `generate_latest()` from `prometheus_client`, so any metric on the default registry is automatically included in the `/metrics` response.
- Local verification command on 2026-03-05:

```bash
cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token .venv/bin/python -c "from prometheus_client import REGISTRY; from app.ai.adk import metrics as adk_metrics; print(sorted([m.name for m in REGISTRY.collect() if m.name.startswith('adk_')]))"
```

Observed result: `['adk_invocation_duration_seconds', 'adk_invocations', 'adk_invocations_in_flight']`

### 3. Runtime instrumentation covers the required operational outcomes

- Unsupported tools record `status="error"` immediately at `backend-hormonia/app/ai/adk/runtime.py:131-146`.
- The main execution path starts timing before session resolution at `backend-hormonia/app/ai/adk/runtime.py:148-157`, which means session resolution, policy checks, and execution latency all contribute to the histogram.
- Success, timeout, cancelled, limit-exceeded, tool-error, upstream-error, and policy-block/other normalized statuses all call `record_adk_invocation(...)` before returning in `backend-hormonia/app/ai/adk/runtime.py:219-343`.
- The in-flight gauge is incremented/decremented around the tracked execution window in `backend-hormonia/app/ai/adk/runtime.py:215-217` and `backend-hormonia/app/ai/adk/runtime.py:341-343`.

### 4. Automated evidence is green

- Metrics module tests cover histogram, counter, structured log, and exception-safe gauge behavior in `backend-hormonia/tests/unit/test_adk_metrics.py:22-90`.
- Runtime integration tests cover success, timeout, policy-block, unsupported-tool, tool-error, and the in-flight gauge lifecycle in `backend-hormonia/tests/unit/test_adk_tools_runtime.py:1195-1393`.
- Full Phase 46 ADK suite rerun on 2026-03-05:

```bash
cd backend-hormonia && WHATSAPP_WUZAPI_TOKEN=test-token .venv/bin/python -m pytest tests/unit/test_adk_metrics.py tests/unit/test_adk_tools_runtime.py tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py -x -q
```

Observed result: exit code `0` with the full selected suite green.

### 5. Structured logging contains the required identifiers without polluting metric labels

- `backend-hormonia/app/ai/adk/metrics.py:34-61` records low-cardinality Prometheus labels (`tool_name`, `status`) while logging `adk_invocation_id` and `adk_session_id` only in structured log fields.
- `backend-hormonia/tests/unit/test_adk_metrics.py:61-78` proves the emitted log record includes:
  - `adk_tool_name`
  - `adk_status`
  - `adk_duration_ms`
  - `adk_invocation_id`
  - `adk_session_id`
  - `metric_type="adk_invocation"`

## Remaining Notes

- Local verification required `WHATSAPP_WUZAPI_TOKEN=test-token` because backend settings bootstrap validates that variable even though the ADK observability tests themselves do not hit WuzAPI.
- The existing `/metrics` route already exposes the default registry, so no additional deployment-time code changes are required for the new ADK series.

## Final Assessment

Phase 46 satisfies OBS-02 in repository evidence: the canonical ADK runtime now emits Prometheus metrics and structured invocation logs that operators can use to monitor latency, throughput, and error rates per tool/agent.

**Final status: `passed`**
