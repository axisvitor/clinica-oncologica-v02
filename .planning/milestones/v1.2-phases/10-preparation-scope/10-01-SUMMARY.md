---
phase: 10-preparation-scope
plan: 01
subsystem: infra
tags: [langgraph, langchain, pydantic-ai, gemini, migration]
requires:
  - phase: 10-preparation-scope
    provides: v1.2 migration direction and dependency decisions
provides:
  - LANGGRAPH_AUDIT env-gated import scanner in app/main.py
  - pydantic-ai-slim dependency pinned for migration coexistence
affects: [phase-11-agent-migration, phase-12-langgraph-removal]
tech-stack:
  added: [pydantic-ai-slim[google,retries]]
  patterns: [env-gated static import auditing, staged framework coexistence]
key-files:
  created: [.planning/phases/10-preparation-scope/10-01-SUMMARY.md]
  modified: [backend-hormonia/app/main.py, backend-hormonia/requirements.txt]
key-decisions:
  - "Keep LangGraph and pydantic-ai-slim coexisting during migration phases 10-12."
  - "Pin pydantic-ai-slim below 2.0.0 to avoid planned April 2026 breaking changes."
patterns-established:
  - "Audit Pattern: Use AST scanning under env flag to map import touchpoints with zero default runtime cost."
  - "Dependency Pattern: Add migration framework dependency without removing incumbent framework until replacement is complete."
requirements-completed: [PREP-01, PREP-02]
duration: 4 min
completed: 2026-02-24
---

# Phase 10 Plan 01: Preparation Scope Summary

**Env-gated AST import audit and pydantic-ai-slim dependency baseline were added to enable safe, traceable LangGraph-to-pydantic-ai migration.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-24T00:27:14-03:00
- **Completed:** 2026-02-24T03:31:47Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `LANGGRAPH_AUDIT` scanner in `backend-hormonia/app/main.py` using `ast.parse` + `ast.walk` over `app/**/*.py`.
- Extended audit matching to direct and indirect imports (`langgraph`, `langchain_core`, `langchain_google_genai`, `app.ai.langgraph`) with sorted deduplicated output.
- Installed and validated `pydantic-ai-slim[google,retries]>=1.63.0,<2.0.0` in project virtualenv and declared it in `backend-hormonia/requirements.txt`.
- Verified `from pydantic_ai import Agent` import and `pip check` pass with no dependency conflicts.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add LANGGRAPH_AUDIT env-gated import scanner to app/main.py** - `86d9569f` (feat)
2. **Task 2: Install pydantic-ai-slim and update requirements.txt** - `61f9fd28` (chore)

## Files Created/Modified
- `backend-hormonia/app/main.py` - Added env-gated AST import audit hook for LangGraph/LangChain migration mapping.
- `backend-hormonia/requirements.txt` - Added pydantic-ai-slim dependency block with migration rationale and version pin.
- `.planning/phases/10-preparation-scope/10-01-SUMMARY.md` - Execution summary and traceability metadata.

## Decisions Made
- Kept LangGraph dependencies in place while introducing pydantic-ai-slim for phased coexistence during migration.
- Standardized dependency pin to `<2.0.0` for pydantic-ai-slim to avoid unplanned v2 API breakage during v1.2 rollout.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Python executable mismatch in local shell**
- **Found during:** Task 1 verification
- **Issue:** `python` command was unavailable in shell (`python: command not found`), blocking required verification commands.
- **Fix:** Used project virtualenv binaries (`.venv/bin/python`, `.venv/bin/pip`) for all execution and verification steps.
- **Files modified:** None
- **Verification:** Audit hook output, pydantic-ai import, and pip checks all succeeded via virtualenv binaries.
- **Committed in:** N/A (execution environment adaptation only)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No scope creep; adaptation was execution-only and preserved all planned deliverables.

## Authentication Gates
None.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Import touchpoints are now machine-auditable with a deterministic command (`LANGGRAPH_AUDIT=1 .venv/bin/python -c "import app.main"`).
- pydantic-ai-slim baseline is installed and pinned; next migration plans can implement agent replacements without dependency bootstrap work.

---
*Phase: 10-preparation-scope*
*Completed: 2026-02-24*

## Self-Check: PASSED

- FOUND: `.planning/phases/10-preparation-scope/10-01-SUMMARY.md`
- FOUND: `86d9569f`
- FOUND: `61f9fd28`
