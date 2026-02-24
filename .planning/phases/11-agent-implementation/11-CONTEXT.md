# Phase 11: Agent Implementation - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace 4 direct GeminiClient AI calls (humanize, sentiment, variation, empathy) with typed pydantic-ai agents. Each agent gets mandatory PII redaction via PIISafeAgent base class, reconnected output guardrails via @result_validator decorators, and a GeminiDomainClient shim with AI_FRAMEWORK feature flag so callers (flow_core.py, flow_service.py, enhanced_flow_engine.py) see zero breaking changes.

</domain>

<decisions>
## Implementation Decisions

### Guardrail strictness
- Hard fail (raise exception) when any guardrail check fails -- no silent fallbacks, no swallowed errors
- Each agent declares its own @result_validator decorators (not shared in base class) -- allows agent-specific thresholds (e.g., sentiment needs shorter output than humanize)
- SentimentResult: core fields (sentiment, confidence) are required; optional fields (key_themes, suggested_follow_up, etc.) fill with Pydantic defaults if Gemini omits them
- Downstream alert logic never encounters a KeyError because Pydantic model guarantees all 7 fields are populated

### Feature flag transition
- One global AI_FRAMEWORK environment variable toggles all 4 operations at once
- Lives in .env / Cloud Run env config -- standard pattern for this codebase
- When AI_FRAMEWORK is off (legacy path), log at INFO level that legacy path is active
- GeminiDomainClient shim reads the flag and delegates to either new agents or old direct calls

### PII redaction boundaries
- Use existing `sanitize_prompt_text_for_external_ai()` from `app/ai/pii_redaction.py` as-is -- no modifications
- PIISafeAgent enforces sanitization automatically on every call -- mandatory, no opt-out, no skip_pii flag
- Also scan Gemini OUTPUT for leaked PII before returning to caller (belt-and-suspenders for LGPD)
- If sanitization itself fails/errors, block the agent call entirely -- do NOT call Gemini with unsanitized data

### Agent failure handling
- Gemini timeout/unavailable: retry once with backoff, then raise exception to caller
- Gemini returns bad output (unparseable, wrong structure): use pydantic-ai's built-in validation retry (re-sends with "your output was invalid" hint), one retry, then fail
- 30-second timeout per agent call
- Structured logging on every agent call: operation name, input hash, latency, success/failure, retry count, error type

### Claude's Discretion
- Which specific old guardrails to keep, adjust, or drop -- based on codebase analysis of existing GeminiClient checks
- How long both paths coexist before old direct calls are removed -- based on complexity and maintenance burden assessment
- Exact retry backoff strategy and timing
- Structured log format (JSON, Python logging dict, etc.)

</decisions>

<specifics>
## Specific Ideas

- pydantic-ai's `@result_validator` decorator pattern is the preferred mechanism for guardrails -- not post-processing hooks
- The PIISafeAgent base class is the single enforcement point for LGPD compliance -- all 4 agents MUST inherit from it
- The regression test suite (50 scenarios) compares old GeminiClient output vs new agent output to confirm behavioral parity
- AIDeps dataclass carries shared dependencies (Gemini client config, PII sanitizer, logger) into all agents

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 11-agent-implementation*
*Context gathered: 2026-02-24*
