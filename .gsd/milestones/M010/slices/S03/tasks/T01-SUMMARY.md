---
id: T01
parent: S03
milestone: M010
provides:
  - "8 dead files deleted: MedicoDashboard, PacientesList, ProntuarioView, MedicoAuthContext (+test), useMedicoDashboardStats, types/medico, MedicoRoutes"
  - "Dead types removed from api-wave2.ts: MedicoDashboardStatsResponse, MedicoDashboardQueryOptions, MEDICO_DASHBOARD"
key_files:
  - frontend-hormonia/src/types/api-wave2.ts (modified — dead types removed)
key_decisions:
  - "MedicoLogin.tsx preserved — thin wrapper around LoginPage, still used by routeDefinitions for /medico/login"
  - "MedicoRoutes.tsx deleted — completely orphaned, not imported by any file"
patterns_established: []
observability_surfaces:
  - none
duration: ~8min
verification_result: passed
completed_at: 2026-03-17
blocker_discovered: false
---

# T01: Deletar código morto /medico/* e artefatos associados

**Deleted 8 dead files (MedicoDashboard, PacientesList, ProntuarioView, MedicoAuthContext, MedicoRoutes, useMedicoDashboardStats, types/medico) and cleaned dead types from api-wave2.ts — zero remaining references, build green**

## What Happened

Scouted all references to dead medico components via `rg`. Confirmed dependency graph: MedicoDashboard, PacientesList, ProntuarioView imported only by orphaned MedicoRoutes; MedicoAuthContext imported only by dead pages and its own test; useMedicoDashboardStats imported only by dead MedicoDashboard; types/medico.ts imported only by dead MedicoAuthContext; MedicoRoutes.tsx not imported by any file.

Preserved MedicoLogin.tsx — 4-line wrapper around LoginPage used by routeDefinitions.tsx for `/medico/login`.

Cleaned api-wave2.ts: removed `MedicoDashboardStatsResponse`, `MedicoDashboardQueryOptions`, and `MEDICO_DASHBOARD` endpoint constant.

## Verification

- `rg "MedicoDashboard|PacientesList|ProntuarioView|MedicoAuthContext|useMedicoDashboardStats|MedicoRoutes"` → exit code 1 (zero matches) ✓
- `tsc --noEmit` — zero non-e2e errors ✓
- `vite build` — built in 1m 17s ✓

## Diagnostics

none

## Deviations

none

## Known Issues

none

## Files Created/Modified

- `frontend-hormonia/src/pages/medico/MedicoDashboard.tsx` — DELETED
- `frontend-hormonia/src/pages/medico/PacientesList.tsx` — DELETED
- `frontend-hormonia/src/pages/medico/ProntuarioView.tsx` — DELETED
- `frontend-hormonia/src/app/providers/MedicoAuthContext.tsx` — DELETED
- `frontend-hormonia/src/app/providers/__tests__/MedicoAuthContext.test.tsx` — DELETED
- `frontend-hormonia/src/hooks/api/useMedicoDashboardStats.ts` — DELETED
- `frontend-hormonia/src/types/medico.ts` — DELETED
- `frontend-hormonia/src/app/routes/MedicoRoutes.tsx` — DELETED
- `frontend-hormonia/src/types/api-wave2.ts` — modified (removed dead types and endpoint constant)
