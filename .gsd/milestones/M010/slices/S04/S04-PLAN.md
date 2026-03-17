# S04: Polish responsivo + verificação integrada

**Goal:** Fazer dashboard e detalhe do paciente funcionarem bem em mobile (375px) e desktop (1280px+). Verificação final integrada.
**Demo:** Dashboard e detalhe funcionam em mobile (cards touch-friendly) e desktop (tabela densa). Typecheck + build green.

## Must-Haves
- PhysicianPatientTable: table em desktop (≥768px), card layout empilhado em mobile (<768px)
- PatientDetailPage: grid 2-col em desktop, seções empilhadas em mobile
- PhysicianDashboard: filtros empilhados em mobile, inline em desktop (já feito com flex-col/sm:flex-row)
- `tsc --noEmit` green
- `vite build` green
- DashboardPage.tsx (admin) inalterado

## Tasks

- [x] **T01: Responsive PhysicianPatientTable + verificação final**
  Adicionar card layout mobile ao PhysicianPatientTable (hidden table / visible cards em <768px). Verificar build final.

## Files Likely Touched
- `frontend-hormonia/src/features/dashboard/components/physician/PhysicianPatientTable.tsx`
