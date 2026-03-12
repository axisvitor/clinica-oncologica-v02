# Project

## What This Is

Sistema de acompanhamento oncológico via WhatsApp para acompanhamento contínuo entre consultas. O backend roda em FastAPI + Celery + PostgreSQL + Redis/Dragonfly, com WuzAPI como provedor único de WhatsApp e frontends web para operação clínica. O milestone M001 já endureceu o pipeline de fluxo de mensagens; o próximo foco é substituir o Firebase Auth por autenticação própria, porque o login atual depende de uma cadeia híbrida Firebase + sessão Redis que vem gerando problemas recorrentes de autenticação.

## Core Value

Médicos e operadores precisam acessar o sistema com confiabilidade para acompanhar pacientes oncológicos continuamente, sem atrito de autenticação e sem depender de um provedor externo frágil para o login da equipe.

## Current State

- M001 concluído: pipeline de fluxo agora tem retry, recovery, observabilidade e testes de integração.
- M002/S01 concluído: `POST /api/v2/auth/login` agora autentica por email/senha local, emite a sessão canônica DB + Redis + cookie HttpOnly, e `verify-session` / `logout` / auth de rota protegida funcionam no contrato centrado em `user_id`.
- As rotas autenticadas de perfil foram expostas canonicamente em `/api/v2/users/*`, mantendo alias legado oculto em `/api/v2/auth/*` para não quebrar consumidores durante a transição.
- O acesso da equipe ainda não completou o hard cut: frontend e bootstrap realtime continuam dependendo de Firebase SDK/tokens até S03.
- Fluxos de reset/first-access, ativação de contas criadas por admin e remoção final dos caminhos/runtime de Firebase Auth ainda ficam para S02–S04.

## Architecture / Key Patterns

- Backend FastAPI com AsyncSession nas rotas API e Session síncrona nos workers Celery.
- Sessão autenticada baseada em Redis + cookie HttpOnly, com validação em `backend-hormonia/app/dependencies/auth_dependencies.py`.
- Frontend dashboard em React/Vite com `AuthContext`, `apiClient` modular e bootstrap de WebSocket.
- Modelo `User` central em PostgreSQL; padrões existentes de segurança incluem password hashing, CSRF, rate limiting, audit logging e reset token assinado.
- Compatibilidade e contratos antigos estão documentados em `docs/compatibility/backward-compatibility-inventory.md`.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [x] M001: Bulletproof Flow Pipeline — fluxo WhatsApp resiliente com retry, recovery, observabilidade e prova integrada ponta a ponta.
- [ ] M002: First-Party Authentication Cutover — S01 concluído (core local de login/sessão), com reset/migração, cutover frontend/realtime e hard cut final ainda pendentes em S02–S04.
