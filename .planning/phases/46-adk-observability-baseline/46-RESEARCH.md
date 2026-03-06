# Phase 46: ADK Observability Baseline - Research

**Researched:** 2026-03-06
**Domain:** Prometheus metrics instrumentation for ADK runtime latency, throughput, and error rates
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| OBS-02 | Operador pode monitorar latencia, throughput e taxa de erro ADK em producao por invocacao e agente | Confirmed: prometheus_client is already in requirements.txt and used extensively in app/core/metrics.py and app/monitoring/metrics.py. ADK runtime has a single execution choke point (`run_adk_tool`) where Histogram/Counter instrumentation can be added with tool_name and status labels. The /metrics endpoint already exists at `app/api/v2/metrics.py` and serves `generate_latest()`. |

</phase_requirements>

## Summary

Phase 46 adds Prometheus metrics to the ADK execution path so operators can monitor latency, throughput, and error rates per invocation and per agent (tool_name) in production without manual log inspection. The project already has prometheus_client installed (`>=0.24.1,<1.0.0`), a `/metrics` endpoint serving `generate_latest()`, and dozens of existing Histogram/Counter/Gauge definitions across `app/core/metrics.py` and `app/monitoring/metrics.py`. The ADK layer currently has zero Prometheus instrumentation.

The implementation surface is narrow and well-defined. `run_adk_tool()` in `app/ai/adk/runtime.py` is the single mandatory execution boundary for all ADK invocations -- every call flows through it regardless of whether the ADK runner path or direct-handler fallback is active. This function already captures tool_name, invocation_id, terminal status, and elapsed time (via `asyncio.wait_for`). Adding three Prometheus instruments at this boundary -- a Histogram for latency, a Counter for total invocations (with status/tool_name labels), and an optional Gauge for in-flight invocations -- gives operators full visibility with minimal code changes.

The structured logging layer (`app/utils/structured_logger.py`) already emits JSON logs with correlation_id and request_id. Phase 46 should add structured log lines at the ADK runtime boundary with invocation_id, tool_name, status, and duration_ms so operators can correlate metrics spikes with specific invocations. This complements Prometheus (which aggregates) with log-level detail (which identifies individual requests).

**Primary recommendation:** Add a small `app/ai/adk/metrics.py` module defining three Prometheus instruments (Histogram, Counter, Gauge) and a thin `record_adk_invocation()` helper. Instrument `run_adk_tool()` with a single try/finally block that records latency, status, and tool_name. Add structured log emission at the same boundary.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| prometheus_client | >=0.24.1,<1.0.0 | Histogram, Counter, Gauge metrics | Already in requirements.txt, used in 18+ source files, exposed via `/metrics` |
| logging (stdlib) | Python 3.13 | Structured JSON log lines at ADK boundary | Already used in every ADK module via `logging.getLogger(__name__)` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| time (stdlib) | Python 3.13 | `time.monotonic()` for latency measurement | More precise than `time.time()` for duration tracking |
| app.utils.structured_logger | Project-owned | JSON-formatted log lines with correlation context | When emitting structured ADK invocation logs |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| prometheus_client Histogram | AIMetricsCollector (app/services/ai/metrics.py) | AIMetricsCollector is in-memory only with no /metrics exposure; Prometheus integrates with existing scraping infrastructure |
| New /adk/metrics endpoint | Existing /metrics endpoint | No reason to create a separate endpoint; Prometheus standard is single /metrics serving all instruments |
| structlog | stdlib logging + pythonjsonlogger | Project already uses pythonjsonlogger through app/utils/logging.py; no reason to add another dependency |

### Do Not Introduce

No new dependencies are needed. prometheus_client and the logging stack are already present and active.

## Architecture Patterns

### Recommended Module Structure

```
backend-hormonia/app/ai/adk/
    __init__.py          # existing
    metrics.py           # NEW: Prometheus instruments + record helper
    runtime.py           # MODIFIED: import and call record helper in run_adk_tool
    wrapper.py           # UNCHANGED
    tools.py             # UNCHANGED
    session_store.py     # UNCHANGED
```

### Pattern 1: Dedicated ADK Metrics Module

**What:** A single `app/ai/adk/metrics.py` file that defines all ADK-specific Prometheus instruments and a thin recording function.

**When to use:** Always -- keeps metric definitions centralized and testable independently of the runtime.

**Example:**

```python
# app/ai/adk/metrics.py
from prometheus_client import Counter, Histogram, Gauge

ADK_INVOCATION_DURATION_SECONDS = Histogram(
    "adk_invocation_duration_seconds",
    "ADK invocation latency in seconds",
    ["tool_name", "status"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

ADK_INVOCATIONS_TOTAL = Counter(
    "adk_invocations_total",
    "Total ADK invocations",
    ["tool_name", "status"],
)

ADK_INVOCATIONS_IN_FLIGHT = Gauge(
    "adk_invocations_in_flight",
    "Number of ADK invocations currently in progress",
    ["tool_name"],
)


def record_adk_invocation(
    *,
    tool_name: str,
    status: str,
    duration_seconds: float,
) -> None:
    ADK_INVOCATION_DURATION_SECONDS.labels(
        tool_name=tool_name,
        status=status,
    ).observe(duration_seconds)
    ADK_INVOCATIONS_TOTAL.labels(
        tool_name=tool_name,
        status=status,
    ).inc()
```

### Pattern 2: Instrument at the run_adk_tool Boundary

**What:** Wrap the existing `run_adk_tool()` execution with `time.monotonic()` start/stop and a `try/finally` block that calls `record_adk_invocation()`.

**When to use:** Always -- this is the single mandatory choke point.

**Why here and not at the route or wrapper level:**
- The route (`adk.py`) is a thin adapter and does not own the final status.
- The wrapper (`PIISafeADKWrapper`) handles PII sanitization; the actual execution status is determined inside `run_adk_tool()`.
- `run_adk_tool()` already has all the required context: tool_name, final status, and all exception-to-status mappings.

**Example:**

```python
# Inside run_adk_tool(), simplified structure:
import time
from app.ai.adk.metrics import (
    record_adk_invocation,
    ADK_INVOCATIONS_IN_FLIGHT,
)

async def run_adk_tool(request: ADKToolRunRequest) -> dict[str, Any]:
    tool_name = request.tool_name.strip().lower()
    # ... existing registry lookup, session resolution, etc. ...

    ADK_INVOCATIONS_IN_FLIGHT.labels(tool_name=tool_name).inc()
    start = time.monotonic()
    try:
        # ... existing execution logic with all exception handlers ...
        return result
    finally:
        duration = time.monotonic() - start
        final_status = result.get("status", "unknown")
        record_adk_invocation(
            tool_name=tool_name,
            status=final_status,
            duration_seconds=duration,
        )
        ADK_INVOCATIONS_IN_FLIGHT.labels(tool_name=tool_name).dec()
```

### Pattern 3: Structured Log Emission at Runtime Boundary

**What:** Add a structured JSON log line at `run_adk_tool()` completion with invocation metadata.

**When to use:** Always -- operators need both aggregated metrics (Prometheus) and per-invocation detail (logs).

**Example:**

```python
import logging

logger = logging.getLogger(__name__)

# After recording metrics, in the finally block:
logger.info(
    "ADK invocation completed",
    extra={
        "adk_tool_name": tool_name,
        "adk_status": final_status,
        "adk_duration_ms": round(duration * 1000, 2),
        "adk_invocation_id": invocation_id,
        "adk_session_id": session_id,
        "metric_type": "adk_invocation",
    },
)
```

### Pattern 4: Follow Existing Prometheus Naming Conventions

**What:** Use the same naming pattern established in `app/core/metrics.py` and `app/monitoring/metrics.py`.

**Naming rules from the existing codebase:**
- Suffix `_total` for Counters (e.g., `app_requests_total`)
- Suffix `_seconds` for Histograms measuring duration (e.g., `app_request_duration_seconds`)
- Descriptive metric names with underscores (e.g., `circuit_breaker_call_duration_seconds`)
- Labels for dimensions: `["tool_name", "status"]`

**ADK metrics should follow this pattern:**
- `adk_invocation_duration_seconds` (Histogram)
- `adk_invocations_total` (Counter)
- `adk_invocations_in_flight` (Gauge)

### Anti-Patterns to Avoid

- **Recording metrics inside individual tool handlers:** Creates coupling and misses early-exit paths (policy_block, session errors, unsupported tool). The boundary must be `run_adk_tool()`.
- **Using the in-memory AIMetricsCollector for this:** It has no Prometheus exposure, no persistence across restarts, and an asyncio.Lock that adds overhead. Prometheus instruments are thread-safe and lock-free.
- **Creating a separate /adk/metrics endpoint:** Breaks the Prometheus single-scrape convention. The existing `/metrics` endpoint already serves `generate_latest()` from the default registry.
- **Measuring latency with `time.time()`:** Use `time.monotonic()` to avoid clock-drift issues.
- **Adding high-cardinality labels (invocation_id, user_id, session_id):** These belong in logs, not in Prometheus labels. High cardinality destroys Prometheus performance.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Latency histograms | Custom timer + Redis storage | prometheus_client.Histogram | Already in the stack, thread-safe, auto-exported via /metrics |
| Throughput counters | Manual counter in session_store | prometheus_client.Counter | Same reason; atomic increments, no race conditions |
| In-flight tracking | Lock-protected dict (like _IN_FLIGHT_INVOCATIONS) | prometheus_client.Gauge with inc()/dec() | Thread-safe, auto-exported, no cleanup needed |
| Metrics endpoint | New FastAPI route | Existing /metrics route at app/api/v2/metrics.py | Already configured and presumably scraped in production |
| Structured logging | Custom JSON serializer | Existing StructuredFormatter + logger.info(extra={...}) | pythonjsonlogger already formats these fields as JSON |

**Key insight:** The project already has complete Prometheus infrastructure (client, exporter, endpoint) and complete structured logging (JSON formatter, correlation IDs). Phase 46 needs to wire ADK into these existing systems, not build new ones.

## Common Pitfalls

### Pitfall 1: Instrumenting at the Wrong Layer

**What goes wrong:** Metrics added at the route level miss early exits (unsupported tool, session errors). Metrics added inside tool handlers miss policy blocks and timeouts.
**Why it happens:** The route looks simpler to instrument, and tool handlers are the "business logic."
**How to avoid:** Instrument exclusively at `run_adk_tool()` in runtime.py. This is the single choke point that all ADK invocations pass through.
**Warning signs:** Some status values appear in logs but not in Prometheus, or vice versa.

### Pitfall 2: High-Cardinality Labels

**What goes wrong:** Using invocation_id, session_id, or user_id as Prometheus labels creates millions of time series and crashes Prometheus.
**Why it happens:** Desire for per-invocation visibility in dashboards.
**How to avoid:** Use only `tool_name` (4 values: sentiment, humanize, variation, empathy) and `status` (8 values: success, completed, cancelled, timeout, limit_exceeded, policy_block, tool_error, upstream_error, error) as labels. Put per-invocation detail in structured logs.
**Warning signs:** Prometheus scrape timeouts or /metrics response growing unbounded.

### Pitfall 3: Missing Early-Exit Paths in Metrics

**What goes wrong:** `run_adk_tool()` has multiple early return paths: unsupported tool, cancel action, session close, session errors. If the timing/recording starts after session resolution, these paths are unmeasured.
**Why it happens:** The timing instrumentation is placed too deep in the function.
**How to avoid:** Start timing at the very top of `run_adk_tool()` and record in the `finally` block of a try/finally wrapping the entire function body. Handle early returns by extracting their status before the finally block.
**Warning signs:** Sum of all `adk_invocations_total` does not match the API-level request count for `/api/v2/adk/run`.

### Pitfall 4: Not Differentiating Pre-Execution from Execution Metrics

**What goes wrong:** Session resolution latency (Redis lookups) gets folded into the same histogram as actual LLM execution latency, making p99 meaningless.
**Why it happens:** Single timing boundary wraps everything.
**How to avoid:** This phase should accept the combined measurement as the baseline (the operator cares about total endpoint latency per invocation). A future phase (OBS-03) can add sub-span instrumentation for session resolution vs. tool execution vs. LLM call.
**Warning signs:** None for this phase -- this is a conscious scope decision.

### Pitfall 5: Forgetting the Default Registry

**What goes wrong:** Metrics defined with a custom CollectorRegistry (like in prometheus_exporters.py) are NOT served by the default `generate_latest()` call in `/metrics`.
**Why it happens:** The project has two patterns: `app/core/metrics.py` uses default registry, `app/monitoring/prometheus_exporters.py` uses a custom registry.
**How to avoid:** Define ADK metrics without a `registry=` parameter so they register on the default registry, which is what `app/api/v2/metrics.py` serves.
**Warning signs:** Metrics appear in code but not in `/metrics` output.

### Pitfall 6: Not Testing Metric Values

**What goes wrong:** Metrics code is added but tests only verify functional behavior, not that the metrics were actually recorded.
**Why it happens:** Prometheus instruments are global singletons and testing them requires using the `.collect()` API or `prometheus_client.REGISTRY`.
**How to avoid:** Tests should assert that after a successful invocation, the counter sample with matching labels has incremented. The pattern is to read `REGISTRY.get_sample_value("metric_name", {"label": "value"})`.
**Warning signs:** Metrics module has 100% line coverage from import but 0% behavioral coverage.

## Code Examples

### Example 1: Complete metrics module

```python
# app/ai/adk/metrics.py
"""Prometheus metrics for ADK invocation observability (OBS-02)."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Generator

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# -- Prometheus instruments (default registry) --

ADK_INVOCATION_DURATION_SECONDS = Histogram(
    "adk_invocation_duration_seconds",
    "ADK invocation latency in seconds",
    ["tool_name", "status"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

ADK_INVOCATIONS_TOTAL = Counter(
    "adk_invocations_total",
    "Total ADK invocations by tool and outcome status",
    ["tool_name", "status"],
)

ADK_INVOCATIONS_IN_FLIGHT = Gauge(
    "adk_invocations_in_flight",
    "ADK invocations currently executing",
    ["tool_name"],
)


def record_adk_invocation(
    *,
    tool_name: str,
    status: str,
    duration_seconds: float,
    invocation_id: str | None = None,
    session_id: str | None = None,
) -> None:
    """Record Prometheus metrics and emit structured log for one ADK invocation."""
    ADK_INVOCATION_DURATION_SECONDS.labels(
        tool_name=tool_name, status=status,
    ).observe(duration_seconds)
    ADK_INVOCATIONS_TOTAL.labels(
        tool_name=tool_name, status=status,
    ).inc()
    logger.info(
        "ADK invocation completed",
        extra={
            "adk_tool_name": tool_name,
            "adk_status": status,
            "adk_duration_ms": round(duration_seconds * 1000, 2),
            "adk_invocation_id": invocation_id or "",
            "adk_session_id": session_id or "",
            "metric_type": "adk_invocation",
        },
    )


@contextmanager
def track_adk_invocation(tool_name: str) -> Generator[dict[str, Any], None, None]:
    """Context manager that tracks in-flight count and yields a result holder."""
    ADK_INVOCATIONS_IN_FLIGHT.labels(tool_name=tool_name).inc()
    ctx: dict[str, Any] = {"start": time.monotonic()}
    try:
        yield ctx
    finally:
        ADK_INVOCATIONS_IN_FLIGHT.labels(tool_name=tool_name).dec()
```

### Example 2: Instrumentation in run_adk_tool

```python
# Simplified view of run_adk_tool() after instrumentation
async def run_adk_tool(request: ADKToolRunRequest) -> dict[str, Any]:
    tool_name = request.tool_name.strip().lower()
    handler = registry.get(tool_name)
    if handler is None:
        result = _build_result(status="error", result={...})
        record_adk_invocation(
            tool_name=tool_name, status="error", duration_seconds=0.0,
        )
        return result

    start = time.monotonic()
    ADK_INVOCATIONS_IN_FLIGHT.labels(tool_name=tool_name).inc()
    try:
        # ... existing logic (session, invocation, execution, exception handlers) ...
        return result
    finally:
        duration = time.monotonic() - start
        record_adk_invocation(
            tool_name=tool_name,
            status=result.get("status", "unknown"),
            duration_seconds=duration,
            invocation_id=invocation_id,
            session_id=session_id,
        )
        ADK_INVOCATIONS_IN_FLIGHT.labels(tool_name=tool_name).dec()
```

### Example 3: Testing metrics recording

```python
# tests/unit/test_adk_metrics.py
import pytest
from prometheus_client import REGISTRY

from app.ai.adk.metrics import record_adk_invocation


def test_record_adk_invocation_increments_counter():
    # Get baseline
    before = REGISTRY.get_sample_value(
        "adk_invocations_total",
        {"tool_name": "sentiment", "status": "success"},
    ) or 0.0

    record_adk_invocation(
        tool_name="sentiment",
        status="success",
        duration_seconds=0.42,
    )

    after = REGISTRY.get_sample_value(
        "adk_invocations_total",
        {"tool_name": "sentiment", "status": "success"},
    )
    assert after == before + 1.0


def test_record_adk_invocation_records_histogram():
    before_count = REGISTRY.get_sample_value(
        "adk_invocation_duration_seconds_count",
        {"tool_name": "humanize", "status": "timeout"},
    ) or 0.0

    record_adk_invocation(
        tool_name="humanize",
        status="timeout",
        duration_seconds=5.0,
    )

    after_count = REGISTRY.get_sample_value(
        "adk_invocation_duration_seconds_count",
        {"tool_name": "humanize", "status": "timeout"},
    )
    assert after_count == before_count + 1.0
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| OpenTelemetry instrumentation packages | Sentry + Prometheus (post-OTel cleanup in v1.7) | Phase 40 (2026-03-03) | ADK re-introduced OTel core as transitive dep but project instrumention uses Sentry + Prometheus only |
| In-memory AIMetricsCollector | In-memory only, not Prometheus-exposed | Pre-v1.0 | AI call metrics exist but are not scraped; ADK metrics should go directly to Prometheus |
| No ADK metrics at all | Zero instrumentation in ADK layer | Current state | This phase introduces the first ADK observability baseline |

**Deprecated/outdated:**
- OTel instrumentation packages were removed in v1.7 (Phase 40). The project uses Sentry for error tracking/tracing and Prometheus for metric aggregation.
- `AIMetricsCollector` at `app/services/ai/metrics.py` is a useful pattern but its in-memory-only design means it is not suitable as the sole ADK metrics path. Prometheus instruments persist across requests and are scraped externally.

## Open Questions

1. **Is Prometheus scraping already configured in production (Cloud Run)?**
   - What we know: `/metrics` endpoint exists and serves `generate_latest()`. prometheus_client is installed.
   - What's unclear: Whether the production Cloud Run deployment actually has a Prometheus scraper configured.
   - Recommendation: This does not block implementation. The metrics will be served regardless; scraping configuration is an ops concern outside this phase's scope. The structured logs provide fallback visibility via Railway/Cloud Logging.

2. **Should the in-flight gauge track by tool_name or be a single aggregate?**
   - What we know: There are only 4 tool names, so per-tool tracking is low cardinality.
   - What's unclear: Whether operators care about per-tool in-flight counts or just aggregate.
   - Recommendation: Use per-tool labels. The cardinality is 4 -- negligible cost with useful breakdown.

3. **Should session resolution latency be measured separately?**
   - What we know: Session resolution involves Redis lookups which can add significant latency.
   - What's unclear: Whether operators need this granularity in the baseline phase.
   - Recommendation: Defer to a future phase (OBS-03). The baseline should measure total invocation latency. Sub-span decomposition adds complexity without matching a v1.8 requirement.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 |
| Config file | `backend-hormonia/pyproject.toml` |
| Quick run command | `cd backend-hormonia && pytest tests/unit/test_adk_metrics.py tests/unit/test_adk_tools_runtime.py -q` |
| Full suite command | `cd backend-hormonia && pytest tests/unit/test_adk_metrics.py tests/unit/test_adk_tools_runtime.py tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OBS-02-a | Latency histogram records duration per invocation | unit | `pytest tests/unit/test_adk_metrics.py::test_histogram_records_duration -x` | No -- Wave 0 |
| OBS-02-b | Counter increments per invocation with tool_name and status labels | unit | `pytest tests/unit/test_adk_metrics.py::test_counter_increments -x` | No -- Wave 0 |
| OBS-02-c | In-flight gauge tracks concurrent invocations | unit | `pytest tests/unit/test_adk_metrics.py::test_in_flight_gauge -x` | No -- Wave 0 |
| OBS-02-d | Structured log emitted with adk_tool_name, adk_status, adk_duration_ms | unit | `pytest tests/unit/test_adk_metrics.py::test_structured_log_emitted -x` | No -- Wave 0 |
| OBS-02-e | run_adk_tool records metrics for all terminal statuses | unit | `pytest tests/unit/test_adk_tools_runtime.py -k "metrics" -x` | No -- Wave 0 |
| OBS-02-f | Existing runtime regressions stay green after instrumentation | unit | `pytest tests/unit/test_adk_tools_runtime.py -x` | Yes |
| OBS-02-g | Route-level regressions stay green | integration | `pytest tests/api/v2/test_adk.py -x` | Yes |

### Sampling Rate

- **Per task commit:** `cd backend-hormonia && pytest tests/unit/test_adk_metrics.py tests/unit/test_adk_tools_runtime.py -q`
- **Per wave merge:** `cd backend-hormonia && pytest tests/unit/test_adk_metrics.py tests/unit/test_adk_tools_runtime.py tests/api/v2/test_adk.py tests/unit/test_pii_safe_adk_wrapper.py -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/test_adk_metrics.py` -- covers OBS-02 a/b/c/d (new file)
- [ ] `app/ai/adk/metrics.py` -- Prometheus instruments + record helper (new file)
- [ ] Metrics integration tests inside `tests/unit/test_adk_tools_runtime.py` -- verify run_adk_tool records metrics for success/error/timeout/policy_block statuses

## Sources

### Primary (HIGH confidence)

- `backend-hormonia/app/core/metrics.py` -- Established Prometheus metric definitions (Counter, Histogram, Gauge patterns)
- `backend-hormonia/app/monitoring/metrics.py` -- Additional Prometheus metrics with label patterns
- `backend-hormonia/app/api/v2/metrics.py` -- Existing /metrics endpoint serving generate_latest()
- `backend-hormonia/requirements.txt` -- prometheus-client>=0.24.1,<1.0.0 already installed
- `backend-hormonia/app/ai/adk/runtime.py` -- Single execution boundary (run_adk_tool) with all status classifications
- `backend-hormonia/app/ai/adk/tools.py` -- Tool registry (4 tools: sentiment, humanize, variation, empathy)
- `backend-hormonia/app/utils/structured_logger.py` -- JSON structured logging with correlation IDs
- `backend-hormonia/app/utils/logging.py` -- pythonjsonlogger-based StructuredFormatter

### Secondary (MEDIUM confidence)

- `backend-hormonia/app/services/ai/metrics.py` -- AIMetricsCollector pattern (in-memory only, not Prometheus-exposed)
- `backend-hormonia/app/core/setup/sentry.py` -- Sentry integration confirming project's observability stack

### Tertiary (LOW confidence)

- Production Prometheus scraping configuration -- unverified whether Cloud Run deployment actually has a scraper configured; does not block implementation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- prometheus_client already installed and extensively used; logging infrastructure fully established
- Architecture: HIGH -- single execution boundary (run_adk_tool) is unambiguous instrumentation point
- Pitfalls: HIGH -- based on direct codebase analysis of existing metric patterns and ADK execution flow

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable -- prometheus_client API and project patterns are well-established)

---
*Phase: 46-adk-observability-baseline*
*Research completed: 2026-03-06*
