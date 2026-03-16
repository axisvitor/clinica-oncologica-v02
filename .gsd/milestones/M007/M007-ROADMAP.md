# M007: Refinamento dos Fluxos de Acompanhamento

**Vision:** Transformar o sistema de acompanhamento de um protótipo funcional em uma ferramenta clínica real: o paciente recebe mensagens bem sequenciadas e reformuladas por IA no WhatsApp, responde livremente, o médico configura os templates do seu consultório, e antes de cada consulta tem um resumo inteligente do mês inteiro de acompanhamento.

## Success Criteria

- Mensagens do dia são enviadas respeitando a mecânica de espera: quando configurada, a próxima mensagem só sai após resposta do paciente
- O médico edita o conteúdo de cada dia do fluxo numa interface simples de lista e o paciente recebe o conteúdo atualizado
- O paciente percebe variação natural nas perguntas ao longo de 45+ dias
- Respostas livres do paciente ficam vinculadas ao contexto do fluxo (dia, mensagem, timestamp)
- Alertas clínicos do quiz mensal chegam ao médico com ação clara
- O médico acessa um resumo IA do mês antes da consulta

## Key Risks / Unknowns

- Bug de disparo em bulk pode ter race conditions na mecânica distribuída de send_mode/awaiting_response
- Calibração de grounding IA para reformulação natural vs. fidelidade ao template
- Integração do pipeline de respostas livres com o PatientSummaryService

## Proof Strategy

- Bug de sequenciamento → retire em S01 provando que mensagens com `expects_response=true` realmente esperam resposta antes de continuar
- Abstrações mortas → retire em S02 provando build/typecheck/testes verdes após remoção do FlowDesigner e simplificações
- Editor de templates → retire em S03 provando que médico cria/edita template e paciente recebe conteúdo atualizado
- Personalização e respostas → retire em S04 provando que IA reformula com grounding e respostas são armazenadas com contexto
- Alertas quiz → retire em S05 provando que alerta clínico chega ao médico via notificação/dashboard
- Resumo mensal → retire em S06 provando que IA gera resumo a partir das respostas do mês e médico acessa no dashboard

## Verification Classes

- Contract verification: testes unitários/integração para sequenciamento, armazenamento de respostas, alertas
- Integration verification: fluxo ponta a ponta envio → resposta → armazenamento → resumo no stack real
- Operational verification: editor funcional no dashboard, resumo acessível, alertas visíveis
- UAT / human verification: qualidade subjetiva da reformulação IA e do resumo mensal (review manual)

## Milestone Definition of Done

This milestone is complete only when all are true:

- O bug de disparo em bulk está corrigido com prova de sequenciamento correto
- FlowDesigner visual e abstrações mortas foram removidos com build/testes verdes
- Médico consegue editar templates dia-a-dia no dashboard e o conteúdo atualizado chega ao paciente
- Respostas livres do paciente são persistidas com contexto de fluxo
- Alertas do quiz mensal chegam ao médico de forma acionável
- Resumo mensal por IA é gerado e acessível no dashboard do médico
- Os success criteria são verificados por testes e por exercício real do fluxo

## Requirement Coverage

- Covers: R057, R058, R059, R060, R061, R062, R063
- Partially covers: none
- Leaves for later: R064 (override por paciente — deferred)
- Orphan risks: none
- Coverage summary: 7 active requirements · 7 mapped · 0 orphaned

## Slices

- [ ] **S01: Corrigir sequenciamento e espera de resposta** `risk:high` `depends:[]`
  > After this: mensagens do dia são enviadas uma por vez; quando `expects_response=true`, a próxima só sai depois que o paciente responde. Prova por testes focados de sequenciamento.

- [ ] **S02: Remover abstrações mortas do subsistema de fluxo** `risk:medium` `depends:[]`
  > After this: FlowDesigner visual (~3300 linhas) deletado, FlowTypes fantasma removidos do enum, knowledge graph morto removido, tombstones residuais limpos. Build e testes verdes.

- [ ] **S03: Editor de templates dia-a-dia para o médico** `risk:high` `depends:[S01,S02]`
  > After this: o médico abre uma UI de lista de dias no dashboard, edita conteúdo, define tipo (pergunta/motivação/lembrete), marca se espera resposta, e salva. Template publicado afeta todos os pacientes do médico.

- [ ] **S04: Personalização IA e armazenamento de respostas** `risk:medium` `depends:[S01]`
  > After this: a IA reformula perguntas com grounding calibrado, e respostas livres do paciente são persistidas com contexto (dia, mensagem, timestamp) para alimentar o resumo mensal.

- [ ] **S05: Review do quiz mensal e alertas acionáveis** `risk:medium` `depends:[S04]`
  > After this: alertas clínicos do quiz chegam ao médico via notificação e destaque no dashboard, com ação recomendada. Regras de alerta revisadas.

- [ ] **S06: Resumo mensal por IA para consulta do médico** `risk:high` `depends:[S04,S05]`
  > After this: o médico acessa no dashboard um resumo IA do mês de acompanhamento do paciente — síntese de respostas, padrões, preocupações, pontos de atenção — e economiza tempo de consulta.

## Boundary Map

### S01 → S03

Produces:
- Mecânica de sequenciamento corrigida: `send_day_messages()` respeita `expects_response` por mensagem, com estado `awaiting_response` persistido em `PatientFlowState.step_data`
- Contrato de `day_config` validado: cada mensagem tem `content`, `type` (question/motivation/reminder), `expects_response`

Consumes:
- nothing (first slice)

### S01 → S04

Produces:
- Pipeline de envio estável onde a personalização IA pode operar sobre o conteúdo de cada mensagem individual sem risco de disparo em bulk

Consumes:
- nothing (first slice)

### S02 → S03

Produces:
- Subsistema de fluxo limpo de abstrações mortas: sem FlowDesigner, sem FlowTypes fantasma, sem knowledge graph morto
- Template system simplificado usando apenas `FlowTemplateVersion` + `EnhancedTemplateLoader`

Consumes:
- nothing (independent slice)

### S03 → S06

Produces:
- API CRUD para templates por médico (`POST/PUT /api/v2/flow-templates/{doctor_id}/days`)
- UI de edição de lista de dias no dashboard
- Modelo de dados: cada dia tem `day_number`, `content`, `message_type` (question/motivation/reminder), `expects_response`

Consumes from S01:
- Contrato de `day_config` com `expects_response` por mensagem
Consumes from S02:
- Subsistema limpo sem abstrações mortas

### S04 → S05

Produces:
- Respostas do paciente armazenadas com contexto de fluxo (dia, mensagem, timestamp) em `patient_responses` ou similar
- Pipeline de personalização IA calibrado com grounding metrics

Consumes from S01:
- Sequenciamento estável para vincular resposta à mensagem correta

### S04 → S06

Produces:
- Dados estruturados de respostas do paciente ao longo do mês, prontos para consumo pelo `PatientSummaryService`
- Personalização IA validada

Consumes from S01:
- Sequenciamento estável

### S05 → S06

Produces:
- Alertas do quiz mensal com path acionável até o médico (notificação + dashboard)
- Dados de quiz review integráveis ao resumo mensal

Consumes from S04:
- Respostas estruturadas que contextualizam os alertas

### S06

Produces:
- Resumo mensal por IA acessível no dashboard do médico
- Integração completa: respostas livres + quiz + alertas → resumo inteligente

Consumes from S04:
- Respostas do paciente estruturadas com contexto
Consumes from S05:
- Dados de quiz e alertas clínicos
