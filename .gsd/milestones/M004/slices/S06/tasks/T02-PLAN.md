---
estimated_steps: 4
estimated_files: 6
---

# T02: Fechar a aceitação auth/session-first no stack montado

**Slice:** S06 — Prova integrada de runtime sem Firebase
**Milestone:** M004

## Description

Usar o runner montado para que a prova auth deixe de ser apenas verdade de contrato e passe a ser verdade do runtime vivo. Este task ataca primeiro o seam mais frágil conhecido — `/login` → `/dashboard` com reload/restore/reset/logout reais — porque uma prova de rotas sem esse ciclo auth verde ainda deixaria R047 em aberto.

## Steps

1. Rodar o residue guard e o pack operacional/backend no mesmo contrato blank-Firebase para confirmar que o boundary publicado em S04/S05 continua honesto antes do browser replay.
2. Executar o `session-first-hard-cut.spec.ts` contra o backend/frontend vivos preparados pelo runner e observar onde o login, restore, reset, password change, logout ou logout-all quebram.
3. Corrigir apenas regressões reais de bootstrap/auth/session expostas por esse caminho, sem reabrir `X-Session-ID`, bearer fallback, `/session/*` ou qualquer semântica funcional de Firebase.
4. Reexecutar o pack até a aceitação Chromium e os sinais de health/config do backend ficarem verdes no mesmo runtime montado.

## Must-Haves

- [ ] A aceitação auth usa o stack real e o usuário admin semeado localmente, não atalhos de mock auth.
- [ ] Qualquer correção preserva envs Firebase em branco, transporte cookie-only e ausência de requests Firebase no navegador.
- [ ] `/health/ready` e `/api/v2/system/config` continuam contando a história canônica de `session_auth` sem drift operacional.

## Verification

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
- `cd backend-hormonia && pytest -q tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth`

## Observability Impact

- Signals added/changed: readiness/config probes do backend, traces/screenshots/logs do Playwright auth, e fase `auth` no runner montado.
- How a future agent inspects this: runner `--auth`, `bg_shell` digest dos processos locais, e logs de rede/console do Playwright quando o browser divergir do backend.
- Failure state exposed: fase auth quebrada, última URL/assertion do Chromium, e mismatch explícito entre runtime vivo e provas de contrato.

## Inputs

- `.gsd/milestones/M004/slices/S04/S04-SUMMARY.md` — boundary cookie-only/tombstone que não pode regredir.
- `.gsd/milestones/M004/slices/S05/S05-SUMMARY.md` — boundary pós-Firebase adjacente que deve permanecer intacto no runtime montado.
- `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` — runner e seed preparados em T01.

## Expected Output

- `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` — subfluxo `--auth` confiável para replay do auth lifecycle montado.
- `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts` — aceitação Chromium verde contra o stack local sem Firebase.
- `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/api/v2/auth_session_shared.py`, `frontend-hormonia/src/features/auth/ProtectedRoute.tsx`, `frontend-hormonia/src/lib/config-initializer.tsx` — ajustes apenas se a prova montada expuser regressões reais nesses seams.
