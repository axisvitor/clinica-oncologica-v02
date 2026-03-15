# S06: Prova integrada de runtime sem Firebase

**Goal:** Provar o runtime oficial montado sem Firebase Auth com um replay estreito e executável: preflight do boundary, stack local backend+frontend com Firebase em branco e WuzAPI mockado, auth lifecycle canônico e smoke autenticado de `/dashboard`, `/admin` e `/whatsapp`.
**Demo:** A partir de um único roteiro replayável, o stack local sobe sem Firebase Auth, semeia material efêmero de prova, passa pela aceitação Chromium do contrato session-first e termina com smoke roteado verde nas três rotas críticas do app oficial.

## Must-Haves

- O replay montado usa backend/frontend vivos com `FIREBASE_ADMIN_*` e `VITE_FIREBASE_*` em branco, `WHATSAPP_WUZAPI_USE_MOCK=true` e token WuzAPI dummy, sem depender de edição manual de `.env`.
- O fluxo de prova semeia um usuário admin e reset token efêmeros fora dos artefatos versionados, alimenta o spec `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts` e mantém o contrato cookie-only.
- Existe uma verificação fina e autenticada para `/dashboard`, `/admin` e `/whatsapp` no mesmo stack, e a slice publica evidência replayável suficiente para sustentar R047 e R053.

## Proof Level

- This slice proves: final-assembly
- Real runtime required: yes
- Human/UAT required: no

## Verification

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
- `cd backend-hormonia && pytest -q tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth`
- `cd frontend-hormonia && npx playwright test tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts --project=chromium`
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all`
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight && curl -fsS http://localhost:8000/health/ready && curl -fsS http://localhost:8000/api/v2/system/config`

## Observability / Diagnostics

- Runtime signals: `/health/ready` com `session_auth`, `/api/v2/system/config`, saída faseada do runner montado, traces/screenshots/logs do Playwright, e resposta de status mockada do WuzAPI.
- Inspection surfaces: `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh ...`, `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`, os pytests operacionais/backend de auth, `bg_shell` digest dos processos locais quando a prova estiver rodando, e artefatos Playwright.
- Failure visibility: falha deve apontar a fase (`preflight`, `seed`, `auth`, `smoke`), a última URL/assertion do navegador e o endpoint/request que quebrou, sem ambiguidade entre problema de bootstrap e regressão de contrato.
- Redaction constraints: credenciais e reset token de prova ficam só em `/tmp` de forma mascarada/efêmera; nada sensível entra em `.gsd/`, logs versionados ou respostas finais.

## Integration Closure

- Upstream surfaces consumed: `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`, `.gsd/milestones/M002/slices/S04/S04-PROOF.md`, `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py`, `backend-hormonia/tests/integration/test_local_auth_core_flow.py`, `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`, `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts`, `frontend-hormonia/src/app/routes/routeDefinitions.tsx`, `frontend-hormonia/src/pages/DashboardPage.tsx`, `frontend-hormonia/src/features/admin/AdminDashboard.tsx`, `frontend-hormonia/src/features/whatsapp/WhatsAppDashboard.tsx`.
- New wiring introduced in this slice: runner da slice para subir/semear/verificar o stack montado e um smoke Playwright fino para `/dashboard`, `/admin` e `/whatsapp` no mesmo runtime ao vivo.
- What remains before the milestone is truly usable end-to-end: nothing

## Tasks

- [x] **T01: Codificar o replay montado da prova sem Firebase** `est:1h30m`
  - Why: S06 vira prova frágil se stack launch, seed e smoke dependerem de comandos manuais ou receitas divergentes; a slice precisa de um único caminho replayável antes de depurar o runtime.
  - Files: `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh`, `.gsd/milestones/M004/slices/S06/seed-proof-user.py`, `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts`, `frontend-hormonia/tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts`
  - Do: Capturar o contrato de stack do M002/S04 num runner da slice que zera envs de Firebase, injeta WuzAPI mockado, sobe backend/frontend nos ports oficiais, semeia usuário admin + reset token efêmeros em `/tmp`, exporta o contrato `E2E_SESSION_FIRST_*` esperado pelo spec canônico e adiciona um smoke fino para `/dashboard`, `/admin` e `/whatsapp` sem reviver `/admin/login` nem transporte legado.
  - Verify: `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight`
  - Done when: existe um único entrypoint replayável que prepara o stack montado e a autenticação de prova sem edição manual de `.env` nem segredos persistidos no repositório.
- [x] **T02: Fechar a aceitação auth/session-first no stack montado** `est:2h`
  - Why: O maior risco conhecido da slice é o seam real `/login` → `/dashboard`; sem a aceitação auth Chromium verde no runtime vivo, R047 continua só em prova de contrato.
  - Files: `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh`, `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/api/v2/auth_session_shared.py`, `frontend-hormonia/src/features/auth/ProtectedRoute.tsx`, `frontend-hormonia/src/lib/config-initializer.tsx`, `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts`
  - Do: Rodar o residue guard e o pack operacional/backend no mesmo contrato blank-Firebase, executar a aceitação Chromium existente contra o stack montado e corrigir apenas regressões reais de bootstrap/auth/restore/reset/logout expostas por esse caminho, preservando cookie-only, ausência de tráfego Firebase e o boundary já validado em S04/S05.
  - Verify: `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all && cd backend-hormonia && pytest -q tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_auth_hard_cut_end_to_end.py && cd ../frontend-hormonia && ../.gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth`
  - Done when: login, reload/restore, reset, troca de senha, logout e logout-all passam no stack montado com Firebase em branco e o backend continua reportando o contrato canônico vivo.
- [x] **T03: Provar as rotas oficiais e publicar a evidência replayável** `est:1h30m`
  - Why: R053 só fecha quando o mesmo runtime vivo também prova `/dashboard`, `/admin` e `/whatsapp` e deixa claro, em artefatos, o que foi exercitado e o que sobra apenas para M005.
  - Files: `frontend-hormonia/tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts`, `frontend-hormonia/src/pages/DashboardPage.tsx`, `frontend-hormonia/src/features/admin/AdminDashboard.tsx`, `frontend-hormonia/src/features/whatsapp/WhatsAppDashboard.tsx`, `.gsd/milestones/M004/slices/S06/S06-UAT.md`, `.gsd/milestones/M004/slices/S06/S06-SUMMARY.md`
  - Do: Rodar e ajustar o smoke roteado fino no mesmo stack já validado em T02 para provar fetch real de `/api/v2/dashboard/main`, render roteado de `/admin` via entrypoint `/login` e sucesso de `/api/v2/monitoring/wuzapi/session/status` em `/whatsapp`, depois publicar comandos, evidências e resíduo remanescente exclusivamente estrutural em artefatos da slice.
  - Verify: `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --smoke && bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all`
  - Done when: o replay completo fecha verde para auth + smoke roteado no mesmo stack local sem Firebase e a slice deixa um resumo/UAT que outro agente consegue repetir sem reconstruir a história.

## Files Likely Touched

- `.gsd/milestones/M004/slices/S06/S06-PLAN.md`
- `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh`
- `.gsd/milestones/M004/slices/S06/seed-proof-user.py`
- `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts`
- `frontend-hormonia/tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts`
- `backend-hormonia/app/api/v2/routers/auth.py`
- `backend-hormonia/app/api/v2/auth_session_shared.py`
- `frontend-hormonia/src/features/auth/ProtectedRoute.tsx`
- `frontend-hormonia/src/pages/DashboardPage.tsx`
- `frontend-hormonia/src/features/admin/AdminDashboard.tsx`
- `frontend-hormonia/src/features/whatsapp/WhatsAppDashboard.tsx`
- `.gsd/milestones/M004/slices/S06/S06-UAT.md`
- `.gsd/milestones/M004/slices/S06/S06-SUMMARY.md`
