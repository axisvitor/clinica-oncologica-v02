---
id: S03
parent: M010
milestone: M010
provides:
  - "8 dead files deleted: MedicoDashboard, PacientesList, ProntuarioView, MedicoAuthContext (+ test), useMedicoDashboardStats, types/medico, MedicoRoutes"
  - "MedicoDashboardStatsResponse + MedicoDashboardQueryOptions removed from api-wave2.ts"
  - "MEDICO_DASHBOARD endpoint constant removed from api-wave2.ts"
  - "Zero references to deleted components in codebase"
requires: []
affects: [S04]
key_files:
  - frontend-hormonia/src/types/api-wave2.ts (modified — dead types removed)
key_decisions:
  - "MedicoLogin.tsx preserved — thin wrapper around LoginPage, still used by routeDefinitions for /medico/login"
  - "MedicoRoutes.tsx deleted — completely orphaned, not imported by any file"
patterns_established: []
drill_down_paths: []
duration: ~8min
verification_result: passed
completed_at: 2026-03-17
---

# S03: Limpeza do código morto /medico/*

**Deleted 8 dead files (MedicoDashboard, PacientesList, ProntuarioView, MedicoAuthContext, MedicoRoutes, useMedicoDashboardStats, types/medico) and cleaned dead types from api-wave2.ts — zero remaining references, build green**

## What Happened

Scouted all references to the dead medico components via `rg`. Confirmed dependency graph:
- MedicoDashboard, PacientesList, ProntuarioView — imported only by orphaned MedicoRoutes
- MedicoAuthContext — imported only by dead pages and its own test
- useMedicoDashboardStats — imported only by dead MedicoDashboard
- types/medico.ts — imported only by dead MedicoAuthContext
- MedicoRoutes.tsx — not imported by any file (completely orphaned)

Preserved MedicoLogin.tsx — it's a 4-line wrapper around LoginPage used by routeDefinitions.tsx for the `/medico/login` route.

Cleaned api-wave2.ts: removed `MedicoDashboardStatsResponse`, `MedicoDashboardQueryOptions`, and `MEDICO_DASHBOARD` endpoint constant.

## Verification

- `rg "MedicoDashboard|PacientesList|ProntuarioView|MedicoAuthContext|useMedicoDashboardStats|MedicoRoutes"` → exit code 1 (zero matches) ✓
- `tsc --noEmit` — zero non-e2e errors ✓
- `vite build` — built in 1m 17s ✓

## Requirements Advanced

- R094 — All dead /medico/* code removed. MedicoLogin preserved (functional). Zero references to deleted components. Ready for validation.
