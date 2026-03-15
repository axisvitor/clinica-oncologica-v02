---
estimated_steps: 4
estimated_files: 7
---

# T02: Republicar o guard de resíduo com zero-approved no backend auth/session

**Slice:** S01 — Fechar a costura auth/session legado ainda “viva”
**Milestone:** M006

## Description

Depois do corte do chokepoint, ainda falta a parte que torna o slice honesto no tempo: o guard de resíduo não pode continuar chamando de “approved” exatamente os hotspots que S01 promete aposentar. Este task republica o boundary do verificador para que as quatro categorias backend de auth/session deixem de carregar dívida aprovada e transfere qualquer menção legada sobrevivente apenas para superfícies explicitamente aposentadas, com prova focada de websocket, `/session/*` e auth/admin/system rejection.

## Steps

1. Ajustar `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — e `verify-runtime-residue.sh` se a modelagem exigir — para que os scopes backend de `firebase_uid`, `x_session_id`, `session_bearer_fallback` e `websocket_session_id_query` não tenham mais hotspots approved nas superfícies live de auth/session.
2. Quando uma menção legada ainda precisar permanecer montada como rejeição/tombstone, tirá-la do guard apenas com uma fronteira explícita e verificável, nunca como relaxamento genérico de scope.
3. Estender `tests/unit/test_runtime_residue_guard.py` se a semântica de scope/exclude mudar e reforçar os testes focados de websocket, `/session/*`, auth cleanup e system/admin para carregar a prova que saiu do allowlist.
4. Rodar o guard backend e o pack de provas substitutas até que zero-approved signifique de fato “sem resíduo runtime vivo aqui”.

## Must-Haves

- [ ] O runtime residue guard backend fica verde sem approved hits para `firebase_uid`, `x_session_id`, `session_bearer_fallback` e `websocket_session_id_query` nas superfícies backend de auth/session.
- [ ] Websocket, `/session/*` e rejection plumbing que continuarem existindo ficam sustentados por testes focados com diagnósticos estáveis, não por allowlist debt.

## Verification

- `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_validation.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/v2/test_system_auth_hard_cut_operational.py`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`

## Observability Impact

- Signals added/changed: o verificador passa a distinguir drift real de runtime auth/session versus superfícies explicitamente aposentadas; websocket e tombstones seguem expondo códigos/mensagens estáveis para inspeção.
- How a future agent inspects this: `verify-runtime-residue.sh --report backend`, `tests/unit/test_runtime_residue_guard.py`, `tests/api/test_websocket_session_auth_contract.py` e `tests/auth/test_session_validation.py`.
- Failure state exposed: a falha mostra se houve reintrodução de hotspot live no backend, se o allowlist ficou desatualizado, ou se uma superfície aposentada perdeu seu diagnóstico explícito.

## Inputs

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — contrato atual ainda aprova hotspots backend que S01 precisa aposentar.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — script que precisa continuar sendo o entrypoint do guard, não uma nova ferramenta paralela.
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py` — já exerce a semântica do guard e deve prender qualquer mudança de scope/approved semantics.
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` — prova focada da rejeição websocket que substitui allowlist debt nesse boundary.
- `backend-hormonia/tests/auth/test_session_validation.py` — prova tombstone para `/session/*`, inclusive ignorando headers/cookies legados.
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py` — prova HTTP de rejeição e retirement surfaces no contrato pós-hard-cut.

## Expected Output

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — backend auth/session republished com zero-approved nas quatro categorias-alvo.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — mantido como entrypoint do guard, ajustado apenas se necessário para expressar o novo boundary com honestidade.
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py` — cobertura do verificador alinhada à nova semântica zero-approved.
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` — prova explícita da rejeição websocket substituindo o antigo hotspot aprovado.
- `backend-hormonia/tests/auth/test_session_validation.py` — tombstone proof do root `/session/*` sustentando a fronteira aposentada fora do allowlist.
- `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py` — checks operacionais/admin sem narrativa ou fallback Firebase reintroduzidos.
