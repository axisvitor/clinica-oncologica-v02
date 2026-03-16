# S06 — Research: Resumo mensal por IA integrado ao dashboard

**Date:** 2026-03-16

## Summary

The backend infrastructure for AI summary generation is **already fully built**: `PatientSummaryService` (669 lines), `SummaryDataAggregator`, prompt templates, `PatientSummary` model with Alembic migration, Pydantic schemas, and a complete REST API at `/api/v2/ai/summary`. The frontend also has a working `PatientAISummary` component (593 lines) in the `PatientDetailPage` under the "Resumo IA" tab, with hooks (`usePatientSummary`), API client methods, PDF export, and feature flags (`FEATURES.AI_SUMMARY`).

**The critical gap is data integration**: the `SummaryDataAggregator` does NOT consume `patient_flow_responses` (from S04) or quiz alert data with recommendations (from S05). It aggregates only `QuizResponse`, `Message`, and `Alert` models — missing the structured free-text responses that are the core value of the monthly summary. Additionally, the aggregator's alert formatting references `alert.message` which doesn't exist on the `Alert` model (it has `description`), and misses the `recommendation` field from JSONB `data`.

The work is: (1) wire `patient_flow_responses` into the aggregator, (2) enrich alert aggregation with recommendation/title from S05's JSONB data, (3) update the prompt to include flow responses, (4) write focused tests proving the integration, and (5) verify the frontend renders it. No new API endpoints, no new models, no new frontend components — everything is plumbing existing pieces together.

## Recommendation

**Light-to-targeted approach**: the service, API, frontend, schemas, and models all exist. The work is wiring the S04/S05 data sources into the existing aggregator and prompt, then proving it with focused tests. No architectural decisions needed.

Build order: aggregator integration first (it's the core gap), then prompt update, then tests. Frontend verification is last since the component already renders `SummaryContent` — it just needs real data flowing through.

## Implementation Landscape

### Key Files

- `backend-hormonia/app/services/ai/summary_data_aggregator.py` — **Main change target.** Currently aggregates `QuizResponse`, `Message`, `Alert` but NOT `PatientFlowResponse`. Needs: (1) import and query `PatientFlowResponse`, (2) add `flow_responses` field to `AggregatedPatientData`, (3) format flow responses for prompt, (4) fix alert aggregation to use `description` instead of non-existent `message` attr, and extract `recommendation`/`title` from `alert.data` JSONB
- `backend-hormonia/app/services/ai/prompts/patient_summary.py` — Prompt needs a new section for flow responses (free-text patient replies with day/context). Currently has `{quiz_responses}`, `{messages_summary}`, `{alerts}` — needs `{flow_responses}` section
- `backend-hormonia/app/services/ai/patient_summary_service.py` — 669 lines, mostly complete. No structural changes needed — just passes `AggregatedPatientData.to_prompt_context()` to the prompt template
- `backend-hormonia/app/models/patient_flow_response.py` — S04 model ready for consumption: `patient_id`, `day_number`, `message_index`, `response_text`, `responded_at`, nullable `flow_state_id`
- `backend-hormonia/app/models/alert.py` — Has `description` column (NOT `message`), `data` JSONB with `rule_name`, `recommendation`, `quiz_session_id`, `triggered_rule_id` from S05
- `backend-hormonia/app/api/v2/routers/ai/summary.py` — REST API already complete: `POST /api/v2/ai/summary`, `GET /summary/patient/{id}`, `GET /summary/{id}`, `GET /summary/{id}/pdf`. No changes needed
- `backend-hormonia/app/schemas/v2/patient_summary.py` — Pydantic schemas complete: `SummaryContent`, `GenerateSummaryRequest`, `PatientSummaryResponse`. No changes needed
- `frontend-hormonia/src/features/ai/PatientAISummary.tsx` — 593-line component already renders summary sections (overview, quiz findings, health concerns, engagement, compliance, recommendations). Already mounted in `PatientDetailPage` under "Resumo IA" tab behind `FEATURES.AI_SUMMARY` flag. No changes needed unless we want dashboard-level access
- `frontend-hormonia/src/hooks/usePatientSummary.ts` — React Query hooks (`useGenerateSummary`, `usePatientSummaries`, `usePatientSummaryManager`) already wrap the API. No changes needed
- `frontend-hormonia/src/lib/api-client/ai.ts` — API client methods (`generateSummary`, `getSummaries`, `getSummary`, `exportSummaryPdf`) already implemented. No changes needed
- `frontend-hormonia/src/pages/PhysicianDashboard.tsx` — Currently shows patients, insights, analytics tabs but has NO summary tab/section. The summary is accessible via `PatientDetailPage` only. For the "médico acessa resumo no dashboard" requirement, either add a summary button/link per patient in the risk table, or add a "Resumo IA" access point in the dashboard.
- `frontend-hormonia/src/pages/PatientDetailPage.tsx` — Already imports `PatientAISummary` and renders it in the "ai-summary" tab with `canAccessAiSummary` guard

### Specific Bugs/Gaps in Existing Code

1. **`summary_data_aggregator.py` L237**: `"message": alert.message if hasattr(alert, "message") else str(alert)` — `Alert` model has no `message` attribute. The `hasattr` check would return False and fall back to `str(alert)` which produces `<Alert(patient_id=..., type=..., severity=...)>`. Should use `alert.description`.
2. **Missing alert recommendation in aggregation**: S05 added `recommendation` to `alert.data` JSONB and `_serialize_alert()` projects it. The aggregator doesn't extract it.
3. **Missing flow responses entirely**: `patient_flow_responses` table created in S04 is not queried by the aggregator. This is the primary data gap.
4. **Prompt template has no flow response section**: The prompt template formats quiz responses and messages but doesn't include patient free-text flow responses with day context.

### Build Order

1. **Aggregator integration** — Wire `PatientFlowResponse` into `SummaryDataAggregator`: add `_aggregate_flow_responses()` method, add field to `AggregatedPatientData`, fix alert `message` → `description` bug, extract recommendation from JSONB. This unblocks everything else.
2. **Prompt update** — Add `{flow_responses}` section to `PATIENT_SUMMARY_PROMPT` and `to_prompt_context()`. Keep the existing JSON output schema unchanged — flow responses feed into the existing `overview`, `health_concerns`, and `recommendations` sections.
3. **Tests** — Focused tests proving: (a) aggregator queries `PatientFlowResponse` correctly, (b) alert description and recommendation are formatted, (c) flow responses appear in prompt context, (d) end-to-end summary generation with flow data. Use mock DB pattern from S04/S05 tests.
4. **Frontend verification** — The component already renders `SummaryContent` correctly. The slice should verify the "Resumo IA" tab is accessible from the physician dashboard flow (PhysicianDashboard → patient click → PatientDetailPage → "Resumo IA" tab). If R063 requires dashboard-level access, add a minimal "Gerar Resumo" button per patient or a link to the patient detail AI summary tab.

### Verification Approach

- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_summary_integration.py -v` — new focused test file
- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/ -v` — no regressions across 168+ existing tests
- `cd frontend-hormonia && npx tsc --noEmit` — typecheck green
- `cd frontend-hormonia && npm run build` — build green (if it was green before)
- Diagnostic: verify aggregator formats flow responses with day context in prompt

## Constraints

- `PatientSummaryService` uses Gemini via `genai.Client` — tests must mock AI calls, never hit real API
- The existing `SummaryContent` Pydantic schema and frontend types must NOT change shape — flow response data feeds into existing fields (`overview`, `health_concerns`, `recommendations`) via the AI prompt, not via new schema fields
- The `patient_flow_responses` composite index `ix_pfr_patient_responded` on `(patient_id, responded_at)` is optimized for period queries — aggregator should use this pattern
- Alert model has `description` column, NOT `message` — this is a latent bug in the aggregator

## Common Pitfalls

- **Changing SummaryContent schema** — The frontend types in `types/api.ts` mirror the backend schema. Adding new fields would require frontend type updates and component changes. Instead, feed flow responses into the AI prompt and let the AI incorporate them into the existing schema fields.
- **Alert.message confusion** — The aggregator references `alert.message` which doesn't exist. The fix is `alert.description` for the text and `(alert.data or {}).get("recommendation", "")` for the recommendation.
- **Over-engineering the frontend** — The `PatientAISummary` component is already 593 lines and fully functional. The path from physician dashboard to summary exists via patient click → PatientDetailPage → "Resumo IA" tab. Adding a massive new dashboard component is unnecessary.
