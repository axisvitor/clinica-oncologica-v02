---
phase: 13-sdk-migration-cleanup
plan: 04
subsystem: ai
tags: [pydantic-ai, celery, sync-bridge, domain-client]
requires:
  - phase: 13-sdk-migration-cleanup
    provides: PIISafeAgent._safe_run_sync wrapper and async domain client methods from prior plans
provides:
  - Public sync methods on all four pydantic-ai wrappers using _safe_run_sync
  - GeminiDomainClient sync APIs for humanize, variation, sentiment, and empathy flows
  - Unit tests proving sync delegation and async-path compatibility
affects: [celery-ai-call-chain, sdk-03-gap-closure, domain-client-callers]
tech-stack:
  added: []
  patterns: [dual async+sync agent API surface, sync domain delegation via _build_ai_deps]
key-files:
  created:
    - backend-hormonia/tests/unit/ai/test_agent_sync_methods.py
  modified:
    - backend-hormonia/app/ai/agents/humanize_agent.py
    - backend-hormonia/app/ai/agents/variation_agent.py
    - backend-hormonia/app/ai/agents/sentiment_agent.py
    - backend-hormonia/app/ai/agents/empathy_agent.py
    - backend-hormonia/app/ai/client_domain.py
key-decisions:
  - "Reuse existing prompt construction and post-processing paths in sync methods to keep output behavior aligned with async methods."
  - "Expose explicit sync APIs on GeminiDomainClient without adding new settings or framework toggles."
patterns-established:
  - "Agent wrappers offer paired async and sync entrypoints with identical signatures and contracts."
  - "Sentiment sync results stay backward-compatible by returning model_dump() dictionaries at the domain layer."
requirements-completed: [SDK-03]
duration: 7 min
completed: 2026-02-24
---

# Phase 13 Plan 04: Sync API Surface Summary

**All four AI operations now expose explicit run_sync-backed agent and domain entrypoints so Celery paths can call synchronous APIs directly while FastAPI async paths remain unchanged.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-24T19:51:39Z
- **Completed:** 2026-02-24T19:59:26Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Added `humanize_sync`, `vary_sync`, `analyze_sync`, and `follow_up_sync` methods to the four pydantic-ai agent wrappers using `_safe_run_sync`.
- Added `humanize_flow_message_sync`, `generate_varied_question_sync`, `analyze_response_sentiment_sync`, and `create_empathetic_follow_up_sync` to `GeminiDomainClient` with unchanged async methods.
- Added focused unit tests that validate sync delegation, sentiment dict output shape, and async-path compatibility.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add public sync methods to all four pydantic-ai agent wrappers** - `770d6d05` (feat)
2. **Task 2: Expose GeminiDomainClient sync methods and add sync-path unit tests** - `dfd205cd` (feat)

## Files Created/Modified
- `backend-hormonia/app/ai/agents/humanize_agent.py` - added `humanize_sync` mirroring async humanize prompt flow.
- `backend-hormonia/app/ai/agents/variation_agent.py` - added `vary_sync` with the same non-repetitive fallback behavior.
- `backend-hormonia/app/ai/agents/sentiment_agent.py` - added `analyze_sync` returning `SentimentResult` through `_safe_run_sync`.
- `backend-hormonia/app/ai/agents/empathy_agent.py` - added `follow_up_sync` with existing compacted-context prompt assembly.
- `backend-hormonia/app/ai/client_domain.py` - added four sync domain methods that build deps and delegate to agent sync methods.
- `backend-hormonia/tests/unit/ai/test_agent_sync_methods.py` - new tests for sync delegation, sentiment dict keys, and unchanged async behavior.

## Decisions Made
- Reused each agent's existing prompt helper path inside sync methods to avoid behavior drift between async and sync execution.
- Kept GeminiDomainClient async methods intact and added separate sync methods instead of introducing mode toggles.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Sync APIs now exist on agents and domain client, enabling direct Celery task chain rewiring in the next plan.
- Unit verification is in place for sync/async API compatibility and can be reused during final regression checks.

## Self-Check: PASSED
- Confirmed summary file exists on disk.
- Confirmed task commits `770d6d05` and `dfd205cd` exist in git history.

---
*Phase: 13-sdk-migration-cleanup*
*Completed: 2026-02-24*
