# Phase 40: OTel Removal & ADK Foundation - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Remove OpenTelemetry instrumentation packages that conflict with google-adk installation, tombstone `app/core/tracing.py`, install ADK cleanly in Python 3.13, and scaffold PIISafeADKWrapper with CI guard — all before any patient data can reach ADK. Sentry transaction integrity verified intact.

</domain>

<decisions>
## Implementation Decisions

### OTel Removal Scope
- Remove all 9 OTel packages from requirements.txt (api, sdk, 4 instrumentations, exporter-otlp, exporter-otlp-proto-http, proto) — ADK manages its own transitive OTel deps
- Remove tracing imports entirely from the 2 callers (message_service.py, unified_whatsapp_service.py) — Sentry auto-instruments these paths already
- Clean tombstone for `app/core/tracing.py`: docstring + `raise ImportError` (consistent with established tombstone pattern) — all callers cleaned first

### ADK Installation Strategy
- Standalone first task: dry-run `pip install` in clean venv validating `google-adk` + `pydantic-ai-slim[google]` coexist in Python 3.13, document resolved versions — only then proceed to modify requirements.txt
- Remove all 9 OTel packages before adding ADK to avoid resolution conflicts

### PIISafeADKWrapper Design
- Call-site wrapper pattern (mirrors PIISafeAgent) — all ADK invocations go through `PIISafeADKWrapper.safe_run()` which sanitizes input, calls ADK, scans output
- Reuse existing `AIDeps` dataclass for runtime model injection (model_name, gemini_api_key) — single config surface for all AI calls
- File location: `app/ai/adk/wrapper.py` in new `app/ai/adk/` package (matches roadmap success criteria path)
- Include output PII scanning (`_warn_on_output_pii`) from day one — full LGPD contract in the wrapper, tested with synthetic PHI input

### CI Guard Extension
- Extend existing `check_agent_run_calls.py` (single script, single CI step) to cover ADK call patterns
- Claude's Discretion: exact ADK patterns to block (determined during implementation based on ADK v1.26.0 API surface)
- Exemption list hardcoded: `app/ai/agents/base.py` (existing) + `app/ai/adk/wrapper.py` (new)
- Failing fixture: pytest test that creates a temp file with direct ADK call, runs the guard, asserts exit code 1

### Sentry Verification
- Code audit + import test: verify sentry.py has zero OTel imports, confirm Sentry init succeeds and produces test transaction
- Add `CeleryIntegration` to `setup_sentry()` (currently missing — needed for Celery transaction capture per success criteria)
- Verification baked into each task (no standalone verification plan)
- `monitoring_config.py` left as-is — separate concern, no OTel references to clean

### Claude's Discretion
- Exact ADK Runner/generate_content call patterns to block in CI guard
- ADK package version pinning strategy (exact pin vs range)
- Temporary venv setup approach for dry-run install validation
- Internal structure of `app/ai/adk/__init__.py` exports

</decisions>

<specifics>
## Specific Ideas

- Tombstone pattern must match existing codebase convention (docstring + `raise ImportError`)
- PIISafeADKWrapper mirrors PIISafeAgent API shape for team familiarity
- Dry-run pip install is a gate — no code changes proceed until dependency resolution is confirmed clean

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/ai/pii_redaction.py`: Mature PII sanitization (prompt/context/history/log) — reused by PIISafeADKWrapper
- `app/ai/agents/base.py` (PIISafeAgent): Pattern template for call-site wrapping with PII scan + structured logging
- `app/ai/agents/deps.py` (AIDeps): Runtime model injection dataclass — reused for ADK wrapper
- `scripts/check_agent_run_calls.py`: CI guard to extend with ADK patterns

### Established Patterns
- Tombstone pattern: docstring + `raise ImportError` (used in 20+ files)
- PIISafeAgent call-site wrapping: `_safe_run()` sanitizes input, calls agent, scans output, logs latency
- CI guard: regex-based static analysis with file-level exemption list

### Integration Points
- `app/core/tracing.py` — tombstoned (callers in message_service.py and unified_whatsapp_service.py cleaned first)
- `app/core/setup/sentry.py` — add CeleryIntegration to integrations list
- `requirements.txt` lines 116-131 — OTel block removed, ADK packages added
- `app/ai/adk/` — new package directory scaffolded

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 40-otel-removal-adk-foundation*
*Context gathered: 2026-03-03*
