# Phase 40: OTel Removal & ADK Foundation - Research

**Researched:** 2026-03-03
**Domain:** Dependency conflict resolution (OTel vs ADK), tombstone pattern, PIISafeADKWrapper, CI guard extension
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### OTel Removal Scope
- Remove all 9 OTel packages from requirements.txt (api, sdk, 4 instrumentations, exporter-otlp, exporter-otlp-proto-http, proto) — ADK manages its own transitive OTel deps
- Remove tracing imports entirely from the 2 callers (message_service.py, unified_whatsapp_service.py) — Sentry auto-instruments these paths already
- Clean tombstone for `app/core/tracing.py`: docstring + `raise ImportError` (consistent with established tombstone pattern) — all callers cleaned first

#### ADK Installation Strategy
- Standalone first task: dry-run `pip install` in clean venv validating `google-adk` + `pydantic-ai-slim[google]` coexist in Python 3.13, document resolved versions — only then proceed to modify requirements.txt
- Remove all 9 OTel packages before adding ADK to avoid resolution conflicts

#### PIISafeADKWrapper Design
- Call-site wrapper pattern (mirrors PIISafeAgent) — all ADK invocations go through `PIISafeADKWrapper.safe_run()` which sanitizes input, calls ADK, scans output
- Reuse existing `AIDeps` dataclass for runtime model injection (model_name, gemini_api_key) — single config surface for all AI calls
- File location: `app/ai/adk/wrapper.py` in new `app/ai/adk/` package (matches roadmap success criteria path)
- Include output PII scanning (`_warn_on_output_pii`) from day one — full LGPD contract in the wrapper, tested with synthetic PHI input

#### CI Guard Extension
- Extend existing `check_agent_run_calls.py` (single script, single CI step) to cover ADK call patterns
- Claude's Discretion: exact ADK patterns to block (determined during implementation based on ADK v1.26.0 API surface)
- Exemption list hardcoded: `app/ai/agents/base.py` (existing) + `app/ai/adk/wrapper.py` (new)
- Failing fixture: pytest test that creates a temp file with direct ADK call, runs the guard, asserts exit code 1

#### Sentry Verification
- Code audit + import test: verify sentry.py has zero OTel imports, confirm Sentry init succeeds and produces test transaction
- Add `CeleryIntegration` to `setup_sentry()` (currently missing — needed for Celery transaction capture per success criteria)
- Verification baked into each task (no standalone verification plan)
- `monitoring_config.py` left as-is — separate concern, no OTel references to clean

### Claude's Discretion
- Exact ADK Runner/generate_content call patterns to block in CI guard
- ADK package version pinning strategy (exact pin vs range)
- Temporary venv setup approach for dry-run install validation
- Internal structure of `app/ai/adk/__init__.py` exports

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ADK-01 | OTel instrumentation packages removed from requirements.txt without breaking Sentry | Confirmed: 9 OTel packages identified at lines 120-129; Sentry uses its own SDK, not OTel; ADK pulls OTel 1.36-1.39 as its own transitive dep |
| ADK-02 | `app/core/tracing.py` tombstoned with ImportError (fallback mock already exists) | Confirmed: tracing.py has built-in mock fallback already; callers are exactly 2 files; tombstone pattern documented |
| ADK-03 | google-adk installed and resolved with pydantic-ai-slim[google] in Python 3.13 | Confirmed: ADK 1.26.0 supports Python >=3.10 including 3.13; conflict is OTel version mismatch (project pins >=1.28,<2 vs ADK needs >=1.36,<1.39); removing project's OTel packages resolves this |
| ADK-04 | PIISafeADKWrapper created in `app/ai/adk/` with PII sanitization before any Gemini call via ADK | Confirmed: before_model_callback is the canonical ADK hook; call-site wrapper mirrors PIISafeAgent pattern using existing pii_redaction.py |
| ADK-05 | CI guard (`check_agent_run_calls.py`) extended to cover ADK call patterns | Confirmed: script structure understood, exemption pattern identified, ADK patterns to block identified |
</phase_requirements>

## Summary

Phase 40 resolves the pip conflict that has blocked google-adk installation since v1.2. The root cause is confirmed: the project currently pins `opentelemetry-api>=1.28.0,<2.0.0` but google-adk 1.26.0 requires `opentelemetry-api>=1.36.0,<1.39.0`. These ranges do not conflict on version (1.36 satisfies >=1.28), but the real conflict is that installing ADK's transitive OTel deps alongside the project's explicit OTel instrumentation packages creates resolution chaos (especially with `opentelemetry-exporter-otlp` and `opentelemetry-proto` on different sub-version constraints). The clean solution — removing all 9 project OTel packages and letting ADK manage its own OTel tree — is correct.

The two callers of `app/core/tracing.py` (message_service.py and unified_whatsapp_service.py) both assign `self.tracer = get_tracer()` but never call any method on `self.tracer` beyond initialization. The `@trace` decorator is used once in message_service.py. These are trivially removable: delete the import line, delete the `self.tracer = get_tracer()` assignment, and replace the `@trace` decorator with nothing (the function works without it). After callers are cleaned, tombstone `app/core/tracing.py`.

Sentry is completely independent of OTel in this codebase. `app/core/setup/sentry.py` imports from `sentry_sdk` only — zero OTel imports. CeleryIntegration is currently missing from `setup_sentry()` and must be added explicitly (it does not auto-install in all Celery worker startup contexts).

**Primary recommendation:** Run the dry-run pip install first (gate), then remove OTel packages + clean callers + tombstone tracing.py as a single atomic task, then scaffold PIISafeADKWrapper, then extend CI guard.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-adk | 1.26.0 (latest as of 2026-02-26) | Google Agent Development Kit — agent orchestration, tool framework | Locked decision; ADK 1.26.0 is current stable |
| pydantic-ai-slim[google,retries] | >=1.63.0,<2.0.0 | Existing typed agent framework | Already installed; must coexist with ADK |
| sentry-sdk[fastapi] | >=1.38.0,<2.0.0 | Error tracking and performance monitoring | Already installed; replaces OTel for tracing |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sentry_sdk.integrations.celery | (bundled with sentry-sdk) | Celery transaction capture | Add to sentry.py setup_sentry() in this phase |
| app/ai/pii_redaction.py | (existing) | PII sanitization for LGPD compliance | Reused directly by PIISafeADKWrapper |
| app/ai/agents/deps.py (AIDeps) | (existing) | Runtime model injection dataclass | Reused for ADK wrapper |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| before_model_callback (ADK hook) | call-site wrapper | before_model_callback is elegant but has known bug: Plugin callbacks not invoked by InMemoryRunner (Issue #4464); call-site wrapper is 100% reliable |
| call-site wrapper pattern | before_model_callback | Call-site wrapper chosen — mirrors PIISafeAgent, works regardless of ADK runner type |

**Installation (after OTel removal):**
```bash
# In clean Python 3.13 venv — dry-run first
pip install --dry-run google-adk pydantic-ai-slim[google,retries]

# If dry-run clean, add to requirements.txt:
google-adk>=1.26.0,<2.0.0
```

## Architecture Patterns

### Recommended Project Structure
```
app/ai/
├── agents/          # Existing: 4 Pydantic AI agents + PIISafeAgent base
│   ├── base.py      # PIISafeAgent (model for PIISafeADKWrapper)
│   └── deps.py      # AIDeps dataclass (reused by ADK wrapper)
├── adk/             # NEW: ADK package directory
│   ├── __init__.py  # Exports: PIISafeADKWrapper
│   └── wrapper.py   # PIISafeADKWrapper implementation
├── pii_redaction.py # Shared PII layer (imported by both agents/ and adk/)
└── client_domain.py # GeminiDomainClient (delegates to agents/)
```

### Pattern 1: Tombstone Pattern (for tracing.py)
**What:** Replace file content with docstring + `raise ImportError` immediately on import
**When to use:** File is dead code with no active callers (callers must be cleaned first)
**Example:**
```python
# Source: Established codebase pattern (20+ tombstoned files)
"""
app/core/tracing.py — TOMBSTONED

OpenTelemetry distributed tracing. Removed in Phase 40 (OTel Removal & ADK Foundation)
as part of ADK dependency conflict resolution.

OTel instrumentation is no longer installed. Sentry handles all transaction
tracing via FastApiIntegration and CeleryIntegration.

All callers have been cleaned:
- app/integrations/whatsapp/services/message_service.py
- app/services/unified_whatsapp_service.py
"""
raise ImportError(
    "app.core.tracing is tombstoned. "
    "Sentry handles all tracing via FastApiIntegration and CeleryIntegration. "
    "See Phase 40: OTel Removal & ADK Foundation."
)
```

### Pattern 2: PIISafeADKWrapper (mirroring PIISafeAgent)
**What:** Call-site wrapper that sanitizes input before any ADK Gemini invocation and scans output for leaked PII
**When to use:** Any code path that calls ADK tools/agents with patient-derived data
**Example:**
```python
# Source: mirrors app/ai/agents/base.py (PIISafeAgent) pattern
# app/ai/adk/wrapper.py

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from app.ai.agents.deps import AIDeps
from app.ai.pii_redaction import sanitize_prompt_text_for_external_ai
from app.ai.pii_redaction import _CPF_PATTERN, _PHONE_PATTERN, _EMAIL_PATTERN  # or inline

logger = logging.getLogger(__name__)


class PIISafeADKWrapper:
    """LGPD-compliant wrapper for all google-adk invocations.

    Mirrors PIISafeAgent API shape for team familiarity.
    Every call through safe_run() guarantees:
    - PII sanitization before ADK/Gemini receives input
    - Output scan for PII leakage
    - Structured latency logging
    """

    async def safe_run(self, prompt: str, deps: AIDeps, *, operation: str) -> Any:
        try:
            safe_prompt = sanitize_prompt_text_for_external_ai(prompt)
        except Exception as exc:
            raise RuntimeError(
                f"PII sanitization failed for {operation} -- blocking ADK call"
            ) from exc

        input_hash = hashlib.sha256(safe_prompt.encode("utf-8")).hexdigest()[:12]
        start = time.monotonic()
        logger.info(
            "ADK call started",
            extra={"operation": operation, "input_hash": input_hash},
        )

        try:
            result = await self._invoke_adk(safe_prompt, deps)
        except Exception as exc:
            latency_ms = round((time.monotonic() - start) * 1000)
            logger.error(
                "ADK call failed",
                extra={
                    "operation": operation,
                    "input_hash": input_hash,
                    "latency_ms": latency_ms,
                    "success": False,
                    "error_type": type(exc).__name__,
                },
            )
            raise

        latency_ms = round((time.monotonic() - start) * 1000)
        logger.info(
            "ADK call completed",
            extra={
                "operation": operation,
                "input_hash": input_hash,
                "latency_ms": latency_ms,
                "success": True,
            },
        )
        self._warn_on_output_pii(str(result), operation=operation)
        return result

    async def _invoke_adk(self, safe_prompt: str, deps: AIDeps) -> Any:
        """Override in subclasses with actual ADK runner invocation."""
        raise NotImplementedError

    def _warn_on_output_pii(self, output_text: str, *, operation: str) -> None:
        """Scan output for PII leakage — warn do not block (LGPD best effort)."""
        import re
        _CPF = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")
        _PHONE = re.compile(r"\+?55\s?\(?\d{2}\)?\s?\d{4,5}[-\s]?\d{4}")
        _EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        for pii_type, pattern in (("cpf", _CPF), ("phone", _PHONE), ("email", _EMAIL)):
            if pattern.search(output_text):
                logger.warning(
                    "PII detected in ADK output",
                    extra={"operation": operation, "pii_type": pii_type},
                )
```

### Pattern 3: CI Guard Extension (for ADK call patterns)
**What:** Extend regex-based static analysis in `check_agent_run_calls.py` to also catch direct ADK invocations
**When to use:** Any runner.run_async() or runner.run() call outside PIISafeADKWrapper
**Example:**
```python
# Source: extends app/scripts/check_agent_run_calls.py

# Existing pattern (pydantic-ai):
RUN_CALL_PATTERN = re.compile(
    r"\b\w*agent\b\.run(?:_sync|_stream)?\s*\(",
    flags=re.IGNORECASE,
)

# New ADK pattern to add:
ADK_RUN_PATTERN = re.compile(
    r"\brunner\b\.run(?:_async)?\s*\(",
    flags=re.IGNORECASE,
)

# Exemption list update:
EXEMPT_FILES = {
    "app/ai/agents/base.py",    # existing PIISafeAgent
    "app/ai/adk/wrapper.py",    # new PIISafeADKWrapper
}

def _is_exempt(path: Path) -> bool:
    return any(path.as_posix().endswith(f) for f in EXEMPT_FILES)
```

### Pattern 4: CeleryIntegration Addition to Sentry
**What:** Add CeleryIntegration explicitly to sentry.py so Celery worker transactions appear in Sentry
**When to use:** During Sentry verification task — it is currently missing from setup_sentry()
**Example:**
```python
# Source: https://docs.sentry.io/platforms/python/integrations/celery/
# app/core/setup/sentry.py — ADD these lines

from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init(
    dsn=sentry_dsn,
    environment=environment,
    traces_sample_rate=traces_sample_rate,
    profiles_sample_rate=0.1,
    integrations=[
        FastApiIntegration(transaction_style="endpoint"),
        SqlalchemyIntegration(),
        RedisIntegration(),
        CeleryIntegration(monitor_beat_tasks=True),  # ADD THIS
    ],
    send_default_pii=False,
    release="hormonia-backend@2.0.0",
    before_send=_sentry_before_send,
)
```

### Anti-Patterns to Avoid
- **Tombstoning before cleaning callers:** Always clean callers first, then tombstone — reversed order causes startup crash
- **Using before_model_callback for PII:** Known bug in ADK (Issue #4464) — Plugin callbacks not invoked by InMemoryRunner; use call-site wrapper instead
- **Keeping any OTel package while adding ADK:** ADK 1.26.0 requires opentelemetry-api>=1.36.0,<1.39.0; project's current constraint (>=1.28.0,<2.0.0) overlaps but combined with instrumentation packages creates resolution noise — remove all project OTel packages, let ADK own its OTel subtree
- **Touching protobuf pin during OTel removal:** The current `protobuf>=5.0,<7.0.0` pin was added for OTel-proto; after removing OTel, verify protobuf pin is still valid for google-adk's transitive deps before removing it

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PII regex patterns | New regex from scratch | Import from `app/ai/pii_redaction.py` (CPF, phone, email patterns already proven) | Duplication risk; existing patterns handle Brazilian PII edge cases |
| venv-based dry-run | Custom subprocess orchestration | `python -m venv /tmp/adk-test-venv && /tmp/adk-test-venv/bin/pip install --dry-run google-adk pydantic-ai-slim[google,retries]` | Shell one-liner is sufficient; no wrapper needed |
| Custom tracing fallback | New no-op tracer | Remove the tracer entirely — callers don't call any methods on self.tracer beyond `.setup()` and none in unified_whatsapp_service.py at all | Zero actual usage means zero replacement needed |
| Output PII scanning | New scanning library | Reuse `_warn_on_output_pii` pattern from PIISafeAgent verbatim | Pattern is proven; copy or inherit |

**Key insight:** The existing `app/ai/agents/base.py` PIISafeAgent is the exact template. PIISafeADKWrapper is a structural copy with `self._agent.run()` replaced by `self._invoke_adk()`. No novel design needed.

## Common Pitfalls

### Pitfall 1: Caller Cleanup Order
**What goes wrong:** Tombstoning tracing.py before cleaning message_service.py and unified_whatsapp_service.py causes `ImportError` at service instantiation time — production crash if deployed
**Why it happens:** tracing.py has 2 active importers; tombstone raises ImportError immediately
**How to avoid:** Clean callers first (remove import + self.tracer assignment + @trace decorator), confirm tests pass, then tombstone
**Warning signs:** Any import of `app.core.tracing` remaining when tombstone is applied

### Pitfall 2: ADK OTel Version Range Conflict
**What goes wrong:** Installing google-adk 1.26.0 alongside the current project OTel packages forces pip into an impossible resolution (project pins 1.28-2.0, ADK requires 1.36-1.39; technically overlapping but instrumentation sub-packages add additional sub-constraints)
**Why it happens:** ADK 1.26.0 depends on: opentelemetry-api>=1.36.0,<1.39.0; opentelemetry-sdk>=1.36.0,<1.39.0; opentelemetry-exporter-otlp-proto-http>=1.36.0; plus its own gcp exporters — these are incompatible with the project's current instrumentation packages
**How to avoid:** Remove all 9 project OTel packages first, then add google-adk — the dry-run gate in Task 1 confirms this
**Warning signs:** `pip check` failing after ADK install; ResolutionImpossible errors during pip

### Pitfall 3: protobuf Pin After OTel Removal
**What goes wrong:** `protobuf>=5.0,<7.0.0` was added specifically for `opentelemetry-proto>=1.28.0` (line 131 in requirements.txt). After removing OTel packages, this pin may be unnecessary or wrong for google-adk's transitive deps
**Why it happens:** Protobuf version requirements come from multiple Google packages; removing OTel changes the constraint graph
**How to avoid:** In dry-run task, check what protobuf version google-adk resolves to via `pip install --dry-run --report -` — verify the pin still applies
**Warning signs:** pip resolution warnings about protobuf after changes

### Pitfall 4: CeleryIntegration Not Auto-Installing in Workers
**What goes wrong:** Assuming CeleryIntegration auto-installs when `sentry_sdk.init()` is called — Sentry docs say it auto-installs "if celery package is in your dependencies" but this only works when `sentry_sdk.init()` is called at worker startup, not just in the module where tasks are defined
**Why it happens:** Celery workers may import task modules before sentry_sdk.init() runs
**How to avoid:** Add `CeleryIntegration(monitor_beat_tasks=True)` explicitly to the integrations list in `setup_sentry()`; ensure `setup_sentry()` is called in the Celery app init path
**Warning signs:** Celery tasks not appearing as transactions in Sentry Performance dashboard

### Pitfall 5: @trace Decorator Leaving Dead Reference
**What goes wrong:** Removing `from app.core.tracing import get_tracer, trace` import but leaving `@trace(...)` decorator in message_service.py line 574
**Why it happens:** The decorator and the get_tracer() call are on different lines; partial cleanup is easy to miss
**How to avoid:** Search for ALL uses: `grep -n "get_tracer\|@trace\|self.tracer" message_service.py` — confirm all 3 lines removed
**Warning signs:** `NameError: name 'trace' is not defined` at startup

### Pitfall 6: before_model_callback Not Firing in InMemoryRunner
**What goes wrong:** Using ADK's before_model_callback hook for PII sanitization instead of call-site wrapping — callbacks are not invoked by InMemoryRunner (ADK Issue #4464, confirmed open)
**Why it happens:** Plugin callbacks have a known bug in ADK; only direct agent callbacks work
**How to avoid:** Use call-site wrapper pattern (PIISafeADKWrapper.safe_run()) — guaranteed to run regardless of runner type
**Warning signs:** PII test passing in integration but not in unit tests using InMemoryRunner

## Code Examples

Verified patterns from official sources and codebase:

### Caller Cleanup: message_service.py (BEFORE vs AFTER)
```python
# BEFORE (lines 26, 314, 574):
from app.core.tracing import get_tracer, trace   # REMOVE
self.tracer = get_tracer()                       # REMOVE
@trace(name="send_message_impl", attributes={"service": "wuzapi"})  # REMOVE decorator only

# AFTER:
# Line 26: deleted
# Line 314: self.tracer = get_tracer() deleted
# Line 574: @trace(...) deleted, _send_message_impl() definition kept as-is
```

### Caller Cleanup: unified_whatsapp_service.py (BEFORE vs AFTER)
```python
# BEFORE (lines 51, 142):
from app.core.tracing import get_tracer   # REMOVE
self.tracer = get_tracer()               # REMOVE

# AFTER:
# Both lines deleted; no other tracing references in this file
```

### Dry-Run pip Install Validation
```bash
# Source: pip documentation — standard dry-run pattern
# Step 1: Create clean venv
python3.13 -m venv /tmp/adk-test-venv

# Step 2: Dry-run install (check resolution without installing)
/tmp/adk-test-venv/bin/pip install \
  "google-adk>=1.26.0,<2.0.0" \
  "pydantic-ai-slim[google,retries]>=1.63.0,<2.0.0" \
  --dry-run 2>&1

# Step 3: Full install to capture resolved versions
/tmp/adk-test-venv/bin/pip install \
  "google-adk>=1.26.0,<2.0.0" \
  "pydantic-ai-slim[google,retries]>=1.63.0,<2.0.0" && \
  /tmp/adk-test-venv/bin/pip list | grep -E "google-adk|opentelemetry|protobuf|pydantic"

# Step 4: Final check
/tmp/adk-test-venv/bin/pip check
```

### ADK FunctionTool — simplest form
```python
# Source: https://google.github.io/adk-docs/tools-custom/function-tools/
# Python ADK: plain function passed in tools list is auto-wrapped as FunctionTool

from google.adk.agents import LlmAgent

def my_tool_function(param: str) -> dict:
    """Tool docstring — ADK uses this for schema generation.

    Args:
        param: description of parameter

    Returns:
        dict with result
    """
    return {"result": param}

agent = LlmAgent(
    model="gemini-2.0-flash",
    tools=[my_tool_function],  # auto-wrapped
)
```

### ADK Runner — programmatic invocation
```python
# Source: ADK quickstart docs
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

agent = LlmAgent(model="gemini-2.0-flash", tools=[...])
session_service = InMemorySessionService()
runner = Runner(agent=agent, app_name="my_app", session_service=session_service)

# async invocation pattern:
async for event in runner.run_async(
    user_id="user123",
    session_id="session456",
    new_message=types.Content(role="user", parts=[types.Part(text="prompt")])
):
    # process events
    pass
```

### CI Guard Failing Fixture Pattern
```python
# Source: project test pattern for guard scripts
# tests/test_ci_guards.py (or similar)

import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

def test_adk_direct_call_blocked(tmp_path):
    """Guard must reject direct runner.run_async() outside PIISafeADKWrapper."""
    bad_file = tmp_path / "app" / "bad_module.py"
    bad_file.parent.mkdir(parents=True)
    bad_file.write_text(textwrap.dedent("""
        # Simulated violation: direct ADK runner call
        result = await runner.run_async(user_id="u", session_id="s", new_message=msg)
    """))

    result = subprocess.run(
        [sys.executable, "scripts/check_agent_run_calls.py"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 1, "Guard should have rejected direct runner.run_async() call"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| OTel instrumentation packages for distributed tracing | Sentry SDK with FastApiIntegration + CeleryIntegration | Phase 40 (now) | No functional regression — Sentry auto-instruments FastAPI/Celery paths; removes 9 packages and pip conflict |
| before_model_callback for ADK PII guard | Call-site wrapper (PIISafeADKWrapper) | Phase 40 (now) | Callback approach unreliable with InMemoryRunner (ADK bug #4464); wrapper is 100% reliable |
| google-adk blocked (dep conflict) | google-adk installed cleanly | Phase 40 (now) | Enables Phase 41 (ADK wiring) and eventually Phase 41 ADK tool wrapping |

**Deprecated/outdated:**
- `app/core/tracing.py`: Entire file tombstoned. `DistributedTracer`, `TracingConfig`, `get_tracer()`, `setup_tracing()`, `trace()`, `trace_context()`, `trace_context_async()` all dead after this phase
- `opentelemetry-*` (all 9 packages): Removed; ADK brings its own OTel >=1.36 tree as transitive deps

## Open Questions

1. **protobuf pin validity after OTel removal**
   - What we know: `protobuf>=5.0,<7.0.0` was pinned for `opentelemetry-proto` (line 131 of requirements.txt comment says so). google-adk doesn't list protobuf as a direct dep but uses it transitively via google-genai and gcp exporters.
   - What's unclear: Exact protobuf version google-adk 1.26.0 resolves to in Python 3.13 without the project OTel packages present
   - Recommendation: The dry-run pip install task captures this — check `pip list | grep protobuf` in the clean venv; if the pin is still needed keep it, if google-adk pulls a different range update accordingly

2. **ADK Runner call patterns to block in CI guard**
   - What we know: ADK uses `runner.run_async()` for async invocation. There may also be `runner.run()` synchronous variants.
   - What's unclear: Full ADK 1.26.0 Runner API surface — are there other direct-call patterns (e.g., `agent.run()` which conflicts with existing pydantic-ai guard)?
   - Recommendation: Claude's Discretion as locked — inspect `google.adk.runners.Runner` source at install time; likely `runner.run_async`, `runner.run`, plus possibly `agent.generate_content` direct calls

3. **ADK and `pydantic-ai-slim` coexistence on pydantic version**
   - What we know: ADK 1.26.0 requires `pydantic>=2.12.0,<3.0.0`; project already pins `pydantic>=2.12.5,<3.0.0` — these are compatible
   - What's unclear: Whether pydantic-ai-slim 1.63+ has any pydantic constraints that conflict with ADK's pydantic requirement
   - Recommendation: Confirmed by dry-run; low risk given both use pydantic >=2.12

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — `backend-hormonia/requirements.txt` lines 116-134 (OTel block), `app/core/tracing.py` (full file), `app/core/setup/sentry.py` (full file), `app/ai/agents/base.py` (PIISafeAgent), `app/ai/pii_redaction.py`, `scripts/check_agent_run_calls.py`
- google/adk-python pyproject.toml (fetched) — opentelemetry-api>=1.36.0,<1.39.0; pydantic>=2.12.0,<3.0.0; google-genai>=1.56.0,<2.0.0
- https://pypi.org/project/google-adk/ — version 1.26.0 confirmed, Python >=3.10 including 3.13
- https://docs.sentry.io/platforms/python/integrations/celery/ — CeleryIntegration import and configuration
- https://google.github.io/adk-docs/tools-custom/function-tools/ — FunctionTool pattern (plain function in tools=[])
- https://google.github.io/adk-docs/callbacks/types-of-callbacks/ — before_model_callback signature and capabilities

### Secondary (MEDIUM confidence)
- https://github.com/google/adk-python/releases — release dates and 1.26.0 changelog verified
- ADK Issue #4464 (referenced in WebSearch results): Plugin callbacks not invoked by InMemoryRunner — confirms call-site wrapper is safer than before_model_callback

### Tertiary (LOW confidence)
- WebSearch results on pip conflict patterns between OTel versions and google-adk — corroborates the conflict analysis, not independently verified against live pip resolution in this exact environment

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — ADK 1.26.0 confirmed as latest; pydantic-ai-slim already installed; Sentry already installed
- OTel removal scope: HIGH — 9 packages confirmed by inspection of requirements.txt; 2 callers confirmed by grep; self.tracer never called confirmed by grep
- Architecture (PIISafeADKWrapper): HIGH — mirrors PIISafeAgent exactly, pattern verified in codebase
- ADK Runner API: MEDIUM — confirmed from docs; exact call patterns to block in CI guard need ADK source inspection at install time
- Protobuf pin impact: MEDIUM — logic is sound but exact resolved version needs dry-run confirmation
- Pitfalls: HIGH — all pitfalls verified against actual code (callers, decorator usage, sentry.py missing CeleryIntegration)

**Research date:** 2026-03-03
**Valid until:** 2026-04-03 (ADK releases weekly; recheck if using a version other than 1.26.0)
