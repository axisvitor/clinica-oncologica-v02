---
estimated_steps: 6
estimated_files: 1
---

# T01: Prove grounding calibration with focused unit tests

**Slice:** S04 — Personalização IA e armazenamento de respostas
**Milestone:** M007

## Description

Write focused unit tests proving the existing IA personalization grounding pipeline works correctly. The production code in `personalization.py` already implements `_personalization_is_grounded()`, `_select_template_variation()`, `_lightly_rephrase_question()`, and `_personalize_message_ai()`. This task only adds tests — no production code changes.

The grounding thresholds are:
- With keywords: `overlap_ratio >= 0.2 OR similarity >= 0.6`
- Without keywords (no tokens ≥ 4 chars): `similarity >= 0.35`

## Steps

1. Create `backend-hormonia/tests/unit/services/flow/test_personalization_grounding.py` using the same module-isolation shim pattern from `test_sequential_message_handler.py` (mock `app.services.unified_whatsapp_service` and `app.services.enhanced_flow_engine` before importing the handler).

2. Write grounding threshold tests for `_personalization_is_grounded()`:
   - Test identical text passes (similarity ~1.0)
   - Test completely unrelated text fails (no keyword overlap, low similarity)
   - Test anchored reformulation passes (same keywords, slightly different phrasing — realistic Portuguese oncology content like "Como você está se sentindo hoje com o tratamento?")
   - Test hallucinated content fails (different topic entirely)
   - Test boundary: high similarity but no keyword overlap still passes (similarity ≥ 0.6)
   - Test boundary: low similarity but good keyword overlap still passes (overlap ≥ 0.2)
   - Test no-keyword path: short content with similarity ≥ 0.35 passes
   - Test empty inputs return False

3. Write `_select_template_variation()` tests:
   - Test determinism: same inputs always produce the same variation
   - Test different patient IDs produce different selections (with enough variations)
   - Test empty/no variations returns original content
   - Test duplicate/identical-to-base variations are filtered out

4. Write `_lightly_rephrase_question()` tests:
   - Test question (has "?") gets a prefix wrapper
   - Test non-question (no "?") is returned unchanged
   - Test content with existing prefix is not double-wrapped
   - Test different day_number/message_index cycle through the 3 wrappers

5. Write `_personalize_message_ai()` test:
   - Test that when `expects_response=False`, AI is skipped entirely (engine never called) and fallback content is returned with `record_ai_fallback(reason="non_response_message")`

6. Run all tests and verify 0 regressions:
   ```bash
   cd backend-hormonia && python -m pytest tests/unit/services/flow/test_personalization_grounding.py -v
   cd backend-hormonia && python -m pytest tests/unit/services/flow/ -v --tb=short
   ```

## Must-Haves

- [ ] `_personalization_is_grounded()` boundary cases tested with realistic Portuguese oncology content
- [ ] `_select_template_variation()` determinism proven
- [ ] `_lightly_rephrase_question()` question vs non-question behavior proven
- [ ] `_personalize_message_ai` AI-skip for `expects_response=False` proven
- [ ] All existing flow tests remain green (0 regressions)

## Verification

- `cd backend-hormonia && python -m pytest tests/unit/services/flow/test_personalization_grounding.py -v` — 10+ tests green
- `cd backend-hormonia && python -m pytest tests/unit/services/flow/ -v --tb=short` — all existing tests green

## Inputs

- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/personalization.py` — The production code under test. Contains `PersonalizationMixin` with `_personalization_is_grounded()` (line 45), `_select_template_variation()` (line 163), `_lightly_rephrase_question()` (line 201), `_personalize_message_ai()` (line 62). Grounding thresholds: `overlap_ratio >= 0.2 OR similarity >= 0.6` (with keywords), `similarity >= 0.35` (no keywords).
- `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py` — Existing test file with the shim pattern for module isolation (lines 1-35). Copy this shim pattern for the new test file.
- `backend-hormonia/app/services/flow/metrics.py` — `record_ai_fallback()` Prometheus counter. Mock this to verify AI skip records the correct reason.

## Expected Output

- `backend-hormonia/tests/unit/services/flow/test_personalization_grounding.py` — New test file with 10+ focused tests covering grounding thresholds, variation selection, light rephrasing, and AI skip behavior. Proves R060 contract.
