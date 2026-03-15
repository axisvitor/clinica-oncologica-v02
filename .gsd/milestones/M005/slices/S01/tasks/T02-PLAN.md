---
estimated_steps: 4
estimated_files: 6
---

# T02: Neutralizar imports históricos que quebram o walk do grafo

**Slice:** S01 — Alembic operável sem segredos de runtime
**Milestone:** M005

## Description

Fechar o segundo grande acoplamento do slice: revisions antigas que ainda importam `app.utils` e outros helpers de runtime durante o load do grafo. Este task transforma o grafo Alembic em algo realmente inspecionável, mantendo a semântica das migrations, mas removendo side effects de import que hoje tornam `history` e `heads` dependentes do runtime da aplicação.

## Steps

1. Criar um módulo Alembic autocontido para helpers de timestamp/validação usados por migrations históricas, evitando import via `app.utils`.
2. Atualizar as revisions 016, 018, 019 e `c9a6d2f7b3e1` para usar esses helpers locais ou equivalentes stdlib, preservando a semântica de banco.
3. Estender `tests/migrations/test_alembic_operability.py` para executar `history` e `heads` sob env scrubbed de WuzAPI/Firebase.
4. Garantir que falhas futuras do graph walk nomeiem a revision/import path ofensora em vez de reaparecerem como erro genérico de settings.

## Must-Haves

- [ ] Nenhuma revision necessária para `history`/`heads` faz import top-level de `app.utils` ou helper de runtime equivalente.
- [ ] O grafo carrega inteiro sob env scrubbed de WuzAPI/Firebase sem alterar a semântica das migrations.
- [ ] O harness focado registra claramente qual command/revision quebrou quando o graph walk voltar a falhar.

## Verification

- `cd backend-hormonia && TEST_DATABASE_URL=${TEST_DATABASE_URL:?} pytest -q tests/migrations/test_alembic_operability.py -k "history or heads"`
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL=${TEST_DATABASE_URL:?} python3 -m alembic -c alembic.ini history`

## Observability Impact

- Signals added/changed: o pack de operabilidade passa a capturar stdout/stderr de `history` e `heads` com nome do comando e da revision ofensora.
- How a future agent inspects this: rodando `pytest -q tests/migrations/test_alembic_operability.py -k "history or heads"` ou repetindo `python3 -m alembic -c alembic.ini history` sob env scrubbed.
- Failure state exposed: regressões deixam um ponto de queda reproduzível no walk do grafo, em vez de uma cascata opaca de validação global.

## Inputs

- `backend-hormonia/tests/migrations/test_alembic_operability.py` — harness inicial criado em T01 e pronto para ser ampliado para graph walk.
- `backend-hormonia/alembic/versions/016_validate_patient_metadata.py` — revision com import runtime de validação.
- `backend-hormonia/alembic/versions/018_seed_flow_templates_for_onboarding.py` — revision que hoje quebra `history` via `app.utils.timezone`.

## Expected Output

- `backend-hormonia/alembic/runtime_helpers.py` — helpers autocontidos para as migrations históricas desta frente.
- `backend-hormonia/alembic/versions/016_validate_patient_metadata.py` — revision sem import runtime no load do grafo.
- `backend-hormonia/alembic/versions/018_seed_flow_templates_for_onboarding.py` — revision carregável por `history`/`heads` sem segredos da app.
- `backend-hormonia/alembic/versions/019_seed_welcome_message_template.py` — revision carregável por `history`/`heads` sem segredos da app.
- `backend-hormonia/alembic/versions/c9a6d2f7b3e1_ensure_message_templates_table.py` — revision carregável por `history`/`heads` sem segredos da app.
- `backend-hormonia/tests/migrations/test_alembic_operability.py` — cobertura de `history`/`heads` sob env scrubbed.
