---
phase: 12-flow-orchestration-replacement
plan: 01
subsystem: api
tags: [flow, langgraph, feature-flag, imports, lifecycle]
requires:
  - phase: 11-agent-implementation
    provides: pydantic-ai helper shim surface and AI_FRAMEWORK compatibility layer
provides:
  - Direct async flow function orchestration path for message and response handling
  - AI_FLOW_FRAMEWORK runtime toggle to switch legacy vs direct flow execution
  - Centralized helper import surface for langgraph prompt/node helper consumers
  - Lifespan startup decoupled from langgraph availability check
affects: [12-02-package-removal, 12-03-tombstoning, flow-runtime]
tech-stack:
  added: []
  patterns: [feature-flagged runtime branching, helper-shim import routing, direct node orchestration]
key-files:
  created: [backend-hormonia/app/services/flow/_flow_functions.py]
  modified:
    [
      backend-hormonia/app/services/flow/sequential_message_handler.py,
      backend-hormonia/app/config/settings/integrations.py,
      backend-hormonia/.env.example,
      backend-hormonia/app/ai/agents/helpers.py,
      backend-hormonia/app/ai/client_domain.py,
      backend-hormonia/app/agents/communication/message_composer/composer.py,
      backend-hormonia/app/services/enhanced_flow_engine.py,
      backend-hormonia/app/services/analytics/data_extraction/service.py,
      backend-hormonia/app/services/follow_up_system/generators/empathy.py,
      backend-hormonia/app/services/follow_up_system/generators/response.py,
      backend-hormonia/app/core/lifespan.py,
      backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py,
    ]
key-decisions:
  - "Kept LangGraph legacy path intact and switched to direct functions only when AI_FLOW_FRAMEWORK=direct."
  - "Moved all non-flow direct app.ai.langgraph prompt/node helper imports to app.ai.agents.helpers to isolate tombstoning to one shim."
patterns-established:
  - "Flow branching: gate new execution path with runtime settings read via app.config.settings."
  - "Import indirection: consumer modules use helpers.py as the sole public helper surface."
requirements-completed: [FLOW-01, FLOW-02]
duration: 15 min
completed: 2026-02-24
---

# Phase 12 Plan 01: Flow Orchestration Replacement Summary

**Direct flow node execution behind AI_FLOW_FRAMEWORK with helper-shim import routing and lifespan startup decoupling from LangGraph checks.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-02-24T16:45:00Z
- **Completed:** 2026-02-24T17:00:20Z
- **Tasks:** 2
- **Files modified:** 13

## Accomplishments
- Added `run_flow_message` and `run_flow_response` in `backend-hormonia/app/services/flow/_flow_functions.py` to execute flow nodes directly without graph runtime orchestration.
- Added `AI_FLOW_FRAMEWORK` configuration and wired `SequentialMessageHandler` to call direct functions when set to `direct`, preserving legacy `graph.ainvoke()` behavior by default.
- Redirected all listed direct `app.ai.langgraph.{prompts,nodes_ai}` imports to `app.ai.agents.helpers`, including `_parse_sentiment_analysis` re-export.
- Removed `_check_langgraph_available()` and its startup invocation from `backend-hormonia/app/core/lifespan.py`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create direct flow functions and feature-flagged sequential handler path** - `e2d67079` (feat)
2. **Task 2: Redirect direct langgraph helper imports and remove lifespan langgraph gate** - `b4c2a0f9` (refactor)

## Files Created/Modified
- `backend-hormonia/app/services/flow/_flow_functions.py` - Direct async wrappers that execute flow node sequence for message and response handling.
- `backend-hormonia/app/services/flow/sequential_message_handler.py` - Feature-flag branch for direct functions while preserving legacy graph path.
- `backend-hormonia/app/config/settings/integrations.py` - `AI_FLOW_FRAMEWORK` setting with legacy default.
- `backend-hormonia/.env.example` - `AI_FLOW_FRAMEWORK` example toggle.
- `backend-hormonia/app/ai/agents/helpers.py` - Added `_parse_sentiment_analysis` export.
- `backend-hormonia/app/ai/client_domain.py` - Repointed prompt/node helper imports to helper shim.
- `backend-hormonia/app/agents/communication/message_composer/composer.py` - Repointed helper imports to shim.
- `backend-hormonia/app/services/enhanced_flow_engine.py` - Repointed helper imports to shim.
- `backend-hormonia/app/services/analytics/data_extraction/service.py` - Repointed helper imports to shim.
- `backend-hormonia/app/services/follow_up_system/generators/empathy.py` - Repointed empathetic prompt import to shim.
- `backend-hormonia/app/services/follow_up_system/generators/response.py` - Repointed empathetic prompt import to shim.
- `backend-hormonia/app/core/lifespan.py` - Removed langgraph availability startup check.
- `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py` - Added direct-path tests and fixed async db mock behavior.

## Decisions Made
- Kept direct execution path additive and runtime-toggled, so production behavior remains legacy until explicit opt-in.
- Preserved top-level legacy flow imports in `sequential_message_handler.py` per plan scope, deferring tombstoning to 12-03.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed async DB mock awaiting failure in sequential handler unit tests**
- **Found during:** Task 1 verification
- **Issue:** `mock_db.commit` / `mock_db.rollback` were `MagicMock`, causing `TypeError` when awaited in async flow progress code.
- **Fix:** Changed both to `AsyncMock` in test fixture.
- **Files modified:** `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py`
- **Verification:** `python3 -m pytest tests/unit/services/flow/test_sequential_message_handler.py -x -q`
- **Committed in:** `e2d67079` (part of Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Required for test stability and did not change runtime behavior scope.

## Issues Encountered
- Direct import verification of `app.ai.agents.helpers` via package path required unavailable `pydantic_ai` runtime in this environment; verified exports by executing `helpers.py` directly with `runpy` instead.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 12-01 outputs are in place for package removal/tombstoning in 12-02 and 12-03.
- Legacy and direct flow orchestration paths are both available behind explicit runtime selection.

---
*Phase: 12-flow-orchestration-replacement*
*Completed: 2026-02-24*

## Self-Check: PASSED

- FOUND: `.planning/phases/12-flow-orchestration-replacement/12-01-SUMMARY.md`
- FOUND: `e2d67079`
- FOUND: `b4c2a0f9`
