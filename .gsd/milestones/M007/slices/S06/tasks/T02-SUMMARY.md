---
id: T02
parent: S06
milestone: M007
provides:
  - Quick-access "Resumo IA" Brain icon button per patient in PhysicianDashboard risk table
  - Direct navigation to PatientDetailPage with ?tab=ai-summary pre-selected
key_files:
  - frontend-hormonia/src/features/dashboard/components/physician/PhysicianRiskTable.tsx
  - frontend-hormonia/src/pages/PhysicianDashboard.tsx
key_decisions:
  - Button placed in Ações column alongside existing "Detalhes" button, not as a separate column
  - onAISummaryClick prop is optional — table works without it for backward compatibility
patterns_established:
  - Ghost icon button with Tooltip for secondary per-row actions in risk table
observability_surfaces:
  - aria-label="Ver Resumo IA" on Brain icon button in PhysicianRiskTable rows
duration: 8m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T02: Add dashboard AI summary access and run full verification

**Added "Resumo IA" Brain icon button per patient in PhysicianDashboard risk table with full regression verification green**

## What Happened

Modified `PhysicianRiskTable` to accept an optional `onAISummaryClick` callback and render a Brain icon button with tooltip "Ver Resumo IA" in the Ações column next to the existing "Detalhes" button. The button uses `e.stopPropagation()` to prevent row click interference. In `PhysicianDashboard`, added `handleAISummaryClick` that navigates to `/physician/patients/${patientId}?tab=ai-summary` and wired it as the `onAISummaryClick` prop. The `PatientDetailPage` already reads `searchParams.get('tab')` and uses it as `defaultValue` for the Tabs component, so `?tab=ai-summary` automatically opens the AI summary tab — no changes needed there.

## Verification

- `cd frontend-hormonia && npx tsc --noEmit` — ✅ green (only pre-existing e2e playwright config errors, 0 new errors)
- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/ -v` — ✅ 181 passed, 4 skipped, 1 pre-existing failure (sequencing.py line-count contract), 0 regressions from S06 work
- `cd backend-hormonia && python3 -m pytest tests/unit/services/flow/test_summary_integration.py -v` — ✅ 13/13 passed
- Slice verification: all 4 checks pass (T01 tests green, flow suite green, typecheck green, aggregator `to_prompt_context()` includes `flow_responses` key confirmed in T01)

## Diagnostics

- In browser: PhysicianRiskTable Ações column shows a Brain icon button with `aria-label="Ver Resumo IA"` per patient row
- Clicking the Brain icon navigates to `/physician/patients/${patientId}?tab=ai-summary`
- If button is absent, check `onAISummaryClick` prop wiring in PhysicianDashboard.tsx

## Deviations

- Modified `PhysicianRiskTable.tsx` (component file) rather than inlining the button directly in `PhysicianDashboard.tsx` — cleaner separation since the table owns its row rendering.

## Known Issues

- Pre-existing: `test_split_files_under_500_lines` fails because `sequencing.py` is 521 lines (not from S06)
- Pre-existing: 6 e2e playwright config TS errors (process.env index signature access)

## Files Created/Modified

- `frontend-hormonia/src/features/dashboard/components/physician/PhysicianRiskTable.tsx` — added Brain icon import, Tooltip imports, optional `onAISummaryClick` prop, and Brain icon button with tooltip in Ações column
- `frontend-hormonia/src/pages/PhysicianDashboard.tsx` — added `handleAISummaryClick` callback and wired `onAISummaryClick` prop on `<PhysicianRiskTable>`
- `.gsd/milestones/M007/slices/S06/tasks/T02-PLAN.md` — added Observability Impact section
- `.gsd/milestones/M007/slices/S06/S06-PLAN.md` — marked T02 as [x]
