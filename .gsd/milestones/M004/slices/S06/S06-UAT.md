# S06: Prova integrada de runtime sem Firebase — UAT

**Milestone:** M004
**Written:** 2026-03-15T07:55:00-03:00

## UAT Type
- UAT mode: live-runtime
- Why this mode is sufficient: O comportamento-alvo é operacional (backend+frontend montados com contratos vivos); não é validação de UI isolada nem unitária.

## Preconditions
- `backend-hormonia/.venv` com dependências instaladas e ativo para execução de seed e backend.
- `frontend-hormonia/node_modules` presente.
- `Redis` e `PostgreSQL` disponíveis nos padrões do stack local (como já usado pelos testes de auth do projeto).
- Portas livres para uso temporário de `localhost:8000` e `localhost:5173` antes de cada execução do runner.
- Variáveis Firebase mantidas em branco pelo runner (ou equivalentes em ambiente equivalente).

## Smoke Test
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all`
- Esperado: `status: passed` em `/tmp/gsd-s06-mounted-proof/status.json`, com sequência de auth seguida de smoke sem falhas e artifacts Playwright gerados.

## Test Cases

### 1) Prova final canônica end-to-end no stack montado
1. Execute: `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all`
2. Abra `frontend-hormonia/test-results/e2e-results.json` e localize:
   - `runtime/no-firebase-runtime-smoke.spec.ts`
   - `session-first-hard-cut.spec.ts`
3. Confirme os dois testes com `status: expected`/`passed`.
4. Abra também:
   - `/tmp/gsd-s06-mounted-proof/status.json`
   - `frontend-hormonia/test-results/e2e-results.json`

**Expected:**
- O fluxo de autenticação canônica fica verde com login/restore/reset/password reset/ logout/logout-all.
- O smoke roteado chega a `/admin`, `/dashboard` e `/whatsapp` em uma só execução.
- `status` final não é `failed`.

### 2) Validação de rota com evidência estruturada
1. Execute: `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --smoke`
2. Localize o artefato `frontend-hormonia/test-results/runtime-no-firebase-runtim-*/route-smoke-evidence.json`.
3. Valide que o JSON contém:
   - `phase: completed`
   - `lastSuccessfulRoute: /whatsapp`
   - `admin.analyticsOverview.url` com `/api/v2/analytics/overview` e `status` 200
   - `dashboard.request.url` com `/api/v2/dashboard/main` e `status` 200
   - `whatsapp.request.url` com `/api/v2/monitoring/wuzapi/session/status` e `responseBody.connected == true`, `logged_in == true`, `mock == true`
   - `unexpectedFirebaseRequests == []`

**Expected:** toda a evidência de rota está verde e com zero chamadas Firebase no replay.

### 3) Verificação de observabilidade pós-preflight
1. Execute: `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight && curl -fsS http://localhost:8000/health/ready && curl -fsS http://localhost:8000/api/v2/system/config`
2. Verifique:
   - `/tmp/gsd-s06-mounted-proof/status.json` contém `status: passed` e `status` de seed saudável.
   - `/tmp/gsd-s06-mounted-proof/health-ready.json` contém `dependencies.session_auth`.
   - `/tmp/gsd-s06-mounted-proof/system-config.json` não traz chaves `VITE_FIREBASE_*`.
   - `/tmp/gsd-s06-mounted-proof/wuzapi-status.json` retorna `{connected: true, logged_in: true, mock: true}`.

**Expected:** o stack responde ao pré-check em branco Firebase e os artefatos de saúde/config/métrica WuzAPI refletem o contrato esperado.

### 4) Verificação do hard gate de resíduos antes do runtime
1. Execute: `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`

**Expected:** saída `--check all OK` sem falha do guardrail de S01.

### 5) Replay puntual com bootstrap helper (alternativo)
1. Copie caminhos de evidência:
   - `export BOOTSTRAP=/tmp/gsd-s06-browser-bootstrap`
2. Execute o fluxo local opcional:
   - `$BOOTSTRAP -- bash -lc 'cd frontend-hormonia && npx playwright test tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts --project=chromium'`

**Expected:** o comando acima entra no mesmo contrato sem segredos persistidos; quando `E2E_SESSION_FIRST_*` estiver ausente a execução deve pular explícita e conscientemente.

## Edge Cases

### A) Conflito de porta ocupada
1. Levante qualquer serviço em `8000` ou `5173`.
2. Execute `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth`.

**Expected:** falha explícita de pré-flight com diagnóstico de processo/porta ocupado (não deve iniciar em estado falso positivo).

### B) Replay repetido sem artefatos antigos
1. Remova ` /tmp/gsd-s06-mounted-proof`, `/tmp/gsd-s06-proof.env`, `/tmp/gsd-s06-browser-bootstrap`.
2. Execute `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all`.

**Expected:** runner recria artefatos e mantém resultado verde com nova seed.

## Failure Signals
- `run-mounted-proof.sh` retorna `FAILED` ou finaliza sem `status=passed` no `status.json`.
- Evidência de rota em `route-smoke-evidence.json` com falha por rota (`/admin`, `/dashboard` ou `/whatsapp`).
- `unexpectedFirebaseRequests` não vazio.
- `health-ready.json` sem `session_auth`.
- `system-config.json` expondo chaves `VITE_FIREBASE_*` ou chaves anômalas de Firebase.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` com falha.

## Requirements Proved By This UAT
- `R047` — runtime oficial sem Firebase no estado montado.
- `R050` — frontend oficial no contrato canônico sem resíduo funcional Firebase.
- `R053` — prova integrada de runtime montado em estado final.

## Not Proven By This UAT
- `R051`: resíduos estruturais de schema/migração.
- `R052`: purga final completa de código morto fora do boundary S06.
- Cobertura de fluxos fora de `/admin`, `/dashboard`, `/whatsapp` e fora do stack no escopo de runtime.

## Notes for Tester
- `passlib` continua emitindo warning de `bcrypt` durante bootstrap; isso é conhecido e não bloqueante.
- Se executar o spec diretamente sem `--auth/--smoke/--all`, o teste pode terminar em `skip` por falta de `E2E_SESSION_FIRST_*`; isso é comportamento esperado sem bootstrap helper.
