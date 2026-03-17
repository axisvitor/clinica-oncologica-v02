---
estimated_steps: 6
estimated_files: 21
---

# T01: Sweep staleTime and refetchInterval values across all hooks

**Slice:** S02 — Frontend request discipline
**Milestone:** M011

## Description

R102 requires dashboard/patient hooks to use `staleTime ≥ 60s` and `refetchInterval ≥ 120s`. D020 extends this to admin hooks (`staleTime ≥ 120s`, `refetchInterval ≥ 120s`) and static config (`staleTime: Infinity`).

This task performs all value changes across ~21 files. Every change is a numeric literal bump + comment update. No structural changes, no type changes, no new imports.

**Critical rule:** Do NOT touch monitoring/real-time hooks. These are explicitly skipped:
- `features/system/HealthStatusMonitor.tsx`
- `features/monitoring/SystemStatus.tsx`
- `components/hive-mind/SystemHealth.tsx`
- `components/hive-mind/AgentSwarm.tsx`
- `pages/ClinicalMonitoringDashboard.tsx`
- `features/admin/tabs/AdminMonitoringTab.tsx`
- `hooks/api/useSystemStats.ts` (the one in `hooks/api/`, NOT `hooks/useSystemStats.ts`)
- All `features/whatsapp/` hooks

## Steps

1. **Global defaults** — Edit `frontend-hormonia/src/lib/react-query/queryClient.ts`:
   - Default `staleTime: 30 * 1000` → `staleTime: 60 * 1000` (update comment to "60 seconds")
   - Preset `paginated.staleTime: 30 * 1000` → `staleTime: 60 * 1000` (update comment)
   - Leave `realtime` and `static` presets as-is

2. **Dashboard/Patient hooks** — Edit these files, bumping values:
   - `pages/DashboardPage.tsx` — staleTime 30s→60s, refetchInterval 60s→120s
   - `hooks/api/useClinicalMetrics.ts` — default refetchInterval 30s→120s, staleTime 30s→60s
   - `hooks/api/useRiskPatients.ts` — default refetchInterval 60s→120s (staleTime 60s already OK)
   - `hooks/useFlows.ts` — useFlows: staleTime 30s→60s, refetchInterval 60s→120s. useFlowState: staleTime 30s→60s, refetchInterval 60s→120s
   - `hooks/useFlowEngine.ts` — useFlowState: staleTime 30s→60s, refetchInterval 60s→120s
   - `hooks/useMonthlyQuizStatus.ts` — two staleTime 30s→60s (around lines 84 and 135)
   - `hooks/useMonthlyQuizAdmin.ts` — staleTime 30s→60s (around line 91)
   - `hooks/useMonthlyQuizAdminSecure.ts` — staleTime 30s→60s (around line 140)
   - `hooks/useSystemStats.ts` (the one in `hooks/`, NOT `hooks/api/`) — staleTime 10s→60s, refreshInterval default 30s→120s
   - `features/dashboard/AlertsPanel.tsx` — refetchInterval 30s→120s
   - `features/dashboard/RecentQuizCompletions.tsx` — refetchInterval 60s→120s

3. **Admin hooks** — Edit these files, bumping to ≥ 120s per D020:
   - `hooks/admin/useUserStats.ts` — staleTime 10s→120s
   - `hooks/admin/useUserList.ts` — staleTime 10s→120s
   - `hooks/admin/useUserAdmin.ts` — staleTime 30s→120s
   - `features/admin/AuditLogViewer.tsx` — refetchInterval 30s→120s
   - `features/admin/tabs/AdminUsersTab.tsx` — refetchInterval 30s→120s
   - `features/admin/AdminNavigationMenu.tsx` — refetchInterval 60s→120s
   - `pages/AdminPage.tsx` — refetchInterval 30s→120s

4. **Other non-monitoring hooks:**
   - `components/layout/NotificationCenter.tsx` — refetchInterval 30s→120s
   - `pages/DLQDashboard.tsx` — refetchInterval 30s→120s (two occurrences around lines 171 and 181)

5. **Comment sweep** — For every value changed, update the adjacent comment (e.g. `// 30 seconds` → `// 60 seconds`, `// 30s` → `// 120s`, `// Poll every 30s` → `// Poll every 120s`). If no comment exists, no need to add one.

6. **Self-audit** — After all edits, run:
   ```bash
   cd frontend-hormonia && rg "staleTime|refetchInterval" --type ts --type-add 'tsx:*.tsx' --type tsx src/ | grep -v node_modules
   ```
   Visually confirm no dashboard/patient/admin hook has staleTime < 60_000 or refetchInterval < 120_000 (excluding the explicitly-skipped monitoring files).

## Must-Haves

- [ ] Global default staleTime bumped 30s → 60s in queryClient.ts
- [ ] All dashboard/patient hooks meet staleTime ≥ 60s, refetchInterval ≥ 120s
- [ ] All admin hooks meet staleTime ≥ 120s, refetchInterval ≥ 120s
- [ ] Monitoring/real-time hooks untouched
- [ ] Comments updated alongside changed values

## Verification

- Run `rg "staleTime|refetchInterval" --type ts --type-add 'tsx:*.tsx' --type tsx frontend-hormonia/src/` and confirm all changed values meet thresholds
- No file in the "Explicitly SKIP" list was modified

## Inputs

- Research doc identified every file, line number, current value, and target value
- All paths relative to repo root (prefix with `frontend-hormonia/src/`)

## Expected Output

- ~21 files modified with bumped staleTime/refetchInterval values
- Comments updated alongside values
- No structural or type changes — pure numeric literal edits
