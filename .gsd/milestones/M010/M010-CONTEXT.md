# M010: Refinamento do Dashboard Médico

**Gathered:** 2026-03-17
**Status:** Ready for planning

## Project Description

Refinamento do physician dashboard para servir o workflow real do oncologista: visão patient-centric como tela principal (não analytics), tela de preparo pré-consulta consolidada (resumo IA + respostas + alertas + fluxo num clique), e responsivo verdadeiro desktop + mobile. Inclui limpeza do código morto /medico/* que já são redirects.

## Why This Milestone

M007 construiu o resumo IA, as respostas livres, os alertas do quiz, e o editor de templates. M008 provou o pipeline ponta-a-ponta. M009 migrou a infra para Taskiq. Mas o dashboard do médico — a interface onde ele consome todo esse valor — ainda é um dashboard de analytics genérico. A tabela de risk assessment é útil mas não mostra o que o médico precisa num relance: em que dia do fluxo está cada paciente, quem respondeu, quem tem alertas pendentes. A tela de detalhe do paciente tem tudo (AI summary, timeline, quiz, mensagens) mas escondido em tabs — precisa virar uma tela de preparo pré-consulta onde tudo é visível.

R087 explicitamente adiou este trabalho de M009 para M010.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Abrir `/physician/dashboard` e ver todos os pacientes com fase do fluxo, dia atual, último contato, e flags de atenção — num relance
- Clicar num paciente e ver o resumo IA + respostas livres + alertas + status fluxo consolidados numa tela, prontos para a consulta
- Usar o dashboard confortavelmente no celular entre consultas e no desktop no consultório
- Não encontrar mais código morto de MedicoDashboard/PacientesList/ProntuarioView no repositório

### Entry point / environment

- Entry point: `/physician/dashboard` no browser (rota autenticada)
- Environment: local dev — React 19 + Vite + Tailwind 4 + shadcn/ui
- Live dependencies involved: backend API (FastAPI), Dragonfly (cache), PostgreSQL

## Completion Class

- Contract complete means: componentes renderizam com dados mock, types corretos, build green
- Integration complete means: dashboard consome APIs reais e mostra dados de pacientes com fluxo
- Operational complete means: none — frontend milestone, não tem lifecycle de serviço

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- PhysicianDashboard mostra lista patient-centric com dados de fluxo por paciente (fase, dia, último contato)
- 1 clique de qualquer paciente na lista leva à tela pré-consulta com resumo IA visível
- Tela pré-consulta consolida resumo IA + respostas + alertas + fluxo sem tabs obrigatórios
- Interface responsiva funciona em viewport mobile (375px) e desktop (1280px+)
- Código morto /medico/* removido (grep retorna zero)
- `tsc --noEmit` e `vite build` green

## Risks and Unknowns

- **API de listagem enriquecida** — O endpoint risk-assessments atual (`/api/v2/physician/risk-assessments`) retorna `PatientRiskAssessment` com risk score mas sem dados de fluxo (fase, dia atual). Precisa de novo endpoint ou enriquecimento do existente. Risco: JOIN com `patient_flow_states` pode ter performance com muitos pacientes.
- **Recomposição de componentes** — PatientAISummary (593 linhas), FlowStatus (283 linhas), QuizResponseViewer (324 linhas) foram construídos como componentes standalone para tabs. Consolidar numa tela única pode exigir refactor significativo para evitar duplicação de queries e layout conflicts.
- **MedicoLogin dependency** — MedicoLogin.tsx e MedicoAuthContext.tsx podem ter dependências não óbvias. Precisa verificar se o login do médico usa esse contexto ou o AuthContext principal antes de deletar.

## Existing Codebase / Prior Art

- `frontend-hormonia/src/pages/PhysicianDashboard.tsx` — 727 linhas: dashboard atual com risk table, AI tabs, chat dialog, export dialog
- `frontend-hormonia/src/pages/PatientDetailPage.tsx` — 255 linhas: detalhe do paciente com tabs (overview, timeline, quiz, AI summary, messages)
- `frontend-hormonia/src/pages/medico/MedicoDashboard.tsx` — código morto, rotas redirecionam para /physician
- `frontend-hormonia/src/pages/medico/PacientesList.tsx` — código morto
- `frontend-hormonia/src/pages/medico/ProntuarioView.tsx` — código morto
- `frontend-hormonia/src/app/providers/MedicoAuthContext.tsx` — possivelmente morto
- `frontend-hormonia/src/hooks/api/useMedicoDashboardStats.ts` — possivelmente morto
- `frontend-hormonia/src/hooks/api/usePhysicianRiskAssessments.ts` — hook atual da risk table
- `frontend-hormonia/src/features/dashboard/components/physician/` — 5 componentes physician (MetricsCards, RiskTable, InsightsPanel, ChatDialog, ExportDialog)
- `frontend-hormonia/src/features/patients/FlowStatus.tsx` — 283 linhas, status do fluxo do paciente
- `frontend-hormonia/src/features/ai/PatientAISummary.tsx` — 593 linhas, resumo IA do paciente
- `frontend-hormonia/src/features/patients/QuizResponseViewer.tsx` — 324 linhas, respostas do quiz
- `backend-hormonia/app/api/v2/routers/patients/crud.py` — list_patients com filtros avançados
- `backend-hormonia/app/api/v2/routers/patients/flow_responses.py` — GET /{patient_id}/flow-responses
- `backend-hormonia/app/api/v2/routers/analytics/patient_analytics.py` — risk-assessment endpoint
- `backend-hormonia/app/models/flow.py` — PatientFlowState model (current_step, status, step_data, flow_kind_id)

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions.

## Relevant Requirements

- R089 — Visão patient-centric com contexto clínico no dashboard
- R090 — Tela de preparo pré-consulta consolidada
- R091 — API enriquecida com dados de fluxo
- R092 — Acesso ao resumo IA em 1 clique
- R093 — Interface responsiva desktop + mobile
- R094 — Remoção do código morto /medico/*
- R095 — Dashboards admin e médico separados

## Scope

### In Scope

- Novo endpoint backend com listagem de pacientes + dados de fluxo enriquecidos
- Rewrite do PhysicianDashboard para visão patient-centric
- Recomposição do PatientDetailPage para tela de preparo pré-consulta consolidada
- Responsive polish para desktop e mobile em ambas as telas
- Deleção de código morto /medico/*
- Wiring do endpoint flow-responses no frontend (já existe no backend)

### Out of Scope / Non-Goals

- Mudanças no DashboardPage.tsx (admin dashboard) — R099
- Mudanças em lógica de tasks, fluxos, ou processamento de mensagens — R098
- Push notifications / realtime alerts — R096
- Export PDF real — R097
- Novas features de backend além da API de listagem enriquecida

## Technical Constraints

- React 19 + Vite + Tailwind CSS 4 + shadcn/ui — manter consistência com o stack existente
- `apiClient` modular — novos endpoints seguem o padrão createXxxApi() em lib/api-client/
- PatientFlowState tem `current_step` (int), `status` (string), `step_data` (JSONB) — o dia do fluxo é derivado de `step_data.current_flow_day` ou do `current_step`
- O endpoint risk-assessments usa cache Redis de 60s — o novo endpoint deve ter cache similar
- PhysicianDashboard já tem debounced search e server-side filtering — preservar o padrão

## Integration Points

- **Backend API** — novo endpoint `/api/v2/physician/patients` ou enriquecimento de `/api/v2/physician/risk-assessments` com dados de fluxo
- **Frontend apiClient** — novo módulo ou extensão de `physician.ts` e `dashboard.ts`
- **PatientFlowState model** — JOIN para dados de fluxo na listagem
- **patient_flow_responses table** — dados de respostas livres do paciente (endpoint já existe, precisa wiring frontend)

## Open Questions

- **Enriquecer risk-assessments ou criar novo endpoint?** — Inclino para novo endpoint `/api/v2/physician/patients` que retorna patient + flow state + alert counts numa query. O risk-assessments é focado em AI risk scoring que pode não ser necessário na visão principal.
- **MedicoLogin.tsx**: Verificar se o fluxo de login do médico usa MedicoAuthContext (que seria deletado) ou o AuthContext principal. Se usa MedicoAuthContext, precisa migrar antes de deletar.
