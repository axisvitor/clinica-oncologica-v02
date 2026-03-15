---
id: T01
parent: S01
milestone: M005
provides:
  - Settings-free Alembic metadata/bootstrap path plus the first operability regression pack
key_files:
  - backend-hormonia/app/db/base.py
  - backend-hormonia/app/db/migrations.py
  - backend-hormonia/alembic/env.py
  - backend-hormonia/tests/migrations/test_alembic_operability.py
key_decisions:
  - Alembic now loads metadata and resolves the database URL through settings-free `app.db` helpers instead of importing `app.database` / `app.config.settings`
  - Package-level `app.utils` and `app.integrations*` exports are lazy so deep model imports no longer bootstrap unrelated runtime settings
patterns_established:
  - Keep declarative metadata in `app.db.base` and leave engine/session bootstrap in `app.database`
  - Prove import safety with scrubbed-env subprocess tests that assert forbidden modules and named failure phases
observability_surfaces:
  - pytest -q tests/migrations/test_alembic_operability.py
  - env -i PATH="$PATH" HOME="$HOME" DATABASE_URL=... python3 -m alembic -c alembic.ini history
  - env -i PATH="$PATH" HOME="$HOME" DATABASE_URL=... python3 -m alembic -c alembic.ini heads
duration: ~1h
verification_result: passed
completed_at: 2026-03-14
blocker_discovered: false
---

# T01: Extrair a trilha de metadata Alembic sem settings de runtime

**Extraí a trilha de metadata/URL do Alembic para `app.db`, mantive `app.database` como bootstrap de runtime, e deixei um pack inicial que prova bootstrap scrubbed sem `app.config.settings`.**

## What Happened

- Criei `backend-hormonia/app/db/base.py` para hospedar o `Base` declarativo em um módulo sem engine, settings ou validação de runtime.
- Criei `backend-hormonia/app/db/migrations.py` com `resolve_migration_database_url()` e `get_migration_metadata()`, incluindo erros nomeados de bootstrap (`db_url_resolution`, `graph-load`) para o pack de operabilidade.
- Reaproveitei esse `Base` em `backend-hormonia/app/database.py` sem mudar o bootstrap de engine/sessões do runtime.
- Reapontei os consumidores diretos de `Base` (`app/models/base.py`, `app/models/patient_deletion_audit.py`, `app/integrations/whatsapp/models/message.py`) para o módulo settings-free.
- Reescrevi `backend-hormonia/alembic/env.py` para consumir a trilha segura de metadata/URL e parar de importar `app.config.settings` no carregamento do ambiente Alembic.
- Adicionei `backend-hormonia/tests/migrations/test_alembic_operability.py` com os primeiros contratos do slice: bootstrap de metadata em subprocess scrubbed, normalização/resolução do DB URL e falha nomeada quando não há fonte de URL.
- Durante o bootstrap scrubbed apareceu um acoplamento extra fora do `Base`: `app.utils.__init__` e `app.integrations*.__init__` importavam runtime pesado no ato de abrir um submódulo. Converti esses pacotes para exports lazy para que imports profundos de modelos parem de acionar settings globais.
- Esse corte lateral foi suficiente para deixar `history` e `heads` verdes em ambiente scrubbed já no T01, antes do trabalho previsto originalmente para T02.

## Verification

- `cd backend-hormonia && python3 -m pytest -q tests/migrations/test_alembic_operability.py -k db_url_resolution` ✅
- `cd backend-hormonia && pytest -q tests/migrations/test_alembic_operability.py -k settings_free_metadata` ✅
- `cd backend-hormonia && pytest -q tests/migrations/test_alembic_operability.py` ✅
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://user:pass@localhost/dbname' python3 -m alembic -c alembic.ini history` ✅
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://user:pass@localhost/dbname' python3 -m alembic -c alembic.ini heads` ✅
- O wrapper exato `TEST_DATABASE_URL=${TEST_DATABASE_URL:?} ...` do plano não rodou na shell do agente porque `TEST_DATABASE_URL` não estava presente; o pack criado neste task é deliberadamente DB-free e passou sem depender desse env.

## Diagnostics

- `backend-hormonia/tests/migrations/test_alembic_operability.py` agora separa falhas de `settings_free_metadata` e `db_url_resolution`.
- `backend-hormonia/app/db/migrations.py` expõe `MigrationBootstrapError` com mensagens nomeadas para resolução de URL e import de metadata.
- O teste scrubbed falha explicitamente se `app.database`, `app.config` ou `app.config.settings` reaparecerem no caminho de bootstrap.
- Os comandos scrubbed `python3 -m alembic -c alembic.ini history|heads` já funcionam como superfície direta de inspeção do controle plane sem segredos de runtime.

## Deviations

- Toquei `backend-hormonia/app/utils/__init__.py`, `backend-hormonia/app/integrations/__init__.py` e `backend-hormonia/app/integrations/whatsapp/__init__.py`, embora não estivessem na lista inicial do task, porque seus side effects de import ainda puxavam settings quando os modelos carregavam submódulos desses pacotes.
- Isso antecipou parte do efeito esperado em T02: `history` e `heads` já ficaram operáveis sob env scrubbed no T01.

## Known Issues

- O caminho real de banco para `current` / `upgrade head` ainda não foi provado neste task; isso segue para os próximos tasks do slice.
- A shell do agente não tinha `TEST_DATABASE_URL`, então os checks que exigem banco de prova real continuam dependentes desse env quando forem executados no formato do plano.

## Files Created/Modified

- `backend-hormonia/app/db/base.py` — novo módulo settings-free para o `Base` declarativo.
- `backend-hormonia/app/db/migrations.py` — helpers seguros de metadata e resolução de URL para Alembic.
- `backend-hormonia/app/database.py` — runtime passa a reaproveitar o `Base` extraído.
- `backend-hormonia/app/models/base.py` — `BaseModel` passa a depender do novo `Base` seguro.
- `backend-hormonia/app/models/patient_deletion_audit.py` — modelo LGPD deixa de importar `app.database`.
- `backend-hormonia/app/integrations/whatsapp/models/message.py` — modelos WhatsApp deixam de importar `app.database`.
- `backend-hormonia/alembic/env.py` — bootstrap Alembic troca settings/runtime por helper seguro.
- `backend-hormonia/tests/migrations/test_alembic_operability.py` — primeiro pack de operabilidade do slice.
- `backend-hormonia/app/utils/__init__.py` — exports lazy para evitar side effects de runtime em imports profundos.
- `backend-hormonia/app/integrations/__init__.py` — exports lazy para evitar bootstrap de integrações pesadas em imports profundos.
- `backend-hormonia/app/integrations/whatsapp/__init__.py` — exports lazy para o pacote WhatsApp.
- `.gsd/milestones/M005/slices/S01/S01-PLAN.md` — verificação do slice ganhou o check diagnóstico e T01 foi marcado como concluído.
- `.gsd/DECISIONS.md` — decisão registrada sobre a fronteira de import do bootstrap Alembic.
- `.gsd/STATE.md` — próximo passo atualizado para T02.
