---
id: T02
parent: S01
milestone: M005
provides:
  - Historical Alembic revisions now load through migration-only helpers, and the operability pack proves scrubbed `history`/`heads` graph walk without runtime imports
key_files:
  - backend-hormonia/alembic/runtime_helpers.py
  - backend-hormonia/alembic_runtime_helpers.py
  - backend-hormonia/alembic/versions/016_validate_patient_metadata.py
  - backend-hormonia/alembic/versions/018_seed_flow_templates_for_onboarding.py
  - backend-hormonia/alembic/versions/019_seed_welcome_message_template.py
  - backend-hormonia/alembic/versions/c9a6d2f7b3e1_ensure_message_templates_table.py
  - backend-hormonia/tests/migrations/test_alembic_operability.py
key_decisions:
  - Historical revisions use migration-only timestamp/validation helpers instead of importing `app.utils` at graph-load time
  - The helper source stays under `backend-hormonia/alembic/`, with `backend-hormonia/alembic_runtime_helpers.py` as the importable shim because the installed Alembic package already owns `alembic.*`
patterns_established:
  - Keep historical migration semantics intact while replacing runtime-coupled helpers with self-contained migration copies
  - Make graph-walk regressions fail with command/revision/import-path diagnostics instead of a generic settings cascade
observability_surfaces:
  - pytest -q tests/migrations/test_alembic_operability.py -k "history or heads"
  - pytest -q tests/migrations/test_alembic_operability.py -k graph_walk_bootstrap_avoids_runtime_helpers
  - env -i PATH="$PATH" HOME="$HOME" DATABASE_URL=... python3 -m alembic -c alembic.ini history
  - env -i PATH="$PATH" HOME="$HOME" DATABASE_URL=... python3 -m alembic -c alembic.ini heads
duration: ~1h10m
verification_result: passed
completed_at: 2026-03-14
blocker_discovered: false
---

# T02: Neutralizar imports históricos que quebram o walk do grafo

**Substituí os imports históricos de `app.utils` por helpers de migration autocontidos, e ampliei o pack de operabilidade para provar o graph walk scrubbed com diagnóstico nomeado de command/revision/import path.**

## What Happened

- Criei `backend-hormonia/alembic/runtime_helpers.py` com as únicas duas responsabilidades que as revisions históricas desta frente ainda precisavam do runtime: `now_sao_paulo_naive()` e a validação JSON Schema usada pela migration 016.
- Como o nome `alembic.*` já pertence ao pacote instalado, adicionei `backend-hormonia/alembic_runtime_helpers.py` como shim importável a partir da raiz do backend; isso mantém a fonte dos helpers ao lado do grafo sem shadowing do Alembic real.
- Reapontei as revisions `016_validate_patient_metadata`, `018_seed_flow_templates`, `019_seed_welcome_message_template` e `c9a6d2f7b3e1` para os helpers de migration, preservando a semântica de banco e removendo os imports de `app.utils.timezone` / `app.utils.jsonb_validator` do caminho do grafo.
- Ampliei `backend-hormonia/tests/migrations/test_alembic_operability.py` com três superfícies novas: walk do grafo via `ScriptDirectory` sob env scrubbed com assert de módulos proibidos, execução real dos comandos `history` e `heads` sob env scrubbed, e uma mensagem de falha estruturada que carrega `command`, `offending_revision` e `offending_import_path` quando o graph walk voltar a quebrar.
- Com isso, os três must-haves deste task ficaram cobertos no código e no resumo de prova: não sobrou import top-level de `app.utils` nas revisions necessárias para `history`/`heads`; o grafo carrega inteiro com apenas config de banco scrubbed; e o harness agora devolve o comando e a trilha ofensora quando o walk falha.

## Verification

- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://graph-walk:graph-walk@localhost:5432/hormonia_graph_walk' pytest -q tests/migrations/test_alembic_operability.py -k "history or heads"` ✅
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://graph-walk:graph-walk@localhost:5432/hormonia_graph_walk' pytest -q tests/migrations/test_alembic_operability.py` ✅
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://graph-walk:graph-walk@localhost:5432/hormonia_graph_walk' python3 -m pytest -q tests/migrations/test_alembic_operability.py -k db_url_resolution` ✅
- `cd backend-hormonia && python3 -m pytest -q tests/migrations/test_alembic_operability.py -k missing_source_has_named_failure` ✅
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://graph-walk:graph-walk@localhost:5432/hormonia_graph_walk' python3 -m alembic -c alembic.ini history` ✅
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://graph-walk:graph-walk@localhost:5432/hormonia_graph_walk' python3 -m alembic -c alembic.ini heads` ✅
- `cd backend-hormonia && rg -n "from app\.utils|import app\.utils|app\.utils\.timezone|jsonb_validator" alembic/versions -g '*.py'` → no matches ✅

## Diagnostics

- `backend-hormonia/tests/migrations/test_alembic_operability.py` agora expõe um check explícito de `phase=graph-load` que falha se `app.database`, `app.config`, `app.utils`, `app.utils.timezone` ou `app.utils.jsonb_validator` reaparecerem no carregamento do grafo.
- Em caso de regressão de `history`/`heads`, o helper `_graph_command_failure_message()` inclui `command=...`, `offending_revision=...` e `offending_import_path=...`, além de stdout/stderr com URLs mascaradas.
- A inspeção mais barata segue sendo `pytest -q tests/migrations/test_alembic_operability.py -k "history or heads"`; para ver a superfície direta do Alembic, repita `python3 -m alembic -c alembic.ini history` ou `heads` com env scrubbed.

## Deviations

- Adicionei `backend-hormonia/alembic_runtime_helpers.py` além do arquivo previsto no plano porque `backend-hormonia/alembic/runtime_helpers.py` não é importável diretamente como `alembic.runtime_helpers` sem conflitar com o pacote Alembic instalado.

## Known Issues

- O slice ainda não provou `current` / `upgrade head` contra Postgres real; isso segue para T03.

## Files Created/Modified

- `backend-hormonia/alembic/runtime_helpers.py` — helpers autocontidos de timezone/validação para migrations históricas.
- `backend-hormonia/alembic_runtime_helpers.py` — shim importável que carrega os helpers locais sem shadowing do pacote Alembic instalado.
- `backend-hormonia/alembic/versions/016_validate_patient_metadata.py` — migração 016 deixa de depender de `app.utils.jsonb_validator`.
- `backend-hormonia/alembic/versions/018_seed_flow_templates_for_onboarding.py` — migração 018 troca `app.utils.timezone` por helper de migration.
- `backend-hormonia/alembic/versions/019_seed_welcome_message_template.py` — migração 019 troca `app.utils.timezone` por helper de migration.
- `backend-hormonia/alembic/versions/c9a6d2f7b3e1_ensure_message_templates_table.py` — migration histórica de `message_templates` deixa de importar helper de runtime.
- `backend-hormonia/tests/migrations/test_alembic_operability.py` — pack de operabilidade agora cobre graph walk scrubbed, `history`, `heads` e diagnóstico nomeado.
- `.gsd/milestones/M005/slices/S01/S01-PLAN.md` — T02 marcado como concluído e verificação do slice mantém o check diagnóstico.
- `.gsd/DECISIONS.md` — decisão registrada sobre o shim importável dos helpers de migration.
- `.gsd/STATE.md` — próximo passo apontado para T03.
