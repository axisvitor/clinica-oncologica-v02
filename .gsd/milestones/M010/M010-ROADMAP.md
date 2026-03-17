# M010: Refinamento do Dashboard Médico

**Vision:** Transformar o physician dashboard de um painel analytics-heavy num instrumento clínico: visão patient-centric com contexto de fluxo por paciente como tela principal, preparo pré-consulta consolidado a 1 clique, responsivo desktop + mobile, código morto removido.

## Success Criteria

- Médico abre /physician/dashboard e vê todos os pacientes com fase do fluxo, dia atual, último contato, e flags de atenção — sem cliques adicionais
- 1 clique num paciente leva à tela pré-consulta com resumo IA visível sem navegar por tabs
- Tela pré-consulta mostra resumo IA + respostas livres recentes + alertas do quiz + status do fluxo consolidados
- Dashboard funciona bem em viewport mobile (375px) e desktop (1280px+) — não só "não quebra" mas funciona bem
- Zero código de MedicoDashboard/PacientesList/ProntuarioView/MedicoAuthContext no repositório
- `tsc --noEmit` e `vite build` green
- DashboardPage.tsx (admin) não foi alterado

## Key Risks / Unknowns

- API de listagem com JOIN patient_flow_states pode ter performance com muitos pacientes — precisa de query otimizada
- Componentes PatientAISummary/FlowStatus/QuizResponseViewer foram desenhados para tabs independentes — recomposição numa tela única pode gerar conflitos de layout ou duplicação de queries
- MedicoLogin/MedicoAuthContext pode ter dependências não óbvias que precisam ser resolvidas antes da deleção

## Proof Strategy

- API performance → retirar em S01 provando que o endpoint enriquecido responde com dados de fluxo por paciente
- Recomposição de componentes → retirar em S02 provando que PatientDetailPage consolida tudo numa tela sem tab-hunting
- MedicoLogin deps → retirar em S03 provando que a deleção não quebra nenhuma rota funcional

## Verification Classes

- Contract verification: `tsc --noEmit`, `vite build`, grep por código morto, verificação de responsividade via viewport resize
- Integration verification: dashboard consome API real e mostra dados de fluxo por paciente, 1 clique navega para detalhe com AI summary
- Operational verification: none (frontend milestone)
- UAT / human verification: médico (ou usuário) navega pelo dashboard em mobile e desktop e confirma que a experiência é fluida

## Milestone Definition of Done

This milestone is complete only when all are true:

- PhysicianDashboard mostra lista patient-centric com dados de fluxo (fase, dia, último contato, flags)
- PatientDetailPage é tela de preparo pré-consulta com resumo IA + respostas + alertas + fluxo visíveis
- 1 clique do dashboard leva ao resumo IA do paciente
- Interface responsiva funciona em mobile (375px) e desktop (1280px+)
- Código morto /medico/* removido
- DashboardPage.tsx (admin) inalterado
- `tsc --noEmit` e `vite build` green
- Success criteria re-verificados em browser

## Requirement Coverage

- Covers: R089, R090, R091, R092, R093, R094, R095
- Partially covers: none
- Leaves for later: R096 (push notifications), R097 (PDF export)
- Orphan risks: none

## Slices

- [x] **S01: API enriquecida + Dashboard patient-centric** `risk:high` `depends:[]`
  > After this: médico abre /physician/dashboard e vê todos os pacientes com fase do fluxo, dia atual, último contato, e flags de atenção na lista principal. API backend retorna dados enriquecidos num único endpoint.

- [x] **S02: Tela de preparo pré-consulta consolidada** `risk:medium` `depends:[S01]`
  > After this: médico clica num paciente → vê resumo IA + respostas livres + alertas + status fluxo consolidados na tela, sem navegar por tabs. Brain icon desnecessário — resumo IA já é visível.

- [x] **S03: Limpeza do código morto /medico/*** `risk:low` `depends:[]`
  > After this: MedicoDashboard, PacientesList, ProntuarioView, MedicoAuthContext e hooks associados deletados. grep por esses componentes retorna zero. Build green.

- [x] **S04: Polish responsivo + verificação integrada** `risk:low` `depends:[S01,S02,S03]`
  > After this: dashboard e detalhe do paciente funcionam bem em mobile (375px, cards touch-friendly) e desktop (1280px+, tabela densa). Typecheck e build green. Verificação visual em browser com viewport resize.

## Boundary Map

### S01 → S02

Produces:
- Endpoint backend `GET /api/v2/physician/patients` retornando lista de pacientes com: `flow_phase` (onboarding/daily_follow_up/quiz_mensal), `flow_current_day` (int), `last_interaction` (datetime), `unacknowledged_alerts_count` (int), `flow_status` (active/paused/completed)
- Hook `usePhysicianPatients()` no frontend consumindo o novo endpoint com search, filtering, pagination
- `PhysicianDashboard.tsx` reescrito com visão patient-centric (tabela com flow data por paciente)
- Click handler que navega para `/physician/patients/:id`

Consumes:
- nothing (first slice)

### S01 → S04

Produces:
- Mesmos que S01 → S02 — o PhysicianDashboard e o hook precisam de polish responsivo

Consumes:
- nothing (first slice)

### S02 → S04

Produces:
- `PatientDetailPage.tsx` refatorado como tela de preparo pré-consulta consolidada
- Seções visíveis sem tabs: AI summary, respostas recentes, alertas, flow status
- Wiring do endpoint `GET /api/v2/patients/{id}/flow-responses` no frontend

Consumes from S01:
- Hook `usePhysicianPatients()` para navegação de volta ao dashboard
- Rota `/physician/patients/:id` já conectada ao PhysicianDashboard

### S03 (independent)

Produces:
- Deleção de: `MedicoDashboard.tsx`, `PacientesList.tsx`, `ProntuarioView.tsx`, `MedicoAuthContext.tsx`, `useMedicoDashboardStats.ts`
- Limpeza de rotas /medico/* em `MedicoRoutes.tsx` (preservar redirects mínimos se MedicoLogin ficar)
- Build green após deleção

Consumes:
- nothing (independent cleanup)

### S04 (terminal)

Produces:
- Responsive polish em PhysicianDashboard (desktop: tabela densa, mobile: cards)
- Responsive polish em PatientDetailPage (desktop: grid multi-coluna, mobile: seções empilhadas)
- Verificação visual em browser com viewport resize
- `tsc --noEmit` + `vite build` green

Consumes from S01:
- PhysicianDashboard com tabela de pacientes
Consumes from S02:
- PatientDetailPage com tela pré-consulta
Consumes from S03:
- Codebase limpo sem código morto /medico/*
