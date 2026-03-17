# Project

## What This Is

Sistema de acompanhamento oncológico via WhatsApp para acompanhamento contínuo entre consultas. O backend roda em FastAPI + Taskiq + PostgreSQL + Dragonfly (drop-in Redis), com WuzAPI como provedor único de WhatsApp e frontends web para operação clínica. Pacientes em hormonioterapia recebem mensagens diárias por WhatsApp em 3 fases (onboarding 15 dias, follow-up diário até dia 45, ciclo mensal depois), respondem livremente com texto, e a IA reformula perguntas para manter engajamento natural. Cada médico configura o template do seu consultório. A cada 30 dias, um quiz web avalia sintomas clínicos. Antes da consulta, a IA gera um resumo mensal detalhado para o médico não precisar re-perguntar o mês inteiro ao paciente.

## Core Value

Diminuir o tempo de consulta e melhorar a qualidade do atendimento oncológico: o paciente mantém acompanhamento contínuo entre consultas via WhatsApp com respostas livres, e o médico chega na consulta com um resumo inteligente gerado por IA do mês inteiro de acompanhamento.

## Current State

- M001–M009 concluídos: pipeline de fluxo, auth canônico, refactor estrutural, convergência runtime/schema, purga de código morto, refinamento de fluxos, onboarding real ponta-a-ponta, migração Celery→Taskiq.
- M010 concluído: dashboard médico refinado — visão patient-centric com contexto de fluxo, tela de preparo pré-consulta consolidada, responsivo desktop+mobile, código morto /medico/* removido.
- M011 em andamento: S01 (backend caching + index composto) concluído — Redis caching per-user no physician/patients (TTL=60s), composite index em patient_flow_states. S02 (frontend request discipline) concluído — 21 hooks normalizados (staleTime ≥ 60s dashboard, ≥ 120s admin; refetchInterval ≥ 120s), tsc + vite build green. S03 (verificação integrada) pendente.

## Architecture / Key Patterns

- Backend FastAPI com AsyncSession nas rotas API e Session síncrona em serviços ORM internos dos workers Taskiq.
- Sessão autenticada baseada em Dragonfly + cookie HttpOnly, com identidade canônica por `user_id`.
- Frontend dashboard em React 19/Vite com `AuthContext`, `apiClient` modular, shadcn/ui + Tailwind CSS 4 + Recharts.
- Task queue via Taskiq (async-native) com Dragonfly como broker (ListQueueBroker), 13 task modules (72 tasks).
- Cache infrastructure: CacheMiddleware (HTTP-level, 90s auth TTL), @cache_response decorator (per-endpoint Redis), CacheManager (unified CRUD).
- Physician dashboard em `/physician/dashboard` com patient-centric table, `/physician/patients/:id` com pre-consultation consolidated view.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [x] M001: Bulletproof Flow Pipeline
- [x] M002: First-Party Authentication Cutover
- [x] M003: Structural Refactor And Dead-Code Cleanup
- [x] M004: Convergência Canônica de Runtime
- [x] M005: Fechamento Definitivo de Schema e Migrações
- [x] M006: Purga Final de Código Morto e Resíduo Legado
- [x] M007: Refinamento dos Fluxos de Acompanhamento
- [x] M008: Onboarding Real de Pacientes
- [x] M009: Substituição do Celery por Taskiq
- [x] M010: Refinamento do Dashboard Médico
- [ ] M011: Otimização de Carregamento e Redução de Stress no Banco
