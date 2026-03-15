---
id: T03
parent: S01
milestone: M005
provides:
  - Clean Postgres replay now reaches Alembic head/current without WuzAPI/Firebase secrets, and the operability pack proves `history`, `heads`, `upgrade head`, and `current` with named failure phases
key_files:
  - backend-hormonia/alembic/versions/020_encrypt_cpf_lgpd.py
  - backend-hormonia/alembic/versions/029_migrate_email_phone_to_encrypted.py
  - backend-hormonia/alembic/versions/73a9d4d7cf05_align_patient_lgpd_encryption.py
  - backend-hormonia/alembic/versions/lgpd03_add_ai_audit_event_types.py
  - backend-hormonia/tests/migrations/test_alembic_operability.py
key_decisions:
  - LGPD backfill revisions now count pending rows before importing `app.services.encryption`, so empty clean-schema replays do not bootstrap runtime settings or unrelated secrets
  - `lgpd03_add_ai_audit_event_types` now guards the missing `audit_event_type` enum on the clean replay path instead of aborting `upgrade head`
patterns_established:
  - For migration operability, import runtime-coupled services only after proving there is real backfill work to do
  - Make Alembic command failures name `command`, `phase`, `offending_revision`, and `offending_import_path`, with database URLs masked in stderr/stdout
observability_surfaces:
  - pytest -q tests/migrations/test_alembic_operability.py
  - env -i PATH="$PATH" HOME="$HOME" DATABASE_URL=... python3 -m alembic -c alembic.ini upgrade head
  - env -i PATH="$PATH" HOME="$HOME" DATABASE_URL=... python3 -m alembic -c alembic.ini current
  - env -i PATH="$PATH" HOME="$HOME" DATABASE_URL=... python3 -m alembic -c alembic.ini history
  - env -i PATH="$PATH" HOME="$HOME" DATABASE_URL=... python3 -m alembic -c alembic.ini heads
duration: ~1h35m
verification_result: passed
completed_at: 2026-03-14
blocker_discovered: false
---

# T03: Provar `base -> head` e `current` em Postgres real sem segredos extras

**Guardei os backfills LGPD vazios contra imports de runtime, corrigi a suposição de enum no head limpo e fechei o pack de operabilidade com prova real de `upgrade head`/`current` em Postgres scrubbed.**

## What Happened

- Em `020_encrypt_cpf_lgpd`, `029_migrate_email_phone_to_encrypted` e `73a9d4d7cf05_align_patient_lgpd_encryption`, movi o import de `app.services.encryption` para depois da checagem de trabalho pendente. Em banco limpo, essas migrations agora seguem adiante sem puxar `app.config.settings`, WuzAPI ou Firebase.
- Estendi `backend-hormonia/tests/migrations/test_alembic_operability.py` com o harness de Postgres real: reset de schema reaproveitando o padrão do pack de migrations existente, fixture que exige Postgres local via `TEST_DATABASE_URL`, execução scrubbed de `upgrade head` e `current`, e mensagens de falha estruturadas com `phase=graph-load|upgrade|current`, `offending_revision` e `offending_import_path`.
- Na primeira repro limpa, o upgrade passou pelas revisions LGPD e travou em `lgpd03_add_ai_audit_event_types` porque o caminho histórico limpo não possui o enum `audit_event_type` — o `audit_logs.event_type` ainda é `varchar` nessa trilha. Para manter S01 honesto sem fingir convergência canônica antes de S03, tornei a migration idempotente também para esse caso: se o enum não existe, ela emite `NOTICE` e não derruba o replay.
- Com isso, a prova operacional da slice fechou: `history`, `heads`, `upgrade head` e `current` funcionam em Postgres local com ambiente scrubbed, e qualquer regressão volta apontando a fase e a revision exata em vez de reabrir discovery.

## Verification

- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py` ✅
- `cd backend-hormonia && python3 -m pytest -q tests/migrations/test_alembic_operability.py -k db_url_resolution` ✅
- `cd backend-hormonia && python3 -m pytest -q tests/migrations/test_alembic_operability.py -k missing_source_has_named_failure` ✅
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini history` ✅
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini heads` ✅
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini upgrade head` ✅
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini current` ✅

## Diagnostics

- `backend-hormonia/tests/migrations/test_alembic_operability.py` agora distingue `phase=graph-load`, `phase=upgrade` e `phase=current`, e mascara credenciais de URL em stdout/stderr antes de montar a assertion message.
- A superfície mais barata para esta slice virou `pytest -q tests/migrations/test_alembic_operability.py`; para isolar a CLI real, repita `python3 -m alembic -c alembic.ini history|heads|upgrade head|current` sob `env -i ... DATABASE_URL=...`.
- Se um backfill voltar a importar runtime indevido, a mensagem de falha do harness aponta `command`, `phase`, `offending_revision` e `offending_import_path` diretamente.

## Deviations

- Além dos arquivos previstos, ajustei `backend-hormonia/alembic/versions/lgpd03_add_ai_audit_event_types.py` porque o primeiro replay limpo mostrou uma suposição histórica não documentada: o enum `audit_event_type` não existe no caminho `base -> head`, então a migration precisava tolerar a ausência desse objeto legado para que S01 pudesse provar operabilidade real.

## Known Issues

- O replay limpo agora chega ao head, mas a trilha histórica ainda deixa `audit_logs.event_type` como `varchar`; a convergência do schema limpo/existente para o contrato canônico segue pertencendo a S03.

## Files Created/Modified

- `backend-hormonia/alembic/versions/020_encrypt_cpf_lgpd.py` — backfill de CPF agora só importa o serviço de encryption quando há linhas pendentes.
- `backend-hormonia/alembic/versions/029_migrate_email_phone_to_encrypted.py` — migração de email/phone conta trabalho pendente antes de tocar no runtime de encryption.
- `backend-hormonia/alembic/versions/73a9d4d7cf05_align_patient_lgpd_encryption.py` — revision consolidada só inicializa encryption services quando o replay realmente precisa migrar dados.
- `backend-hormonia/alembic/versions/lgpd03_add_ai_audit_event_types.py` — migration de head agora tolera a ausência do enum legado `audit_event_type` no caminho limpo.
- `backend-hormonia/tests/migrations/test_alembic_operability.py` — pack final da slice cobre `history`, `heads`, `upgrade head` e `current` em Postgres real com mensagens de falha por fase/revision.
- `.gsd/milestones/M005/slices/S01/S01-PLAN.md` — T03 marcado como concluído.
- `.gsd/DECISIONS.md` — decisão registrada para os guard rails de clean replay / backfills runtime-coupled.
- `.gsd/STATE.md` — próximo passo apontado para o fechamento da slice S01 e início de S02.
