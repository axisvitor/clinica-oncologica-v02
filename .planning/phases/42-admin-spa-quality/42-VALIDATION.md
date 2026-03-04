# Phase 42: Admin SPA Quality - Validation

**Created:** 2026-03-04
**Source:** 42-RESEARCH.md Validation Architecture section

---

## Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest 3.2.4 |
| Config file | `vite.config.ts` (vitest inline config) |
| Quick run command | `cd frontend-hormonia && npm test` |
| Full suite command | `cd frontend-hormonia && npm test && npx tsc --noEmit && npx eslint .` |

---

## Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ADMIN-01 | Zero grep hits for VITE_ENABLE_EVOLUTION in src/ | Shell grep | `cd frontend-hormonia && grep -r "VITE_ENABLE_EVOLUTION" src/ \| wc -l` (must be 0) | N/A -- shell check |
| ADMIN-02 | hive-mind.ts exports only health + agents functions | Shell grep + tsc | `cd frontend-hormonia && npx tsc --noEmit && grep -c "SwarmStatus\|IntegrationStatus\|AgentMetrics\|HiveMindSystemStats\|ProcessFlowsResponse\|ConductQuizResponse" src/lib/api-client/hive-mind.ts \| xargs test 0 -eq` | N/A -- shell check |
| ADMIN-03 | Duplicate WhatsApp API calls eliminated; types aligned with v2 contracts | Shell grep + tsc | `cd frontend-hormonia && npx tsc --noEmit` (type alignment verified by compiler) | N/A -- shell check |
| ADMIN-04 | AgentSwarm and SystemHealth use useQuery, no raw polling | Shell grep | `cd frontend-hormonia && grep -c "useQuery" src/components/hive-mind/AgentSwarm.tsx src/components/hive-mind/SystemHealth.tsx` (must be >0 in both) and `grep -c "setInterval" src/components/hive-mind/AgentSwarm.tsx src/components/hive-mind/SystemHealth.tsx` (must be 0 in both) | N/A -- shell check |
| ADMIN-05 | prettier --check exits 0 | Format check | `cd frontend-hormonia && npx prettier --check 'src/**/*.{ts,tsx}'` | Wave 0 gap -- no prettier installed yet |
| ADMIN-06 | eslint exits with 0 errors | Lint check | `cd frontend-hormonia && npx eslint . --max-warnings 999` | Passes now (0 errors, 1 warning) |
| ADMIN-07 | Unused packages removed after knip audit | Audit + build | `cd frontend-hormonia && npx tsc --noEmit && npm run build` | knip v5.85.0 available via npx |
| ADMIN-08 | Visual layout consistency across admin pages | Manual review | Manual -- checkpoint:human-verify in Plan 42-04 | N/A -- visual check |

---

## Sampling Rate

- **Per task commit:** `cd frontend-hormonia && npx tsc --noEmit && npx eslint . --max-warnings 50`
- **Per wave merge:** `cd frontend-hormonia && npm test && npx tsc --noEmit && npx eslint .`
- **Phase gate:** Full suite green + `npm run build` succeeds before `/gsd:verify-work`

---

## Wave 0 Gaps

- [ ] Prettier must be installed: `npm install --save-dev prettier eslint-config-prettier` (Plan 42-03)
- [ ] `.prettierrc` config file to create (Plan 42-03)
- [ ] `.prettierignore` file to create (Plan 42-03)
- [ ] `eslint-config-prettier` to be added to `eslint.config.js` (Plan 42-03)

*(tsc and eslint already pass -- no test infrastructure gaps for those checks)*

---

## Phase Gate Command

```bash
cd frontend-hormonia && \
  npx tsc --noEmit && \
  npx eslint . --max-warnings 50 && \
  npx prettier --check 'src/**/*.{ts,tsx}' && \
  npm run build && \
  grep -r "VITE_ENABLE_EVOLUTION" src/ | wc -l | xargs test 0 -eq && \
  grep -c "setInterval" src/components/hive-mind/AgentSwarm.tsx src/components/hive-mind/SystemHealth.tsx | grep -v ":0$" | wc -l | xargs test 0 -eq && \
  echo "Phase 42 validation PASSED"
```
