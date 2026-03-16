---
estimated_steps: 4
estimated_files: 2
---

# T02: Add dashboard AI summary access and run full verification

**Slice:** S06 — Resumo mensal por IA integrado ao dashboard
**Milestone:** M007

## Description

The path from PhysicianDashboard to "Resumo IA" already works: click patient → `PatientDetailPage` → "Resumo IA" tab. URL param `?tab=ai-summary` is already handled by `PatientDetailPage` (reads `searchParams.get('tab')` as `defaultValue`). This task adds a small "Resumo IA" quick-access button per patient in the dashboard's patient list that navigates directly to `/physician/patients/${patientId}?tab=ai-summary`, improving discoverability for R063. Then runs full regression verification.

## Steps

1. **Add "Resumo IA" quick-access button in PhysicianDashboard**: In the patient risk table/list section where `handlePatientClick` is already used (around line 598 `onPatientClick={handlePatientClick}`), add a small icon button (use `FileText` or `Brain` icon from lucide-react) per patient row that calls `navigate(\`/physician/patients/${patientId}?tab=ai-summary\`)`. Style it as a ghost button with tooltip text "Ver Resumo IA". Keep it subtle — the main click still goes to patient overview.

2. **Run frontend typecheck**: `cd frontend-hormonia && npx tsc --noEmit` — must pass (only pre-existing e2e playwright errors expected, no new errors).

3. **Run full backend flow test suite**: `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/ -v` — verify 0 regressions across all 168+ existing tests plus the new T01 tests.

4. **Verify T01 tests specifically**: `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_summary_integration.py -v` — all pass (confirming T01 work is stable).

## Must-Haves

- [ ] PhysicianDashboard has a "Resumo IA" quick-access button per patient that navigates to `?tab=ai-summary`
- [ ] Frontend typecheck green (no new errors)
- [ ] Backend flow tests pass with 0 regressions
- [ ] T01 summary integration tests pass

## Verification

- `cd frontend-hormonia && npx tsc --noEmit` — green (pre-existing e2e errors only)
- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/ -v` — all tests pass, 0 regressions
- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_summary_integration.py -v` — all pass

## Inputs

- `frontend-hormonia/src/pages/PhysicianDashboard.tsx` — already imports `useNavigate`, has `handlePatientClick` callback at L338-342, patient list around L598
- `frontend-hormonia/src/pages/PatientDetailPage.tsx` — already reads `searchParams.get('tab')` at L32 and uses it as `defaultValue={defaultTab}` at L128; value `"ai-summary"` already matches the TabsTrigger at L133. **No changes needed to this file.**
- T01 output: `tests/unit/services/flow/test_summary_integration.py` exists and passes
- Available icons in PhysicianDashboard imports: `FileText`, `Brain`, or similar from `lucide-react` (check existing imports)
- Existing lucide imports at L4-13: `AlertCircle, Activity, Users, Bell, Search, TrendingUp, Calendar, ChevronDown, Download, Filter`

## Expected Output

- `frontend-hormonia/src/pages/PhysicianDashboard.tsx` — modified: added "Resumo IA" icon button per patient in the risk table/list
- All verification commands green
