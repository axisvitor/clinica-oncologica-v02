# Project

## What This Is

Sistema de acompanhamento oncológico via WhatsApp para acompanhamento contínuo entre consultas. O backend roda em FastAPI + Celery + PostgreSQL + Redis/Dragonfly, com WuzAPI como provedor único de WhatsApp e frontends web para operação clínica. M001 endureceu o pipeline de fluxo de mensagens; M002 concluiu o corte de autenticação da equipe para um fluxo próprio de email/senha com sessão Redis + cookie HttpOnly, removendo a dependência operacional de Firebase Auth para staff login.

## Core Value

Médicos e operadores precisam acessar o sistema com confiabilidade para acompanhar pacientes oncológicos continuamente, sem atrito de autenticação e sem depender de um provedor externo frágil para o login da equipe.

## Current State

- M001 concluído: pipeline de fluxo agora tem retry, recovery, observabilidade e testes de integração.
- M002 concluído: `POST /api/v2/auth/login` autentica por email/senha local, emite a sessão canônica DB + Redis + cookie HttpOnly, e `verify-session` / `logout` / auth de rota protegida funcionam no contrato centrado em `user_id`.
- Usuários existentes e contas criadas por admin agora recuperam/ativam acesso por email através de `reset-request` / `reset-confirm`, sem recriação manual e sem senha temporária em texto puro no caminho canônico.
- O frontend e o realtime foram cortados para semântica session-first: `AuthContext`, `/login`, `/medico/login`, rotas públicas de recuperação e bootstrap websocket não dependem mais de Firebase SDK/tokens.
- O hard cut foi concluído: runtime/config de staff auth não exige Firebase Auth, `session_auth` virou o sinal operacional verdadeiro, e o repositório ganhou provas focadas + guarda estática para evitar reintrodução.
- O replay local sem Firebase confirmou login browser → `/dashboard` → reload no contrato novo; o stack ainda pode exibir erros pós-login de dashboard relacionados a drift de query/dados fora do escopo de auth.

## Architecture / Key Patterns

- Backend FastAPI com AsyncSession nas rotas API e Session síncrona nos workers Celery.
- Sessão autenticada baseada em Redis + cookie HttpOnly, com validação em `backend-hormonia/app/dependencies/auth_dependencies.py` e identidade canônica por `user_id`.
- Frontend dashboard em React/Vite com `AuthContext`, `apiClient` modular e bootstrap de WebSocket orientados a sessão própria.
- Modelo `User` central em PostgreSQL; padrões existentes de segurança incluem password hashing, CSRF, rate limiting, audit logging e reset token assinado.
- Compatibilidade e contratos antigos estão documentados em `docs/compatibility/backward-compatibility-inventory.md`.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [x] M001: Bulletproof Flow Pipeline — fluxo WhatsApp resiliente com retry, recovery, observabilidade e prova integrada ponta a ponta.
- [x] M002: First-Party Authentication Cutover — login local, recuperação/first-access, cutover frontend/realtime e hard cut sem Firebase Auth para staff concluídos.
