---
estimated_steps: 7
estimated_files: 3
---

# T01: Wire flow responses and fix alerts in aggregator + prompt

**Slice:** S06 — Resumo mensal por IA integrado ao dashboard
**Milestone:** M007

## Description

The `SummaryDataAggregator` currently collects `QuizResponse`, `Message`, and `Alert` data but completely ignores `patient_flow_responses` (the structured free-text patient replies from S04). It also has a latent bug: `alert.message` doesn't exist on the `Alert` model (it has `description`), and it doesn't extract the `recommendation` field from the JSONB `data` column (enriched by S05).

This task wires the missing data source into the aggregator, fixes the alert bug, updates the prompt template to include flow responses, and writes focused tests proving the integration.

## Steps

1. **Add flow response fields to `AggregatedPatientData`**: Add `flow_response_count: int` and `flow_responses: List[Dict[str, Any]]` fields to the dataclass. Update `to_prompt_context()` to include `flow_responses` (formatted string from `_format_flow_responses()`) and `flow_response_count`.

2. **Add `_aggregate_flow_responses()` to `SummaryDataAggregator`**: Import `PatientFlowResponse` from `app.models.patient_flow_response`. Query by `patient_id` and `responded_at` between `start_dt` and `end_dt` (uses composite index `ix_pfr_patient_responded`). Order by `responded_at ASC`. Format each response as `{"day_number": ..., "response_text": ..., "date": ..., "message_index": ...}`. Call this in `aggregate_patient_data()` alongside the other aggregations (add to the `asyncio.gather` call). Wire results into `AggregatedPatientData` constructor.

3. **Add `_format_flow_responses()` to `AggregatedPatientData`**: Format flow responses for the prompt. Each entry: `"- [DD/MM/YYYY] Dia {day_number}: {response_text}"`. Limit to 20 most recent. If empty, return `"Nenhuma resposta de acompanhamento no período."`. Log info with count.

4. **Fix alert aggregation**: In `_aggregate_alerts()`, change `alert.message if hasattr(alert, "message") else str(alert)` to `alert.description`. Add `"recommendation": (alert.data or {}).get("recommendation", "")` and `"title": (alert.data or {}).get("rule_name", alert.alert_type if hasattr(alert, "alert_type") else "Alerta")` to the formatted alert dict. Update `_format_alerts()` to include recommendation when present: `"- [date] [SEVERITY] title: description (Recomendação: recommendation)"`.

5. **Update prompt template**: In `patient_summary.py`, add a new section to `PATIENT_SUMMARY_PROMPT` between "Mensagens Relevantes" and "Alertas de Saúde":
   ```
   ### Respostas de Acompanhamento Diário ({flow_response_count} respostas)
   {flow_responses}
   ```

6. **Write focused tests** in `tests/unit/services/flow/test_summary_integration.py`:
   - `test_aggregate_flow_responses_formats_correctly` — mock DB returns PatientFlowResponse rows, verify formatted output
   - `test_aggregate_flow_responses_empty` — no responses returns fallback text
   - `test_aggregate_flow_responses_respects_date_range` — verify date filtering in query
   - `test_alert_aggregation_uses_description_not_message` — mock Alert with `description` attr (no `message`), verify correct formatting
   - `test_alert_aggregation_extracts_recommendation` — mock Alert with `data={"recommendation": "...", "rule_name": "..."}`, verify both appear in formatted output
   - `test_prompt_context_includes_flow_responses` — create `AggregatedPatientData` with flow_responses, verify `to_prompt_context()` has `flow_responses` key with formatted content
   - `test_prompt_context_includes_flow_response_count` — verify `flow_response_count` in context
   - `test_flow_responses_limited_to_20` — verify truncation with > 20 responses

7. **Add logger.info for flow response aggregation**: After querying, log `f"Aggregated {len(responses)} flow responses for patient {patient_id}"`.

## Must-Haves

- [ ] `AggregatedPatientData` has `flow_responses` and `flow_response_count` fields
- [ ] `_aggregate_flow_responses()` queries `PatientFlowResponse` by patient_id + responded_at range
- [ ] `_format_flow_responses()` produces day-level formatted text for the prompt
- [ ] Alert aggregation uses `alert.description` (not `alert.message`) and extracts `recommendation` from JSONB `data`
- [ ] Prompt template has `{flow_responses}` and `{flow_response_count}` placeholders
- [ ] `to_prompt_context()` populates both new placeholders
- [ ] 8+ focused tests prove all integration points

## Verification

- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_summary_integration.py -v` — all tests pass
- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/ -v` — 0 regressions
- Diagnostic: `to_prompt_context()` output includes `flow_responses` key with `"Dia 1:"` formatted content when data is present

## Observability Impact

- Signals added: `logger.info("Aggregated {count} flow responses for patient {patient_id}")` in aggregator
- How a future agent inspects this: call `to_prompt_context()` and check for `flow_responses` and `flow_response_count` keys
- Failure state exposed: empty flow responses produce "Nenhuma resposta de acompanhamento no período." in prompt (info-level, not error)

## Inputs

- `backend-hormonia/app/services/ai/summary_data_aggregator.py` — current aggregator (373 lines) that needs flow response integration and alert fix
- `backend-hormonia/app/services/ai/prompts/patient_summary.py` — prompt template (97 lines) that needs `{flow_responses}` section
- `backend-hormonia/app/models/patient_flow_response.py` — S04 model with `patient_id`, `day_number`, `message_index`, `response_text`, `responded_at` fields, nullable `flow_state_id`
- `backend-hormonia/app/models/alert.py` — has `description` column (NOT `message`), `data` JSONB with `recommendation`, `rule_name`, `quiz_session_id`, `triggered_rule_id`
- S04 summary: `patient_flow_responses` composite index `ix_pfr_patient_responded` on `(patient_id, responded_at)` is optimized for period queries
- S05 summary: alert JSONB `data` contains `rule_name`, `recommendation`, `relevant_responses`, `evaluated_at` from `QuizResponseEvaluator`

## Expected Output

- `backend-hormonia/app/services/ai/summary_data_aggregator.py` — modified: new fields on dataclass, `_aggregate_flow_responses()` method, `_format_flow_responses()` method, fixed `_aggregate_alerts()`, updated `to_prompt_context()` and `aggregate_patient_data()`
- `backend-hormonia/app/services/ai/prompts/patient_summary.py` — modified: new `{flow_responses}` section in prompt template
- `backend-hormonia/tests/unit/services/flow/test_summary_integration.py` — new: 8+ focused tests proving aggregator integration
