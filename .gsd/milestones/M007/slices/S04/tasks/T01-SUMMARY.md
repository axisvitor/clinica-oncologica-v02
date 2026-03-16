---
id: T01
parent: S04
milestone: M007
provides:
  - Focused unit tests proving PersonalizationMixin grounding calibration, variation determinism, question rephrasing, and AI-skip behavior
key_files:
  - backend-hormonia/tests/unit/services/flow/test_personalization_grounding.py
key_decisions:
  - Used _make_handler() helper with mock DB to instantiate SequentialMessageHandler (which inherits PersonalizationMixin) for direct method testing
  - Tested grounding boundary with empirically verified similarity values rather than assumed thresholds
patterns_established:
  - Module-isolation shim pattern for PersonalizationMixin testing (same as test_sequential_message_handler.py)
observability_surfaces:
  - record_ai_fallback(reason="non_response_message") counter increment verified in AI-skip test
duration: 15m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T01: Prove grounding calibration with focused unit tests

**Added 25 unit tests proving PersonalizationMixin grounding thresholds, variation determinism, question rephrasing logic, and AI-skip for non-response messages.**

## What Happened

Created `test_personalization_grounding.py` with 4 test classes covering the full PersonalizationMixin surface:

1. **TestPersonalizationIsGrounded** (11 tests): Boundary cases for `_personalization_is_grounded()` — identical text passes, unrelated/hallucinated text fails, anchored reformulation passes, high-similarity-no-keyword-overlap passes (≥0.6), low-similarity-good-keyword-overlap passes (≥0.2), no-keyword path passes/fails at 0.35 boundary, empty inputs return False.

2. **TestSelectTemplateVariation** (6 tests): Determinism proof (same inputs → same result), different patient IDs produce different selections, no/empty variations return original, duplicate-to-base variations filtered, non-string variations skipped.

3. **TestLightlyRephraseQuestion** (5 tests): Questions get prefix wrapper, non-questions unchanged, existing prefix not double-wrapped, wrappers cycle through 3 options with day+index, empty content unchanged.

4. **TestPersonalizeMessageAiSkip** (3 tests): AI skipped when `expects_response=False` with correct fallback reason recorded, AI engine never instantiated for non-response messages, `ai_disabled` reason when `use_ai_personalization=False`.

One boundary test needed correction: the no-keyword-below-threshold case required more divergent short text (original pair had similarity 0.389 > 0.35 threshold).

## Verification

- `cd backend-hormonia && python -m pytest tests/unit/services/flow/test_personalization_grounding.py -v --timeout=30` → **25 passed**
- `cd backend-hormonia && python -m pytest tests/unit/services/flow/ -v --tb=short --timeout=30` → **140 passed, 4 skipped, 1 pre-existing failure** (unrelated `test_split_files_under_500_lines` on `sequencing.py` at 521 lines)
- Diagnostic check `pytest -k "hallucin or empty or ai_skip"` → **7 passed**

### Slice-level verification status (T01/T03):
- ✅ T01: `test_personalization_grounding.py` — 25 tests green
- ⬜ T02: `PatientFlowResponse` model — not yet created
- ⬜ T03: `test_patient_flow_responses.py` — not yet created
- ✅ Existing flow tests: 140 passed, 0 regressions

## Diagnostics

- Run `cd backend-hormonia && python -m pytest tests/unit/services/flow/test_personalization_grounding.py -v -k "hallucin or empty"` to verify failure-path coverage
- All tests use realistic Portuguese oncology content matching production usage patterns

## Deviations

- Fixed `test_no_keyword_short_content_below_threshold_fails`: original text pair ("Oi, é bom te ver." / "Ah, um dia bem sol.") had similarity 0.389 which is above the 0.35 threshold. Replaced with more divergent pair yielding similarity 0.308.

## Known Issues

- Pre-existing: `test_split_files_under_500_lines` fails because `sequencing.py` is 521 lines — not related to this task.

## Files Created/Modified

- `backend-hormonia/tests/unit/services/flow/test_personalization_grounding.py` — New test file with 25 focused tests for PersonalizationMixin (grounding, variations, rephrasing, AI skip)
- `.gsd/milestones/M007/slices/S04/S04-PLAN.md` — Added diagnostic failure-path verification step
- `.gsd/milestones/M007/slices/S04/tasks/T01-PLAN.md` — Added Observability Impact section
