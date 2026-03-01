---
phase: 04-ai-reliability
plan: "02"
subsystem: ai
tags: [langgraph, sentry, error-handling, gemini, fallback]

# Dependency graph
requires:
  - phase: 04-01
    provides: FeatureNotAvailableError exception class in app.core.exceptions

provides:
  - centralized invoke_langgraph_graph() wrapper (app/ai/langgraph/_invoke.py)
  - explicit FeatureNotAvailableError on empty LangGraph output (4 methods in client_domain.py)
  - Sentry capture + structured fallback for humanization and sentiment failures in enhanced_flow_engine.py
  - elimination of silent confidence=0.5 neutral sentiment fallback

affects:
  - 05-async-migration
  - 08-ai-rationalization
  - any phase touching LangGraph call sites

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "invoke_langgraph_graph() wrapper: single invocation point replacing per-site ainvoke+None-check pattern"
    - "FeatureNotAvailableError catch + sentry_sdk.capture_exception before fallback branch"
    - "confidence=0.0 signals fallback sentiment (not real analysis); confidence>threshold checks work correctly"

key-files:
  created:
    - backend-hormonia/app/ai/langgraph/_invoke.py
  modified:
    - backend-hormonia/app/ai/langgraph/__init__.py
    - backend-hormonia/app/ai/client_domain.py
    - backend-hormonia/app/services/enhanced_flow_engine.py

key-decisions:
  - "AI-02: invoke_langgraph_graph() wrapper centralizes None validation — expect_dict=True for sentiment (dict), False for strings"
  - "AI-02: humanization fallback uses message_template.base_content (unhumanized but informative) — patient always receives a message"
  - "AI-02: sentiment fallback uses confidence=0.0 (not 0.5) so downstream threshold checks correctly treat it as low-confidence"
  - "AI-02: sentry_sdk.capture_exception before fallback branch in enhanced_flow_engine.py — every AI failure visible in dashboards"

patterns-established:
  - "Wrapper pattern: invoke_langgraph_graph() is the sole way to call any compiled LangGraph graph; no bare graph.ainvoke() allowed"
  - "Sentry-first fallback: capture exception before taking fallback path, never silently absorb AI failures"

requirements-completed: [AI-02]

# Metrics
duration: 2min
completed: 2026-02-22
---

# Phase 4 Plan 02: LangGraph None-Fallback Elimination Summary

**Centralized `invoke_langgraph_graph()` wrapper replaces 6 bare `graph.ainvoke()` call sites with explicit `FeatureNotAvailableError`, Sentry capture, and structured fallbacks — eliminating silent AI degradation**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-22T21:08:11Z
- **Completed:** 2026-02-22T21:10:20Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created `_invoke.py` with `invoke_langgraph_graph()` that raises `FeatureNotAvailableError` on empty/invalid output — supports both string and dict output validation via `expect_dict` flag
- Replaced all 4 bare `graph.ainvoke()` patterns in `client_domain.py` — `humanize_flow_message`, `generate_varied_question`, `analyze_response_sentiment`, `create_empathetic_follow_up`
- Replaced 2 bare `graph.ainvoke()` patterns in `enhanced_flow_engine.py` with try/except blocks that capture to Sentry before taking fallback — humanization falls back to `message_template.base_content`, sentiment falls back to `confidence=0.0`
- Eliminated the silent `{"sentiment": "neutral", "confidence": 0.5}` fallback — replaced with explicit error path at `confidence=0.0`

## Task Commits

Each task was committed atomically:

1. **Task 1: Create centralized LangGraph invocation wrapper** - `9e4da3a9` (feat)
2. **Task 2: Replace bare ainvoke calls with wrapper in client_domain.py and enhanced_flow_engine.py** - `ffb6928c` (feat)

**Plan metadata:** (docs commit — recorded below after state update)

## Files Created/Modified
- `backend-hormonia/app/ai/langgraph/_invoke.py` - New centralized wrapper; `invoke_langgraph_graph()` with expect_dict support
- `backend-hormonia/app/ai/langgraph/__init__.py` - Re-exports `invoke_langgraph_graph` via `from ._invoke import invoke_langgraph_graph`
- `backend-hormonia/app/ai/client_domain.py` - 4 call sites replaced; `GeminiAPIError` empty-output raises eliminated (wrapper raises `FeatureNotAvailableError`)
- `backend-hormonia/app/services/enhanced_flow_engine.py` - 2 call sites replaced; `sentry_sdk` + `FeatureNotAvailableError` imports added; both failure paths now captured to Sentry before fallback

## Decisions Made
- `invoke_langgraph_graph()` uses deferred import of `FeatureNotAvailableError` (inside function body) to avoid circular import risk at module load time
- `expect_dict=True` for sentiment analysis call site — validates `isinstance(output, dict) and output` rather than simple truthiness check
- Humanization fallback: `message_template.base_content` (unhumanized but complete template) — patient always receives the clinical information
- Sentiment fallback: `confidence=0.0` not `0.5` — downstream logic using `confidence > threshold` correctly skips low-confidence fallback values; `0.5` would have been interpreted as real analysis

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 04 complete (2/2 plans done) — AI Reliability requirements AI-01 and AI-02 satisfied
- LangGraph invocation is now fully instrumented; any future graph failures will appear in Sentry with graph_name and operation context
- Phase 05 (Async Migration) can proceed — enhanced_flow_engine.py is now cleaner with explicit error paths

---
*Phase: 04-ai-reliability*
*Completed: 2026-02-22*

## Self-Check: PASSED

All files exist and all commits verified:
- FOUND: `backend-hormonia/app/ai/langgraph/_invoke.py`
- FOUND: `backend-hormonia/app/ai/langgraph/__init__.py`
- FOUND: `backend-hormonia/app/ai/client_domain.py`
- FOUND: `backend-hormonia/app/services/enhanced_flow_engine.py`
- FOUND commit `9e4da3a9`: feat(04-02): create centralized LangGraph invocation wrapper
- FOUND commit `ffb6928c`: feat(04-02): replace bare ainvoke calls with centralized wrapper
