# T02: Frontend hook + apiClient + PhysicianDashboard rewrite

**Slice:** S01
**Milestone:** M010

## Goal
Criar hook usePhysicianPatients, estender apiClient com novo endpoint, e reescrever PhysicianDashboard.tsx como visão patient-centric consumindo o novo endpoint.

## Must-Haves

### Truths
- `usePhysicianPatients({ search, flow_phase, flow_status, page, size })` retorna `{ data, isLoading, error }`
- Data shape: `{ items: PhysicianPatient[], total: number }`
- PhysicianDashboard mostra tabela com colunas: Paciente, Fase do Fluxo, Dia, Último Contato, Alertas, Status
- Search input com debounce filtra por nome
- Filtro de fase do fluxo (select: Todos, Onboarding, Follow-up Diário, Quiz Mensal)
- Filtro de status (select: Todos, Ativo, Pausado, Concluído)
- Paginação funcional
- Click numa row navega para `/physician/patients/:id`
- Chat IA e Export dialogs preservados do dashboard atual
- Skeleton loading durante fetch
- Error state com mensagem e retry
- `tsc --noEmit` green
- `vite build` green

### Artifacts
- `frontend-hormonia/src/lib/api-client/physician.ts` — estendido com `patients()` method
- `frontend-hormonia/src/hooks/api/usePhysicianPatients.ts` — novo hook (exports: usePhysicianPatients)
- `frontend-hormonia/src/pages/PhysicianDashboard.tsx` — reescrito (patient-centric)
- `frontend-hormonia/src/features/dashboard/components/physician/PhysicianPatientTable.tsx` — novo componente de tabela

### Key Links
- `usePhysicianPatients.ts` → `apiClient.physician.patients()` via import
- `PhysicianDashboard.tsx` → `usePhysicianPatients` via import
- `PhysicianDashboard.tsx` → `PhysicianPatientTable` via import
- `PhysicianDashboard.tsx` → `PhysicianChatDialog` + `PhysicianExportDialog` via import (preservados)
- `PhysicianPatientTable.tsx` → `useNavigate` para click → `/physician/patients/:id`

## Steps
1. Estender `lib/api-client/physician.ts`: adicionar `patients(params)` que chama GET /api/v2/physician/patients
2. Criar type `PhysicianPatient` e `PhysicianPatientListResponse` em types
3. Criar `hooks/api/usePhysicianPatients.ts` com useQuery, debounced search, filter params
4. Criar `PhysicianPatientTable.tsx` com Table do shadcn/ui, colunas de flow data, Badge para fase/status, click handler
5. Reescrever `PhysicianDashboard.tsx`: header com título + ações (Atualizar, Chat IA, Exportar), filtros (search + selects), PhysicianPatientTable, paginação, loading/error states
6. Remover imports/código não usado (PhysicianMetricsCards risk cards, PhysicianRiskTable, AI Insights/Analytics tabs)
7. Verificar: `tsc --noEmit`, `vite build`

## Context
- PhysicianDashboard atual (727 linhas) tem: risk metrics cards, risk table com search/filter, AI insights tab, AI analytics tab, chat dialog, export dialog
- Preservar: chat dialog (PhysicianChatDialog) e export dialog (PhysicianExportDialog) — são features úteis
- Remover: PhysicianMetricsCards (risk count cards), PhysicianRiskTable (substituída pela nova tabela), tabs de Insights/Analytics (movidas para detalhe do paciente em S02)
- Padrão de hook existente: usePhysicianRiskAssessments usa useQuery + apiClient.request
- Padrão de tabela existente: PhysicianRiskTable usa Table/TableHeader/TableBody/TableRow do shadcn/ui
- useDebounce já existe em hooks/useDebounce
- shadcn/ui components disponíveis: Table, Badge, Button, Input, Select, Card, Skeleton, Alert, Tabs
