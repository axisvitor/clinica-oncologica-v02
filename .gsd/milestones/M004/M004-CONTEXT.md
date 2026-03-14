# M004: Convergência Canônica de Runtime — Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

## Project Description

Primeiro milestone da frente de lapidar toda a base de código. O objetivo aqui não é adicionar feature nova: é remover o restante das compatibilidades vivas do runtime oficial, tirar o Firebase de vez do sistema em termos práticos de execução e fechar os caminhos duplos de auth/sessão que ainda sobraram após M002 e M003.

## Why This Milestone

Depois do hard cut de M002 e da limpeza estrutural de M003, o sistema já deveria estar em auth próprio, mas ainda há resíduos reais de Firebase e compatibilidades de sessão espalhados no backend, no frontend oficial e em módulos adjacentes. Se isso continuar vivo, qualquer limpeza posterior de schema, migrações ou mortos repo-wide fica ambígua e arriscada. O momento certo para convergir o runtime é agora: o usuário deixou claro que não utilizaremos mais Firebase no sistema, só o app oficial consome esses contratos, e o restante das escolhas pode ser decidido pela melhor convergência técnica.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Fazer login da equipe, restaurar sessão, navegar em `/dashboard` e `/admin`, e operar as superfícies críticas sem qualquer dependência real de Firebase no caminho oficial.
- Olhar para auth/sessão do runtime e encontrar um caminho canônico claro, em vez de múltiplas compatibilidades ainda vivas.

### Entry point / environment

- Entry point: stack local do repositório (`backend-hormonia` + `frontend-hormonia`) e os loops `/login`, `verify-session`, logout, `/dashboard`, `/admin` e `/whatsapp`.
- Environment: local dev + suites focadas + smoke browser no stack local montado.
- Live dependencies involved: PostgreSQL, Redis/Dragonfly, WuzAPI, frontend Vite/React, bootstrap websocket e rotas sensíveis de auth/sessão.

## Completion Class

- Contract complete means: o runtime oficial de auth/sessão e o frontend oficial usam apenas o contrato canônico; qualquer resíduo legado em escopo foi removido, tombstonado ou explicitamente rejeitado; e a fronteira viva fica protegida por guardrails executáveis.
- Integration complete means: login, verify-session, restore e logout continuam funcionando no stack local sem Firebase, e `/dashboard`, `/admin` e `/whatsapp` continuam acessíveis no estado montado.
- Operational complete means: backend e frontend sobem com variáveis de Firebase Auth em branco no estado oficial deste milestone, sem hacks novos para manter auth/sessão funcionando.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- O stack local autentica a equipe e mantém sessão pelo contrato canônico sem depender de Firebase no runtime oficial.
- O app oficial não precisa mais de `/session/*`, `X-Session-ID`, `firebase_uid` no happy path nem semântica funcional de Firebase para login/restore/logout.
- Qualquer resíduo que precise ficar para M005 é explicitamente schema/migration-only, não uma ambiguidade de runtime.

## Risks and Unknowns

- `backend-hormonia/app/routers/auth_session.py` ainda está montado e pode esconder consumidores ou contratos legados reais — cortar cedo demais pode quebrar logout/restore silenciosamente.
- `firebase_uid` ainda aparece em cache, auditoria, tipos e payloads de runtime — se a convergência ficar pela metade, o sistema continua com identidade canônica ambígua.
- `Authorization: Bearer <session_id>` e `X-Session-ID` ainda aparecem em superfícies oficiais e adjacentes — é fácil deixar um caminho antigo sobreviver por acidente.
- O frontend ainda carrega comentários, tipos e trechos operacionais falando em Firebase auto-refresh — se o comportamento oficial continuar ancorado nisso, o corte nunca fecha de verdade.
- Só o app oficial consome os contratos, mas testes, docs e scripts internos podem ainda espelhar o contrato velho e mascarar uso real.

## Existing Codebase / Prior Art

- `backend-hormonia/app/dependencies/auth_dependencies.py` — fachada canônica de auth/sessão já reduzida em M003; é a base para fechar o caminho oficial.
- `backend-hormonia/app/routers/auth_session.py` — ilha de compatibilidade ainda viva para `/session/*`.
- `backend-hormonia/app/utils/user_cache.py` — resíduo forte de `firebase_uid` em cache/profile/rate-limit.
- `backend-hormonia/app/api/v2/auth_session_shared.py` e `backend-hormonia/app/api/v2/user_cache_shared.py` — helpers onde compatibilidade de sessão/UID ainda vaza para camadas novas.
- `frontend-hormonia/src/hooks/auth/useSessionManagement.ts` e `frontend-hormonia/src/features/admin/AdminSessionManager.tsx` — ainda carregam narrativa/comportamento operacional de Firebase.
- `frontend-hormonia/src/types/api.ts`, `src/types/admin.ts` e `shared-types/src/admin.ts` — ainda expõem campos e semântica de Firebase em superfícies oficiais.
- `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md` — fronteira autoritativa do que M003 removeu vs. deixou como ilha viva.

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R047 — tirar Firebase de vez do runtime oficial.
- R048 — convergir auth/sessão para um contrato canônico único.
- R049 — remover dependência de `firebase_uid` da identidade canônica no runtime.
- R050 — alinhar o frontend oficial ao contrato canônico sem resíduo funcional de Firebase.

## Scope

### In Scope

- Inventário executável e guardrails para resíduos vivos de Firebase/auth legado no runtime oficial.
- Convergência do backend oficial de auth/sessão para o caminho canônico.
- Convergência do frontend oficial (`/login`, `/dashboard`, `/admin` e bootstrap relacionado) para semântica session-first sem Firebase.
- Aposentadoria, tombstone ou rejeição explícita das superfícies legadas de auth/sessão em escopo do app oficial.
- Remoção de resíduo funcional de Firebase em cache, auditoria, docs operacionais e módulos adjacentes de runtime.
- Prova integrada em stack local sem Firebase Auth.

### Out of Scope / Non-Goals

- Limpeza definitiva de colunas, enums, índices e grafo Alembic relacionados a Firebase — isso é M005.
- Purga repo-wide de bridges, tombstones e mortos fora da frente de runtime — isso é M006.
- Reescrita ampla de arquitetura, redesign de produto ou novas features.

## Technical Constraints

- Não quebrar os loops críticos já fechados em M001–M003: login/logout/restore, dashboard/admin e superfícies críticas de operação WhatsApp.
- Como não há consumidor externo real além do app oficial, compatibilidades legadas não precisam ser preservadas por padrão se o app oficial e a prova montada ficarem verdes.
- O happy path oficial não pode continuar dependendo de `firebase_uid`, Firebase SDK ou comentários/diagnósticos que contem a história errada.
- O que não couber em M004 deve sair explicitamente como dívida de schema/migração para M005, não ficar ambíguo no runtime.
- Fechamento exige slice final explícita de prova integrada no stack local sem Firebase.

## Integration Points

- Redis/PostgreSQL de sessão — a convergência não pode quebrar emissão, restore, revogação ou leitura de sessão.
- Frontend `AuthContext`, `apiClient`, rotas `/dashboard` e `/admin` — precisam consumir só o contrato oficial.
- `/whatsapp` e runtime adjacente — smoke final precisa confirmar que a convergência de auth não causou regressão visível nas superfícies críticas.
- Websocket/bootstrap e rotas protegidas — qualquer fallback legado precisa ser removido ou explicitamente rejeitado sem degradar o comportamento oficial.

## Open Questions

- Até onde `/session/*` ainda é usado por rotas/scripts internos reais? — pensamento atual: como o app oficial já é o único consumidor real, a expectativa é aposentar ou tombstonar a superfície em M004, não carregá-la para sempre.
- `X-Session-ID` pode cair completamente do escopo oficial ou precisa ficar rejeitado/tombstonado por um período? — pensamento atual: o app oficial deve parar de depender disso; permanência só com justificativa clara.
- Quais campos de Firebase ainda precisam sobreviver até M005 apenas como resíduo de schema/auditoria? — pensamento atual: o runtime deve parar de depender deles em M004; o drop físico e a consolidação do schema ficam para o milestone seguinte.
