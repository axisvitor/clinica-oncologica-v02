# Project

## What This Is

Sistema de acompanhamento oncológico via WhatsApp para acompanhamento contínuo entre consultas. O backend roda em FastAPI + Celery + PostgreSQL + Redis/Dragonfly, com WuzAPI como provedor único de WhatsApp e frontends web para operação clínica. M001 endureceu o pipeline de fluxo de mensagens; M002 concluiu o corte de autenticação da equipe para um fluxo próprio de email/senha com sessão Redis + cookie HttpOnly; M003 fechou a primeira grande limpeza estrutural; M004 convergiu o runtime oficial sem Firebase; M005 fechou a convergência de schema/migrações e a próxima frente é M006 (purga final de resíduos e compatibilidades restantes).

## Core Value

Médicos e operadores precisam acessar e operar o sistema com confiabilidade, e quem mantém a base precisa conseguir evoluí-la sem medo de quebrar auth, fluxo WhatsApp, dashboard ou integrações sensíveis por causa de legado ambíguo, caminhos duplos ou resíduos mortos ainda vivos no runtime.

## Current State

- M001 concluído: pipeline de fluxo agora tem retry, recovery, observabilidade e testes de integração.
- M002 concluído: `POST /api/v2/auth/login` autentica por email/senha local, emite a sessão canônica DB + Redis + cookie HttpOnly, e `verify-session` / `logout` / auth de rota protegida funcionam no contrato centrado em `user_id`.
- M003 concluído: os hotspots centrais de backend auth/session e frontend api-client/types foram fatiados em seams menores com contratos preservados (`auth_dependencies.py` 1579→675, `src/lib/api-client/index.ts` 1304→223, `src/lib/api-client/types.ts` 1159→26).
- M004 concluído: backend + frontend oficiais estão vinculados ao contrato session-first canônico sem Firebase, `/session/*` foi aposentado/tombstonado, e o stack local sobe sem Firebase Auth com smoke roteado de `/login`, `/dashboard`, `/admin`, `/whatsapp`.
- O verificador de S01 é o gate vivo do contrato: `--report backend`/`--check backend` agora mostram zero resíduo aprovado em auth/session backend e separam as fronteiras aposentadas em `[backend-proof-only]`; `--report all`/`--check all` continuam com zero resíduo aprovado no frontend.
- M005/S01 concluído: `alembic history`, `heads`, `upgrade head` e `current` agora rodam em Postgres scrubbed só com configuração de banco; revisions históricas e backfills vazios deixaram de puxar `app.config.settings`, WuzAPI ou Firebase para o controle plane de migrations.
- M005/S02 concluído: `user_sync_log` foi publicado como `firebase_sync_history`, `audit_logs.firebase_uid` ficou quarantined como resíduo histórico/read-only, e payloads oficiais de users/admin/physicians deixaram de anunciar `firebase_uid` como contrato vivo sem quebrar a compat fallback centrada em `user_id`.
- M005/S03 concluído: banco novo (`base -> head`) e banco existente (`m005_s02_t01_publish_firebase_history_boundary -> head`) agora convergem para `m005_s03_t02_align_audit_history_head`, com `users` republicado sob colunas canônicas neutras, `audit_logs.event_type` em enum canônico e `firebase_sync_history` mantido apenas como histórico explícito.
- O harness compartilhado de testes em Postgres agora provisiona o schema via `alembic upgrade head` quando `TEST_DATABASE_URL` está definido, o que faz as suites de runtime validarem o head real em vez de um `Base.metadata.create_all()` incompleto.
- M005/S04 concluído: `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` prepara os histories `fresh` e `existing`, reexecuta os packs críticos pós-M004 no head final e sobe um uvicorn real no mesmo schema para provar `/health/ready`, `/api/v2/system/config` e o fluxo `login -> verify-session -> /users/me -> logout` sem Firebase.
- M005 concluído: o controle plane Alembic, a convergência estrutural do head canônico e a prova montada do backend agora contam a mesma história operacional sobre o schema final.
- O closeout consolidado está publicado em `.gsd/milestones/M005/M005-SUMMARY.md`, e o runner final de schema de S04 vira o baseline de não-regressão para a frente seguinte.
- M006/S01 concluído: `get_current_user()` e os chokepoints/admin wrappers de staff auth agora resolvem identidade só pelo contrato canônico de sessão por cookie; `X-Session-ID`, session-as-Bearer e `session_id` legado sobrevivem apenas como superfícies explícitas de rejeição/tombstone sob prova focada.
- O próximo foco é M006/S02: remover o resíduo estrutural de Firebase ainda preso a `users` e leitores adjacentes, mantendo verdes o replay final-schema `fresh|existing` e os packs canônicos de auth/session.
- Prova final de M004 consolidada em `.gsd/milestones/M004/M004-SUMMARY.md`.

## Architecture / Key Patterns

- Backend FastAPI com AsyncSession nas rotas API e Session síncrona nos workers Celery.
- Sessão autenticada baseada em Redis + cookie HttpOnly, com validação em `backend-hormonia/app/dependencies/auth_dependencies.py` e identidade canônica por `user_id`.
- Frontend dashboard em React/Vite com `AuthContext`, `apiClient` modular e bootstrap de WebSocket orientados a sessão própria.
- O repo já usa uma mistura de refactors por composição, shims estritos, tombstones e camadas de compatibilidade; a lapidação final precisa distinguir o que ainda é ponte necessária do que virou resíduo removível.
- M004–M006 seguem a régua estabelecida em M003: remover legado por evidência e fechar cada frente com prova real em vez de confiar em limpeza estética.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [x] M001: Bulletproof Flow Pipeline — fluxo WhatsApp resiliente com retry, recovery, observabilidade e prova integrada ponta a ponta.
- [x] M002: First-Party Authentication Cutover — login local, recuperação/first-access, cutover frontend/realtime e hard cut sem Firebase Auth para staff concluídos.
- [x] M003: Structural Refactor And Dead-Code Cleanup — hotspots críticos menores, compatibilidade obsoleta reduzida e base mais segura de manter sem regressão visível desnecessária.
- [x] M004: Convergência Canônica de Runtime — runtime oficial sem Firebase, auth/sessão convergidos e superfícies oficiais alinhadas ao contrato canônico.
- [x] M005: Fechamento Definitivo de Schema e Migrações — schema/Alembic alinhados ao modelo final, sem resíduo estrutural de Firebase e sem migrações ambíguas penduradas.
- [ ] M006: Purga Final de Código Morto e Resíduo Legado — bridges, aliases, tombstones, docs e código morto restantes removidos com prova integrada final.
