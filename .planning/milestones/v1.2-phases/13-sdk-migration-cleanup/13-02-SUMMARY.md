---
phase: 13-sdk-migration-cleanup
plan: 02
subsystem: ai
tags: [pydantic-ai, langchain-removal, flow-cleanup, ci-guard]
requires:
  - phase: 13-sdk-migration-cleanup
    provides: google-genai SDK migration baseline from plan 13-01
provides:
  - GeminiDomainClient hard-cut to unconditional pydantic-ai delegation
  - Removal of AI framework toggles from runtime settings and env template
  - Permanent AST-based CI guard preventing LangChain import reintroduction
affects: [13-03-celery-bridge, ai-runtime, ci-regressions]
tech-stack:
  added: []
  patterns: [no-toggle agent path, direct flow-only orchestration, AST import regression gate]
key-files:
  created:
    - backend-hormonia/tests/no_langchain_imports.py
  modified:
    - backend-hormonia/app/ai/client_domain.py
    - backend-hormonia/app/config/settings/integrations.py
    - backend-hormonia/.env.example
    - backend-hormonia/app/services/flow/sequential_message_handler.py
    - backend-hormonia/app/main.py
    - backend-hormonia/tests/validation/detailed_import_analysis.py
    - backend-hormonia/tests/validation/import_analysis_report.json
key-decisions:
  - "Delete AI_FRAMEWORK and AI_FLOW_FRAMEWORK outright instead of deprecating/tombstoning."
  - "Keep only direct flow functions in SequentialMessageHandler and remove all legacy LangGraph branches."
patterns-established:
  - "Guard against LangChain regressions with AST import checks over every app/*.py file."
  - "Domain AI client remains stable at call sites while agent dependencies are built centrally via _build_ai_deps()."
requirements-completed: [SDK-02]
duration: 7 min
completed: 2026-02-24
---

# Phase 13 Plan 02: SDK Migration Cleanup Summary

**LangChain/LangGraph toggles were fully removed from runtime paths, and a permanent CI gate now blocks any LangChain import from re-entering production code.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-24T18:48:42Z
- **Completed:** 2026-02-24T18:56:16Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Collapsed `GeminiDomainClient` to unconditional pydantic-ai agent calls and removed `_use_pydantic_agents` toggle logic.
- Deleted `AI_FRAMEWORK` and `AI_FLOW_FRAMEWORK` from `IntegrationsSettings` and `backend-hormonia/.env.example`.
- Simplified `SequentialMessageHandler` to direct flow execution only, with legacy LangGraph branches and toggle checks removed.
- Cleaned residual LangChain references in startup audit and validation fixtures, then added `tests/no_langchain_imports.py` as permanent AST-based CI protection.

## Task Commits

Each task was committed atomically:

1. **Task 1: Collapse GeminiDomainClient shim and remove feature-flag settings** - `ff17fa93` (feat)
2. **Task 2: Purge remaining langchain references and add permanent CI test** - `2d7d8db4` (test)

**Plan metadata:** `11b29169` (docs)

## Files Created/Modified
- `backend-hormonia/app/ai/client_domain.py` - Removes legacy branching and makes pydantic-ai agent delegation unconditional.
- `backend-hormonia/app/config/settings/integrations.py` - Deletes `AI_FRAMEWORK` and `AI_FLOW_FRAMEWORK` settings.
- `backend-hormonia/.env.example` - Removes framework toggle env vars.
- `backend-hormonia/app/services/flow/sequential_message_handler.py` - Removes legacy flow toggle and LangGraph fallback path.
- `backend-hormonia/app/main.py` - Cleans obsolete LangChain entries from `LANGGRAPH_AUDIT` patterns.
- `backend-hormonia/tests/validation/detailed_import_analysis.py` - Removes obsolete `langchain_*` package entries.
- `backend-hormonia/tests/validation/import_analysis_report.json` - Removes obsolete `langchain_*` report entries.
- `backend-hormonia/tests/no_langchain_imports.py` - Adds permanent AST-based test to fail on LangChain imports under `app/`.

## Decisions Made
- Kept method signatures and public call surfaces intact in `GeminiDomainClient` while removing internals for legacy fallback behavior.
- Retained `LANGGRAPH_AUDIT` block itself but narrowed it to active patterns (`langgraph`, `app.ai.langgraph`) only.

## Deviations from Plan

None - plan executed exactly as written.

## Authentication Gates

None.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 13-03 can focus on Celery bridge/run_sync validation without carrying framework-toggle compatibility logic.
- CI now enforces the zero-LangChain-import contract for production modules under `app/`.

---
*Phase: 13-sdk-migration-cleanup*
*Completed: 2026-02-24*

## Self-Check: PASSED

- FOUND: `.planning/phases/13-sdk-migration-cleanup/13-02-SUMMARY.md`
- FOUND: `ff17fa93`
- FOUND: `2d7d8db4`
