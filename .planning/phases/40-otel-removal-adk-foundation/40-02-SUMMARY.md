---
phase: 40-otel-removal-adk-foundation
plan: 02
subsystem: ai
tags: [adk, lgpd, pii-redaction, pytest]

requires:
  - phase: 40-01
    provides: ADK dependency baseline and OTel removal groundwork
provides:
  - PIISafe ADK boundary package with safe_run contract
  - Prompt sanitization and output PII scan behavior for ADK wrapper
  - Synthetic PHI regression tests for ADK call-site safety
affects: [41-adk-agent-integration, ai-safety, ci-guard]

tech-stack:
  added: []
  patterns: [call-site-safety-wrapper, type-checking-only imports, red-green-refactor]

key-files:
  created:
    - backend-hormonia/app/ai/adk/__init__.py
    - backend-hormonia/app/ai/adk/wrapper.py
    - backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py
  modified:
    - backend-hormonia/app/ai/adk/wrapper.py

key-decisions:
  - "Mirror PIISafeAgent safety contract in PIISafeADKWrapper.safe_run before ADK wiring"
  - "Keep AIDeps typing via TYPE_CHECKING to avoid runtime import side effects during package import"

patterns-established:
  - "ADK boundary pattern: sanitize input then invoke internal boundary then scan output"
  - "Synthetic PHI tests validate no raw identifiers cross the ADK call-site"

requirements-completed: [ADK-04]

duration: 9 min
completed: 2026-03-03
---

# Phase 40 Plan 02: PIISafe ADK Wrapper Summary

**PIISafeADKWrapper now enforces prompt sanitization and output PII scanning with synthetic PHI tests proving safe ADK call boundaries.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-03T20:10:17Z
- **Completed:** 2026-03-03T20:19:58Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added `app.ai.adk` package and exported `PIISafeADKWrapper` for downstream integration.
- Implemented wrapper boundary that sanitizes prompts, blocks on sanitization failure, and scans output for CPF/phone/email leakage.
- Added TDD regression tests using synthetic PHI and validated RED -> GREEN cycle.

## Task Commits

Each task was committed atomically:

1. **Task 0: Define ADK wrapper contracts before implementation** - `3fef891e` (feat)
2. **Task 1 (RED): Add failing wrapper safety tests** - `37da0ef0` (test)
3. **Task 1 (GREEN): Implement wrapper sanitization and output scan** - `979de63a` (feat)
4. **Task 1 (REFACTOR): Remove runtime import side effects** - `1cde568a` (refactor)

**Plan metadata:** pending

## Files Created/Modified
- `backend-hormonia/app/ai/adk/__init__.py` - Public ADK package export for `PIISafeADKWrapper`.
- `backend-hormonia/app/ai/adk/wrapper.py` - Safety wrapper with mandatory sanitization and output PII warning scan.
- `backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py` - Synthetic PHI unit tests for sanitizer boundary and warning path.

## Decisions Made
- Reused `sanitize_prompt_text_for_external_ai` and PIISafeAgent-style regex scans to preserve established LGPD behavior.
- Kept `AIDeps` as the wrapper dependency contract while moving import behind `TYPE_CHECKING` so package import does not require full app settings bootstrap.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed wrapper import side effect that broke package import verification**
- **Found during:** Task 1 verification
- **Issue:** Runtime import of `app.ai.agents.deps` triggered heavy package initialization and failed without required env var.
- **Fix:** Switched `AIDeps` import to `TYPE_CHECKING`-only in wrapper while preserving annotation contract.
- **Files modified:** `backend-hormonia/app/ai/adk/wrapper.py`
- **Verification:** `pytest tests/unit/test_pii_safe_adk_wrapper.py -q` and `python3 -c "from app.ai.adk import PIISafeADKWrapper"`
- **Committed in:** `1cde568a` (part of task commit sequence)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Fix was required to satisfy import verification and keep ADK wrapper importable without unrelated environment bootstrapping.

## Issues Encountered
- Verification import initially failed because `AIDeps` runtime import pulled transitive modules that require `WHATSAPP_WUZAPI_TOKEN`; resolved via type-checking-only import.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- PIISafe ADK boundary contract is in place and tested, ready for Phase 41 ADK runner/tool wiring.
- Wrapper now imports cleanly from backend root and can be integrated by downstream ADK endpoints.

## Self-Check: PASSED

- Verified summary file and all planned wrapper/test files exist on disk.
- Verified all task commits (`3fef891e`, `37da0ef0`, `979de63a`, `1cde568a`) exist in git history.
