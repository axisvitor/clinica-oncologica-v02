# T01: Refatorar PatientDetailPage como tela de preparo pré-consulta

**Slice:** S02
**Milestone:** M010

## Goal
Reorganizar PatientDetailPage para que o médico veja resumo IA, status do fluxo, e alertas como conteúdo primário visível ao abrir a página — sem precisar navegar por tabs.

## Must-Haves

### Truths
- PatientAISummary renderiza como seção principal (não dentro de tab)
- FlowStatus renderiza como seção principal (não dentro de tab)
- PatientQuizSection (alertas) renderiza como seção principal
- Tabs secundários existem para: Timeline, Respostas de Quiz (completo), Mensagens
- URL `?tab=ai-summary` ainda funciona (scroll to ou seção já visível)
- Back link navega para `/physician/dashboard`
- `tsc --noEmit` green (exceto pre-existing e2e errors)
- `vite build` green

### Artifacts
- `frontend-hormonia/src/pages/PatientDetailPage.tsx` — rewritten com layout consolidado

### Key Links
- `PatientDetailPage.tsx` → `PatientAISummary` como seção principal (não em TabsContent)
- `PatientDetailPage.tsx` → `FlowStatus` como seção principal
- `PatientDetailPage.tsx` → `PatientQuizSection` como seção principal
- `PatientDetailPage.tsx` → `Tabs` para Timeline/QuizResponses/Messages (secundário)

## Steps
1. Read current PatientDetailPage.tsx (255 lines) — understand data flow and imports
2. Redesign layout: header → overview card → 2-column grid (left: AI summary, right: flow status + alerts) → tabs (timeline, quiz responses, messages)
3. Move PatientAISummary from TabsContent to always-visible main section
4. Move FlowStatus from TabsContent.overview sidebar to always-visible section
5. Keep PatientQuizSection above tabs (already there, just ensure visible)
6. Reduce tabs to: Timeline, Respostas de Quiz, Mensagens (remove AI Summary and AI Chat tabs)
7. Update back link to navigate to /physician/dashboard instead of /patients
8. Handle ?tab=ai-summary param gracefully (section already visible, no action needed)
9. Verify: `tsc --noEmit`, `vite build`

## Context
- Current layout: header → overview → quiz section → tabs (overview/timeline/quiz-responses/ai-summary/ai-chat/messages)
- PatientAISummary is 593 lines, self-contained, takes patientId + patientName props
- FlowStatus is 283 lines, takes patientId prop, manages its own data fetching
- PatientQuizSection is 152 lines, already above tabs — just needs to stay visible
- S01 Brain icon navigates to ?tab=ai-summary — since AI summary will be visible by default, the param becomes a no-op (section already showing)
- Keep QuickActions in the sidebar for flow operations (start/pause/advance)
