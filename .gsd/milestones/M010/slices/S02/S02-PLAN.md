# S02: Tela de preparo pré-consulta consolidada

**Goal:** Refatorar PatientDetailPage para que resumo IA, status do fluxo, alertas, e respostas recentes sejam visíveis na tela principal sem navegar por tabs.
**Demo:** Médico clica num paciente no dashboard → vê resumo IA + respostas + alertas + status fluxo consolidados, sem navegar por tabs.

## Must-Haves
- PatientDetailPage mostra resumo IA (PatientAISummary) como seção principal visível sem tab
- FlowStatus visível como seção ao lado/acima do resumo IA, não escondido em tab
- Alertas do quiz (PatientQuizSection) visíveis na tela principal
- Tabs preservados para conteúdo secundário: Timeline, Respostas de Quiz completas, Mensagens
- `?tab=ai-summary` param da URL ainda funciona (compatibilidade com Brain icon do S01)
- `tsc --noEmit` green
- `vite build` green
- Back navigation funciona (voltar ao dashboard)

## Tasks

- [x] **T01: Refatorar PatientDetailPage como tela de preparo pré-consulta**
  Reorganizar layout: header + overview card + grid com resumo IA + flow status + alertas como seções primárias. Mover timeline, quiz responses completo, e mensagens para tabs secundários. Manter compatibilidade com ?tab= URL param.

## Files Likely Touched
- `frontend-hormonia/src/pages/PatientDetailPage.tsx` — rewrite layout
