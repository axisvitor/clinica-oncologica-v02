# S02: Frontend request discipline — UAT

**Milestone:** M011
**Written:** 2026-03-17

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: All changes are numeric timing literal bumps in React Query hooks. Verification is purely static — grep audit for threshold compliance plus tsc/vite build for type safety. No runtime behavior change, no new UI, no API change.

## Preconditions

- `frontend-hormonia/node_modules` installed (`npm ci`)
- Working TypeScript toolchain (`npx tsc --noEmit` must be available)
- `rg` (ripgrep) installed for grep audits

## Smoke Test

Run `cd frontend-hormonia && npx tsc --noEmit && npx vite build` — both must exit 0. This confirms the 21 edited files compile and bundle without regressions.

## Test Cases

### 1. Global default staleTime is 60s

1. Open `frontend-hormonia/src/lib/react-query/queryClient.ts`
2. Find the `defaultOptions.queries.staleTime` value
3. **Expected:** `60 * 1000` (60000ms / 60 seconds)

### 2. Dashboard/patient hooks meet staleTime ≥ 60s

1. Run: `rg "staleTime" frontend-hormonia/src/pages/DashboardPage.tsx frontend-hormonia/src/hooks/api/useClinicalMetrics.ts frontend-hormonia/src/hooks/api/useRiskPatients.ts frontend-hormonia/src/hooks/useFlows.ts frontend-hormonia/src/hooks/useFlowEngine.ts frontend-hormonia/src/hooks/useMonthlyQuizStatus.ts frontend-hormonia/src/hooks/useMonthlyQuizAdmin.ts frontend-hormonia/src/hooks/useMonthlyQuizAdminSecure.ts frontend-hormonia/src/hooks/useSystemStats.ts`
2. Check each staleTime value
3. **Expected:** All values ≥ 60000 (60s)

### 3. Dashboard/patient hooks meet refetchInterval ≥ 120s

1. Run: `rg "refetchInterval" frontend-hormonia/src/pages/DashboardPage.tsx frontend-hormonia/src/hooks/api/useClinicalMetrics.ts frontend-hormonia/src/hooks/api/useRiskPatients.ts frontend-hormonia/src/hooks/useFlows.ts frontend-hormonia/src/hooks/useFlowEngine.ts frontend-hormonia/src/features/dashboard/AlertsPanel.tsx frontend-hormonia/src/features/dashboard/RecentQuizCompletions.tsx`
2. Check each refetchInterval value
3. **Expected:** All values ≥ 120000 (120s) or conditional/false

### 4. Admin hooks meet staleTime ≥ 120s

1. Run: `rg "staleTime" frontend-hormonia/src/hooks/admin/useUserStats.ts frontend-hormonia/src/hooks/admin/useUserList.ts frontend-hormonia/src/hooks/admin/useUserAdmin.ts`
2. Check each staleTime value
3. **Expected:** All values ≥ 120000 (120s)

### 5. Admin hooks meet refetchInterval ≥ 120s

1. Run: `rg "refetchInterval" frontend-hormonia/src/hooks/admin/useUserStats.ts frontend-hormonia/src/hooks/admin/useUserList.ts frontend-hormonia/src/hooks/admin/useUserAdmin.ts frontend-hormonia/src/features/admin/AuditLogViewer.tsx frontend-hormonia/src/features/admin/tabs/AdminUsersTab.tsx frontend-hormonia/src/features/admin/AdminNavigationMenu.tsx frontend-hormonia/src/pages/AdminPage.tsx`
2. Check each refetchInterval value
3. **Expected:** All values ≥ 120000 (120s) or conditional/false

### 6. Monitoring hooks untouched

1. Run: `rg "staleTime|refetchInterval" frontend-hormonia/src/features/system/ frontend-hormonia/src/features/monitoring/ frontend-hormonia/src/hooks/api/useSystemStats.ts frontend-hormonia/src/features/whatsapp/`
2. **Expected:** Values remain at their original sub-threshold settings (10s, 30s, etc.) — these are monitoring/real-time hooks that are explicitly exempt

### 7. Full diagnostic grep audit clean

1. Run: `rg "staleTime|refetchInterval" --type ts --type-add 'tsx:*.tsx' --type tsx frontend-hormonia/src/ | grep -v node_modules | grep -v features/system | grep -v features/monitoring | grep -v hive-mind | grep -v ClinicalMonitoring | grep -v AdminMonitoringTab | grep -v hooks/api/useSystemStats | grep -v features/whatsapp`
2. Inspect every numeric value in output
3. **Expected:** No staleTime below 60000 and no refetchInterval below 120000, except `queryPresets.realtime` (allowed monitoring preset) and dead code files (`useOptimizedQuery.helpers.ts`, `ProductionProvider.tsx` — zero imports)

### 8. TypeScript compilation green

1. Run: `cd frontend-hormonia && npx tsc --noEmit`
2. **Expected:** Exit code 0, zero errors

### 9. Vite production build green

1. Run: `cd frontend-hormonia && npx vite build`
2. **Expected:** Exit code 0, `dist/` directory produced with bundled output

## Edge Cases

### Dead code files with sub-threshold values

1. Run: `rg -l "useOptimizedQuery.helpers" frontend-hormonia/src/ --type ts --type-add 'tsx:*.tsx' --type tsx | grep -v useOptimizedQuery.helpers.ts`
2. Run: `rg -l "ProductionProvider" frontend-hormonia/src/ --type ts --type-add 'tsx:*.tsx' --type tsx | grep -v ProductionProvider.tsx`
3. **Expected:** No imports found — these files are dead code and their sub-threshold values don't affect runtime

### useUserAdmin.refreshInterval flowing into child hooks

1. Open `frontend-hormonia/src/hooks/admin/useUserAdmin.ts`
2. Find the `refreshInterval` default parameter value
3. **Expected:** 120000 (120s) — this value flows as refetchInterval into useUserList and useUserStats at runtime

### queryPresets.realtime exemption

1. Open `frontend-hormonia/src/lib/react-query/queryClient.ts`
2. Find `queryPresets.realtime`
3. **Expected:** staleTime=10s, refetchInterval=10s — this is the explicitly allowed monitoring preset, not a violation

## Failure Signals

- `tsc --noEmit` exits with errors → type regression from edited files
- `vite build` fails → import/syntax error introduced by edits
- Grep audit finds staleTime < 60000 outside monitoring hooks → missed file or reverted value
- Grep audit finds refetchInterval < 120000 outside monitoring hooks → missed file or reverted value
- Any monitoring hook file appears in `git diff --name-only` → accidentally edited exempt hook

## Requirements Proved By This UAT

- R102 — All dashboard/patient hooks use staleTime ≥ 60s and refetchInterval ≥ 120s; admin hooks use staleTime ≥ 120s and refetchInterval ≥ 120s. Monitoring hooks preserved at original thresholds.

## Not Proven By This UAT

- Runtime request reduction is not measured — only the timing configuration values are verified
- Backend cache alignment (S01's @cache_response TTL matching frontend staleTime) is not cross-verified here — that's S03 scope
- Actual network traffic patterns under real usage are not tested — this is a static audit

## Notes for Tester

- The canonical diagnostic command is the full `rg` pipeline in Test Case 7 — if that's clean, the slice is correct.
- `queryPresets.realtime` will show sub-threshold values — this is expected and correct. It's the monitoring preset.
- Dead code files (`useOptimizedQuery.helpers.ts`, `ProductionProvider.tsx`) are noise — confirm zero imports and move on.
- The playwright.config.e2e.ts fix is cosmetic (bracket notation for process.env) and unrelated to the timing changes.
