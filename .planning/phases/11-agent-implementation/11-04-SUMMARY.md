---
phase: 11-agent-implementation
plan: 04
subsystem: ai
tags: [pydantic-ai, feature-flag, regression, gemini, pytest]
requires:
  - phase: 11-02
    provides: SentimentAgent typed output and validator baseline
  - phase: 11-03
    provides: Humanize/Variation/Empathy agent implementations and helpers shim
provides:
  - GeminiDomainClient feature-flag shim toggling legacy and pydantic-ai execution paths
  - AI_FRAMEWORK settings declaration and environment template entry
  - 50-scenario regression suite validating structural parity across all four agents
affects: [phase-12-flow-replacement, ai-runtime-routing, regression-safety]
tech-stack:
  added: []
  patterns: [runtime framework toggle via settings, lazy agent imports in shim, scenario-driven agent regression tests]
key-files:
  created:
    - backend-hormonia/tests/unit/ai/conftest.py
    - backend-hormonia/tests/unit/ai/test_agents_regression.py
  modified:
    - backend-hormonia/app/ai/client_domain.py
    - backend-hormonia/app/config/settings/integrations.py
    - backend-hormonia/.env.example
    - backend-hormonia/app/ai/agents/sentiment_agent.py
key-decisions:
  - "Keep AI_FRAMEWORK default as legacy to preserve current production behavior until explicit opt-in."
  - "Convert SentimentAgent output to dict in shim path to maintain existing GeminiDomainClient return signature."
patterns-established:
  - "Shim-first migration: delegate by feature flag while leaving legacy branch untouched."
  - "Regression coverage uses structural assertions and mocked PIISafeAgent calls to avoid live Gemini flakiness."
requirements-completed: [AGENT-07, AGENT-08]
duration: 17 min
completed: 2026-02-24
---

# Phase 11 Plan 04: Domain Shim and Regression Summary

**GeminiDomainClient now switches between legacy generate_content and pydantic-ai agents via AI_FRAMEWORK while a 50-scenario regression suite validates structural parity and guardrail behavior.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-02-24T15:17:17Z
- **Completed:** 2026-02-24T15:34:29Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Added `AI_FRAMEWORK` to `IntegrationsSettings` and `.env.example`, defaulting to `legacy` for safe rollout.
- Implemented `_use_pydantic_agents()` in `GeminiDomainClient` and wired all 4 public methods to delegate to corresponding agents when enabled.
- Added full `tests/unit/ai/test_agents_regression.py` suite with 50 parametrized scenarios across sentiment, humanize, variation, and empathy paths.
- Added test fixtures in `tests/unit/ai/conftest.py` to mock PIISafeAgent runtime calls and avoid external API usage.
- Verified framework toggle behavior, regression suite pass, and ruff checks for modified source files.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add AI_FRAMEWORK setting and wire GeminiDomainClient shim** - `d857bd8f` (feat)
2. **Task 2: Create 50-scenario regression test suite** - `63ba730c` (test)

## Files Created/Modified
- `backend-hormonia/app/config/settings/integrations.py` - declares `AI_FRAMEWORK` Pydantic settings field.
- `backend-hormonia/.env.example` - adds `AI_FRAMEWORK=legacy` toggle entry.
- `backend-hormonia/app/ai/client_domain.py` - adds shim helper and per-method pydantic-ai delegation path.
- `backend-hormonia/tests/unit/ai/conftest.py` - shared `ai_deps` and `_safe_run` patch fixtures.
- `backend-hormonia/tests/unit/ai/test_agents_regression.py` - 50-scenario regression matrix with async and validator checks.
- `backend-hormonia/app/ai/agents/sentiment_agent.py` - normalizes `None` inputs to defaults for all SentimentResult fields expected by parity tests.

## Decisions Made
- Kept lazy imports inside feature-flag branches to avoid loading pydantic-ai modules when legacy mode is active.
- Kept shim as owner of sentiment context compaction and dict conversion so existing callers remain unchanged.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SentimentResult rejected `None` values for optional payload fields**
- **Found during:** Task 2 (regression suite execution)
- **Issue:** Scenario coverage for missing model fields (`None`) failed with Pydantic validation errors, violating parity requirement that downstream callers never hit missing-field issues.
- **Fix:** Added normalizers for `emotional_indicators`, `key_themes`, `requires_attention`, and `suggested_follow_up` to coerce `None` to safe defaults.
- **Files modified:** `backend-hormonia/app/ai/agents/sentiment_agent.py`
- **Verification:** `pytest tests/unit/ai/test_agents_regression.py -q` passes all 50 scenarios.
- **Committed in:** `63ba730c`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Fix was required to satisfy AGENT-08 structural parity and maintain backward-compatible sentiment payload guarantees.

## Authentication Gates

None.

## Issues Encountered

- `ruff check` surfaced an unused import in `client_domain.py`; removed during task completion to satisfy plan verification.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 11 is complete and ready for Phase 12 flow orchestration replacement using the new AI framework shim.
- Feature flag allows controlled rollout/testing before legacy path retirement.

## Self-Check: PASSED
- Found `.planning/phases/11-agent-implementation/11-04-SUMMARY.md` on disk.
- Found task commits `d857bd8f` and `63ba730c` in git history.
