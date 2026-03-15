# S04: Prova integrada de upgrade e backend no schema final

**Goal:** Fechar a lacuna operacional deixada por S03: provar com um entrypoint replayable que o backend sobe no head `m005_s03_t02_align_audit_history_head` e que os loops críticos pós-M004 continuam íntegros tanto em banco recém-bootstrapado quanto em banco existente atualizado.
**Demo:** Um mantenedor roda a prova S04 nos modos `fresh` e `existing` e vê, em sequência, o banco preparado no head final, os packs `test_system_auth_hard_cut_operational.py`, `test_local_auth_core_flow.py` e `test_auth_hard_cut_end_to_end.py` verdes sobre esse head via `TEST_DATABASE_URL`, e um uvicorn real no mesmo banco respondendo `/health/ready`, `/api/v2/system/config` e `login -> verify-session -> /users/me -> logout` sem Firebase.

## Must-Haves

- A prova S04 prepara explicitamente os dois histories canônicos (`base -> head` e `m005_s02_t01_publish_firebase_history_boundary -> head`) em modo serial, sem concorrência sobre o mesmo banco e sem usar o caminho mais fraco de `TestClient(app)` para afirmar “backend sobe”.
- Os packs críticos pós-M004 são reexecutados contra o head final via shared Postgres harness e continuam verdes tanto no cenário fresh quanto no existing-upgrade.
- A camada mounted backend-only valida startup real com Firebase blank + WuzAPI mock e falha com phase/status/log pointers claros quando readiness, config pública ou fluxo real de sessão divergirem.

## Proof Level

- This slice proves: final-assembly
- Real runtime required: yes
- Human/UAT required: no

## Verification

- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_canonical_schema_head_convergence.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh`
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --existing`
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
    backend_log = Path(payload['paths']['backend_log'])
    assert backend_log.exists(), payload
print('s04 status surfaces verified')
PY`

## Observability / Diagnostics

- Runtime signals: status file por fase (`fresh`/`existing`, `pytest_replay`, `mounted_backend`, `live_auth_probe`), asserts nomeadas para `canonical_head`, `runtime_ready`, `runtime_config` e `live_session_flow`, e logs dedicados do backend montado.
- Inspection surfaces: `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh`, `backend-hormonia/tests/runtime/test_mounted_final_schema_proof.py`, `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py`, além do diretório de runtime/status publicado pelo runner.
- Failure visibility: a prova deve expor em qual história (`fresh` vs `existing`) e em qual fase a falha ocorreu, com caminhos de `status.json`, `backend.log` e resultado do probe live para inspeção imediata.
- Redaction constraints: manter apenas artefatos mascarados do proof user; não persistir senha, reset token ou qualquer segredo em texto puro no repositório ou nos logs publicados.

## Integration Closure

- Upstream surfaces consumed: `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py`, `backend-hormonia/tests/conftest.py` com provisioning via Alembic head, os packs `tests/api/v2/test_system_auth_hard_cut_operational.py`, `tests/integration/test_local_auth_core_flow.py`, `tests/integration/test_auth_hard_cut_end_to_end.py`, e os padrões de seed/runtime de `.gsd/milestones/M004/slices/S06/`.
- New wiring introduced in this slice: um runner S04 que serializa preparação de banco, replay pytest focado e backend-only mount/probes sobre a mesma `DATABASE_URL` final.
- What remains before the milestone is truly usable end-to-end: nothing inside M005; qualquer cleanup residual além dessa prova fica explicitamente para M006.

## Tasks

- [x] **T01: Publicar o runner serial de prova final-schema e mounted backend** `est:3h`
  - Why: falta um único entrypoint honesto que componha o head final de S03 com o replay dos loops críticos pós-M004 e com startup real de uvicorn, sem confundir cobertura de pytest com prova de backend montado.
  - Files: `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh`, `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh`, `.gsd/milestones/M004/slices/S06/seed-proof-user.py`, `backend-hormonia/tests/runtime/test_mounted_final_schema_proof.py`, `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py`, `backend-hormonia/tests/integration/test_local_auth_core_flow.py`, `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`, `.gsd/milestones/M005/slices/S04/S04-UAT.md`
  - Do: criar um runner replayable com modos `--fresh` e `--existing` que prepara serialmente o banco a partir dos anchors canônicos de S03, roda os packs críticos sob `TEST_DATABASE_URL`, depois sobe um backend-only uvicorn na mesma `DATABASE_URL` com Firebase blank + WuzAPI mock e executa asserts live para `/health/ready`, `/api/v2/system/config` e `login -> verify-session -> /users/me -> logout`; reutilizar ou estender minimamente os helpers de seed/runtime de S06 em vez de inventar um segundo contrato montado; publicar no UAT os comandos, artefatos e limites de uso serial do banco.
  - Verify: `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh && bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --existing`
  - Done when: os dois histories passam pelo mesmo runner fim a fim, a prova mounted não depende de frontend nem de shortcuts de `TESTING=1`, e qualquer falha aponta para fase, status e logs inspecionáveis.

## Files Likely Touched

- `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh`
- `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh`
- `.gsd/milestones/M004/slices/S06/seed-proof-user.py`
- `backend-hormonia/tests/runtime/test_mounted_final_schema_proof.py`
- `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py`
- `backend-hormonia/tests/integration/test_local_auth_core_flow.py`
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`
- `.gsd/milestones/M005/slices/S04/S04-UAT.md`
