---
estimated_steps: 4
estimated_files: 5
---

# T03: Provar `base -> head` e `current` em Postgres real sem segredos extras

**Slice:** S01 — Alembic operável sem segredos de runtime
**Milestone:** M005

## Description

Fechar a slice com traversal real em banco. Depois que metadata e graph walk estiverem limpos, o último risco é o upgrade ainda depender de serviços/segredos da app dentro de migrations de backfill — especialmente nas revisions LGPD. Este task torna `upgrade head` e `current` realmente replayáveis em Postgres local com apenas configuração de banco e deixa um pack focado que S02/S03 podem reutilizar.

## Steps

1. Ajustar as migrations 020, 029 e `73a9d4d7cf05` para não carregar serviços/segredos da app antes de saber se há dados a migrar, preservando a semântica de banco quando houver trabalho real.
2. Estender `tests/migrations/test_alembic_operability.py` para cobrir `upgrade head` a partir de schema limpo e `current` no banco resultante.
3. Reaproveitar o padrão de reset/schema do pack de migrations existente para manter a prova local e reexecutável em Postgres.
4. Fechar o output de falha com comando, phase e revision para que traversal quebrado seja diagnosticável sem reabrir discovery.

## Must-Haves

- [ ] `upgrade head` em banco limpo/local não exige WuzAPI/Firebase env nem importa serviços da app desnecessariamente quando não há dados para backfill.
- [ ] `current` consegue ler o banco de prova depois do upgrade e reporta o head esperado.
- [ ] O pack `tests/migrations/test_alembic_operability.py` vira a prova executável da slice para `history`, `heads`, `current` e `upgrade`.

## Verification

- `cd backend-hormonia && TEST_DATABASE_URL=${TEST_DATABASE_URL:?} pytest -q tests/migrations/test_alembic_operability.py`
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL=${TEST_DATABASE_URL:?} python3 -m alembic -c alembic.ini heads`

## Observability Impact

- Signals added/changed: o pack final de operabilidade passa a diferenciar falha de `graph-load`, falha de `upgrade` e divergência de `current/head`.
- How a future agent inspects this: `pytest -q tests/migrations/test_alembic_operability.py` e repetição manual dos comandos `alembic history/heads/current` no mesmo banco de prova.
- Failure state exposed: se uma migration voltar a pedir segredo/runtime indevido, a saída precisa dizer qual revision e em qual fase do upgrade isso ocorreu.

## Inputs

- `backend-hormonia/tests/migrations/test_alembic_operability.py` — harness já capaz de provar metadata segura e graph walk após T01/T02.
- `backend-hormonia/alembic/versions/020_encrypt_cpf_lgpd.py` — migration LGPD que hoje importa serviço da app antes do traversal terminar.
- `backend-hormonia/alembic/versions/029_migrate_email_phone_to_encrypted.py` — migration LGPD que hoje importa e inicializa serviço de encryption pelo caminho da app.
- `backend-hormonia/alembic/versions/73a9d4d7cf05_align_patient_lgpd_encryption.py` — revision consolidada que ainda pode reabrir o acoplamento no upgrade.

## Expected Output

- `backend-hormonia/alembic/versions/020_encrypt_cpf_lgpd.py` — upgrade não exige serviço/runtime da app quando não há trabalho real de backfill.
- `backend-hormonia/alembic/versions/029_migrate_email_phone_to_encrypted.py` — upgrade não exige serviço/runtime da app quando não há trabalho real de backfill.
- `backend-hormonia/alembic/versions/73a9d4d7cf05_align_patient_lgpd_encryption.py` — upgrade não reabre acoplamento indevido no head consolidado atual.
- `backend-hormonia/tests/migrations/test_alembic_operability.py` — prova final da slice cobrindo `history`, `heads`, `current` e `upgrade head`.
