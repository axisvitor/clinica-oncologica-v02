# Project

## What This Is

Sistema de acompanhamento oncológico via WhatsApp para acompanhamento contínuo entre consultas. O backend roda em FastAPI + Celery + PostgreSQL + Redis/Dragonfly, com WuzAPI como provedor único de WhatsApp e frontends web para operação clínica. M001 endureceu o pipeline de fluxo de mensagens; M002 concluiu o corte de autenticação da equipe para um fluxo próprio de email/senha com sessão Redis + cookie HttpOnly, removendo a dependência operacional de Firebase Auth para staff login. O próximo foco é M003: reduzir hotspots grandes, remover código morto real e limpar compatibilidades obsoletas sem introduzir regressão funcional desnecessária.

## Core Value

Médicos e operadores precisam acessar e operar o sistema com confiabilidade, e quem mantém a base precisa conseguir evoluí-la sem medo de quebrar auth, fluxo WhatsApp, dashboard ou integrações sensíveis por causa de arquivos enormes e legado mal delimitado.

## Current State

- M001 concluído: pipeline de fluxo agora tem retry, recovery, observabilidade e testes de integração.
- M002 concluído: `POST /api/v2/auth/login` autentica por email/senha local, emite a sessão canônica DB + Redis + cookie HttpOnly, e `verify-session` / `logout` / auth de rota protegida funcionam no contrato centrado em `user_id`.
- Usuários existentes e contas criadas por admin agora recuperam/ativam acesso por email através de `reset-request` / `reset-confirm`, sem recriação manual e sem senha temporária em texto puro no caminho canônico.
- O frontend e o realtime foram cortados para semântica session-first: `AuthContext`, `/login`, `/medico/login`, rotas públicas de recuperação e bootstrap websocket não dependem mais de Firebase SDK/tokens.
- O hard cut foi concluído: runtime/config de staff auth não exige Firebase Auth, `session_auth` virou o sinal operacional verdadeiro, e o repositório ganhou provas focadas + guarda estática para evitar reintrodução.
- O replay local sem Firebase confirmou login browser → `/dashboard` → reload no contrato novo; o stack ainda pode exibir erros pós-login de dashboard relacionados a drift de query/dados fora do escopo de auth.
- M003 preparado: o próximo ciclo é estrutural, começando por inventário de hotspots/dead code e pelos seams mais valiosos de backend auth/session e frontend api-client/types.

## Architecture / Key Patterns

- Backend FastAPI com AsyncSession nas rotas API e Session síncrona nos workers Celery.
- Sessão autenticada baseada em Redis + cookie HttpOnly, com validação em `backend-hormonia/app/dependencies/auth_dependencies.py` e identidade canônica por `user_id`.
- Frontend dashboard em React/Vite com `AuthContext`, `apiClient` modular e bootstrap de WebSocket orientados a sessão própria.
- O repo já usa uma mistura de refactors por composição, shims estritos, tombstones e camadas de compatibilidade; M003 precisa distinguir o que ainda tem valor do que só adiciona ruído.
- As superfícies mais sensíveis para esta fase são auth/sessão, fluxo WhatsApp, dashboard/admin e integrações com Redis/Postgres, WuzAPI e AI/ADK.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [x] M001: Bulletproof Flow Pipeline — fluxo WhatsApp resiliente com retry, recovery, observabilidade e prova integrada ponta a ponta.
- [x] M002: First-Party Authentication Cutover — login local, recuperação/first-access, cutover frontend/realtime e hard cut sem Firebase Auth para staff concluídos.
- [ ] M003: Structural Refactor And Dead-Code Cleanup — hotspots críticos menores, compatibilidade obsoleta reduzida e base mais segura de manter sem regressão visível desnecessária.
