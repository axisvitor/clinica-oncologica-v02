---
estimated_steps: 4
estimated_files: 6
---

# T03: Provar as rotas oficiais e publicar a evidência replayável

**Slice:** S06 — Prova integrada de runtime sem Firebase
**Milestone:** M004

## Description

Fechar a slice com prova montada completa, não só com login verde. Este task usa o mesmo runtime já validado em T02 para exercitar as rotas oficiais que importam operacionalmente e deixar um handoff que outro agente consiga repetir sem reconstruir o contexto da milestone.

## Steps

1. Rodar o smoke fino no stack já autenticado para provar `/dashboard` com fetch real, `/admin` via entrypoint oficial `/login` e `/whatsapp` com sucesso do status mockado do WuzAPI.
2. Corrigir apenas regressões expostas por esse smoke roteado, sem ampliar o escopo para suites históricas ou cobertura profunda fora do boundary da slice.
3. Publicar `S06-SUMMARY.md` e `S06-UAT.md` com comandos, artefatos, sinais observados e o que sobra exclusivamente para M005.
4. Reexecutar o replay completo (`--all`) para fechar auth acceptance + route smoke no mesmo stack local sem Firebase.

## Must-Haves

- [ ] O smoke de `/dashboard` valida o caminho real `/api/v2/dashboard/main` em sessão autenticada.
- [ ] O smoke de `/admin` passa pela entrada oficial `/login`, não por suposições antigas sobre `/admin/login`.
- [ ] O smoke de `/whatsapp` valida o sucesso de `/api/v2/monitoring/wuzapi/session/status` com WuzAPI mockado e deixa evidência replayável.

## Verification

- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --smoke`
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all`

## Observability Impact

- Signals added/changed: assertions por rota, captura do request de dashboard, captura do status WuzAPI mockado e paths finais de artefatos da prova.
- How a future agent inspects this: spec de smoke, traces/network logs do Playwright e os artefatos `S06-SUMMARY.md` / `S06-UAT.md`.
- Failure state exposed: qual rota falhou, última rota bem-sucedida e qual request/status quebrou o smoke.

## Inputs

- `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` — orquestração do stack montado e do replay final.
- `frontend-hormonia/tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts` — smoke fino criado em T01.
- `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts` e resultados de T02 — auth lifecycle já verde no mesmo runtime.

## Expected Output

- `frontend-hormonia/tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts` — smoke roteado verde para `/dashboard`, `/admin` e `/whatsapp`.
- `.gsd/milestones/M004/slices/S06/S06-SUMMARY.md` — fechamento da slice com evidência montada e dívida remanescente restrita a M005.
- `.gsd/milestones/M004/slices/S06/S06-UAT.md` — replay operacional enxuto do proof pack final.
