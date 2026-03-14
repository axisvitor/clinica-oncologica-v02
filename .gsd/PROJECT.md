# Project

## What This Is

Sistema de acompanhamento oncológico via WhatsApp para acompanhamento contínuo entre consultas. O backend roda em FastAPI + Celery + PostgreSQL + Redis/Dragonfly, com WuzAPI como provedor único de WhatsApp e frontends web para operação clínica. M001 endureceu o pipeline de fluxo de mensagens; M002 concluiu o corte de autenticação da equipe para um fluxo próprio de email/senha com sessão Redis + cookie HttpOnly; M003 fechou a primeira grande limpeza estrutural. A frente atual é a lapidação final da base em três milestones: convergir o runtime oficial sem Firebase, realizar as migrações definitivas ainda pendentes e limpar o restante do código morto e das compatibilidades que sobraram.

## Core Value

Médicos e operadores precisam acessar e operar o sistema com confiabilidade, e quem mantém a base precisa conseguir evoluí-la sem medo de quebrar auth, fluxo WhatsApp, dashboard ou integrações sensíveis por causa de legado ambíguo, caminhos duplos ou resíduos mortos ainda vivos no runtime.

## Current State

- M001 concluído: pipeline de fluxo agora tem retry, recovery, observabilidade e testes de integração.
- M002 concluído: `POST /api/v2/auth/login` autentica por email/senha local, emite a sessão canônica DB + Redis + cookie HttpOnly, e `verify-session` / `logout` / auth de rota protegida funcionam no contrato centrado em `user_id`.
- M003 concluído: os hotspots centrais de backend auth/session e frontend api-client/types foram fatiados em seams menores com contratos preservados (`auth_dependencies.py` 1579→675, `src/lib/api-client/index.ts` 1304→223, `src/lib/api-client/types.ts` 1159→26).
- M004/S01 concluído: o runtime oficial de auth/sessão agora tem uma fronteira executável de resíduo (`runtime-residue-allowlist.json` + `verify-runtime-residue.sh` + regressão pytest) que mostra exatamente onde `firebase_uid`, `/session/*`, `X-Session-ID`, bearer fallback, websocket `session_id` e narrativa Firebase ainda sobrevivem.
- M004/S02–S04 concluídos: backend e frontend oficiais já rodam no contrato canônico session-first, o backend aceita apenas a sessão por cookie no caminho oficial, `X-Session-ID`/session-as-Bearer/query fallback foram aposentados, e `/session/*` ficou reduzido a um tombstone 410 explícito.
- M004/S05 concluído: Redis/session/cache/login/websocket-adjacent auth, auditoria/admin/docs e tipos frontend adjacentes agora usam o runtime canônico por `id` / `user_id`; `firebase_uid` saiu do caminho funcional oficial e o frontend ficou com zero resíduo aprovado no verificador.
- O verificador de S01 voltou a ser um gate honesto para o slice inteiro: `--report all`/`--check all` ficam verdes, listando apenas o inventário reduzido de resíduo backend permitido como compatibilidade/rejeição passiva (`firebase_uid`, `x_session_id`, bearer fallback e websocket query) e nenhum resíduo frontend aprovado.
- O próximo foco é M004/S06: subir o stack local sem Firebase Auth e reexecutar `/login`, `/dashboard`, `/admin` e `/whatsapp` no estado montado contra essa fronteira reduzida.

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
- [ ] M004: Convergência Canônica de Runtime — runtime oficial sem Firebase, auth/sessão convergidos e superfícies oficiais alinhadas ao contrato canônico.
- [ ] M005: Fechamento Definitivo de Schema e Migrações — schema/Alembic alinhados ao modelo final, sem resíduo estrutural de Firebase e sem migrações ambíguas penduradas.
- [ ] M006: Purga Final de Código Morto e Resíduo Legado — bridges, aliases, tombstones, docs e código morto restantes removidos com prova integrada final.
