# S06: Prova integrada de runtime sem Firebase — UAT

**Milestone:** M004
**Written:** 2026-03-14T23:32:30-03:00

## UAT Type
- UAT mode: live-runtime
- Why this mode is sufficient: a prova real precisa ocorrer no backend/frontend montado sem Firebase e com seed efêmero; é onde a estabilidade operacional e o contrato canônico se confirmam.

## Preconditions
- `backend-hormonia/.venv` e `frontend-hormonia/node_modules` configurados.
- Nenhum serviço ocupando `localhost:8000` e `localhost:5173` antes de iniciar.
- Variáveis Firebase mantidas em branco pelo runner (ou no fluxo equivalente).

## Smoke Test (replay obrigatório)
### 1) Prova final completa
1. Execute: `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all`
2. Em seguida, inspecione:
   - `/tmp/gsd-s06-mounted-proof/status.json`
   - `frontend-hormonia/tests/e2e/test-results/e2e-results.json`
   - `frontend-hormonia/tests/e2e/test-results/runtime-no-firebase-runtim-*/attachments/route-smoke-evidence-*.json`

**Esperado:**
- `status.json` final com `phase: smoke` e `status: passed`.
- Teste `runtime/no-firebase-runtime-smoke.spec.ts` com resultado expected/passed.
- Evidência de smoke com `unexpectedFirebaseRequests == []` e requests reais de `analytics/overview`, `dashboard/main`, `monitoring/wuzapi/session/status`.

## Test Cases
### 1. Autenticação session-first no stack montado sem Firebase
1. Execute: `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth`
2. Verifique no terminal e artefatos:
   - login via `/login`
   - fluxo `/dashboard`, restore e reset
   - logout e logout-all
   - ausência de chamadas Firebase nos traces

### 2. Smoke roteado `/admin`, `/dashboard`, `/whatsapp`
1. Execute: `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --smoke`
2. Valide evidence em `route-smoke-evidence.json`:
   - `/admin`: ingresso via `/login`, `analytics/overview` 200.
   - `/dashboard`: `api/v2/dashboard/main` 200.
   - `/whatsapp`: `api/v2/monitoring/wuzapi/session/status` com `connected`, `logged_in` e `mock` true.

### 3. Observabilidade pós-preflight
1. Execute: `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight && curl -fsS http://localhost:8000/health/ready && curl -fsS http://localhost:8000/api/v2/system/config`
2. Verifique:
   - `/tmp/gsd-s06-mounted-proof/health-ready.json` com `session_auth`
   - `/tmp/gsd-s06-mounted-proof/system-config.json` sem chaves `VITE_FIREBASE_*`.
   - `/tmp/gsd-s06-mounted-proof/wuzapi-status.json` com `connected=true`, `logged_in=true`, `mock=true`.

### 4. Replay pontual local (alternativo)
1. Para rodar `npx playwright` diretamente, use a semente canônica: `/tmp/gsd-s06-browser-bootstrap -- bash -lc "cd frontend-hormonia && npx playwright test tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts --project=chromium"`
2. Esse fluxo exige stack já levantado e se comporta como replay de camada interna.

**Esperado:** resultado esperado sem `skip` apenas quando os `E2E_SESSION_FIRST_*` estiverem definidos.

## Edge Cases
### A) Porta já em uso
1. Inicie processo em `8000` ou `5173`.
2. Execute `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth`.

**Esperado:** falha explícita com PID dos processos que ocupam a porta.

### B) Reexecução sem artefatos prévios
1. Remova `/tmp/gsd-s06-mounted-proof`, `/tmp/gsd-s06-proof.env`, `/tmp/gsd-s06-browser-bootstrap`.
2. Reexecute `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all`.

**Esperado:** runner recria diretórios/artefatos e permanece reexecutável.

## Failure signals
- Falha em qualquer rota em `route-smoke-evidence.json` (`admin`, `dashboard`, `whatsapp`).
- `status.json` final com `status != passed`.
- `unexpectedFirebaseRequests` não vazio.
- `health-ready.json` sem `session_auth`.
- `system-config.json` com configuração Firebase.

## Requirements Proved By This UAT
- `R047` — runtime oficial sem Firebase no estado montado.
- `R050` — contrato canônico do frontend no path oficial.
- `R053` — prova integrada de runtime montado.

## Not Proven By This UAT
- `R051`: resíduos de schema/migrações (M005).
- `R052`: limpeza completa de código morto/compatibilidade fora do boundary M004/S06.
- UIs/fluxos fora de `/admin`, `/dashboard`, `/whatsapp`.

## Notes for Tester
- Pode haver warning do `passlib` (`bcrypt`) em startup; não bloqueia o fluxo.
- O runner finaliza o stack ao término da execução, exceto o curto hold de `--preflight`.
