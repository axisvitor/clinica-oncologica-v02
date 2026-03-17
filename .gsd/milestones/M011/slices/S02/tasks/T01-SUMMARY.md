---
id: T01
parent: S02
milestone: M011
provides:
  - All dashboard/patient hooks meet staleTime ≥ 60s, refetchInterval ≥ 120s
  - All admin hooks meet staleTime ≥ 120s, refetchInterval ≥ 120s
  - Global default staleTime bumped from 30s to 60s
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
key_decisions: []
patterns_established:
  - "Dashboard/patient hooks: staleTime ≥ 60s, refetchInterval ≥ 120s"
  - "Admin hooks: staleTime ≥ 120s, refetchInterval ≥ 120s"
  - "Monitoring/real-time hooks are exempt from these thresholds"
observability_surfaces:
  - "rg 'staleTime|refetchInterval' audit across frontend-hormonia/src/ is the canonical diagnostic"
duration: 25m
verification_result: passed
completed_at: 2026-03-17
blocker_discovered: false
---

# T01: Sweep staleTime and refetchInterval values across all hooks

**Bumped staleTime/refetchInterval across 21 frontend hooks to meet R102/D020 request-discipline thresholds — monitoring hooks untouched**

## What Happened

Applied numeric literal bumps across 21 files in three categories:

1. **Global defaults** (`queryClient.ts`): Default staleTime 30s→60s, paginated preset staleTime 30s→60s. Updated all adjacent comments and header docs.

2. **Dashboard/Patient hooks** (11 files): All staleTime values bumped to ≥ 60s (60000ms), all refetchInterval values bumped to ≥ 120s (120000ms). Includes DashboardPage, useClinicalMetrics, useRiskPatients, useFlows (3 query instances), useFlowEngine, useMonthlyQuizStatus (2 instances), useMonthlyQuizAdmin, useMonthlyQuizAdminSecure, useSystemStats (hooks/ variant), AlertsPanel, RecentQuizCompletions.

3. **Admin hooks** (7 files): All staleTime values bumped to ≥ 120s (120000ms), all refetchInterval values bumped to ≥ 120s. Includes useUserStats, useUserList, useUserAdmin (both staleTime and default refreshInterval), AuditLogViewer, AdminUsersTab, AdminNavigationMenu, AdminPage.

4. **Other non-monitoring hooks** (2 files): NotificationCenter and DLQDashboard (2 query instances) — refetchInterval bumped to 120s.

5. **Comment sweep**: All adjacent comments updated to match new values. JSDoc examples in useUserStats, useUserList, useClinicalMetrics, useRiskPatients updated. queryClient.ts header comments about deduplication window updated from 30s to 60s.

Monitoring/real-time hooks were verified untouched via `git diff --name-only`.

## Verification

- `git diff --name-only -- 'frontend-hormonia/src/'` → exactly 21 source files modified
- `git diff --name-only | grep -E "HealthStatusMonitor|SystemStatus|SystemHealth|AgentSwarm|ClinicalMonitoringDashboard|AdminMonitoringTab|hooks/api/useSystemStats|whatsapp"` → no matches (monitoring hooks untouched)
- `rg "staleTime:" ... | grep -v monitoring` → all non-monitoring staleTime values ≥ 60000
- `rg "refetchInterval:" ... | grep -v monitoring` → all non-monitoring refetchInterval values ≥ 120000 or dynamic/false
- Slice-level verification (`tsc --noEmit`, `vite build`) deferred to T02

## Diagnostics

- Run `rg "staleTime|refetchInterval" --type ts --type-add 'tsx:*.tsx' --type tsx frontend-hormonia/src/` to audit all values
- Filter out monitoring hooks with: `grep -v features/system | grep -v features/monitoring | grep -v hive-mind | grep -v ClinicalMonitoring | grep -v AdminMonitoringTab | grep -v hooks/api/useSystemStats | grep -v features/whatsapp`
- In browser: Network tab should show ≥ 120s gaps between automatic refetch calls for non-monitoring endpoints

## Deviations

- Also bumped `useUserAdmin.refreshInterval` default from 30000→120000 — the plan didn't list this explicitly, but it's the value that flows into `useUserList` and `useUserStats` as their `refetchInterval`, so leaving it at 30s would have violated D020 at runtime.

## Known Issues

None

## Files Created/Modified

- `frontend-hormonia/src/lib/react-query/queryClient.ts` — Global default staleTime 30s→60s, paginated preset 30s→60s, comments updated
- `frontend-hormonia/src/pages/DashboardPage.tsx` — staleTime 30s→60s, refetchInterval 60s→120s
- `frontend-hormonia/src/hooks/api/useClinicalMetrics.ts` — staleTime 30s→60s, default refetchInterval 30s→120s, JSDoc updated
- `frontend-hormonia/src/hooks/api/useRiskPatients.ts` — default refetchInterval 60s→120s, JSDoc updated
- `frontend-hormonia/src/hooks/useFlows.ts` — useFlows + useFlowState staleTime 30s→60s, refetchInterval 60s→120s
- `frontend-hormonia/src/hooks/useFlowEngine.ts` — useFlowState staleTime 30s→60s, refetchInterval 60s→120s
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
