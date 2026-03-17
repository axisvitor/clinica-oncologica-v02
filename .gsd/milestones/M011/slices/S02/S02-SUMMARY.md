---
id: S02
parent: M011
milestone: M011
provides:
  - All dashboard/patient hooks use staleTime ≥ 60s and refetchInterval ≥ 120s
  - All admin hooks use staleTime ≥ 120s and refetchInterval ≥ 120s
  - Global default staleTime bumped from 30s to 60s in queryClient.ts
  - tsc --noEmit and vite build green after all changes
requires:
  - slice: none
    provides: independent slice
affects:
  - S03
key_files:
  - frontend-hormonia/src/lib/react-query/queryClient.ts
  - frontend-hormonia/src/pages/DashboardPage.tsx
  - frontend-hormonia/src/hooks/api/useClinicalMetrics.ts
  - frontend-hormonia/src/hooks/api/useRiskPatients.ts
  - frontend-hormonia/src/hooks/useFlows.ts
  - frontend-hormonia/src/hooks/useFlowEngine.ts
  - frontend-hormonia/src/hooks/useMonthlyQuizStatus.ts
  - frontend-hormonia/src/hooks/useMonthlyQuizAdmin.ts
  - frontend-hormonia/src/hooks/useMonthlyQuizAdminSecure.ts
  - frontend-hormonia/src/hooks/useSystemStats.ts
  - frontend-hormonia/src/features/dashboard/AlertsPanel.tsx
  - frontend-hormonia/src/features/dashboard/RecentQuizCompletions.tsx
  - frontend-hormonia/src/hooks/admin/useUserStats.ts
  - frontend-hormonia/src/hooks/admin/useUserList.ts
  - frontend-hormonia/src/hooks/admin/useUserAdmin.ts
  - frontend-hormonia/src/features/admin/AuditLogViewer.tsx
  - frontend-hormonia/src/features/admin/tabs/AdminUsersTab.tsx
  - frontend-hormonia/src/features/admin/AdminNavigationMenu.tsx
  - frontend-hormonia/src/pages/AdminPage.tsx
  - frontend-hormonia/src/components/layout/NotificationCenter.tsx
  - frontend-hormonia/src/pages/DLQDashboard.tsx
  - frontend-hormonia/tests/e2e/playwright.config.e2e.ts
key_decisions:
  - D020 — Frontend staleTime discipline thresholds (≥ 60s dashboard, ≥ 120s admin)
patterns_established:
  - "Dashboard/patient hooks: staleTime ≥ 60s (60000ms), refetchInterval ≥ 120s (120000ms)"
  - "Admin hooks: staleTime ≥ 120s (120000ms), refetchInterval ≥ 120s (120000ms)"
  - "Monitoring/real-time hooks (system health, WhatsApp, agent swarm) are explicitly exempt from these thresholds"
  - "queryPresets.realtime in queryClient.ts is the only allowed sub-threshold preset definition"
observability_surfaces:
  - "rg 'staleTime|refetchInterval' across frontend-hormonia/src/ filtered by monitoring exclusions is the canonical audit command"
  - "Browser Network tab: non-monitoring requests should space ≥ 120s apart"
drill_down_paths:
  - .gsd/milestones/M011/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M011/slices/S02/tasks/T02-SUMMARY.md
duration: 37m
verification_result: passed
completed_at: 2026-03-17
---

# S02: Frontend request discipline

**Normalized staleTime and refetchInterval across 21 frontend hooks to eliminate redundant backend requests — dashboard ≥ 60s/120s, admin ≥ 120s/120s, monitoring untouched**

## What Happened

The slice swept all React Query timing values across the frontend to enforce R102 request-discipline thresholds, done in two tasks:

**T01 (value sweep):** Applied numeric literal bumps across 21 files in three categories. Global default staleTime in `queryClient.ts` went from 30s→60s. Dashboard/patient hooks (11 files including DashboardPage, useClinicalMetrics, useRiskPatients, useFlows, useFlowEngine, useMonthlyQuiz*, AlertsPanel, RecentQuizCompletions) got staleTime ≥ 60s and refetchInterval ≥ 120s. Admin hooks (7 files including useUserStats, useUserList, useUserAdmin, AuditLogViewer, AdminUsersTab, AdminNavigationMenu, AdminPage) got staleTime ≥ 120s and refetchInterval ≥ 120s. Two remaining non-monitoring hooks (NotificationCenter, DLQDashboard) got refetchInterval ≥ 120s. All adjacent comments and JSDoc examples were updated to match new values. Monitoring/real-time hooks (HealthStatusMonitor, SystemStatus, SystemHealth, AgentSwarm, ClinicalMonitoringDashboard, AdminMonitoringTab, hooks/api/useSystemStats, WhatsApp) were verified untouched via git diff.

**T02 (build verification):** Installed 542 packages via `npm ci`. Fixed 6 pre-existing TS errors in `tests/e2e/playwright.config.e2e.ts` (process.env dot notation → bracket notation for `noPropertyAccessFromIndexSignature`). Ran `tsc --noEmit` (exit 0), `vite build` (exit 0, 4741 modules), and four-pass grep audit confirming no staleTime < 60s or refetchInterval < 120s outside monitoring exclusions. Two files with sub-threshold values were identified as non-issues: `queryPresets.realtime` (explicitly a monitoring preset) and dead code files (`useOptimizedQuery.helpers.ts`, `ProductionProvider.tsx`) with zero imports.

## Verification

| Check | Result |
|-------|--------|
| `tsc --noEmit` | ✅ exit 0, zero errors |
| `vite build` | ✅ exit 0, 4741 modules, dist/ produced |
| staleTime < 60000 grep (outside monitoring) | ✅ empty — no violations |
| refetchInterval < 120000 grep (outside monitoring) | ✅ empty — no violations |
| Monitoring hooks untouched | ✅ git diff confirms zero changes to system/monitoring/whatsapp/hive-mind |
| 21 files modified | ✅ exact count confirmed via git diff |

## Requirements Advanced

- R102 — All dashboard/patient hooks now use staleTime ≥ 60s and refetchInterval ≥ 120s; all admin hooks use staleTime ≥ 120s and refetchInterval ≥ 120s. Monitoring real-time hooks preserved at lower thresholds as specified.

## Requirements Validated

- none — R102 validation requires S03 integrated verification to confirm no regressions across the full stack

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- **useUserAdmin.refreshInterval default** bumped from 30000→120000 — not explicitly listed in the plan, but this value flows into useUserList and useUserStats as their refetchInterval at runtime, so leaving it at 30s would have violated D020.
- **playwright.config.e2e.ts fix** — 6 pre-existing TS errors (process.env.CI → process.env['CI']) were fixed to unblock tsc --noEmit. These errors pre-date S02 and are unrelated to the timing changes.

## Known Limitations

- `useOptimizedQuery.helpers.ts` has a 30s staleTime fallback — dead code today (zero imports) but should be cleaned up if reactivated.
- `ProductionProvider.tsx` has 1s dev-mode staleTime — also dead code (zero imports), same cleanup note.
- 5 npm vulnerabilities (2 moderate, 3 high) — pre-existing, not related to S02 changes.

## Follow-ups

- none — S03 handles integrated verification

## Files Created/Modified

- `frontend-hormonia/src/lib/react-query/queryClient.ts` — Global default staleTime 30s→60s, paginated preset 30s→60s, comments updated
- `frontend-hormonia/src/pages/DashboardPage.tsx` — staleTime 30s→60s, refetchInterval 60s→120s
- `frontend-hormonia/src/hooks/api/useClinicalMetrics.ts` — staleTime 30s→60s, default refetchInterval 30s→120s, JSDoc updated
- `frontend-hormonia/src/hooks/api/useRiskPatients.ts` — default refetchInterval 60s→120s, JSDoc updated
- `frontend-hormonia/src/hooks/useFlows.ts` — three query instances: staleTime 30s→60s, refetchInterval 60s→120s
- `frontend-hormonia/src/hooks/useFlowEngine.ts` — staleTime 30s→60s, refetchInterval 60s→120s
- `frontend-hormonia/src/hooks/useMonthlyQuizStatus.ts` — two staleTime 30s→60s
- `frontend-hormonia/src/hooks/useMonthlyQuizAdmin.ts` — staleTime 30s→60s
- `frontend-hormonia/src/hooks/useMonthlyQuizAdminSecure.ts` — staleTime 30s→60s
- `frontend-hormonia/src/hooks/useSystemStats.ts` — staleTime 10s→60s, refreshInterval default 30s→120s
- `frontend-hormonia/src/features/dashboard/AlertsPanel.tsx` — refetchInterval 30s→120s
- `frontend-hormonia/src/features/dashboard/RecentQuizCompletions.tsx` — refetchInterval 60s→120s
- `frontend-hormonia/src/hooks/admin/useUserStats.ts` — staleTime 10s→120s, JSDoc updated
- `frontend-hormonia/src/hooks/admin/useUserList.ts` — staleTime 10s→120s, JSDoc updated
- `frontend-hormonia/src/hooks/admin/useUserAdmin.ts` — staleTime 30s→120s, default refreshInterval 30s→120s
- `frontend-hormonia/src/features/admin/AuditLogViewer.tsx` — refetchInterval 30s→120s
- `frontend-hormonia/src/features/admin/tabs/AdminUsersTab.tsx` — refetchInterval 30s→120s
- `frontend-hormonia/src/features/admin/AdminNavigationMenu.tsx` — refetchInterval 60s→120s
- `frontend-hormonia/src/pages/AdminPage.tsx` — refetchInterval 30s→120s
- `frontend-hormonia/src/components/layout/NotificationCenter.tsx` — refetchInterval 30s→120s
- `frontend-hormonia/src/pages/DLQDashboard.tsx` — two refetchInterval 30s→120s
- `frontend-hormonia/tests/e2e/playwright.config.e2e.ts` — fixed process.env bracket notation for TS compliance

## Forward Intelligence

### What the next slice should know
- All 21 files are pure numeric literal changes with updated comments. No structural or logic changes. S03 verification should focus on confirming `tsc --noEmit` + `vite build` green (already proven here) and that response shapes are unchanged.

### What's fragile
- `useOptimizedQuery.helpers.ts` and `ProductionProvider.tsx` contain sub-threshold staleTime values but are dead code (zero imports). If anyone re-imports them, the grep audit will flag violations.
- `queryPresets.realtime` in `queryClient.ts` has staleTime=10s and refetchInterval=10s — this is intentionally the monitoring preset and must stay sub-threshold. The grep audit excludes it by context, not by value.

### Authoritative diagnostics
- `rg "staleTime|refetchInterval" --type ts --type-add 'tsx:*.tsx' --type tsx frontend-hormonia/src/ | grep -v features/system | grep -v features/monitoring | grep -v hive-mind | grep -v ClinicalMonitoring | grep -v AdminMonitoringTab | grep -v hooks/api/useSystemStats | grep -v features/whatsapp` — canonical audit command, all values should be ≥ 60000 (staleTime) or ≥ 120000 (refetchInterval)

### What assumptions changed
- None — all assumptions held. The ~20 files estimate was accurate (21 files touched).
