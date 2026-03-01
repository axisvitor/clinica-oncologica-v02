---
phase: 13-sdk-migration-cleanup
plan: 01
subsystem: ai
tags: [google-genai, sdk-migration, gemini, pii-redaction, langchain-removal]
requires:
  - phase: 12-flow-orchestration-replacement
    provides: LangChain package removal baseline and helper tombstoning boundary
provides:
  - GeminiClient running on google.genai.Client async generate_content calls
  - PatientSummaryService migrated to google-genai with system_instruction config
  - PII redaction unit test stubs aligned to google-genai response structure
affects: [13-02-langchain-purge, ai-runtime, regression-safety]
tech-stack:
  added: []
  patterns: [direct google-genai client usage, enum-based finish_reason handling, system_instruction config for summaries]
key-files:
  created: []
  modified:
    - backend-hormonia/app/ai/client.py
    - backend-hormonia/app/services/ai/patient_summary_service.py
    - backend-hormonia/tests/unit/test_gemini_client_pii_redaction.py
key-decisions:
  - "Hard-cut GeminiClient and PatientSummaryService from LangChain to google-genai without feature toggles."
  - "Preserve existing retry/rate-limit/circuit-breaker/public interfaces while swapping only SDK internals."
patterns-established:
  - "Use response.candidates[0].finish_reason.name for completion checks instead of metadata dict parsing."
  - "Use GenerateContentConfig(system_instruction=...) for summary generation instead of message wrapper objects."
requirements-completed: [SDK-01]
duration: 11 min
completed: 2026-02-24
---

# Phase 13 Plan 01: SDK Migration Summary

**GeminiClient and PatientSummaryService now call google-genai SDK directly, removing LangChain message/model wrappers while preserving existing resilience and guardrail flows.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-02-24T18:17:58Z
- **Completed:** 2026-02-24T18:29:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Replaced `ChatGoogleGenerativeAI` and `HumanMessage/SystemMessage` usage in `GeminiClient` with `genai.Client` + `aio.models.generate_content`.
- Updated Gemini finish-reason handling to use `response.candidates[0].finish_reason.name` and restricted complete statuses to `STOP`/`FINISH_REASON_UNSPECIFIED`.
- Migrated `PatientSummaryService` to google-genai using `GenerateContentConfig(system_instruction=...)` and SDK-native usage metadata extraction.
- Updated PII redaction tests to stub google-genai response shape and removed `pytest.importorskip("langchain_google_genai")` dependency.

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate GeminiClient to google-genai SDK** - `657c2b73` (feat)
2. **Task 2: Migrate PatientSummaryService and update PII test** - `197d6058` (feat)

## Files Created/Modified
- `backend-hormonia/app/ai/client.py` - Swaps model init/inference path to google-genai client/config and SDK finish-reason parsing.
- `backend-hormonia/app/services/ai/patient_summary_service.py` - Replaces LangChain messages/model with google-genai client calls and `system_instruction` config.
- `backend-hormonia/tests/unit/test_gemini_client_pii_redaction.py` - Uses google-genai response stubs and asserts redaction on `contents` payload.

## Decisions Made
- Kept `self.model` as a sentinel alias to the SDK client so existing health-check guards (`if not self.model`) continue to work.
- Kept timeout/rate-limit/retry/circuit-breaker logic unchanged and scoped migration strictly to SDK integration points.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Enforced string contract for summary parser input**
- **Found during:** Task 2
- **Issue:** SDK response typing can expose non-str payload variants; `_parse_summary_response` requires `str`.
- **Fix:** Normalized summary content with `str(response.text or "").strip()` before JSON parsing.
- **Files modified:** `backend-hormonia/app/services/ai/patient_summary_service.py`
- **Verification:** `python3 -c "import ast, sys; tree = ast.parse(open('app/services/ai/patient_summary_service.py').read()); mods = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module and 'langchain' in n.module]; sys.exit(1) if mods else print('zero langchain imports in patient_summary_service')"`
- **Committed in:** `197d6058`

**2. [Rule 3 - Blocking] Resolved strict return typing path in GeminiClient guardrail flow**
- **Found during:** Task 1
- **Issue:** Static analysis flagged optional cached-response flow and missing terminal error path in `generate_content` after refactor.
- **Fix:** Switched cache-hit check to `is not None` and added explicit terminal `GeminiAPIError` raise.
- **Files modified:** `backend-hormonia/app/ai/client.py`
- **Verification:** `python3 -c "from app.ai.client import GeminiClient; print('import OK')"`
- **Committed in:** `657c2b73`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both fixes were contained to migrated files and required to keep typed/runtime contracts stable after SDK cutover.

## Authentication Gates

None.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 13-02 can now remove remaining LangChain shims/settings using SDK-native runtime paths as the default baseline.
- LangChain imports are eliminated from the three plan-target files and PII regression coverage remains passing.

---
*Phase: 13-sdk-migration-cleanup*
*Completed: 2026-02-24*

## Self-Check: PASSED

- FOUND: `.planning/phases/13-sdk-migration-cleanup/13-01-SUMMARY.md`
- FOUND: `657c2b73`
- FOUND: `197d6058`
