# Phase 4: AI Reliability - Context

**Gathered:** 2026-02-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Ensure LangGraph/Gemini failures are visible and explicit -- no silent degradation delivering robotic messages to oncology patients. This phase adds a startup health check (AI-01) and converts silent None fallbacks to explicit FeatureNotAvailableError (AI-02). It does NOT rationalize graph structure (Phase 8) or add circuit breakers (Phase 8).

</domain>

<decisions>
## Implementation Decisions

### Startup behavior
- Startup check verifies connectivity only -- no quota/rate-limit checks at boot
- Claude's discretion: hard fail vs degraded mode, import-only vs API ping, location in lifespan.py vs separate module

### Failure visibility
- Patient never sees AI failure indicators -- failures are purely backend/ops visibility
- Claude's discretion: Sentry error vs warning level, notification channels (Sentry vs Sentry+logging), error detail richness (PII-safe)

### Fallback strategy
- When humanization fails: queue for retry first, then send unhumanized as final fallback
- After retry exhaustion, the raw template message is sent -- patient gets the information, just without humanization
- Claude's discretion: retry count and backoff strategy, per-operation vs uniform fallback across graph types

### Scope of None sweep
- Claude's discretion: all 5 graph types vs production paths only, LangGraph-only vs including direct Gemini calls, new exception class vs reuse existing, centralized wrapper vs per-call-site checks

### Claude's Discretion
- Startup mode (hard fail vs degraded) and health check depth (import vs API ping)
- Health check module location (lifespan.py inline vs separate module)
- Sentry severity level for AI failures (error vs warning)
- Notification approach (Sentry-only vs Sentry + structured logging)
- Error detail richness in FeatureNotAvailableError (graph name + PII-safe context)
- Retry count and backoff timing for failed humanization
- Whether fallback strategy is uniform across all graph types or per-operation
- Which graph types to sweep (all 5 vs active production paths)
- Whether to also cover direct GeminiClient calls or LangGraph-only
- Whether to create new FeatureNotAvailableError or reuse existing exception
- Centralized wrapper vs per-call-site None checks

</decisions>

<specifics>
## Specific Ideas

- Connectivity-only startup check -- quota issues surface at runtime, not at boot
- Queue-then-fallback pattern: retry LangGraph first, send unhumanized only after retry exhaustion
- Backend-only failure visibility -- oncology patients should never see AI failure indicators

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 04-ai-reliability*
*Context gathered: 2026-02-22*
