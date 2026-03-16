# S06: Resumo mensal por IA integrado ao dashboard — UAT

**Milestone:** M007
**Written:** 2026-03-16

## UAT Type

- UAT mode: mixed (artifact-driven for backend aggregator + AI prompt; live-runtime for dashboard navigation)
- Why this mode is sufficient: The backend data aggregation and prompt formatting are fully testable via unit tests and inspection of `to_prompt_context()` output. The dashboard navigation requires visual confirmation that the Brain icon exists and routes correctly to the AI summary tab.

## Preconditions

- Backend running (`cd backend-hormonia && uvicorn app.main:app --reload`)
- Frontend dev server running (`cd frontend-hormonia && npm run dev`)
- At least one patient with flow responses in `patient_flow_responses` table (from S04 daily check-in interactions)
- At least one patient with quiz alerts (from S05 quiz evaluation)
- Logged in as a physician user in the dashboard

## Smoke Test

1. Open PhysicianDashboard → see patient risk table → confirm each patient row has a Brain icon in the Ações column
2. Click the Brain icon → confirm navigation to PatientDetailPage with the "Resumo IA" tab pre-selected

## Test Cases

### 1. Brain icon visibility in PhysicianDashboard

1. Navigate to `/physician/dashboard` (logged in as physician)
2. Locate the patient risk table showing patient rows
3. In each row, look at the "Ações" column
4. **Expected:** Each row shows a Brain icon button (hover tooltip: "Ver Resumo IA") next to the existing "Detalhes" button

### 2. Brain icon navigates to AI summary tab

1. In the PhysicianDashboard patient risk table, click the Brain icon for a patient
2. **Expected:** Browser navigates to `/physician/patients/{patientId}?tab=ai-summary`
3. **Expected:** PatientDetailPage opens with the "Resumo IA" tab already selected (not the default "overview" tab)

### 3. Clicking "Detalhes" still works independently

1. In the same patient row, click the "Detalhes" button (not the Brain icon)
2. **Expected:** Navigates to PatientDetailPage with the default "overview" tab selected, not the AI summary tab

### 4. AI summary generates with flow response data

1. Navigate to a patient's AI summary tab (via Brain icon or manually appending `?tab=ai-summary`)
2. Click "Gerar Resumo" (or equivalent summary generation trigger)
3. **Expected:** The generated summary includes references to patient free-text replies from daily check-ins (the flow responses), not just quiz data and messages
4. **Expected:** The summary includes alert information with severity and recommendations when applicable

### 5. AI summary with no flow responses

1. Navigate to the AI summary tab for a patient who has no flow responses (new patient or one who hasn't replied to daily messages)
2. Generate a summary
3. **Expected:** Summary generates without error; the flow responses section shows "Nenhuma resposta de acompanhamento no período." or equivalent. No crash, no missing section.

### 6. Alert data includes recommendation in summary context

1. Find a patient who has quiz alerts with recommendations (created by QuizResponseEvaluator in S05)
2. Generate an AI summary for that patient
3. **Expected:** The alert section in the summary includes the recommendation text (e.g., "Avaliar antiemético imediatamente") alongside the alert severity and description

## Edge Cases

### Patient with >20 flow responses in the period

1. Find or create a patient with more than 20 flow responses in the analysis period
2. Generate the AI summary
3. **Expected:** Only the 20 most recent responses are included in the AI prompt context; a "... e mais N respostas anteriores" note appears in the formatted flow_responses section. Summary still generates successfully.

### Patient with no doctor assigned (doctor_id is NULL)

1. If a patient has no `doctor_id`, navigate to their AI summary
2. **Expected:** Summary generation proceeds normally — the aggregator queries by patient_id, not doctor_id. Alerts may not have generated notifications (S05 skips notification when doctor_id is NULL), but the summary itself uses alert data directly.

### Brain icon click doesn't trigger row click

1. Click the Brain icon for a patient
2. **Expected:** Only navigation to `?tab=ai-summary` occurs. The row's `onPatientClick` handler does NOT fire simultaneously (prevented by `e.stopPropagation()`).

## Failure Signals

- Brain icon missing from PhysicianRiskTable → check `onAISummaryClick` prop wiring in PhysicianDashboard.tsx
- AI summary tab not pre-selected after Brain icon click → check `searchParams.get('tab')` in PatientDetailPage.tsx matches `ai-summary` exactly (case-sensitive)
- Summary generation fails or excludes flow responses → check `SummaryDataAggregator._aggregate_flow_responses()` query against `patient_flow_responses` table; verify table has data for the patient and date range
- Alert formatting shows "undefined" or empty descriptions → check `alert.description` column has data (not `alert.message` which was the old bug); verify `alert.data` JSONB contains `recommendation` and `rule_name` keys
- Console error on Brain icon click → check lucide-react `Brain` import and `Tooltip` component imports in PhysicianRiskTable.tsx

## Requirements Proved By This UAT

- R063 — "Médico acessa resumo no dashboard" — Test cases 1-4 prove the doctor can access the AI summary from the dashboard with flow response data and enriched alerts included in the summary context

## Not Proven By This UAT

- Subjective quality of AI-generated summaries for actual clinical decision-making — requires ongoing human evaluation by physicians over multiple real patient summaries
- Performance of `_aggregate_flow_responses()` under high patient volume (100+ responses per patient across many concurrent requests) — requires load testing
- Gemini 2.5 Flash prompt response quality with the new `{flow_responses}` section — the prompt is well-structured but LLM output quality is inherently variable

## Notes for Tester

- The `PatientSummaryService` makes real Gemini API calls — you need a valid `GOOGLE_AI_API_KEY` or `GEMINI_API_KEY` env var. Without it, summary generation will fail with an API error (this is expected — the service, not S06, owns the API integration).
- The Brain icon uses lucide-react's `Brain` icon — it's a small brain-shaped icon, not text. Look for it next to the "Detalhes" button.
- S06 did NOT modify `PatientSummaryService` or `PatientDetailPage` — if issues exist in those components, they are pre-existing, not S06 regressions.
- The 1 pre-existing test failure (`sequencing.py` >500 lines) is unrelated to S06 — ignore it.
