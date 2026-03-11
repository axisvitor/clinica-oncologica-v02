# Project

## What This Is

Sistema de acompanhamento oncológico via WhatsApp para acompanhamento contínuo entre consultas. O backend roda em FastAPI + Celery + PostgreSQL + Redis/Dragonfly, com WuzAPI como provedor único de WhatsApp e frontends web para operação clínica. O milestone M001 já endureceu o pipeline de fluxo de mensagens; o próximo foco é substituir o Firebase Auth por autenticação própria, porque o login atual depende de uma cadeia híbrida Firebase + sessão Redis que vem gerando problemas recorrentes de autenticação.

## Core Value

Médicos e operadores precisam acessar o sistema com confiabilidade para acompanhar pacientes oncológicos continuamente, sem atrito de autenticação e sem depender de um provedor externo frágil para o login da equipe.

## Current State

- M001 concluído: pipeline de fluxo agora tem retry, recovery, observabilidade e testes de integração.
- O acesso da equipe ainda é híbrido: frontend usa Firebase SDK para email/senha, backend valida token Firebase e depois cria sessão Redis/httpOnly.
- O modelo `User` já possui `hashed_password`, `auth_provider`, `force_change_password` e `last_password_change`, então parte da base para auth local já existe.
- Há endpoints e helpers de sessão, logout, password hashing e tokens de reset, mas o caminho canônico de login ainda passa por Firebase.
- Há compat shims documentados para sessão por cookie/header/bearer e para clientes legados; M002 vai decidir o que permanece e o que sai no hard cut.

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
- [ ] M002: First-Party Authentication Cutover — substituir Firebase Auth por login próprio com sessão local, migração de usuários existentes e hard cut sem dependência runtime do Firebase.
