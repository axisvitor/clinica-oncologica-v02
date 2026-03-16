# Project

## What This Is

Sistema de acompanhamento oncológico via WhatsApp para acompanhamento contínuo entre consultas. O backend roda em FastAPI + Celery + PostgreSQL + Dragonfly (drop-in Redis), com WuzAPI como provedor único de WhatsApp e frontends web para operação clínica. Pacientes em hormonioterapia recebem mensagens diárias por WhatsApp em 3 fases (onboarding 15 dias, follow-up diário até dia 45, ciclo mensal depois), respondem livremente com texto, e a IA reformula perguntas para manter engajamento natural. Cada médico configura o template do seu consultório. A cada 30 dias, um quiz web avalia sintomas clínicos. Antes da consulta, a IA gera um resumo mensal detalhado para o médico não precisar re-perguntar o mês inteiro ao paciente.

## Core Value

Diminuir o tempo de consulta e melhorar a qualidade do atendimento oncológico: o paciente mantém acompanhamento contínuo entre consultas via WhatsApp com respostas livres, e o médico chega na consulta com um resumo inteligente gerado por IA do mês inteiro de acompanhamento.

## Current State

- M001 concluído: pipeline de fluxo endurecido com retry, recovery, observabilidade e testes de integração.
- M002 concluído: login local email/senha com sessão canônica DB + Redis + cookie HttpOnly.
- M003 concluído: hotspots centrais de backend e frontend fatiados em seams menores com contratos preservados.
- M004 concluído: runtime oficial sem Firebase, auth/sessão convergidos ao contrato canônico.
- M005 concluído: schema/Alembic alinhados ao modelo final sem resíduo estrutural de Firebase.
- M006 concluído: purga final — dead code removido, bridges/aliases/tombstones removidos, prova integrada com 10 fases verdes publicada em M006-VERIFY.json.
- M007 concluído: sistema de acompanhamento refinado ponta a ponta — bug de sequenciamento corrigido (expects_response por mensagem), ~9400 linhas de abstrações mortas removidas (FlowDesigner, phantom FlowTypes, tombstones), editor de templates dia-a-dia para médico (API + UI), personalização IA calibrada com grounding proof (25 testes), respostas livres do paciente persistidas com contexto completo (dual-write + API), alertas do quiz mensal acionáveis com notificações para médico, resumo mensal por IA integrado ao dashboard. Todos os 7 requisitos (R057–R063) validados com 181 testes verdes.
- M008 concluído: onboarding real de pacientes ponta-a-ponta — stack local operacional (Postgres 5434, Dragonfly 6380, FastAPI 8000, Celery worker, WuzAPI 8081 com WhatsApp real conectado), templates clínicos semeados (onboarding 9 steps + daily follow-up 16 steps + quiz mensal 9 steps), paciente criado via API com saga de 4 steps → welcome message no WhatsApp real, processo diário com personalização Gemini entregue via WuzAPI, webhook de resposta processado com dual-write (patient_flow_responses + step_data), transição automática onboarding→daily_follow_up verificada no dia 16. Bug crítico de auth header WuzAPI corrigido (Token vs Authorization). Hybrid sync/async FlowCore bridging AsyncSession e sync Session. Todos os 8 requisitos (R067–R074) validados com 46 testes novos e 0 regressões.

## Architecture / Key Patterns

- Backend FastAPI com AsyncSession nas rotas API e Session síncrona nos workers Celery.
- Sessão autenticada baseada em Dragonfly + cookie HttpOnly, com identidade canônica por `user_id`.
- Frontend dashboard em React/Vite com `AuthContext`, `apiClient` modular e bootstrap de WebSocket.
- Fluxo de mensagens via WuzAPI com sequenciamento dia-a-dia (`SequentialMessageHandler`), personalização por IA (Gemini) com grounding calibrado, e sistema de follow-up com escalonamento.
- Templates de fluxo armazenados no banco (`FlowTemplateVersion`), editáveis pelo médico via API de day-configs + DayConfigEditor no dashboard, carregados pelo `EnhancedTemplateLoader` com cache in-memory.
- Quiz mensal como formulário web enviado por link WhatsApp, com regras de alerta clínico em `quiz_alert_rules.py` e notificações persistentes para o médico.
- Respostas livres do paciente persistidas em `patient_flow_responses` com contexto de fluxo (dia, mensagem, timestamp), consultáveis via API com filtro de data.
- Resumo mensal por IA via `PatientSummaryService` com Gemini 2.5 Flash, consumindo respostas estruturadas + alertas do quiz.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [x] M001: Bulletproof Flow Pipeline — fluxo WhatsApp resiliente com retry, recovery, observabilidade e prova integrada.
- [x] M002: First-Party Authentication Cutover — login local, recuperação/first-access, cutover frontend/realtime e hard cut sem Firebase Auth.
- [x] M003: Structural Refactor And Dead-Code Cleanup — hotspots menores, compatibilidade obsoleta reduzida.
- [x] M004: Convergência Canônica de Runtime — runtime sem Firebase, auth/sessão convergidos.
- [x] M005: Fechamento Definitivo de Schema e Migrações — schema/Alembic alinhados ao modelo final.
- [x] M006: Purga Final de Código Morto e Resíduo Legado — bridges, aliases, tombstones e código morto removidos com prova final.
- [x] M007: Refinamento dos Fluxos de Acompanhamento — sequenciamento correto, editor de templates para médico, personalização IA, armazenamento de respostas, quiz review, resumo mensal para consulta.
- [x] M008: Onboarding Real de Pacientes — stack local rodando, WuzAPI real conectado, templates semeados, fluxo ponta-a-ponta de criação → welcome → ciclo diário → resposta → transição de fase.
