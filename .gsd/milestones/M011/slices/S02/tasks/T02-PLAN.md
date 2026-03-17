---
estimated_steps: 4
estimated_files: 0
---

# T02: Install dependencies and verify build

**Slice:** S02 — Frontend request discipline
**Milestone:** M011

## Description

Terminal verification for S02. The worktree has no `node_modules`, so dependencies must be installed before running TypeScript checker and Vite build. This task also runs a grep audit to confirm R102 thresholds are met across the codebase.

## Steps

1. **Install dependencies:**
   ```bash
   cd frontend-hormonia && npm ci
   ```

2. **TypeScript check:**
   ```bash
   cd frontend-hormonia && npx tsc --noEmit
   ```
   Must exit 0 with no type errors.

3. **Vite build:**
   ```bash
   cd frontend-hormonia && npx vite build
   ```
   Must exit 0 producing a build output.

4. **Grep audit** — Confirm no staleTime below 60s (60_000ms) or refetchInterval below 120s (120_000ms) outside monitoring hooks:
   ```bash
   cd frontend-hormonia
   # Find any staleTime with a value under 60000 (values like 10_000, 30_000, 10 * 1000, 30 * 1000)
   # Exclude monitoring files that are allowed to have low values
   rg "staleTime:\s*(10|20|30|[1-5][0-9])\s*\*\s*1000" --type ts --type-add 'tsx:*.tsx' --type tsx src/ \
     | grep -v "HealthStatusMonitor\|SystemStatus\|SystemHealth\|AgentSwarm\|ClinicalMonitoring\|AdminMonitoring\|useSystemStats.ts\|whatsapp\|WhatsApp" \
     | grep -v "realtime\|10 \* 1000, // 10 seconds.*realtime"
   # Should return empty (exit code 1 from grep is OK — means nothing found)

   rg "refetchInterval:\s*(5|10|15|20|30|60)\s*\*\s*1000" --type ts --type-add 'tsx:*.tsx' --type tsx src/ \
     | grep -v "HealthStatusMonitor\|SystemStatus\|SystemHealth\|AgentSwarm\|ClinicalMonitoring\|AdminMonitoring\|useSystemStats.ts\|whatsapp\|WhatsApp"
   # Should return empty
   ```

   If any results appear, they indicate missed edits from T01 — fix them before declaring done.

## Must-Haves

- [ ] `npm ci` completes successfully
- [ ] `tsc --noEmit` exits 0
- [ ] `vite build` exits 0
- [ ] Grep audit shows no staleTime < 60s or refetchInterval < 120s outside monitoring hooks

## Verification

- `tsc --noEmit` exit code 0
- `vite build` exit code 0
- Grep audit returns empty (no violations found)

## Observability Impact

- **Build artifacts:** `vite build` produces `frontend-hormonia/dist/` — presence confirms compilable output.
- **TypeScript diagnostics:** `tsc --noEmit` exit code is the primary signal; any type errors from T01 edits surface here.
- **Grep audit:** `rg "staleTime|refetchInterval"` across `frontend-hormonia/src/` is the canonical inspection surface. Values below R102 thresholds outside monitoring hooks indicate regression.
- **Failure visibility:** Build failures or type errors appear as non-zero exit codes. Grep audit violations appear as matched lines in stdout. No runtime signal — this is a compile-time/static-analysis gate.

## Inputs

- T01 completed all value changes across ~21 files
- `frontend-hormonia/package.json` and `frontend-hormonia/package-lock.json` exist for `npm ci`

## Expected Output

- Clean `tsc --noEmit` output (no type errors)
- Successful `vite build` output (build artifacts in `dist/`)
- Clean grep audit confirming R102 compliance
- Slice S02 verification complete
