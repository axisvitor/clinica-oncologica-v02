---
id: T03
parent: S06
milestone: M004
provides:
  - Executed the mounted runtime route smoke on the official no-Firebase stack and confirmed `/admin` (via `/login`), `/dashboard`, and `/whatsapp` endpoints in one replayable path.
key_files:
  - .gsd/milestones/M004/slices/S06/run-mounted-proof.sh
  - frontend-hormonia/tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts
  - .gsd/milestones/M004/slices/S06/S06-SUMMARY.md
  - .gsd/milestones/M004/slices/S06/S06-UAT.md
  - /tmp/gsd-s06-mounted-proof/status.json
  - frontend-hormonia/tests/e2e/test-results/runtime-no-firebase-runtim-*/route-smoke-evidence.json
key_decisions:
  - Keep the mounted runner as the canonical replay path for route smoke; standalone Playwright invocations require the same seeded contract (via bootstrap/env helper) to avoid false skips.
patterns_established:
  - Capture route-level evidence in `route-smoke-evidence.json` and pair it with mounted truth surfaces (`health-ready.json`, `system-config.json`, `wuzapi-status.json`) for clear failure triage by phase/last successful route/request.
observability_surfaces:
  - /tmp/gsd-s06-mounted-proof/status.json
  - /tmp/gsd-s06-mounted-proof/backend.log
  - /tmp/gsd-s06-mounted-proof/frontend.log
  - /tmp/gsd-s06-mounted-proof/health-ready.json
  - /tmp/gsd-s06-mounted-proof/system-config.json
  - /tmp/gsd-s06-mounted-proof/wuzapi-status.json
  - frontend-hormonia/tests/e2e/test-results/e2e-results.json
  - frontend-hormonia/tests/e2e/test-results/runtime-no-firebase-runtim-*/attachments/route-smoke-evidence-*.json
  - /tmp/gsd-s06-proof.env
  - /tmp/gsd-s06-browser-bootstrap
duration: 0h40m
verification_result: passed
completed_at: 2026-03-14T23:32:30-03:00
blocker_discovered: false
---

# T03: Provar as rotas oficiais e publicar a evidência replayável

**Fechei a prova integrada no stack montado sem Firebase, incluindo smoke oficial roteado de `/admin`, `/dashboard` e `/whatsapp` com contratos reais e artifacts rastreáveis para replay.**

## What Happened
- Executei `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --smoke` e o fluxo completo retornou verde em sessão autenticada.
- Executei `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all`, fechando auth acceptance + smoke na mesma instância local sem Firebase.
- O smoke validou explicitamente:
  - `/admin` passa por `/login` (entrada oficial), faz login e chega em `/admin`.
  - `/dashboard` dispara `GET /api/v2/dashboard/main` em sessão autenticada com `status=200`.
  - `/whatsapp` dispara `GET /api/v2/monitoring/wuzapi/session/status` com `connected=true`, `logged_in=true`, `mock=true`.
- A evidência de rota fica em `route-smoke-evidence.json` com `phase: completed`, `lastSuccessfulRoute: /whatsapp` e `unexpectedFirebaseRequests: []`.
- Também confirmei o estado de superfície após `--preflight` via `curl` e fiz as verificações de residue/backend exigidas pelo plano.

## Verification
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --smoke` — **PASS**
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all` — **PASS**
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` — **PASS**
- `cd backend-hormonia && pytest -q tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_auth_hard_cut_end_to_end.py` — **PASS**
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth` — **PASS**
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight && curl -fsS http://localhost:8000/health/ready && curl -fsS http://localhost:8000/api/v2/system/config` — **PASS**
- `cd frontend-hormonia && npx playwright test tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts --project=chromium` sem contrato seed/precondições de stack — **SKIPPED** (testes ignorados por `Seeded auth fixtures missing...`).

## Diagnostics
- Inspeção rápida de sucesso:
  - `route-smoke-evidence.json`: `/tmp/gsd-s06-mounted-proof` não contém logs de artifacts; evidência efetiva está em `frontend-hormonia/tests/e2e/test-results/.../runtime-no-firebase-runtim-.../attachments/route-smoke-evidence-*.json`.
  - `status.json` final em `smoke` com `status: passed`.
  - `health-ready.json` contém `session_auth` e componentes healthy.
  - `wuzapi-status.json` retorna `connected/logged_in/mock = true`.
- Emite warnings de ambiente conhecidas (`passlib`/`bcrypt`) sem impactar funcionalidade.

## Deviations
- Nenhuma mudança de escopo funcional fora do contrato de slice; apenas documentação/registro foi alinhada para refletir o runner como ponto de replay canônico.

## Known Issues
- A execução direta de um único spec sem seed helper e sem stack já levantado fica com `skip` por falta de fixtures; o caminho correto para replay manual é pelo runner montado ou com o helper `/tmp/gsd-s06-browser-bootstrap`.

## Files Created/Modified
- `frontend-hormonia/tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts` — sem alterações funcionais adicionais nesta tarefa; usado pelo smoke roteado final.
- `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` — mantém o ponto único de replay com preflight/seed/auth/smoke.
- `.gsd/milestones/M004/slices/S06/S06-SUMMARY.md` — publicado com estado final e artefatos.
- `.gsd/milestones/M004/slices/S06/S06-UAT.md` — publicado/ajustado com comandos de evidência.
- `.gsd/milestones/M004/slices/S06/S06-PLAN.md` — check de T03 marcado como concluído.
- `.gsd/milestones/M004/slices/S06/tasks/T03-SUMMARY.md` — este arquivo de fechamento.
