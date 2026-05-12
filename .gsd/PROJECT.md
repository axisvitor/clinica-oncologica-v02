# Project

## What This Is

Sistema de acompanhamento oncológico via WhatsApp para acompanhamento contínuo entre consultas. O backend roda em FastAPI + Taskiq + PostgreSQL + Dragonfly, com WuzAPI como provedor de WhatsApp e frontends web para operação clínica. Pacientes em hormonioterapia recebem mensagens diárias por WhatsApp em fases clínicas, respondem livremente com texto, completam quiz mensal, e o médico usa resumos/alertas para chegar à consulta com contexto do mês inteiro.

O estado atual inclui fluxo WhatsApp real, autenticação própria session-first, dashboard médico patient-centric, otimizações de carregamento, Taskiq no lugar de Celery, e override de template por paciente. M013 muda o foco para remediação de segurança crítica/alta baseada no pacote de análise `report.md`, `validation_report.md` e `attack_path_analysis_report.md`.

## Core Value

Diminuir o tempo de consulta e melhorar a qualidade do atendimento oncológico sem expor dados sensíveis: o paciente mantém acompanhamento contínuo entre consultas via WhatsApp, e o médico acessa contexto confiável e protegido do mês inteiro de acompanhamento.

## Project Shape

- **Complexity:** complex
- **Why:** O sistema cruza WhatsApp/WuzAPI, backend FastAPI, sessões, PostgreSQL, workers Taskiq, uploads/reports, quiz público e dados PHI/LGPD; M013 corrige múltiplas fronteiras de segurança críticas/altas com provas negativas.

## Current State

- M001–M009 concluídos: pipeline de fluxo, auth canônico, refactor estrutural, convergência runtime/schema, purga de código morto, refinamento de fluxos, onboarding real ponta-a-ponta, migração Celery→Taskiq.
- M010 concluído: dashboard médico refinado — visão patient-centric com contexto de fluxo, tela de preparo pré-consulta consolidada, responsivo desktop+mobile, código morto `/medico/*` removido.
- M011 concluído: otimização de carregamento e redução de stress no banco — per-user Redis caching no physician/patients e dashboard, composite index em `patient_flow_states`, frontend request discipline em hooks críticos.
- M012 concluído: override de template por paciente — tabela `patient_flow_overrides`, lookup override-first com cache Redis, skip handling nos dois caminhos do pipeline, editor no PatientDetailPage, e verificador `verify-m012.sh` green.
- M013 planejado: remediação dos findings críticos/altos F-01..F-11 do scan de segurança, com controles compartilhados e matriz de prova reproduzível.

## Architecture / Key Patterns

- Backend FastAPI com dependências de autenticação/autorização via `Depends`, sessão Redis/Dragonfly + cookie HttpOnly, e identidade canônica por `user_id`.
- Helpers existentes de autorização/patient access em `app/dependencies/auth_dependencies.py`, `app/dependencies/auth_role_dependencies.py`, `app/dependencies/business_dependencies.py` e `app/api/v2/_quiz_shared.py` devem ser reaproveitados/centralizados em vez de criar patches soltos.
- Task queue via Taskiq com Dragonfly como broker; alguns serviços ORM internos ainda usam sessão síncrona em workers, conforme padrões já documentados em `.gsd/KNOWLEDGE.md`.
- WhatsApp/WuzAPI são fronteiras externas sensíveis; management API exige auth/role e media fetch exige SSRF guard.
- Uploads/reports privados não devem depender de `StaticFiles` público; acesso privado passa por endpoint autenticado/ownership-checked ou URL assinada curta.
- Provas de segurança devem preferir testes negativos com fixtures dois-médicos/dois-pacientes, dependency overrides FastAPI e mocks para WuzAPI/queue quando serviços reais não estiverem disponíveis.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [x] M001: Bulletproof Flow Pipeline — Recuperação e observabilidade do pipeline de acompanhamento.
- [x] M002: First-Party Authentication Cutover — Autenticação própria sem Firebase no caminho oficial.
- [x] M003: Structural Refactor And Dead-Code Cleanup — Redução de hotspots e limpeza comprovada.
- [x] M004: Convergência Canônica de Runtime — Runtime oficial convergido no contrato canônico.
- [x] M005: Fechamento Definitivo de Schema e Migrações — Schema/migrations alinhados ao estado vivo.
- [x] M006: Purga Final de Código Morto e Resíduo Legado — Resíduo legado removido com prova.
- [x] M007: Refinamento dos Fluxos de Acompanhamento — Sequenciamento, templates, IA e alertas clínicos refinados.
- [x] M008: Onboarding Real de Pacientes — Stack local e WhatsApp real ponta a ponta.
- [x] M009: Substituição do Celery por Taskiq — Workers migrados para Taskiq.
- [x] M010: Refinamento do Dashboard Médico — Dashboard médico patient-centric e preparo pré-consulta.
- [x] M011: Otimização de Carregamento e Redução de Stress no Banco — Caching e disciplina de requests.
- [x] M012: Override de Template por Paciente — Personalização por paciente sobre template global.
- [ ] M013: Remediação de Segurança Crítica/Alta — Fechar PHI boundaries críticos/altos com provas negativas reproduzíveis.
- [ ] M014: Hardening Médio e Proof Gaps — Provisório: corrigir médios/deferred não cobertos por M013.
- [ ] M015: Runtime Security Validation — Provisório: harness production-like se necessário para validação dinâmica ampla.
