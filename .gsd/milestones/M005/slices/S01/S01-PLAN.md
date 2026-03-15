# S01: Alembic operável sem segredos de runtime

**Goal:** Desacoplar o controle de migrations do runtime da aplicação para que o grafo Alembic volte a ser uma superfície operacional própria: `history`, `heads`, `current` e um `upgrade head` real devem depender apenas de configuração de banco e de helpers autocontidos de migration.
**Demo:** Em um Postgres local de prova, um mantenedor executa a prova de operabilidade do Alembic com o ambiente scrubbed de WuzAPI/Firebase; `history` e `heads` percorrem o grafo inteiro, `current` responde no banco de teste e `upgrade head` sai de um schema limpo até o head sem importar `app.config.settings` nem exigir segredos de runtime fora do banco.

## Must-Haves

- R051 avança de forma direta: `alembic/env.py`, o carregamento de metadata e as revisions históricas deixam de puxar `app.config.settings` ou helpers de runtime só para percorrer o grafo.
- `history`, `heads` e `current` ficam replayáveis com apenas `DATABASE_URL` / `TEST_DATABASE_URL`, sem WuzAPI/Firebase env e sem introduzir um "modo Alembic" que relaxe a validação normal do runtime.
- Existe prova executável em `backend-hormonia/tests/migrations/test_alembic_operability.py` cobrindo inspeção do grafo e `upgrade head` real em Postgres local, dando suporte concreto a R053 no ponto em que o controle plane de migrations deixa de ser só uma promessa estática.

## Proof Level

- This slice proves: operational
- Real runtime required: yes
- Human/UAT required: no

## Verification

- `cd backend-hormonia && TEST_DATABASE_URL=${TEST_DATABASE_URL:?} pytest -q tests/migrations/test_alembic_operability.py`
- `cd backend-hormonia && python3 -m pytest -q tests/migrations/test_alembic_operability.py -k db_url_resolution`
- `cd backend-hormonia && python3 -m pytest -q tests/migrations/test_alembic_operability.py -k missing_source_has_named_failure`
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL=${TEST_DATABASE_URL:?} python3 -m alembic -c alembic.ini history`
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL=${TEST_DATABASE_URL:?} python3 -m alembic -c alembic.ini heads`

## Observability / Diagnostics

- Runtime signals: o pack `tests/migrations/test_alembic_operability.py` deve capturar stdout/stderr dos comandos Alembic e apontar explicitamente comando, revision e fase (`graph-load`, `current`, `upgrade`) quando algo voltar a exigir runtime indevido.
- Inspection surfaces: `pytest -q tests/migrations/test_alembic_operability.py`, os comandos diretos `python3 -m alembic -c alembic.ini ...`, e as próprias revisions históricas ajustadas em `backend-hormonia/alembic/versions/`.
- Failure visibility: regressões futuras precisam nomear a revision/import path ofensora e distinguir falha de carregamento do grafo, bootstrap de metadata e falha de traversal no banco.
- Redaction constraints: mensagens de falha podem citar nomes de env vars ausentes, mas nunca valores; URLs de banco expostas em assertions/logs devem sair com credenciais mascaradas.

## Integration Closure

- Upstream surfaces consumed: `backend-hormonia/alembic/env.py`, `backend-hormonia/app/database.py`, `backend-hormonia/app/models/base.py`, `backend-hormonia/app/models/patient_deletion_audit.py`, as revisions históricas 016/018/019/020/029/73a9d4d7cf05/c9a6d2f7b3e1, e o padrão de harness já usado em `backend-hormonia/tests/migrations/test_drop_unused_quiz_tables_migration.py`.
- New wiring introduced in this slice: uma trilha de metadata/import helpers segura para migrations e um harness focado que executa Alembic sob env scrubbed contra Postgres real.
- What remains before the milestone is truly usable end-to-end: S02 ainda precisa decidir/publícar a fronteira histórica de Firebase, S03 ainda precisa convergir banco novo e banco existente ao mesmo head canônico, e S04 ainda precisa subir o backend no schema consolidado.

## Tasks

- [x] **T01: Extrair a trilha de metadata Alembic sem settings de runtime** `est:1h30m`
  - Why: hoje `current`/`upgrade` ainda atravessam `app.database` e disparam validação de settings porque o `Base` declarativo vive no módulo errado; sem cortar esse acoplamento, a slice não consegue tornar o controle plane do Alembic independente.
  - Files: `backend-hormonia/app/db/base.py`, `backend-hormonia/app/database.py`, `backend-hormonia/app/models/base.py`, `backend-hormonia/app/models/patient_deletion_audit.py`, `backend-hormonia/alembic/env.py`, `backend-hormonia/tests/migrations/test_alembic_operability.py`
  - Do: extrair o `Base` SQLAlchemy para um módulo sem settings de runtime, fazer models + Alembic consumirem essa trilha segura, manter engine/sessões de runtime em `app.database`, e escrever os primeiros testes focados que provam que o bootstrap de metadata/URL do Alembic não depende mais de `app.config.settings`.
  - Verify: `cd backend-hormonia && TEST_DATABASE_URL=${TEST_DATABASE_URL:?} pytest -q tests/migrations/test_alembic_operability.py -k settings_free_metadata`
  - Done when: a metadata usada pelo Alembic consegue inicializar e apontar para o banco de prova sem importar o settings global da app nem exigir WuzAPI/Firebase env.
- [x] **T02: Neutralizar imports históricos que quebram o walk do grafo** `est:1h30m`
  - Why: mesmo com metadata isolada, `history`/`heads` continuam mortos enquanto revisions antigas carregarem `app.utils` ou outros helpers da app só para resolver timestamp/validação durante import.
  - Files: `backend-hormonia/alembic/runtime_helpers.py`, `backend-hormonia/alembic/versions/016_validate_patient_metadata.py`, `backend-hormonia/alembic/versions/018_seed_flow_templates_for_onboarding.py`, `backend-hormonia/alembic/versions/019_seed_welcome_message_template.py`, `backend-hormonia/alembic/versions/c9a6d2f7b3e1_ensure_message_templates_table.py`, `backend-hormonia/tests/migrations/test_alembic_operability.py`
  - Do: mover helpers de timestamp/validação usados por migrations para um módulo Alembic autocontido ou equivalentes stdlib, preservar a semântica de banco dessas revisions, e ampliar o harness para rodar `history` e `heads` sob env scrubbed de segredos não relacionados.
  - Verify: `cd backend-hormonia && TEST_DATABASE_URL=${TEST_DATABASE_URL:?} pytest -q tests/migrations/test_alembic_operability.py -k "history or heads"`
  - Done when: o grafo completo carrega e `history`/`heads` passam com apenas config de banco, deixando qualquer regressão futura apontar a revision/import path exata.
- [x] **T03: Provar `base -> head` e `current` em Postgres real sem segredos extras** `est:2h`
  - Why: S01 só é verdadeira quando um banco real consegue percorrer o grafo; inspeção verde sem `upgrade head` ainda deixaria R051 pela metade e não sustentaria o handoff para S02/S03.
  - Files: `backend-hormonia/alembic/versions/020_encrypt_cpf_lgpd.py`, `backend-hormonia/alembic/versions/029_migrate_email_phone_to_encrypted.py`, `backend-hormonia/alembic/versions/73a9d4d7cf05_align_patient_lgpd_encryption.py`, `backend-hormonia/tests/migrations/test_alembic_operability.py`, `backend-hormonia/tests/migrations/test_drop_unused_quiz_tables_migration.py`
  - Do: impedir que migrations de backfill vazio carreguem serviços da app ou segredos desnecessários antes de saber se há dados para migrar, estender o harness para cobrir `upgrade head` e `current` em schema limpo/local Postgres, e manter o output de falha amarrado à fase/revision que travar a traversal.
  - Verify: `cd backend-hormonia && TEST_DATABASE_URL=${TEST_DATABASE_URL:?} pytest -q tests/migrations/test_alembic_operability.py`
  - Done when: `history`, `heads`, `current` e `upgrade head` estão provados no pack focado contra Postgres local sem WuzAPI/Firebase env, e o que sobra para S02/S03 já é schema/histórico canônico — não o controle plane do Alembic quebrado.

## Files Likely Touched

- `.gsd/milestones/M005/slices/S01/S01-PLAN.md`
- `backend-hormonia/app/db/base.py`
- `backend-hormonia/app/database.py`
- `backend-hormonia/app/models/base.py`
- `backend-hormonia/app/models/patient_deletion_audit.py`
- `backend-hormonia/alembic/env.py`
- `backend-hormonia/alembic/runtime_helpers.py`
- `backend-hormonia/alembic/versions/016_validate_patient_metadata.py`
- `backend-hormonia/alembic/versions/018_seed_flow_templates_for_onboarding.py`
- `backend-hormonia/alembic/versions/019_seed_welcome_message_template.py`
- `backend-hormonia/alembic/versions/020_encrypt_cpf_lgpd.py`
- `backend-hormonia/alembic/versions/029_migrate_email_phone_to_encrypted.py`
- `backend-hormonia/alembic/versions/73a9d4d7cf05_align_patient_lgpd_encryption.py`
- `backend-hormonia/alembic/versions/c9a6d2f7b3e1_ensure_message_templates_table.py`
- `backend-hormonia/tests/migrations/test_alembic_operability.py`
- `backend-hormonia/tests/migrations/test_drop_unused_quiz_tables_migration.py`
