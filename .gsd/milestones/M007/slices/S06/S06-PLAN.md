# S06: Resumo mensal por IA integrado ao dashboard

**Goal:** O médico acessa no dashboard um resumo IA do mês de acompanhamento do paciente — síntese de respostas livres, padrões, alertas, pontos de atenção — gerado pelo `PatientSummaryService` consumindo dados reais do mês.
**Demo:** Calling `POST /api/v2/ai/summary` with a patient_id produces a summary that includes flow response data and enriched alert data (with recommendations). The "Resumo IA" tab in PatientDetailPage renders the summary. The PhysicianDashboard provides a quick-access link to the AI summary for each patient.

## Must-Haves

- `SummaryDataAggregator` queries `patient_flow_responses` table and includes flow response data (day_number, response_text, responded_at) in `AggregatedPatientData`
- Alert aggregation uses `alert.description` (not `alert.message` which doesn't exist) and extracts `recommendation` from `alert.data` JSONB
- Prompt template includes a `{flow_responses}` section for patient free-text replies with day context
- `to_prompt_context()` formats flow responses for the prompt
- PhysicianDashboard provides a quick-access path to the AI summary per patient
- Focused tests prove aggregator integration with flow responses, alert fix, and prompt context generation

## Proof Level

- This slice proves: integration
- Real runtime required: no (mock DB + mock AI calls in tests)
- Human/UAT required: yes (subjective quality of AI-generated summaries for clinical use)

## Verification

- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_summary_integration.py -v` — all tests green
- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/ -v` — 0 regressions across existing 168+ tests
- `cd frontend-hormonia && npx tsc --noEmit` — typecheck green
- Diagnostic: aggregator `to_prompt_context()` output includes `flow_responses` key with formatted day-level data

## Observability / Diagnostics

- Runtime signals: `logger.info("Aggregated {count} flow responses for patient {patient_id}")` in aggregator
- Inspection surfaces: `to_prompt_context()` return dict includes `flow_responses` and `flow_response_count` keys; `GET /api/v2/ai/summary/patient/{id}` returns summary with flow data incorporated
- Failure visibility: aggregator logs empty flow responses as info (not error — patient may have no responses yet); alert formatting failure surfaces in prompt as "[Alert details unavailable]" fallback
- Redaction constraints: patient response_text may contain PII — already handled by existing `PatientSummaryService` which stores summaries server-side only

## Integration Closure

- Upstream surfaces consumed:
  - `backend-hormonia/app/models/patient_flow_response.py` — S04 model for structured responses
  - `backend-hormonia/app/models/alert.py` — Alert model with `description` column and `data` JSONB (S05 enriched)
  - `backend-hormonia/app/services/ai/patient_summary_service.py` — existing service, no changes needed
  - `frontend-hormonia/src/features/ai/PatientAISummary.tsx` — existing component, no changes needed
  - `frontend-hormonia/src/pages/PatientDetailPage.tsx` — existing "Resumo IA" tab, no changes needed
- New wiring introduced in this slice:
  - `PatientFlowResponse` import and query in `SummaryDataAggregator`
  - `flow_responses` field in `AggregatedPatientData` dataclass
  - `{flow_responses}` placeholder in prompt template
  - Quick-access "Resumo IA" link in PhysicianDashboard patient list
- What remains before the milestone is truly usable end-to-end: nothing — this is the terminal slice

## Tasks

- [x] **T01: Wire flow responses and fix alerts in aggregator + prompt** `est:45m`
  - Why: The core data gap — `SummaryDataAggregator` doesn't consume `patient_flow_responses` and has a latent `alert.message` bug. Without this, the AI summary ignores the patient's free-text replies (the primary value of the monthly summary) and produces broken alert formatting.
  - Files: `backend-hormonia/app/services/ai/summary_data_aggregator.py`, `backend-hormonia/app/services/ai/prompts/patient_summary.py`, `backend-hormonia/tests/unit/services/flow/test_summary_integration.py`
  - Do: (1) Add `flow_responses` field to `AggregatedPatientData` dataclass + `flow_response_count` int field, (2) Add `_aggregate_flow_responses()` method to `SummaryDataAggregator` querying `PatientFlowResponse` by patient_id + responded_at range using the composite index, (3) Add `_format_flow_responses()` to format flow responses for prompt (day number, response text, date), (4) Fix `_aggregate_alerts()` to use `alert.description` instead of `alert.message`, extract `recommendation` from `(alert.data or {}).get("recommendation", "")`, (5) Update `to_prompt_context()` to include `flow_responses` and `flow_response_count`, (6) Add `{flow_responses}` section to `PATIENT_SUMMARY_PROMPT` between messages and alerts sections, (7) Write focused tests proving: aggregator queries PatientFlowResponse correctly, alert description/recommendation are formatted, flow responses appear in prompt context, empty flow responses produce correct fallback text
  - Verify: `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_summary_integration.py -v`
  - Done when: All tests pass, aggregator produces `flow_responses` in prompt context with day-level formatting, alert bug is fixed

- [x] **T02: Add dashboard AI summary access and run full verification** `est:25m`
  - Why: The path from PhysicianDashboard to "Resumo IA" exists (click patient → PatientDetailPage → tab) but R063 says "médico acessa resumo no dashboard" — a direct access hint improves discoverability. Plus full regression verification across backend and frontend.
  - Files: `frontend-hormonia/src/pages/PhysicianDashboard.tsx`
  - Do: (1) In the patient risk table/list where `handlePatientClick` is used, add a small "Resumo IA" icon-button per patient that navigates to `/physician/patients/${patientId}?tab=ai-summary` (same as clicking patient but pre-selecting the AI summary tab), (2) In `PatientDetailPage.tsx`, check if URL has `tab=ai-summary` search param and pre-select that tab on mount (only if not already handled), (3) Run full backend test suite for regressions, (4) Run frontend typecheck and build
  - Verify: `cd frontend-hormonia && npx tsc --noEmit` green, `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/ -v` green with 0 regressions
  - Done when: Frontend typecheck green, dashboard has AI summary quick-access per patient, all backend flow tests pass with 0 regressions

## Files Likely Touched

- `backend-hormonia/app/services/ai/summary_data_aggregator.py`
- `backend-hormonia/app/services/ai/prompts/patient_summary.py`
- `backend-hormonia/tests/unit/services/flow/test_summary_integration.py` (new)
- `frontend-hormonia/src/pages/PhysicianDashboard.tsx`
- `frontend-hormonia/src/pages/PatientDetailPage.tsx`
