---
id: M004
provides:
  - Fechou a convergência canônica de runtime sem Firebase para auth/sessão, publicou o gate vivo de resíduos e validou `/login`, `/dashboard`, `/admin` e `/whatsapp` em stack montado sem dependência de Firebase.
key_decisions:
  - Consolidar a fronteira viva de resíduos em `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` e manter o escopo frontend com `approved: []`, para qualquer reintrodução cair como falha de guardrail.
  - Tratar cookie da sessão como único transporte oficial aceito para auth/sessão, e tombstone explícito (`410`) para `/session/*` em vez de manter compatibilidade invisível.
  - Diferenciar formalmente contratos oficiais vivos de rejeição/passivos/teses de migração, e fechar a lacuna com provas focadas (autenticação, rejeição legada, testes de smoke montado).
patterns_established:
  - Guardrail executável + prova fechada: o verifier (`verify-runtime-residue.sh`) é a fonte rápida de truth para regressão de resíduos, e não foi relaxado para acomodar lixo velho.
  - Fechamento de auth/session passa por contrato canônico em backend + frontend, seguido por prova integrada montada no stack para impedir divergência entre suíte e runtime real.
  - Em vez de apagar tudo de uma vez, limpar por camadas: backend canonical, frontend session-first, aposentadoria formal de legado, depois adjacentes e prova montada.
observability_surfaces:
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
  - `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight`
  - `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth`
  - `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --smoke`
  - `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all`
  - `frontend-hormonia/test-results/runtime-no-firebase-runtim-*/route-smoke-evidence.json`
  - `/tmp/gsd-s06-mounted-proof/{status.json,health-ready.json,system-config.json,wuzapi-status.json}`
requirement_outcomes:
  - id: R047
    from_status: active
    to_status: validated
    proof: S05 retirou dependência funcional adjacente e S06 validou stack montado sem Firebase (`run-mounted-proof.sh --all` + evidência de smoke sem requests Firebase).
  - id: R048
    from_status: active
    to_status: validated
    proof: S02 convergiu contrato backend para `user_id` no caminho oficial, S03 converteu frontend oficial para session-first canônico e S04 aposentou `X-Session-ID`/`Authorization: Bearer <session_id>` como transporte oficial.
  - id: R049
    from_status: active
    to_status: validated
    proof: S05 corrigiu cache/login/websocket-adjacent para `user_id` como pivô e removeu `firebase_uid` funcional de payloads oficiais; evidências em testes backend e guardrail pós-S05.
  - id: R050
    from_status: active
    to_status: validated
    proof: S03 provou `/login`, `/dashboard`, `/admin` sem semântica/session headers Firebase; `verify-runtime-residue.sh --check frontend` sem resíduos aprovados e testes de frontend no escopo.
  - id: R053
    from_status: active
    to_status: validated
    proof: S06 executou prova integrada montada (`--all`) cobrindo auth/session e smoke roteado das superfícies críticas em ambiente sem Firebase Auth.
duration: ~28h42m across 6 slices
verification_result: passed
completed_at: 2026-03-15T07:54:00-03:00
---

# M004: Convergência Canônica de Runtime

**Fechamento canônico do runtime oficial de auth/sessão em seis slices com corte de Firebase, aposentadoria de superfícies legadas e prova integrada de stack montado sem variáveis Firebase Auth.**

## What Happened

A base do milestone foi finalizada em duas frentes complementares: (1) o contrato operacional vivo foi reduzido a um caminho único canônico por `user_id` + cookie (`backend + frontend`), e (2) a fronteira residual foi convertida em guardrail verificável com prova montada final.

No início de M004, o maior risco era confundir “limpeza de grep” com fechamento real. Isso foi resolvido ao manter o `S01` como fonte de verdade executável de resíduos: o guardrail já passou de inventário de strings para um contrato operacional com categorias (`firebase_uid`, `x_session_id`, `session_bearer_fallback`, `websocket_session_id_query`, etc), escopos e anchors.

Em seguida, `S02` fez convergência semântica de backend para identidade canônica `id/user_id` primeiro; `S03` retirou do frontend oficial qualquer emissão/consumo legítimo de `X-Session-ID` ou `Authorization: Bearer <session_id>` e qualquer narrativa operacional de Firebase funcional; `S04` transformou o restante do transporte legado em rejeição/tombstone explícita (`/session/*` 410 e prefixos legados sem bypass);
`S05` sanitizou adjacentes (cache/login/websocket-adjacent, audit/admin/docs, tipos front-end) para remover dependência funcional residual; `S06` finalmente executou o replay montado da pilha inteira sem Firebase Auth e confirmou roteamento crítico.

O resultado final é uma fronteira viva compacta e explícita: apenas resíduos de compatibilidade/rejeição fora do happy path aprovado pelo verifier, zero resíduos aprovados no frontend oficial e smoke de rotas críticas executado com sessão canônica.

## Cross-Slice Verification

### Success Criterion: runtime can authenticate/restore and load `/dashboard`, `/admin`, `/whatsapp` without Firebase in official path
- **Verified:** `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all` (PASS) in `S06-SUMMARY.md`.
- **Verified behavior:** `route-smoke-evidence.json` registra `phase: completed`, `lastSuccessfulRoute: /whatsapp`, e chamadas reais a `GET /api/v2/dashboard/main`, `GET /api/v2/analytics/overview` e `GET /api/v2/monitoring/wuzapi/session/status` sem entradas em `unexpectedFirebaseRequests`.
- **Supporting evidence:** `/tmp/gsd-s06-mounted-proof/{health-ready.json,status.json,wuzapi-status.json}` com `dependencies.session_auth.mode == session-first` e WuzAPI `mock: true` ativo.

### Success Criterion: Firebase, `/session/*`, `X-Session-ID`, and legacy bearer fallbacks are no longer part of the accepted official runtime path (or are explicitly rejected/tombstoned)
- **Verified:** `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` (OK) in this run.
- **Supporting evidence:** Backend report includes `firebase_uid`, `session_bearer_fallback`, `x_session_id`, `websocket_session_id_query` only in approved legacy/backward-compatible categories; frontend report returns `no approved residue`.
- **Supporting behavior evidence:** `backend-hormonia/tests/auth/test_session_validation.py` now fixa `410` tombstone em rotas `/session/*` com `replacement_prefix = /api/v2/auth` e `required_transport = session_cookie`; `S04` testes cobrem rejeição de headers/cookies legacy fora do fluxo canônico.

### Success Criterion: official frontend no longer relies functionally on Firebase semantics/comments
- **Verified:** `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend` (OK, output `no approved residue`).
- **Supporting tests:** `tests/integration/admin-auth-flow.test.tsx`, `tests/integration/auth/session-first-cutover.test.tsx`, `tests/integration/realtime/session-websocket-cutover.test.ts` e testes de normalizadores/tipos em `frontend-hormonia`.
- **Supporting build:** `cd frontend-hormonia && npm run build` green after frontend contract cuts.

### Success Criterion: milestone ends with mounted integrated proof, not only static checks
- **Verified:** `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight`, `--auth`, `--smoke`, `--all` passaram, com artifacts persistentes em `/tmp/gsd-s06-mounted-proof` e `frontend-hormonia/test-results/runtime-no-firebase-runtim-*`.
- **Observed final state:** proof artifacts mostram sessão em modo canônico (`session-first`, `cookie_name=session_id`) e routes `/dashboard`, `/admin`, `/whatsapp` concluídas sem erro de Firebase.

### Did not meet?
- **None.** Todos os critérios de sucesso foram rechecados com evidência viva e passaram.

## Requirement Changes

- **Status transitions validated in this milestone:** R047, R048, R049, R050, R053 (active → validated).
- **No active status reversions.** `R051` e `R052` continuam ativos para M005/M006, respectivamente.

## Forward Intelligence

### What the next milestone should know
- O gate S01 agora é a fronteira oficial para resíduos de runtime: ele é o primeiro ponto de conferência quando qualquer mudança tocar auth/sessão.
- O ponto de verdade montado para S006 é `run-mounted-proof.sh --all` + `route-smoke-evidence.json`; smoke sem bootstrap/manual não é suficiente.
- Em `M005`, não abrir o contrato runtime canônico por padrão; só mexer no que for explicitamente schema/migração.

### What's fragile
- Resíduos legados aprovados em backend (especialmente compatibilidade em `auth_dependencies.py`, `auth_legacy_firebase.py`, `app/api/websockets.py`) ainda precisam ficar sob observação de anchor/no-drift.
- A prova montada depende de portas/stack locais (backend/frontend/WuzAPI), então validações futuras precisam rodar no ambiente montado, não apenas por suíte unitária.

### Authoritative diagnostics
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all`: fechamento de ponta-a-ponta oficial.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`: gate contínuo da fronteira runtime.
- `frontend-hormonia/test-results/runtime-no-firebase-runtim-*/route-smoke-evidence.json`: fonte rápida para regressões de rota crítica.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`: útil para revisar drift notes antes de `--check`.

### What assumptions changed
- Assumir que resolver resíduos apenas com diffs estáticos era suficiente; falsificação: a prova montada no stack revelou diferenças de transporte e comportamento de sessão que só aparecem em integração real.
- Assumir que frontend e backend poderiam evoluir independentes; falsificação: M003 já exigia alinhamento forte e aqui foi necessário fechar com pass-through de contrato e prova conjunta.

## Files Created/Modified

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — fronteira viva de resíduos runtime pós-S05 com categorias e aprovações reduzidas.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — script de check/report executável para guardrail.
- `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` — orchestration do proof montado (preflight/auth/smoke/artefatos).
- `.gsd/milestones/M004/slices/S06/seed-proof-user.py` — bootstrap de usuário/credentials em `/tmp` para replay E2E sem segredo em repo.
- `frontend-hormonia/tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts` — smoke roteado de `/admin`, `/dashboard`, `/whatsapp` no runtime montado.
- `.gsd/milestones/M004/M004-SUMMARY.md` — este resumo final de milestone com evidências de DoD e de critérios de sucesso.
