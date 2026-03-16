---
id: T01
parent: S06
milestone: M007
provides:
  - flow_responses and flow_response_count fields on AggregatedPatientData
  - _aggregate_flow_responses() method querying PatientFlowResponse by patient_id + responded_at range
  - _format_flow_responses() producing day-level formatted text for AI prompt
  - Fixed alert aggregation using alert.description and extracting recommendation from JSONB data
  - Prompt template with {flow_responses} and {flow_response_count} placeholders
key_files:
  - backend-hormonia/app/services/ai/summary_data_aggregator.py
  - backend-hormonia/app/services/ai/prompts/patient_summary.py
  - backend-hormonia/tests/unit/services/flow/test_summary_integration.py
key_decisions:
  - Flow responses are ordered ASC by responded_at and truncated to 20 most recent for prompt (avoids overwhelming the LLM context)
  - Alert dicts now use 'description' and 'title' keys instead of 'message' key, with optional 'recommendation' from JSONB data
  - flow_response_count and flow_responses are required fields on AggregatedPatientData (no defaults) to match existing dataclass pattern
patterns_established:
  - Alert formatting includes recommendation parenthetical only when non-empty
  - Flow response formatting uses "- [DD/MM/YYYY] Dia N: text" pattern consistent with other aggregator formatters
observability_surfaces:
  - logger.info("Aggregated {count} flow responses for patient {patient_id}") in _aggregate_flow_responses()
  - logger.info("Formatted {count} flow responses for prompt (total: {total})") in _format_flow_responses()
  - to_prompt_context() includes flow_responses and flow_response_count keys
  - Empty flow responses produce "Nenhuma resposta de acompanhamento no período." (info-level, not error)
duration: 15m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T01: Wire flow responses and fix alerts in aggregator + prompt

**Wired PatientFlowResponse data into SummaryDataAggregator, fixed alert.message→alert.description bug, and added flow response section to prompt template**

## What Happened

1. Added `flow_response_count: int` and `flow_responses: List[Dict[str, Any]]` fields to `AggregatedPatientData` dataclass.

2. Added `_aggregate_flow_responses()` method to `SummaryDataAggregator` — queries `PatientFlowResponse` by `patient_id` and `responded_at` range (uses composite index `ix_pfr_patient_responded`), orders by `responded_at ASC`, formats each as `{day_number, response_text, date, message_index}`. Wired into `asyncio.gather` alongside existing aggregations.

3. Added `_format_flow_responses()` to `AggregatedPatientData` — formats flow responses as `"- [DD/MM/YYYY] Dia {day_number}: {response_text}"`, limited to 20 most recent, with fallback text for empty list.

4. Fixed `_aggregate_alerts()` — replaced `alert.message if hasattr(alert, "message") else str(alert)` with `alert.description`. Added `recommendation` and `title` (from `alert.data` JSONB) to formatted alert dicts. Updated `_format_alerts()` to include recommendation parenthetical when present.

5. Updated `to_prompt_context()` to include `flow_responses` and `flow_response_count` keys.

6. Added `{flow_responses}` section to `PATIENT_SUMMARY_PROMPT` between "Mensagens Relevantes" and "Alertas de Saúde".

7. Wrote 13 focused tests covering all integration points (flow response formatting, empty fallback, 20-item truncation, prompt context keys, alert description fix, alert recommendation extraction, DB query interaction).

## Verification

- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_summary_integration.py -v` — **13 passed**
- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/ -v` — **181 passed, 1 failed (pre-existing: sequencing.py >500 lines), 4 skipped**
- Syntax check on both modified source files — clean
- Diagnostic: `to_prompt_context()` output includes `flow_responses` key with `"Dia 1:"` formatted content when data is present (verified via test assertions)

### Slice-level verification status (T01 is intermediate):
- ✅ `test_summary_integration.py -v` — 13/13 pass
- ✅ `tests/unit/services/flow/ -v` — 0 regressions (1 pre-existing failure unrelated)
- ⏳ `frontend-hormonia && npx tsc --noEmit` — not applicable to T01 (no frontend changes)
- ✅ Diagnostic: `to_prompt_context()` includes `flow_responses` with day-level data

## Diagnostics

- Call `to_prompt_context()` on an `AggregatedPatientData` instance and check for `flow_responses` and `flow_response_count` keys
- Logger output: `"Aggregated {count} flow responses for patient {patient_id}"` after DB query
- Logger output: `"Formatted {count} flow responses for prompt (total: {total})"` during formatting
- Empty state: produces `"Nenhuma resposta de acompanhamento no período."` in prompt

## Deviations

- Plan suggested `flow_response_count: int = 0` and `flow_responses: List[...] = None` with `__post_init__`. Changed to required fields (no defaults) because Python dataclasses don't allow non-default fields after defaulted ones, and the existing `response_rate` field has no default. All construction sites always provide these values explicitly.
- Wrote 13 tests instead of the planned 8 — added 5 additional tests for better coverage: alert formatting without recommendation, DB-level alert description test, DB-level alert recommendation extraction test, empty DB flow response test, and date range filtering test.

## Known Issues

- Pre-existing: `test_split_files_under_500_lines` fails because `sequencing.py` has 521 lines — unrelated to this task.

## Files Created/Modified

- `backend-hormonia/app/services/ai/summary_data_aggregator.py` — added flow_response fields to dataclass, `_aggregate_flow_responses()` method, `_format_flow_responses()` method, fixed `_aggregate_alerts()` to use description+recommendation, updated `to_prompt_context()` and `aggregate_patient_data()`
- `backend-hormonia/app/services/ai/prompts/patient_summary.py` — added `{flow_responses}` section to prompt template
- `backend-hormonia/tests/unit/services/flow/test_summary_integration.py` — new: 13 focused tests proving aggregator integration
