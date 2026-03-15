---
estimated_steps: 4
estimated_files: 8
---

# T01: Publicar o runner serial de prova final-schema e mounted backend

**Slice:** S04 — Prova integrada de upgrade e backend no schema final
**Milestone:** M005

## Description

S04 não precisa de mais uma família larga de testes; precisa de uma prova composta e replayable. Este task fecha exatamente essa lacuna: preparar o banco no history canônico certo, reexecutar os packs críticos pós-M004 no head final e, em seguida, subir um uvicorn real no mesmo banco para provar readiness/config/login no caminho mounted — tudo com artefatos suficientes para localizar a falha quando fresh e existing divergirem.

## Steps

1. Criar um runner S04 com modos `--fresh` e `--existing` que prepare serialmente a `DATABASE_URL` a partir de `base -> head` ou `m005_s02_t01_publish_firebase_history_boundary -> head`, respeitando o oracle de `test_canonical_schema_head_convergence.py` e sem concorrência sobre o mesmo banco.
2. Encadear nesse runner o replay dos packs `tests/api/v2/test_system_auth_hard_cut_operational.py`, `tests/integration/test_local_auth_core_flow.py` e `tests/integration/test_auth_hard_cut_end_to_end.py` via `TEST_DATABASE_URL`, mantendo o phase/status explícito quando um pack falhar.
3. Reutilizar ou estender minimamente os helpers de `.gsd/milestones/M004/slices/S06/` para um modo backend-only: seed mascarado do proof user, Firebase blank, WuzAPI mock, backend log/status file e startup de uvicorn sem depender do frontend.
4. Adicionar uma prova live nomeada para `/health/ready`, `/api/v2/system/config` e `login -> verify-session -> /users/me -> logout`, publicar o replay contract em `S04-UAT.md` e garantir que o runner a execute para os dois histories.

## Must-Haves

- [ ] O mesmo comando S04 cobre honestamente os dois histories canônicos, reexecuta os packs críticos no head final e depois prova startup mounted no mesmo banco.
- [ ] As falhas deixam explícitos o history (`fresh` ou `existing`), a fase (`pytest_replay`, `mounted_backend`, `live_auth_probe`) e os caminhos dos artefatos/logs, sem vazar credenciais ou tokens do proof user.

## Verification

- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_canonical_schema_head_convergence.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh`
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --existing`

## Observability Impact

- Signals added/changed: status por fase/history, asserts nomeadas para readiness/config/live-session, e resultado separado para replay pytest vs mounted backend.
- How a future agent inspects this: `status.json` e `backend.log` emitidos pelo runner S04, `backend-hormonia/tests/runtime/test_mounted_final_schema_proof.py`, e o output dos três packs focados.
- Failure state exposed: qual history falhou, em que fase, qual endpoint/assert quebrou, e onde estão os logs/artefatos mascarados correspondentes.

## Inputs

- `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py` — define os dois histories canônicos e o head S03 que S04 deve consumir, não reinventar.
- `backend-hormonia/tests/conftest.py` — já provisiona o shared Postgres via `alembic upgrade head` sob `TEST_DATABASE_URL`; o runner precisa respeitar esse contrato e manter execução serial.
- `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` — já resolve blank Firebase env, WuzAPI mock, status/log files e seed contract para a prova montada.
- `.gsd/milestones/M004/slices/S06/seed-proof-user.py` — padrão existente para seed mascarado do proof user, reaproveitável no mounted backend-only flow.
- `backend-hormonia/app/core/lifespan.py` — deixa claro por que `TestClient(app)` não basta para afirmar que o backend realmente sobe fora de modo teste.

## Expected Output

- `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` — runner serial para `--fresh` e `--existing`, com preparação de banco, replay pytest e mount live no mesmo fluxo.
- `backend-hormonia/tests/runtime/test_mounted_final_schema_proof.py` — asserts live nomeadas para readiness/config/login-session sobre uvicorn real.
- `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` — helper reaproveitado ou estendido para suportar backend-only runtime proof sem front-end obrigatório.
- `.gsd/milestones/M004/slices/S06/seed-proof-user.py` — contrato de seed ajustado apenas se necessário para o mounted backend-only replay de S04.
- `.gsd/milestones/M005/slices/S04/S04-UAT.md` — replay contract publicado com comandos, artefatos e a restrição de uso serial do banco.
