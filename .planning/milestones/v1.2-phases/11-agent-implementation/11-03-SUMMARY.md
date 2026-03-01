---
phase: 11-agent-implementation
plan: 03
subsystem: ai
tags: [pydantic-ai, guardrails, humanize, variation, empathy]
requires:
  - phase: 11-01
    provides: PIISafeAgent runtime wrapper and AIDeps injection pattern
  - phase: 11-02
    provides: SentimentAgent baseline and per-agent output validator pattern
provides:
  - HumanizeAgent, VariationAgent, and EmpathyAgent modules with per-agent output validators
  - agents.helpers shim that centralizes prompt/node helper imports for Phase 12 tombstoning
  - unified app.ai.agents exports for all agent classes and shared types
affects: [phase-11-shim, phase-12-langgraph-tombstone, ai-safety]
tech-stack:
  added: []
  patterns: [per-agent ModelRetry guardrails, post-call 88-percent overlap fallback, helper re-export shim]
key-files:
  created:
    - backend-hormonia/app/ai/agents/helpers.py
    - backend-hormonia/app/ai/agents/humanize_agent.py
    - backend-hormonia/app/ai/agents/empathy_agent.py
    - backend-hormonia/app/ai/agents/variation_agent.py
  modified:
    - backend-hormonia/app/ai/agents/__init__.py
    - backend-hormonia/app/ai/agents/sentiment_agent.py
key-decisions:
  - "Keep guardrails duplicated as per-agent output_validator decorators using ModelRetry for re-ask behavior."
  - "Place the 88% similarity check after _safe_run in VariationAgent and fallback deterministically instead of validator retry loops."
  - "Use app.ai.agents.helpers as the only import surface to isolate Phase 12 langgraph tombstoning."
patterns-established:
  - "Text agents validate banned patterns, prompt leak markers, length bounds, and ending punctuation with self-repair."
  - "Agent modules consume langgraph prompt/node helpers indirectly through a shim."
requirements-completed: [AGENT-02, AGENT-03, AGENT-04, AGENT-06]
duration: 5 min
completed: 2026-02-24
---

# Phase 11 Plan 03: Text Output Agents Summary

**Humanize, variation, and empathy pydantic-ai agents now ship with per-agent guardrails, PIISafeAgent execution, and a migration-safe helpers shim.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-24T15:03:19Z
- **Completed:** 2026-02-24T15:09:05Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Implemented `HumanizeAgent` and `EmpathyAgent` with `output_type=str`, per-agent validators, and punctuation self-repair behavior.
- Implemented `VariationAgent` with standard text guardrails and post-call overlap handling via `_is_too_similar_to_recent()` plus deterministic fallback.
- Added `app.ai.agents.helpers` re-export shim and routed package exports through `app.ai.agents.__init__` for all four agents.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create helpers.py re-export shim, HumanizeAgent, and EmpathyAgent** - `1ac313e4` (feat)
2. **Task 2: Create VariationAgent with 88% overlap fallback and update __init__.py exports** - `4b97ae0b` (feat)

## Files Created/Modified
- `backend-hormonia/app/ai/agents/helpers.py` - single import shim for prompt builders and node helper functions.
- `backend-hormonia/app/ai/agents/humanize_agent.py` - HumanizeAgent with per-agent `output_validator` and PIISafeAgent execution.
- `backend-hormonia/app/ai/agents/empathy_agent.py` - EmpathyAgent follow-up generation with mirrored text guardrails.
- `backend-hormonia/app/ai/agents/variation_agent.py` - VariationAgent with post-call 88% overlap fallback.
- `backend-hormonia/app/ai/agents/__init__.py` - exports all agent classes and shared dependencies.
- `backend-hormonia/app/ai/agents/sentiment_agent.py` - imports `build_sentiment_prompt` via helpers shim.

## Decisions Made
- Implemented ending punctuation guardrail as self-repair append (`.`) in all three text-output agents instead of hard-fail.
- Kept overlap-check fallback outside VariationAgent validator to avoid repeated retry loops and preserve existing deterministic behavior.
- Switched package init from lazy-only exports to explicit agent exports now that Phase 11 modules exist.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Routed SentimentAgent prompt import through helpers shim**
- **Found during:** Task 2 (VariationAgent + exports)
- **Issue:** Plan success criteria requires all agents to import prompt builders via `app.ai.agents.helpers`, but SentimentAgent still imported from `app.ai.langgraph.prompts` directly.
- **Fix:** Updated SentimentAgent to import `build_sentiment_prompt` from helpers shim.
- **Files modified:** `backend-hormonia/app/ai/agents/sentiment_agent.py`
- **Verification:** `from app.ai.agents import SentimentAgent` succeeds and `ruff check app/ai/agents/` passes.
- **Committed in:** `4b97ae0b`

**2. [Rule 3 - Blocking] Manually updated STATE.md when state tool parsing failed**
- **Found during:** Post-task state updates
- **Issue:** `state advance-plan` and `state record-session` returned parse errors against existing STATE.md format, blocking required position/session updates.
- **Fix:** Updated Current Position and Session Continuity fields in `.planning/STATE.md` manually to reflect 11-03 completion.
- **Files modified:** `.planning/STATE.md`
- **Verification:** `.planning/STATE.md` now shows `Plan: 3 of 4 in current phase` and `Stopped at: Completed 11-03-PLAN.md`.
- **Committed in:** `2634222f`

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 blocking)
**Impact on plan:** No scope creep; both fixes were required to satisfy success criteria and metadata completeness.

## Issues Encountered
- Local environment does not guarantee global `python`, so verification commands used `.venv/bin/python` when available.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Agent modules are ready for Plan 11-04 GeminiDomainClient shim wiring and regression validation.
- Import migration surface is centralized in `app.ai.agents.helpers` for upcoming langgraph tombstoning.

## Self-Check: PASSED
- Verified `.planning/phases/11-agent-implementation/11-03-SUMMARY.md` exists.
- Verified task commits `1ac313e4` and `4b97ae0b` exist in git history.

---
*Phase: 11-agent-implementation*
*Completed: 2026-02-24*
