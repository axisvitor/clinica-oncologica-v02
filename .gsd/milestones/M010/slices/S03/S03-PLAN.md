# S03: Limpeza do código morto /medico/*

**Goal:** Deletar código morto de MedicoDashboard, PacientesList, ProntuarioView, MedicoAuthContext e artefatos associados.
**Demo:** grep por esses componentes retorna zero. Build green.

## Must-Haves
- MedicoDashboard.tsx, PacientesList.tsx, ProntuarioView.tsx deletados
- MedicoAuthContext.tsx e seu teste deletados
- useMedicoDashboardStats.ts deletado
- types/medico.ts deletado
- MedicoRoutes.tsx deletado (orphaned)
- MedicoDashboardStatsResponse removida de api-wave2.ts
- `tsc --noEmit` green
- `vite build` green
- Zero referências aos componentes deletados no codebase

## Tasks

- [x] **T01: Deletar código morto /medico/* e artefatos associados**
  Remover 8 arquivos mortos, limpar types, verificar build.

## Files Likely Touched
- `pages/medico/MedicoDashboard.tsx` — DELETE
- `pages/medico/PacientesList.tsx` — DELETE
- `pages/medico/ProntuarioView.tsx` — DELETE
- `app/providers/MedicoAuthContext.tsx` — DELETE
- `app/providers/__tests__/MedicoAuthContext.test.tsx` — DELETE
- `hooks/api/useMedicoDashboardStats.ts` — DELETE
- `types/medico.ts` — DELETE
- `app/routes/MedicoRoutes.tsx` — DELETE
- `types/api-wave2.ts` — MODIFIED (remove dead types)
