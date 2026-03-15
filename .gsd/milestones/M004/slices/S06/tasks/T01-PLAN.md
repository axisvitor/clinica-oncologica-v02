---
estimated_steps: 4
estimated_files: 4
---

# T01: Codificar o replay montado da prova sem Firebase

**Slice:** S06 — Prova integrada de runtime sem Firebase
**Milestone:** M004

## Description

Transformar a pesquisa da slice em um caminho único e executável para o runtime montado. Este task existe para tirar drift de ambiente da frente S06: a mesma receita precisa subir o backend/frontend sem Firebase Auth, semear material efêmero de prova e deixar a aceitação auth existente e o novo smoke roteado apontando para o mesmo stack vivo.

## Steps

1. Capturar o contrato de launch do M002/S04 num runner da slice que zera `FIREBASE_ADMIN_*` e `VITE_FIREBASE_*`, injeta `WHATSAPP_WUZAPI_USE_MOCK=true` com token dummy e gerencia backend/frontend de forma consistente.
2. Adicionar um helper de seed que use `backend-hormonia/.venv`, crie/atualize um admin de prova e gere reset token efêmero, escrevendo apenas material mascarado em `/tmp`.
3. Criar `frontend-hormonia/tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts` para provar `/dashboard`, `/admin` e `/whatsapp` no runtime vivo sem usar `/admin/login` nem transporte legado.
4. Amarrar o runner aos envs esperados pelo `session-first-hard-cut.spec.ts` para que os próximos tasks executem auth acceptance e smoke pela mesma entrada.

## Must-Haves

- [ ] O runner controla o contrato blank-Firebase + WuzAPI mockado sem pedir edição manual de `.env`.
- [ ] O seed mantém usuário/senha/token de prova efêmeros e mascarados fora de `.gsd/` e fora do repositório.
- [ ] O novo smoke aponta apenas para as rotas oficiais `/login`, `/dashboard`, `/admin` e `/whatsapp` no contrato cookie-only.

## Verification

- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight`
- `cd frontend-hormonia && npx playwright test tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts --project=chromium --list`

## Observability Impact

- Signals added/changed: saída faseada do runner (`preflight`, `seed`, `auth`, `smoke`), paths de artefatos e status do seed sem segredos.
- How a future agent inspects this: `run-mounted-proof.sh`, arquivo mascarado em `/tmp`, e o spec Playwright fino recém-adicionado.
- Failure state exposed: o preflight deve falhar na fase certa quando boundary, env, seed ou wiring do navegador quebrarem.

## Inputs

- `.gsd/milestones/M002/slices/S04/S04-PROOF.md` — contrato de stack launch que S06 deve reaproveitar em vez de inventar outro.
- `.gsd/milestones/M004/slices/S06/S06-RESEARCH.md` — escopo, constraints e recomendação de prova estreita.
- `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts` — contrato existente de auth acceptance e envs `E2E_SESSION_FIRST_*`.

## Expected Output

- `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` — entrypoint replayável para preflight, seed, auth e smoke do stack montado.
- `.gsd/milestones/M004/slices/S06/seed-proof-user.py` — helper efêmero de seed/reset token sem persistência de segredos no repositório.
- `frontend-hormonia/tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts` — smoke fino das rotas oficiais no runtime sem Firebase.
