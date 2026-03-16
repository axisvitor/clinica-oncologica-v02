# M007: Refinamento dos Fluxos de Acompanhamento

**Gathered:** 2026-03-15
**Status:** Ready for planning

## Project Description

Refinamento completo do sistema de acompanhamento oncológico via WhatsApp: desde o conteúdo que o paciente recebe, passando pela mecânica interna de sequenciamento, até o resumo que o médico vê antes da consulta. Inclui correção de bugs críticos, limpeza de abstrações infladas, construção de editor simples para médicos, calibração da personalização por IA, e integração do resumo mensal inteligente.

## Why This Milestone

O sistema de fluxo foi construído ao longo de M001–M006 com foco em pipeline resiliente e eliminação de legado Firebase. Agora que a base está limpa e estável, o foco muda para a **qualidade da experiência clínica** — o que o paciente recebe, como o médico configura, e como a IA conecta os dois. Os templates atuais são rascunhos de teste, existe um bug de disparo em bulk, e o potencial do resumo mensal por IA ainda não está realizado.

## User-Visible Outcome

### When this milestone is complete, the user can:

- O paciente recebe mensagens uma por vez no WhatsApp, com espera correta de resposta quando configurada
- O médico edita os templates de cada dia do fluxo (conteúdo, tipo, espera-resposta) numa UI simples de lista
- O paciente percebe que as perguntas são variadas e naturais, não repetitivas
- O paciente responde livremente em texto e as respostas ficam vinculadas ao contexto do fluxo
- Alertas clínicos do quiz mensal chegam ao médico de forma acionável
- O médico abre a consulta com um resumo IA do mês inteiro de acompanhamento do paciente

### Entry point / environment

- Entry point: dashboard web (médico) + WhatsApp (paciente) + API backend
- Environment: local dev / browser / WhatsApp via WuzAPI
- Live dependencies involved: Dragonfly (cache/sessão), PostgreSQL (dados), WuzAPI (WhatsApp), Gemini (IA)

## Completion Class

- Contract complete means: sequenciamento testado com prova de espera-de-resposta, editor de templates funcional, respostas persistidas com contexto, resumo gerado por IA
- Integration complete means: fluxo ponta a ponta de envio → resposta → armazenamento → resumo funciona no stack real
- Operational complete means: médico consegue usar o editor e acessar resumos no dashboard real

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- Fluxo de mensagens com `expects_response=true` realmente espera — mensagem seguinte só sai após resposta do paciente
- Médico edita template no dashboard, paciente recebe mensagem com conteúdo atualizado
- Respostas livres do paciente são visíveis no contexto do fluxo
- Resumo mensal por IA é gerado e acessível no dashboard do médico
- Alertas do quiz mensal chegam ao médico (não ficam passivos)

## Risks and Unknowns

- **Bug de disparo em bulk** — a mecânica de send_mode/awaiting_response é complexa e distribuída entre 4 mixins + 2 flow functions; pode haver race conditions não óbvias
- **Qualidade da reformulação IA** — calibrar grounding para ser natural sem inventar conteúdo requer experimentação
- **PatientSummaryService integration** — o serviço existe mas precisa review de como os dados do fluxo diário alimentam o resumo
- **Editor de templates** — precisa ser simples o suficiente para médico usar, mas completo o suficiente para cobrir os tipos de dia

## Existing Codebase / Prior Art

- `backend-hormonia/app/services/flow/_flow_message_flow.py` — orquestração de envio com send_mode dispatch
- `backend-hormonia/app/services/flow/_flow_response_flow.py` — continuação após resposta do paciente
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/` — 4 mixins (Sequencing, State, Personalization, Quiz)
- `backend-hormonia/app/services/template_loader_pkg/` — EnhancedTemplateLoader DB-only com cache
- `backend-hormonia/app/models/flow.py` — FlowKind, FlowTemplateVersion, PatientFlowState
- `backend-hormonia/app/agents/patient/flow_coordinator/` — FlowCoordinatorAgent, DecisionEngine, MessageGenerator, StateManager
- `backend-hormonia/app/services/follow_up_system/` — FollowUpSystemService (607 linhas)
- `backend-hormonia/app/services/ai/patient_summary_service.py` — PatientSummaryService com Gemini
- `backend-hormonia/app/config/quiz_alert_rules.py` — 15 regras de alerta clínico
- `frontend-hormonia/src/features/flow-designer/` — FlowDesigner visual (~2573 linhas) — será removido
- `frontend-hormonia/src/features/templates/TemplateManagementPage.tsx` — gerenciamento de templates existente
- `frontend-hormonia/src/pages/PhysicianDashboard.tsx` — dashboard do médico (716 linhas)

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions.

## Relevant Requirements

- R057 — Sequenciamento respeita espera de resposta
- R058 — Editor de templates simples para médico
- R059 — Abstrações mortas removidas
- R060 — Personalização IA natural e ancorada
- R061 — Respostas livres armazenadas com contexto
- R062 — Alertas do quiz acionáveis
- R063 — Resumo mensal por IA para consulta

## Scope

### In Scope

- Fix do bug de disparo em bulk de mensagens
- Editor de templates dia-a-dia com UI de lista (não canvas visual)
- Remoção do FlowDesigner visual e abstrações mortas
- Calibração da personalização IA para reformulação natural
- Armazenamento estruturado de respostas livres do paciente
- Review do quiz mensal e caminho de alertas até o médico
- Resumo mensal por IA integrado com dashboard do médico
- Template global por médico (todos os pacientes do médico recebem o mesmo fluxo)

### Out of Scope / Non-Goals

- Chatbot com menu/opções — paciente responde livremente (R065)
- Designer visual estilo N8N para médicos (R066)
- Override de template por paciente individual (R064 — deferred)
- Migração de Celery para outro task runner
- Migração de banco de dados (PostgreSQL permanece)
- Mudanças em auth/session (M002–M006 fecharam essa frente)

## Technical Constraints

- Dragonfly é drop-in Redis — código usa biblioteca `redis` do Python, sem mudança necessária
- Templates vivem no banco via `FlowTemplateVersion` com versionamento — o editor precisa usar esse modelo
- Personalização IA usa Gemini via `get_gemini_client()` — manter esse provider
- WhatsApp via WuzAPI — o contrato de envio/recebimento não muda

## Integration Points

- **WuzAPI** — envio e recebimento de mensagens WhatsApp; webhook de resposta do paciente
- **Gemini AI** — personalização de mensagens e geração de resumo mensal
- **Dragonfly** — cache de sessão, estado de follow-up, rate limiting
- **PostgreSQL** — templates, respostas, patient flow state, resumos gerados

## Open Questions

- Calibração exata do grounding de IA (threshold de similaridade) — precisa experimentação durante S04
- Formato ideal do resumo mensal para o médico — texto corrido vs. seções estruturadas vs. ambos — a decidir durante S06
