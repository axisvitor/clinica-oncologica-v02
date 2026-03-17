# S02: Frontend Request Discipline — Research

**Date:** 2026-03-17
**Depth:** Light — known technology (React Query), clear scope, value adjustments across known files.

## Summary

R102 requires dashboard/patient hooks to use `staleTime ≥ 60s` and `refetchInterval ≥ 120s`. D020 adds `≥ 120s` for admin hooks and `Infinity` for static config. The codebase has ~50 `staleTime`/`refetchInterval` declarations across ~30 files. After auditing every occurrence, the work is mechanical: ~20 hooks need value bumps, ~10 are already adequate, and ~10 are real-time monitoring (keep as-is). The global default in `queryClient.ts` also needs a bump from 30s → 60s.

No structural changes, no new dependencies, no type changes. Pure config value adjustments.

## Recommendation

Single task: sweep all hooks and bump values to meet thresholds. Group changes by category (dashboard/patient → admin → global default). Skip monitoring hooks explicitly (HealthStatusMonitor, SystemStatus, ClinicalMonitoringDashboard, WhatsApp instances). Verify with `tsc --noEmit` + `vite build`.

## Implementation Landscape

### Key Files

**Global config (change default):**
- `frontend-hormonia/src/lib/react-query/queryClient.ts` — default `staleTime: 30_000` → `60_000`. Preset `paginated.staleTime: 30_000` → `60_000`. Presets `realtime` and `static` stay as-is.

**Dashboard/Patient hooks (staleTime ≥ 60s, refetchInterval ≥ 120s):**
- `frontend-hormonia/src/pages/DashboardPage.tsx:46-47` — staleTime 30s→60s, refetchInterval 60s→120s
- `frontend-hormonia/src/hooks/api/useClinicalMetrics.ts:66,89-90` — default refetchInterval 30s→120s, staleTime 30s→60s
- `frontend-hormonia/src/hooks/api/useRiskPatients.ts:48,72-73` — default refetchInterval 60s→120s (staleTime 60s OK)
- `frontend-hormonia/src/hooks/useFlows.ts:77-78,202-203` — useFlows: staleTime 30s→60s, refetchInterval 60s→120s. useFlowState: staleTime 30s→60s, refetchInterval 60s→120s
- `frontend-hormonia/src/hooks/useFlowEngine.ts:71-72` — useFlowState: staleTime 30s→60s, refetchInterval 60s→120s
- `frontend-hormonia/src/hooks/useMonthlyQuizStatus.ts:84,135` — two staleTime 30s→60s
- `frontend-hormonia/src/hooks/useMonthlyQuizAdmin.ts:91` — staleTime 30s→60s
- `frontend-hormonia/src/hooks/useMonthlyQuizAdminSecure.ts:140` — staleTime 30s→60s
- `frontend-hormonia/src/hooks/useSystemStats.ts:34-35` — staleTime 10s→60s, refreshInterval default 30s→120s
- `frontend-hormonia/src/features/dashboard/AlertsPanel.tsx:64` — refetchInterval 30s→120s
- `frontend-hormonia/src/features/dashboard/RecentQuizCompletions.tsx:30` — refetchInterval 60s→120s

**Admin hooks (staleTime ≥ 120s, refetchInterval ≥ 120s per D020):**
- `frontend-hormonia/src/hooks/admin/useUserStats.ts:153` — staleTime 10s→120s
- `frontend-hormonia/src/hooks/admin/useUserList.ts:129` — staleTime 10s→120s
- `frontend-hormonia/src/hooks/admin/useUserAdmin.ts:47` — staleTime 30s→120s
- `frontend-hormonia/src/features/admin/AuditLogViewer.tsx:396` — refetchInterval 30s→120s
- `frontend-hormonia/src/features/admin/tabs/AdminUsersTab.tsx:24` — refetchInterval 30s→120s
- `frontend-hormonia/src/features/admin/AdminNavigationMenu.tsx:254` — refetchInterval 60s→120s
- `frontend-hormonia/src/pages/AdminPage.tsx:68` — refetchInterval 30s→120s

**Other hooks to bump (non-monitoring):**
- `frontend-hormonia/src/components/layout/NotificationCenter.tsx:27` — refetchInterval 30s→120s
- `frontend-hormonia/src/pages/DLQDashboard.tsx:171,181` — refetchInterval 30s→120s (operational admin)

**Explicitly SKIP (real-time monitoring — D020 allows 30s):**
- `frontend-hormonia/src/features/system/HealthStatusMonitor.tsx` — refetchInterval 30s (system health)
- `frontend-hormonia/src/features/monitoring/SystemStatus.tsx` — refetchInterval 30s (system status)
- `frontend-hormonia/src/components/hive-mind/SystemHealth.tsx` — refetchInterval 30s (hive mind)
- `frontend-hormonia/src/components/hive-mind/AgentSwarm.tsx` — refetchInterval 30s (hive mind)
- `frontend-hormonia/src/pages/ClinicalMonitoringDashboard.tsx` — refetchInterval 30s (clinical monitoring)
- `frontend-hormonia/src/features/admin/tabs/AdminMonitoringTab.tsx` — refetchInterval 30s (monitoring tab)
- `frontend-hormonia/src/hooks/api/useSystemStats.ts` — staleTime 20s (admin system stats, monitoring-class)
- `frontend-hormonia/src/features/whatsapp/hooks/*` — refetchInterval 5-30s (messaging real-time)
- `frontend-hormonia/src/features/whatsapp/WhatsAppDashboard.tsx` — refetchInterval 30s (messaging)

**Already adequate (no change needed):**
- `hooks/api/usePhysicianPatients.ts` — staleTime 60s, no refetchInterval ✓
- `hooks/usePatients.ts` — staleTime 60s / Infinity ✓
- `hooks/useAI.ts` — staleTime 5-10min ✓
- `hooks/useSettings.ts` — staleTime 5min ✓
- `hooks/api/useQuestionarios.ts` — staleTime 5min ✓
- `hooks/api/useAdherenceData.ts` — staleTime 5min ✓
- `hooks/api/useTreatmentDistribution.ts` — staleTime 5min ✓
- `hooks/api/usePhysicianRiskAssessments.ts` — staleTime 60s ✓
- `hooks/useFlows.ts:useFlowStats` — staleTime 60s, refetchInterval 5min ✓
- `hooks/useFlowEngine.ts:useFlowTemplates` — staleTime 5min ✓
- `hooks/useFlowEngine.ts:useFlowAnalytics` — staleTime 60s, refetchInterval 5min ✓
- `features/ai/AIAnalyticsDashboard.tsx` — staleTime 5min ✓
- `hooks/useMonthlyQuizStatus.ts:166` — staleTime 60s ✓
- `hooks/useMonthlyQuizAdmin.ts:151` — staleTime 60s ✓
- `hooks/useMonthlyQuizAdminSecure.ts:170` — staleTime 60s ✓

### Build Order

1. **T01: Bump global default + presets** in `queryClient.ts` — this sets the baseline; hooks that don't override inherit.
2. **T02: Sweep all dashboard/patient/admin/other hooks** — mechanical value changes across ~20 files.
3. **T03: Verify** — `tsc --noEmit` + `vite build` green. No `node_modules` in worktree, so install first (`npm ci`).

Tasks T01 and T02 can be a single task since they're all value edits with no structural changes. T03 is verification.

### Verification Approach

```bash
cd frontend-hormonia && npm ci && npx tsc --noEmit && npx vite build
```

Additionally, a grep audit to confirm no staleTime < 60s remains outside monitoring:
```bash
rg "staleTime:\s*(1[0-9]{4}|[1-5][0-9]{3}|[0-9]{1,3})\b" --type ts --type tsx \
  | grep -v "HealthStatusMonitor\|SystemStatus\|SystemHealth\|AgentSwarm\|ClinicalMonitoring\|AdminMonitoring\|useSystemStats.ts\|whatsapp\|WhatsApp"
```

## Constraints

- `node_modules` doesn't exist in the worktree — `npm ci` required before build verification.
- Comments must be updated alongside values (e.g. `// 30 seconds` → `// 60 seconds`) to avoid confusion.
- No `refetchInterval` below 120s outside explicit monitoring hooks.
- Hooks that accept `refetchInterval` as a parameter (e.g. `useClinicalMetrics`, `useRiskPatients`, `useUserStats`) need their **default values** changed, not their parameter types — callers can still override for monitoring use cases.
