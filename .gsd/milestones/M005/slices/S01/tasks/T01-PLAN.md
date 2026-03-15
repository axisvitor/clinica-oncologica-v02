---
estimated_steps: 4
estimated_files: 6
---

# T01: Extrair a trilha de metadata Alembic sem settings de runtime

**Slice:** S01 — Alembic operável sem segredos de runtime
**Milestone:** M005

## Description

Abrir um caminho de metadata que o Alembic consiga carregar sem passar pelo bootstrap completo do backend. Este task existe para remover o acoplamento mais estrutural do slice: hoje o `Base` declarativo mora em `app.database`, e isso puxa settings, engine e validação de runtime antes mesmo de o Alembic conseguir responder `current` ou iniciar um upgrade.

## Steps

1. Extrair o `Base` SQLAlchemy para um módulo próprio e sem settings de runtime, ajustando os modelos-base que ainda importam `app.database` diretamente.
2. Fazer `app.database` reaproveitar o novo `Base` sem mudar o comportamento do runtime de engine/sessões.
3. Atualizar `backend-hormonia/alembic/env.py` para consumir a trilha de metadata segura em vez de depender do módulo de runtime que valida settings globais.
4. Criar `backend-hormonia/tests/migrations/test_alembic_operability.py` com os primeiros testes focados no bootstrap de metadata/URL do Alembic sob env scrubbed.

## Must-Haves

- [ ] O `Base` declarativo usado pelos modelos deixa de viver em um módulo que instancia settings/engine na importação.
- [ ] `alembic/env.py` passa a montar metadata e URL de banco por uma trilha segura para migrations, sem criar um bypass global da validação do runtime.
- [ ] O primeiro pedaço do pack `tests/migrations/test_alembic_operability.py` fica pronto para sustentar os próximos tasks.

## Verification

- `cd backend-hormonia && TEST_DATABASE_URL=${TEST_DATABASE_URL:?} pytest -q tests/migrations/test_alembic_operability.py -k settings_free_metadata`
- `cd backend-hormonia && python3 -m pytest -q tests/migrations/test_alembic_operability.py -k db_url_resolution`

## Observability Impact

- Signals added/changed: testes passam a distinguir falha de resolução de URL, falha de import de metadata e regressão por import de settings.
- How a future agent inspects this: `pytest -q tests/migrations/test_alembic_operability.py -k settings_free_metadata` e leitura direta de `backend-hormonia/alembic/env.py`.
- Failure state exposed: o erro deixa de aparecer só como validação global de settings e passa a indicar se o problema está no `Base`, no `env.py` ou na resolução do DB URL.

## Inputs

- `backend-hormonia/alembic/env.py` — ponto atual onde o Alembic importa `app.config.settings` e a metadata via runtime.
- `backend-hormonia/app/database.py` — hoje mistura `Base`, engine e settings globais.
- `backend-hormonia/tests/migrations/test_drop_unused_quiz_tables_migration.py` — padrão local de harness Alembic real contra Postgres.

## Expected Output

- `backend-hormonia/app/db/base.py` — trilha nova e segura para o `Base` declarativo.
- `backend-hormonia/alembic/env.py` — carregamento de metadata/URL desacoplado do bootstrap completo da app.
- `backend-hormonia/tests/migrations/test_alembic_operability.py` — primeiros testes do contrato de operabilidade.
