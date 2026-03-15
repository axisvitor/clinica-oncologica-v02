---
id: S06
parent: M004
milestone: M004
provides:
  - Closed T03 by running a single-mounted, no-Firebase proof of routed runtime smoke after auth acceptance in `--all`.
  - Preserved replay evidence in `/tmp` and Playwright artifacts for `/admin`, `/dashboard`, and `/whatsapp` on the same live stack.
  - Defined remaining boundary as downstream structural debt only (M005).
key_files:
  - .gsd/milestones/M004/slices/S06/run-mounted-proof.sh
  - .gsd/milestones/M004/slices/S06/seed-proof-user.py
  - frontend-hormonia/tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts
  - .gsd/milestones/M004/slices/S06/S06-UAT.md
  - frontend-hormonia/tests/e2e/test-results/e2e-results.json
  - /tmp/gsd-s06-mounted-proof/status.json
  - /tmp/gsd-s06-mounted-proof/health-ready.json
  - /tmp/gsd-s06-mounted-proof/system-config.json
  - /tmp/gsd-s06-mounted-proof/wuzapi-status.json
  - frontend-hormonia/tests/e2e/test-results/runtime-no-firebase-runtim-*/attachments/route-smoke-evidence-*.json
  - .gsd/milestones/M004/slices/S06/tasks/T03-SUMMARY.md
duration: 0h50m
verification_result: passed
completed_at: 2026-03-14T23:32:30-03:00
blocker_discovered: false
---

# S06: Prova integrada de runtime sem Firebase

## Resultado
A slice S06 foi fechada no ponto de prova esperado:
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight` sobe backend/frontend no contrato sem Firebase, valida `health/config` e mantém o estado observável por 10s.
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth` executa a aceitação canônica no stack montado.
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --smoke` valida rotas oficiais no mesmo runtime: 
  - `/admin` via `/login`,
  - `/dashboard` com fetch real de `/api/v2/dashboard/main`,
  - `/whatsapp` com sucesso mockado de `GET /api/v2/monitoring/wuzapi/session/status`.
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all` unifica auth+smoke em uma corrida só.

## Verificações executadas
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --smoke` — **PASS**
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all` — **PASS**
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` — **PASS**
- `cd backend-hormonia && pytest -q tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_auth_hard_cut_end_to_end.py` — **PASS**
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth` — **PASS**
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight && curl -fsS http://localhost:8000/health/ready && curl -fsS http://localhost:8000/api/v2/system/config` — **PASS**
- `cd frontend-hormonia && npx playwright test tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts --project=chromium` (sem seed helper/stack ativo) — **SKIP** por ausência de `E2E_SESSION_FIRST_*`.

## Evidências esperadas
- `/tmp/gsd-s06-mounted-proof/status.json` terminando em `phase: smoke`, `status: passed`.
- `frontend-hormonia/tests/e2e/test-results/e2e-results.json` com o teste `runtime/no-firebase-runtime-smoke.spec.ts` em `status: expected`.
- `frontend-hormonia/tests/e2e/test-results/runtime-no-firebase-runtim-*/attachments/route-smoke-evidence-*.json` contendo:
  - `admin.analyticsOverview.url` com `api/v2/analytics/overview` e `status=200`;
  - `dashboard.request.url` contendo `api/v2/dashboard/main`;
  - `whatsapp.request.url` em `api/v2/monitoring/wuzapi/session/status`;
  - `whatsapp.request.responseBody.connected == true`, `logged_in == true`, `mock == true`;
  - `unexpectedFirebaseRequests == []`.
- `/tmp/gsd-s06-mounted-proof/health-ready.json` com `dependencies.session_auth`.
- `/tmp/gsd-s06-mounted-proof/system-config.json` sem chaves `VITE_FIREBASE_*` e sem referência explícita de Firebase no payload.
- `/tmp/gsd-s06-mounted-proof/wuzapi-status.json` com `connected=true`, `logged_in=true`, `mock=true`.
- `/tmp/gsd-s06-proof.env` e `/tmp/gsd-s06-browser-bootstrap` apenas mascarados.

## Requirements Advanced
- `R047` — Firebase sai do runtime oficial no contrato montado.
- `R050` — O frontend usa o contrato canônico sem tráfego Firebase no fluxo oficial.
- `R053` — Prova integrada de runtime com auth + smoke no mesmo stack.

## Requirements Validated
- `R047`, `R050`, `R053` com evidência passável no replay montado.

## Requirements Invalidated or Re-scoped
- Nenhuma.

## Deviations
- Nenhuma desvio estrutural; apenas foi explicitado que o smoke direto fora do contrato mounted precisa do helper de seed para não pular.

## Known Limitations
- Execução sem `--auth/--smoke` ainda exige que o helper regenere seed+stack antes de um `npx playwright` pontual.
- `passlib` continua emitindo warning não bloqueante relacionado a `bcrypt` durante startup.

## Follow-ups
- `R051` e `R052` continuam em agenda futura/M005; S06 encerra a evidência operacional montada e deixa margem somente para limpeza estrutural/migração fora do boundary.

## Forward Intelligence
- Use `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all` como replay canônico e único para revalidar rapidamente.
- Para inspeção de regressão de rota, priorizar `route-smoke-evidence.json` e `status.json` em conjunto (fase/última rota/request).
