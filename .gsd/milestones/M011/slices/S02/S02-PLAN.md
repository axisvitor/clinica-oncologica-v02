# S02: Frontend request discipline

**Goal:** All dashboard/patient/admin hooks use staleTime ≥ 60s and refetchInterval ≥ 120s, reducing redundant requests to the backend. Monitoring hooks (system health, WhatsApp) stay as-is.
**Demo:** `tsc --noEmit` + `vite build` green. Grep audit confirms no staleTime < 60s or refetchInterval < 120s outside explicitly-skipped monitoring hooks.

## Must-Haves

- Global default staleTime bumped from 30s → 60s in `queryClient.ts`
- Dashboard/patient hooks: staleTime ≥ 60s, refetchInterval ≥ 120s
- Admin hooks: staleTime ≥ 120s, refetchInterval ≥ 120s (per D020)
- Monitoring/real-time hooks explicitly untouched (HealthStatusMonitor, SystemStatus, SystemHealth, AgentSwarm, ClinicalMonitoringDashboard, AdminMonitoringTab, WhatsApp hooks)
- Comments updated alongside values to avoid confusion
- `tsc --noEmit` + `vite build` green

## Verification

- `cd frontend-hormonia && npm ci && npx tsc --noEmit && npx vite build` — all green
- Grep audit: no staleTime below 60_000 (60s) outside monitoring hooks
- Grep audit: no refetchInterval below 120_000 (120s) outside monitoring hooks and `useSystemStats.ts`
- **Diagnostic check:** After build, run `rg "staleTime|refetchInterval" --type ts --type-add 'tsx:*.tsx' --type tsx frontend-hormonia/src/ | grep -v node_modules | grep -v features/system | grep -v features/monitoring | grep -v hive-mind | grep -v ClinicalMonitoring | grep -v AdminMonitoringTab | grep -v hooks/api/useSystemStats | grep -v features/whatsapp` and confirm no value below threshold — this surfaces any regressions or missed files.

## Tasks

- [x] **T01: Sweep staleTime and refetchInterval values across all hooks** `est:45m`
  - Why: R102 requires staleTime ≥ 60s and refetchInterval ≥ 120s for dashboard/patient/admin hooks. ~20 files need value bumps. This is the entire functional change of the slice.
  - Files: `frontend-hormonia/src/lib/react-query/queryClient.ts`, `frontend-hormonia/src/pages/DashboardPage.tsx`, `frontend-hormonia/src/hooks/api/useClinicalMetrics.ts`, `frontend-hormonia/src/hooks/api/useRiskPatients.ts`, `frontend-hormonia/src/hooks/useFlows.ts`, `frontend-hormonia/src/hooks/useFlowEngine.ts`, `frontend-hormonia/src/hooks/useMonthlyQuizStatus.ts`, `frontend-hormonia/src/hooks/useMonthlyQuizAdmin.ts`, `frontend-hormonia/src/hooks/useMonthlyQuizAdminSecure.ts`, `frontend-hormonia/src/hooks/useSystemStats.ts`, `frontend-hormonia/src/features/dashboard/AlertsPanel.tsx`, `frontend-hormonia/src/features/dashboard/RecentQuizCompletions.tsx`, `frontend-hormonia/src/hooks/admin/useUserStats.ts`, `frontend-hormonia/src/hooks/admin/useUserList.ts`, `frontend-hormonia/src/hooks/admin/useUserAdmin.ts`, `frontend-hormonia/src/features/admin/AuditLogViewer.tsx`, `frontend-hormonia/src/features/admin/tabs/AdminUsersTab.tsx`, `frontend-hormonia/src/features/admin/AdminNavigationMenu.tsx`, `frontend-hormonia/src/pages/AdminPage.tsx`, `frontend-hormonia/src/components/layout/NotificationCenter.tsx`, `frontend-hormonia/src/pages/DLQDashboard.tsx`
  - Do: Apply all value changes listed below. Update comments alongside values. Do NOT touch monitoring/real-time hooks (HealthStatusMonitor, SystemStatus, SystemHealth, AgentSwarm, ClinicalMonitoringDashboard, AdminMonitoringTab, useSystemStats in `hooks/api/`, WhatsApp hooks).
  - Verify: `rg "staleTime" --type ts --type-add 'tsx:*.tsx' --type tsx frontend-hormonia/src/` — visually confirm no dashboard/patient/admin hook has staleTime < 60s or refetchInterval < 120s
  - Done when: All ~20 files edited with correct values, comments updated, monitoring hooks untouched

- [x] **T02: Install dependencies and verify build** `est:15m`
  - Why: Worktree has no `node_modules`. Must install before running tsc/vite. This is the slice's terminal verification.
  - Files: `frontend-hormonia/package.json` (read-only)
  - Do: Run `cd frontend-hormonia && npm ci`, then `npx tsc --noEmit`, then `npx vite build`. Also run grep audit to confirm no staleTime < 60s or refetchInterval < 120s outside monitoring hooks.
  - Verify: All three commands exit 0. Grep audit clean.
  - Done when: `tsc --noEmit` green, `vite build` green, grep audit confirms R102 thresholds met

## Observability / Diagnostics

- **Runtime signal:** React Query devtools (if enabled) show staleTime/refetchInterval per query key. In production, Network tab polling frequency is the primary observable — requests should space ≥ 120s apart for non-monitoring queries.
- **Inspection surface:** `rg "staleTime|refetchInterval"` grep audit across `frontend-hormonia/src/` is the canonical diagnostic. Values below threshold outside monitoring hooks indicate regression.
- **Failure visibility:** If a hook's staleTime/refetchInterval regresses below threshold, users will see increased API traffic in browser Network tab and backend request logs. No structured error — this is a performance/cost signal, not a crash path.
- **Redaction:** No secrets or PII involved — all changes are numeric timing literals.

## Files Likely Touched

- `frontend-hormonia/src/lib/react-query/queryClient.ts`
- `frontend-hormonia/src/pages/DashboardPage.tsx`
- `frontend-hormonia/src/hooks/api/useClinicalMetrics.ts`
- `frontend-hormonia/src/hooks/api/useRiskPatients.ts`
- `frontend-hormonia/src/hooks/useFlows.ts`
- `frontend-hormonia/src/hooks/useFlowEngine.ts`
- `frontend-hormonia/src/hooks/useMonthlyQuizStatus.ts`
- `frontend-hormonia/src/hooks/useMonthlyQuizAdmin.ts`
- `frontend-hormonia/src/hooks/useMonthlyQuizAdminSecure.ts`
- `frontend-hormonia/src/hooks/useSystemStats.ts`
- `frontend-hormonia/src/features/dashboard/AlertsPanel.tsx`
- `frontend-hormonia/src/features/dashboard/RecentQuizCompletions.tsx`
- `frontend-hormonia/src/hooks/admin/useUserStats.ts`
- `frontend-hormonia/src/hooks/admin/useUserList.ts`
- `frontend-hormonia/src/hooks/admin/useUserAdmin.ts`
- `frontend-hormonia/src/features/admin/AuditLogViewer.tsx`
- `frontend-hormonia/src/features/admin/tabs/AdminUsersTab.tsx`
- `frontend-hormonia/src/features/admin/AdminNavigationMenu.tsx`
- `frontend-hormonia/src/pages/AdminPage.tsx`
- `frontend-hormonia/src/components/layout/NotificationCenter.tsx`
- `frontend-hormonia/src/pages/DLQDashboard.tsx`
