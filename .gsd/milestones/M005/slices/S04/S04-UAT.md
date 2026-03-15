# S04: Prova integrada de upgrade e backend no schema final — UAT

**Milestone:** M005
**Written:** 2026-03-15T13:55:14-03:00

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: o risco restante desta slice era de montagem final e runtime real, então a prova precisa combinar artefatos publicados (`status.json`, logs, fingerprint canônico) com um backend vivo no schema final em vez de depender só de suites isoladas ou `TestClient(app)`.

## Preconditions

- `backend-hormonia/.venv` presente com dependências instaladas.
- PostgreSQL local disponível em `postgresql://postgres:postgres@localhost:55432/hormonia_test` ou via `FINAL_SCHEMA_PROOF_DATABASE_URL`.
- Redis disponível para o backend local.
- Porta `8000` livre antes do mounted backend proof.
- **Uso serial obrigatório:** não execute os comandos abaixo em paralelo contra o mesmo banco; o runner usa lock em `/tmp/gsd-m005-s04-final-schema-proof/serial.lock` para impor esse contrato.

## Smoke Test

- Execute `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh`.
- **Expected:** o comando termina em `PASS`, publica `/tmp/gsd-m005-s04-final-schema-proof/fresh/status.json` com `status: passed` e `phase: live_auth_probe`, e aponta para logs reais de replay pytest e backend montado.

## Test Cases

### 1. Replay focado do head final pelo shared Postgres harness

1. Execute:
   - `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' .venv/bin/python -m pytest -q tests/migrations/test_canonical_schema_head_convergence.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_auth_hard_cut_end_to_end.py`
2. Confirme que os quatro arquivos terminam verdes.
3. **Expected:** o oracle estrutural de S03 continua verde e os três packs críticos pós-M004 continuam verdes no head final provisionado via Alembic, não por `Base.metadata.create_all()`.

### 2. Runner S04 em history fresh

1. Execute: `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh`
2. Abra:
   - `/tmp/gsd-m005-s04-final-schema-proof/fresh/status.json`
   - `/tmp/gsd-m005-s04-final-schema-proof/fresh/canonical-head.json`
   - `/tmp/gsd-m005-s04-final-schema-proof/fresh/pytest-replay.log`
   - `/tmp/gsd-m005-s04-final-schema-proof/fresh/mounted-backend/backend.log`
   - `/tmp/gsd-m005-s04-final-schema-proof/fresh/mounted-backend/live-auth-probe.log`
3. **Expected:** `history` é `fresh`, `phase` termina em `live_auth_probe`, `status` é `passed`, o fingerprint canônico aponta para `m005_s03_t02_align_audit_history_head`, e os logs do replay pytest e do backend-only mounted proof existem.

### 3. Runner S04 em history existing-upgrade

1. Execute: `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --existing`
2. Abra:
   - `/tmp/gsd-m005-s04-final-schema-proof/existing/status.json`
   - `/tmp/gsd-m005-s04-final-schema-proof/existing/canonical-head.json`
   - `/tmp/gsd-m005-s04-final-schema-proof/existing/pytest-replay.log`
   - `/tmp/gsd-m005-s04-final-schema-proof/existing/mounted-backend/backend.log`
   - `/tmp/gsd-m005-s04-final-schema-proof/existing/mounted-backend/live-auth-probe.log`
3. **Expected:** `history` é `existing`, o runner parte de `m005_s02_t01_publish_firebase_history_boundary`, chega ao mesmo head final, publica os mesmos artefatos do cenário fresh e termina com `status: passed`.

### 4. Superfície de status explícita continua honesta

1. Execute:
   - `python3 - <<'PY'
from __future__ import annotations
import json
from pathlib import Path

root = Path('/tmp/gsd-m005-s04-final-schema-proof')
for history in ('fresh', 'existing'):
    status_path = root / history / 'status.json'
    payload = json.loads(status_path.read_text(encoding='utf-8'))
    assert payload['history'] == history, payload
    assert payload['status'] == 'passed', payload
    assert payload['phase'] == 'live_auth_probe', payload
    for key in ('canonical_log', 'pytest_replay_log', 'mounted_helper_log', 'backend_log', 'live_auth_probe_log'):
        assert Path(payload['paths'][key]).exists(), (history, key, payload)
print('s04 status surfaces verified')
PY`
2. **Expected:** o comando imprime `s04 status surfaces verified`; cada `status.json` mantém `history`/`phase` explícitos e aponta para logs reais inspecionáveis.

## Edge Cases

### Serial lock no mesmo banco

1. Tente iniciar um segundo `run-final-schema-proof.sh` enquanto outro já está executando.
2. **Expected:** o segundo processo não avança concorrendo no mesmo schema; o lock em `/tmp/gsd-m005-s04-final-schema-proof/serial.lock` impede corrida silenciosa.

### Porta 8000 ocupada antes do mounted proof

1. Deixe outro processo ouvindo em `:8000` e execute `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh`.
2. **Expected:** a falha aparece de forma explícita em `status.json`/`backend.log` na fase `mounted_backend` ou `live_auth_probe`; não deve haver falso verde.

## Failure Signals

- `status.json` com `status: failed` ou fase final diferente de `live_auth_probe`.
- `canonical-head.log` mostrando falha no fingerprint/head canônico.
- `pytest-replay.log` com qualquer um dos três packs críticos falhando.
- `backend.log` sem readiness ou `live-auth-probe.log` com falhas `runtime_ready`, `runtime_config` ou `live_session_flow`.
- Qualquer artefato do proof user em texto puro fora dos caminhos mascarados publicados pelo runner.

## Requirements Proved By This UAT

- R053 — prova integrada real do estado convergido: fresh/existing upgrade, replay dos loops críticos e backend montado no schema final.
- R051 — rechecagem operacional do head canônico já validado, agora sob o entrypoint real do backend e não apenas por provas de migration/schema.

## Not Proven By This UAT

- R052 — remoção final de código morto, bridges, aliases e compatibilidades restantes continua pertencendo a M006.
- Browser/frontend smoke amplo não é reexecutado aqui; essa cobertura já foi fechada em M004/S06 e não é o risco que S04 precisava retirar.

## Notes for Tester

- O runner S04 reutiliza o helper mounted de S06 em modo backend-only; não espere frontend ou Playwright nesta slice.
- O seed do proof user continua mascarado em disco (`proof.env`/bootstrap helper), sem vazar senha ou token no repositório.
- Se a porta `8000` estiver ocupada, a falha correta é explícita nos artefatos; não force execução paralela no mesmo banco.
