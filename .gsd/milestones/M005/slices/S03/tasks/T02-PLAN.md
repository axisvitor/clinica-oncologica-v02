---
estimated_steps: 4
estimated_files: 7
---

# T02: Alinhar audit/history e provar convergência clean+existing no mesmo head

**Slice:** S03 — Head canônico de schema sem resíduo estrutural vivo
**Milestone:** M005

## Description

Fechar a parte do head que ainda mente no clean replay: `audit_logs.event_type` segue como `varchar`, `AuditLog` ainda espera `firebase_uid`, e `firebase_sync_history` mantém colunas transitórias que o ORM já não assume como contrato. Este task termina a convergência estrutural e deixa a prova em Postgres real dizendo se banco novo e banco existente chegam exatamente ao mesmo head.

## Steps

1. Adicionar uma revision linear final sobre o trabalho de T01 que garanta `audit_event_type` e `user_role` nos caminhos relevantes e converta `users.role` / `audit_logs.event_type` para enums canônicos com backfill e guards idempotentes.
2. Remover `firebase_uid` do contrato vivo de `AuditLog` em modelos/índices/testes, em vez de adicionar essa coluna ao clean head, e ajustar o runtime de auditoria para continuar honesto com qualquer resíduo histórico preservado fora do contrato vivo.
3. Decidir o shape final de `firebase_sync_history`: consolidar qualquer valor histórico útil de `supabase_user_id`, `sync_action` e `sync_status` em payload archival explícito e então remover essas colunas transitórias do head final e do ORM.
4. Criar a suíte de fingerprint estrutural que executa `base -> head` e `m005_s02_t01_publish_firebase_history_boundary -> head`, compara colunas/tipos/índices/enums/head revision para `users`, `audit_logs` e `firebase_sync_history`, e manter falhas nomeadas por `phase`, `head` e `fingerprint_diff`.

## Must-Haves

- [ ] `users.role` e `audit_logs.event_type` terminam enum-backed nos dois caminhos de upgrade, e `AuditLog` deixa de exigir `firebase_uid` como coluna viva.
- [ ] `firebase_sync_history` termina como tabela archival explícita sem colunas transitórias vivas, e a nova suíte prova que clean replay e existing upgrade chegam ao mesmo fingerprint no head S03.

## Verification

- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py tests/migrations/test_firebase_historical_boundary.py tests/migrations/test_canonical_schema_head_convergence.py`
- `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py -k 'canonical or historical or enum'`
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini current`

## Observability Impact

- Signals added/changed: falhas nomeadas por `canonical_head`, `clean_replay`, `existing_upgrade`, `fingerprint_diff`, `enum_missing` e `historical_shape`.
- How a future agent inspects this: nova suíte `tests/migrations/test_canonical_schema_head_convergence.py`, asserções de `test_firebase_historical_boundary.py`, `test_audit_service.py` e o output de `alembic current` sob env scrubbed.
- Failure state exposed: revisão atual, caminho que falhou, diferenças de colunas/tipos/índices/enums e qualquer tentativa de reintroduzir `audit_logs.firebase_uid` ou colunas transitórias de sync.

## Inputs

- `backend-hormonia/app/models/audit_log.py` — hoje ainda modela `firebase_uid` como coluna viva e assume `audit_event_type` mesmo quando o clean head não o cria.
- `backend-hormonia/app/models/user_sync_log.py` — já publica `firebase_sync_history`, mas o schema ainda carrega colunas transitórias herdadas de `033_fix_user_sync_log_schema.py`.
- `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py` — prova atual ainda aceita `supabase_user_id`, `sync_action` e `sync_status` como shape preservado do upgrade existente.
- `backend-hormonia/tests/migrations/test_alembic_operability.py` — harness base de replay/head/current que precisa passar com o novo head S03.
- `.gsd/milestones/M005/slices/S01/S01-SUMMARY.md` e `.gsd/milestones/M005/slices/S02/S02-SUMMARY.md` — já fixam a harness scrubbed e a fronteira histórica explícita que este task não pode reabrir.

## Expected Output

- `backend-hormonia/alembic/versions/<s03_audit_history_alignment>.py` — revision linear final de enum/backfill/cleanup archival.
- `backend-hormonia/app/models/audit_log.py` — modelo alinhado ao schema canônico sem `firebase_uid` vivo.
- `backend-hormonia/app/models/user_sync_log.py` — ORM alinhado ao shape archival final de `firebase_sync_history`.
- `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py` — prova estrutural clean vs existing no mesmo head.
- `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py` — boundary atualizada para o shape archival final.
- `backend-hormonia/tests/migrations/test_alembic_operability.py` — head esperado atualizado para S03.
- `backend-hormonia/tests/services/audit/test_audit_service.py` — prova de que o runtime de auditoria segue canônico no schema final.
