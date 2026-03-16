# M007: Refinamento dos Fluxos de Acompanhamento

**Vision:** Transformar o sistema de acompanhamento de um protótipo funcional em uma ferramenta clínica real: o paciente recebe mensagens bem sequenciadas e reformuladas por IA no WhatsApp, responde livremente, o médico configura os templates do seu consultório, e antes de cada consulta tem um resumo inteligente do mês inteiro de acompanhamento.

## Success Criteria

- Mensagens do dia são enviadas respeitando a mecânica de espera: quando `expects_response=true`, a próxima mensagem só sai após resposta do paciente
- O médico edita o conteúdo de cada dia do fluxo numa interface de lista e o paciente recebe o conteúdo atualizado na próxima execução
- Abstrações mortas (FlowDesigner visual, FlowTypes fantasma, knowledge graph morto, tombstones) foram removidas sem regredir build ou testes
- O paciente percebe variação natural nas perguntas ao longo de 45+ dias sem perder fidelidade ao template base
- Respostas livres do paciente ficam vinculadas ao contexto do fluxo (dia, mensagem, timestamp) e são consultáveis
- Alertas clínicos do quiz mensal chegam ao médico com ação clara — notificação e destaque no dashboard
- O médico acessa um resumo IA do mês de acompanhamento do paciente antes da consulta

## Key Risks / Unknowns

- Bug de disparo em bulk pode ter race conditions na mecânica distribuída de send_mode/awaiting_response entre 4 mixins + 2 flow functions — sequenciamento precisa de prova antes de qualquer outro trabalho
- Calibração de grounding IA para reformulação natural vs. fidelidade ao template — requer experimentação com prompts e thresholds de similaridade
- PatientSummaryService (669 linhas) já existe com Gemini 2.5 Flash mas a integração com dados de fluxo diário ainda não está fechada

## Proof Strategy

- Bug de sequenciamento → retirar em S01 construindo o fix real no `_send_all_sequential` e `_send_remaining_after_response`, provando que `expects_response=true` no meio da sequência realmente bloqueia
- Abstrações mortas → retirar em S02 provando que build, typecheck e testes permanecem verdes após remoção de ~4800 linhas de FlowDesigner + FlowTypes fantasma + tombstones
- Editor de templates para médico → retirar em S03 provando que médico edita template via UI no dashboard e o conteúdo atualizado é carregado pelo `EnhancedTemplateLoader`
- Calibração IA e respostas → retirar em S04 provando que IA reformula com grounding verificável e respostas livres são persistidas com contexto de fluxo
- Alertas → retirar em S05 provando que alerta clínico gera notificação e aparece destacado no dashboard do médico
- Resumo mensal → retirar em S06 provando que `PatientSummaryService` consome respostas do mês e o resumo é exibido no dashboard

## Verification Classes

- Contract verification: testes unitários/integração para sequenciamento (`sequencing.py`), armazenamento de respostas, alertas do quiz, geração de resumo
- Integration verification: fluxo ponta a ponta envio → resposta → armazenamento → resumo no stack real (backend + DB + Dragonfly)
- Operational verification: editor de templates funcional no dashboard, resumo acessível, alertas visíveis para o médico
- UAT / human verification: qualidade subjetiva da reformulação IA (naturalidade, grounding), utilidade do resumo mensal para consulta médica

## Milestone Definition of Done

This milestone is complete only when all are true:

- Bug de disparo em bulk corrigido: `_send_all_sequential` para no primeiro `expects_response=true` e `_send_remaining_after_response` continua respeitando a mesma regra
- FlowDesigner visual (~4800 linhas incluindo testes), FlowTypes fantasma (TREATMENT_ADHERENCE, SYMPTOM_TRACKING, MEDICATION_REMINDER), knowledge graph morto e tombstones removidos com build + testes verdes
- Médico edita templates dia-a-dia via API + UI no dashboard: CRUD funcional sobre `FlowTemplateVersion` com `day_configs` contendo `content`, `message_type`, `expects_response` por dia
- Respostas livres do paciente persistidas com `flow_state_id`, `day_number`, `message_index`, `timestamp` e consultáveis por paciente/período
- Alertas do quiz mensal geram notificação via modelo `Notification` e aparecem destacados no dashboard
- Resumo mensal por IA é gerado pelo `PatientSummaryService` consumindo respostas estruturadas e alertas, acessível no dashboard
- Success criteria verificados por testes automatizados e por exercício no stack real

## Requirement Coverage

- Covers: R057, R058, R059, R060, R061, R062, R063
- Partially covers: none
- Leaves for later: R064 (override por paciente — deferred)
- Orphan risks: none

## Slices

- [x] **S01: Corrigir sequenciamento e espera de resposta** `risk:high` `depends:[]`
  > After this: mensagens do dia são enviadas uma por vez; quando `expects_response=true`, a próxima só sai depois que o paciente responde. Provado por testes focados de sequenciamento contra o código real.

- [x] **S02: Remover abstrações mortas do subsistema de fluxo** `risk:medium` `depends:[]`
  > After this: FlowDesigner visual (~4800 linhas com testes) deletado, FlowTypes fantasma (TREATMENT_ADHERENCE, SYMPTOM_TRACKING, MEDICATION_REMINDER) removidos do enum, tombstone `templates/manager.py` removido, referências mortas limpas. Build frontend, typecheck e testes backend verdes.

- [x] **S03: Editor de templates dia-a-dia para o médico** `risk:high` `depends:[S01,S02]`
  > After this: o médico abre uma UI de lista de dias no dashboard, edita conteúdo/tipo/espera-resposta por dia, salva — e o template publicado é carregado pelo `EnhancedTemplateLoader` para envio real.

- [x] **S04: Personalização IA e armazenamento de respostas** `risk:medium` `depends:[S01]`
  > After this: a IA reformula mensagens com grounding calibrado (similarity check contra template base), e respostas livres do paciente são persistidas com contexto completo (dia, mensagem, timestamp) e consultáveis via API.

- [x] **S05: Alertas do quiz mensal acionáveis para o médico** `risk:medium` `depends:[S04]`
  > After this: quando o quiz mensal gera um alerta clínico, uma notificação é criada para o médico e o alerta aparece destacado no dashboard com ação recomendada.

- [ ] **S06: Resumo mensal por IA integrado ao dashboard** `risk:high` `depends:[S04,S05]`
  > After this: o médico acessa no dashboard um resumo IA do mês de acompanhamento — síntese de respostas livres, padrões, alertas, pontos de atenção — gerado pelo `PatientSummaryService` e renderizado com dados reais.

## Boundary Map

### S01 → S03

Produces:
- `_send_all_sequential()` em `sequencing.py` respeita `expects_response` por mensagem individual, parando no primeiro `true` e persistindo `awaiting_response` + `current_day_message_index` em `PatientFlowState.step_data`
- `_send_remaining_after_response()` em `_flow_response_flow.py` continua do index salvo, respeitando `expects_response` em cada mensagem restante
- Contrato de `day_config` validado: cada mensagem tem `content` (str), `type` (question|motivation|reminder), `expects_response` (bool)

Consumes:
- nothing (first slice)

### S01 → S04

Produces:
- Pipeline de envio estável onde a personalização IA opera sobre cada mensagem individual sem risco de bulk dispatch
- `pending_response_context` em `step_data` vincula a espera de resposta à mensagem exata (day_number + message_index)

Consumes:
- nothing (first slice)

### S02 → S03

Produces:
- Frontend livre do FlowDesigner: `frontend-hormonia/src/features/flow-designer/` removido, imports mortos limpos
- Backend com `FlowType` enum contendo apenas tipos canônicos (ONBOARDING, DAILY_FOLLOW_UP, QUIZ_MENSAL, CUSTOM)
- `templates/manager.py` tombstone removido, `templates/repository.py` e `templates/validator.py` revisados
- Subsistema de templates limpo usando apenas `FlowTemplateVersion` + `EnhancedTemplateLoader`

Consumes:
- nothing (independent slice)

### S03 → S04

Produces:
- API CRUD para day_configs do template: `GET/PUT /api/v2/flows/templates/{template_id}/days` retornando lista de `{day_number, content, message_type, expects_response}`
- UI de edição de lista de dias no dashboard sob `/templates` ou `/flow-templates`
- `FlowTemplateVersion.day_configs` como JSONB com schema validado por Pydantic

Consumes from S01:
- Contrato de `expects_response` por mensagem respeitado pelo pipeline de envio
Consumes from S02:
- Subsistema limpo sem FlowDesigner, sem FlowTypes fantasma

### S03 → S06

Produces:
- Templates editáveis que definem a estrutura de conteúdo do fluxo para cada médico
- Modelo de dados onde cada dia tem `day_number`, `content`, `message_type`, `expects_response`

Consumes from S01:
- `expects_response` respeitado no envio
Consumes from S02:
- FlowDesigner e abstrações mortas removidos

### S04 → S05

Produces:
- Respostas do paciente armazenadas em tabela `patient_flow_responses` com `flow_state_id`, `day_number`, `message_index`, `response_text`, `responded_at`
- Modelo Alembic migration para `patient_flow_responses`
- API `GET /api/v2/patients/{patient_id}/flow-responses` para consulta de respostas por período
- Pipeline de personalização IA calibrado com grounding metrics (similarity ratio contra template base)

Consumes from S01:
- `pending_response_context` em `step_data` para vincular resposta à mensagem correta

### S04 → S06

Produces:
- Dados estruturados de respostas do paciente ao longo do mês em `patient_flow_responses`
- Query de respostas por paciente + período pronto para consumo pelo `PatientSummaryService`

Consumes from S01:
- Sequenciamento estável com contexto de resposta

### S05 → S06

Produces:
- Alertas do quiz mensal com notificação via modelo `Notification` (tabela `notifications`)
- `quiz_alert_id` linkado à notificação para rastreabilidade
- API de alertas pendentes para o médico com contagem e severidade
- Dados de alertas integráveis ao resumo mensal

Consumes from S04:
- Respostas estruturadas que contextualizam os alertas do quiz

### S06 (terminal)

Produces:
- `PatientSummaryService.generate_monthly_summary()` consumindo `patient_flow_responses` + alertas do quiz
- Componente frontend `PatientMonthlySummary` no dashboard do médico
- API `GET /api/v2/ai/summary/{patient_id}/monthly` retornando resumo estruturado
- Integração completa: respostas livres + quiz + alertas → resumo inteligente

Consumes from S04:
- `patient_flow_responses` com dados estruturados por paciente/período
Consumes from S05:
- Alertas do quiz mensal com severidade e ação recomendada
Consumes from S03:
- Estrutura de templates para contexto de qual conteúdo o paciente recebeu
