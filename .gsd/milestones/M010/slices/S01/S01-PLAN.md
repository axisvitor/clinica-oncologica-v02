# S01: API enriquecida + Dashboard patient-centric

**Goal:** Criar endpoint backend que retorna lista de pacientes com dados de fluxo (fase, dia, último contato, alertas) e reescrever o PhysicianDashboard para visão patient-centric consumindo esse endpoint.
**Demo:** Médico abre /physician/dashboard e vê todos os pacientes com fase do fluxo, dia atual, último contato, e flags de atenção na lista principal.

## Must-Haves
- Endpoint `GET /api/v2/physician/patients` retorna lista paginada com `flow_phase`, `flow_current_day`, `last_interaction`, `unacknowledged_alerts_count`, `flow_status` por paciente
- Endpoint filtrável por `search` (nome), `flow_phase`, `flow_status` e paginável
- Endpoint responde com dados corretos (query real contra Postgres com JOIN patient_flow_states + alerts)
- Hook `usePhysicianPatients()` no frontend consome o endpoint com search debounce + filter + pagination
- PhysicianDashboard.tsx reescrito com tabela patient-centric mostrando: nome, fase do fluxo, dia atual, último contato, contagem de alertas, status
- Click numa row navega para `/physician/patients/:id`
- `tsc --noEmit` green
- `vite build` green (ou `vite build 2>&1 | grep -c error` = 0)
- DashboardPage.tsx (admin) inalterado

## Tasks

- [x] **T01: Endpoint backend GET /api/v2/physician/patients**
  Criar endpoint FastAPI com query async que JOIN patient + patient_flow_states + alert counts.
  Retorna shape paginada com dados de fluxo por paciente. Cache Dragonfly 60s.

- [x] **T02: Frontend hook + apiClient + PhysicianDashboard rewrite**
  Criar módulo apiClient, hook usePhysicianPatients, e reescrever PhysicianDashboard.tsx
  como visão patient-centric consumindo o novo endpoint. Manter chat/export dialogs.

## Files Likely Touched

### Backend
- `backend-hormonia/app/api/v2/routers/physicians/` — novo arquivo para endpoint
- `backend-hormonia/app/api/v2/router.py` — registrar rota (se necessário)
- `backend-hormonia/app/schemas/v2/` — schema Pydantic para response

### Frontend
- `frontend-hormonia/src/lib/api-client/physician.ts` — estender com novo endpoint
- `frontend-hormonia/src/hooks/api/usePhysicianPatients.ts` — novo hook
- `frontend-hormonia/src/pages/PhysicianDashboard.tsx` — rewrite
- `frontend-hormonia/src/features/dashboard/components/physician/PhysicianPatientTable.tsx` — novo componente
