---
id: S06
parent: M007
milestone: M007
provides:
  - SummaryDataAggregator queries patient_flow_responses and includes flow response data in AggregatedPatientData
  - Fixed alert aggregation using alert.description (not alert.message) with recommendation from JSONB data
  - Prompt template with {flow_responses} section for patient free-text replies with day context
  - to_prompt_context() includes flow_responses and flow_response_count keys
  - PhysicianDashboard Brain icon button per patient navigating to ?tab=ai-summary
requires:
  - slice: S04
    provides: PatientFlowResponse model + table with patient_id, day_number, message_index, response_text, responded_at
  - slice: S05
    provides: Alert model with description column and data JSONB containing recommendation and rule_name
  - slice: S03
    provides: Template structure defining day_number, content, message_type, expects_response per day
affects: []
key_files:
  - backend-hormonia/app/services/ai/summary_data_aggregator.py
  - backend-hormonia/app/services/ai/prompts/patient_summary.py
  - backend-hormonia/tests/unit/services/flow/test_summary_integration.py
  - frontend-hormonia/src/features/dashboard/components/physician/PhysicianRiskTable.tsx
  - frontend-hormonia/src/pages/PhysicianDashboard.tsx
key_decisions:
  - Flow responses truncated to 20 most recent for prompt to avoid overwhelming LLM context window
  - Alert dicts use description and title (from JSONB data.rule_name) instead of nonexistent message attribute
  - flow_response_count and flow_responses are required fields on AggregatedPatientData (no defaults) to match existing dataclass pattern
  - Brain icon button in Ações column with optional onAISummaryClick prop for backward compatibility
patterns_established:
  - Alert formatting includes recommendation parenthetical only when non-empty
  - Flow response formatting uses "- [DD/MM/YYYY] Dia N: text" pattern consistent with other aggregator formatters
  - Ghost icon button with Tooltip for secondary per-row actions in risk table
observability_surfaces:
  - logger.info("Aggregated {count} flow responses for patient {patient_id}") in _aggregate_flow_responses()
  - logger.info("Formatted {count} flow responses for prompt (total: {total})") in _format_flow_responses()
  - to_prompt_context() includes flow_responses and flow_response_count keys
  - Empty flow responses produce "Nenhuma resposta de acompanhamento no período." (info-level, not error)
  - aria-label="Ver Resumo IA" on Brain icon button in PhysicianRiskTable rows
drill_down_paths:
  - .gsd/milestones/M007/slices/S06/tasks/T01-SUMMARY.md
  - .gsd/milestones/M007/slices/S06/tasks/T02-SUMMARY.md
duration: 23m
verification_result: passed
completed_at: 2026-03-16
---

# S06: Resumo mensal por IA integrado ao dashboard

**Wired patient flow responses and enriched alerts into SummaryDataAggregator, fixed alert.message bug, extended AI prompt with flow response section, and added quick-access "Resumo IA" Brain icon per patient in PhysicianDashboard**

## What Happened

T01 closed the core data gap: `SummaryDataAggregator` now queries `patient_flow_responses` (the structured response table from S04) via `_aggregate_flow_responses()` using the composite index `ix_pfr_patient_responded`, runs it in `asyncio.gather` alongside existing quiz/message/alert aggregations, and produces `flow_responses` + `flow_response_count` fields on `AggregatedPatientData`. The `_format_flow_responses()` method formats each response as `"- [DD/MM/YYYY] Dia {day_number}: {response_text}"`, limited to 20 most recent to avoid overwhelming the LLM context. A fallback message handles the empty case.

T01 also fixed a latent bug in `_aggregate_alerts()`: it was accessing `alert.message` (which doesn't exist on the Alert model) instead of `alert.description`. Now it extracts `title` from `alert.data.get("rule_name")` and `recommendation` from `alert.data.get("recommendation")`, producing richer alert context for the AI summary. The prompt template gained a `{flow_responses}` section between "Mensagens Relevantes" and "Alertas de Saúde". 13 focused tests prove the complete integration.

T02 added discoverability: `PhysicianRiskTable` gained a Brain icon button (from lucide-react) per patient row in the Ações column with `aria-label="Ver Resumo IA"`. Clicking navigates to `/physician/patients/${patientId}?tab=ai-summary`. `PatientDetailPage` already reads `searchParams.get('tab')` and uses it as `defaultValue` for the Tabs component — no changes needed there. The `onAISummaryClick` prop is optional for backward compatibility.

## Verification

- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_summary_integration.py -v` — **13/13 passed**
- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/ -v` — **181 passed**, 4 skipped, 1 pre-existing failure (sequencing.py >500 lines), **0 regressions from S06**
- `cd frontend-hormonia && npx tsc --noEmit` — **green** (only 6 pre-existing e2e playwright config errors, 0 new errors)
- Diagnostic: `to_prompt_context()` output includes `flow_responses` key with day-level formatted content and `flow_response_count` key — confirmed via test assertions

## Requirements Advanced

- R063 — `SummaryDataAggregator` now consumes `patient_flow_responses` and enriched alerts, AI prompt includes flow response section, PhysicianDashboard provides quick-access to AI summary

## Requirements Validated

- R063 — Proven by 13 focused tests covering: aggregator queries PatientFlowResponse correctly, alert description/recommendation are formatted, flow responses appear in prompt context with day-level data, empty flow responses produce correct fallback text, 20-item truncation works, date range filtering works. Frontend Brain icon button navigates to AI summary tab. Full backend flow suite green with 0 regressions.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- T01: `flow_response_count` and `flow_responses` were made required fields (no defaults) instead of optional with `__post_init__` post-processing, because Python dataclasses don't allow non-default fields after defaulted ones and the existing `response_rate` field already has no default.
- T01: Wrote 13 tests instead of planned 8 — added 5 additional for better coverage (alert formatting without recommendation, DB-level alert description test, DB-level alert recommendation extraction, empty DB flow responses, date range filtering).
- T02: Modified `PhysicianRiskTable.tsx` component directly rather than inlining button in `PhysicianDashboard.tsx` — cleaner separation since the table owns its row rendering.

## Known Limitations

- Flow response truncation to 20 most recent may lose important early context for patients with high response volume; future iteration could apply relevance-based selection instead of recency-only.
- AI summary quality is ultimately dependent on Gemini 2.5 Flash prompt response quality — the structured prompt provides rich context but the output quality requires human clinical evaluation (UAT).
- Pre-existing: `sequencing.py` has 521 lines vs 500-line contract — unrelated to S06.

## Follow-ups

- none — this is the terminal slice of M007

## Files Created/Modified

- `backend-hormonia/app/services/ai/summary_data_aggregator.py` — added flow_response fields to AggregatedPatientData, `_aggregate_flow_responses()` method, `_format_flow_responses()` method, fixed `_aggregate_alerts()` to use description+recommendation, updated `to_prompt_context()` and `aggregate_patient_data()`
- `backend-hormonia/app/services/ai/prompts/patient_summary.py` — added `{flow_responses}` section to PATIENT_SUMMARY_PROMPT
- `backend-hormonia/tests/unit/services/flow/test_summary_integration.py` — new: 13 focused tests proving aggregator integration
- `frontend-hormonia/src/features/dashboard/components/physician/PhysicianRiskTable.tsx` — added Brain icon, Tooltip, optional `onAISummaryClick` prop, Brain icon button per row
- `frontend-hormonia/src/pages/PhysicianDashboard.tsx` — added `handleAISummaryClick` callback, wired `onAISummaryClick` prop

## Forward Intelligence

### What the next slice should know
- M007 is now complete. All 6 slices delivered. The flow pipeline is end-to-end: sequencing → template editing → AI personalization → response storage → quiz alerts with notifications → AI monthly summary for the doctor.
- The `PatientSummaryService` (existing, ~669 lines) was NOT modified in S06 — only its data aggregator was enhanced. The service itself already handles Gemini calls, caching, and the API endpoint.

### What's fragile
- `_aggregate_alerts()` relies on `alert.data` JSONB containing `rule_name` and `recommendation` keys — these are written by `QuizResponseEvaluator._create_alert()` (S05). If alert creation changes the JSONB schema, the aggregator silently degrades to empty strings instead of crashing.
- `PatientDetailPage` tab selection via `searchParams.get('tab')` is case-sensitive — `?tab=ai-summary` must match the Tabs `value` exactly.

### Authoritative diagnostics
- `python3 -m pytest tests/unit/services/flow/test_summary_integration.py -v` — 13 tests covering all S06 integration points
- `to_prompt_context()` on an `AggregatedPatientData` instance — check for `flow_responses` and `flow_response_count` keys
- Logger output: `"Aggregated {count} flow responses"` and `"Formatted {count} flow responses"` in production logs

### What assumptions changed
- Plan assumed `PatientDetailPage` might need changes for `?tab=ai-summary` — it already handled arbitrary tab values via `searchParams.get('tab')`, so no changes were needed there.
- Plan assumed alert fix would be simple field rename — it also required extracting `title` and `recommendation` from JSONB `data`, making the alert context richer than originally planned.
