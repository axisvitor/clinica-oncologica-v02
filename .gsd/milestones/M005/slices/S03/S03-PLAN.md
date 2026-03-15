# S03: Head canônico de schema sem resíduo estrutural vivo

**Goal:** Fechar R051 no nível do head: `users`, `audit_logs` e `firebase_sync_history` passam a contar a mesma história canônica em schema, modelos, serializers e migrations, com dado Firebase ainda vivo republicado sob nomes neutros e com compat/histórico explicitado.
**Demo:** Um Postgres novo (`base -> head`) e um Postgres existente no head de S02 (`m005_s02_t01_publish_firebase_history_boundary -> head`) terminam no mesmo head S03, com `users.role` e `audit_logs.event_type` em enums canônicos, `firebase_sync_history` apenas archival, e superfícies oficiais de user/auth/physician lendo e escrevendo o contrato neutro.

## Must-Haves

- `users` deixa de tratar `firebase_last_sign_in`, `firebase_display_name`, `firebase_photo_url`, `firebase_email_verified` e `firebase_custom_claims` como contrato vivo canônico; as superfícies oficiais passam a usar colunas/campos neutros com compat controlada.
- `audit_logs` converge para o contrato canônico real: `event_type` em `audit_event_type`, índices honestos, e `AuditLog` deixa de exigir `firebase_uid` como schema/index vivo.
- `firebase_sync_history` termina como tabela histórica explícita, sem `supabase_user_id`, `sync_action` e `sync_status` como shape vivo obrigatório do head final.
- A prova em Postgres real demonstra que `base -> head` e `S02 head -> head` chegam ao mesmo fingerprint de `users`, `audit_logs`, `firebase_sync_history`, enums e head revision.

## Proof Level

- This slice proves: integration
- Real runtime required: yes
- Human/UAT required: no

## Verification

- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py tests/migrations/test_firebase_historical_boundary.py tests/migrations/test_canonical_schema_head_convergence.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/services/audit/test_audit_service.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py -k 'canonical_profile or canonical_preferences'`
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini current`

## Observability / Diagnostics

- Runtime signals: named assertion prefixes for `canonical_profile`, `canonical_head`, `audit_contract`, and fingerprint diffs for columns/types/indexes/enums/head revision.
- Inspection surfaces: `tests/migrations/test_canonical_schema_head_convergence.py`, `tests/api/v2/test_canonical_user_profile_contracts.py`, `tests/services/audit/test_audit_service.py`, and direct scrubbed `alembic current`.
- Failure visibility: migration phase (`clean_replay` vs `existing_upgrade`), offending revision/head, missing or extra columns/indexes/enums, and API surface name all stay explicit in failures.
- Redaction constraints: keep database URLs masked in subprocess failures and never log preserved historical identifiers beyond the existing masked fixtures.

## Integration Closure

- Upstream surfaces consumed: S01 Alembic operability harness, S02 Firebase historical-boundary migration/tests, `app.models.user`, `app.models.audit_log`, `app.models.user_sync_log`, and the official `users` / `auth` / `physicians` API serializers.
- New wiring introduced in this slice: linear S03 alignment revision(s), neutral user-profile/settings storage wired through official serializers/writers, and a fingerprint-based migration convergence proof.
- What remains before the milestone is truly usable end-to-end: S04 still has to boot the real backend on this final head and replay the post-M004 critical loops against both freshly bootstrapped and upgraded schemas.

## Tasks

- [x] **T01: Republicar o contrato vivo de `users` sob nomes canônicos** `est:2h`
  - Why: o maior resíduo estrutural restante está em `users`: o runtime oficial já fala em `last_login` / `photo_url`, mas ainda grava e modela esses dados sob nomes `firebase_*` e dentro de `firebase_custom_claims`.
  - Files: `backend-hormonia/alembic/versions/<s03_users_alignment>.py`, `backend-hormonia/app/models/user.py`, `backend-hormonia/app/api/v2/routers/users.py`, `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/api/v2/routers/physicians/crud.py`, `backend-hormonia/app/schemas/v2/auth.py`, `backend-hormonia/app/schemas/v2/physicians.py`, `backend-hormonia/tests/api/v2/test_canonical_user_profile_contracts.py`
  - Do: adicionar uma revision linear a partir de `m005_s02_t01_publish_firebase_history_boundary` que introduza/backfille colunas neutras para login/profile/settings vivos em `users`; atualizar `User` e as superfícies oficiais de user/auth/physician para dual-read/write pelos nomes canônicos; tirar preferências/perfil do papel de storage canônico de `firebase_custom_claims`; manter `firebase_uid` e `auth_provider` apenas como compat explícita enquanto ainda houver leitores/tests que dependem deles.
  - Verify: `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py`
  - Done when: payloads oficiais e writes de `users`/`auth`/`physicians` usam o contrato neutro, e `firebase_custom_claims` deixa de ser o storage canônico vivo para preferências e perfil.
- [ ] **T02: Alinhar audit/history e provar convergência clean+existing no mesmo head** `est:2h`
  - Why: sem fechar `audit_logs` e `firebase_sync_history` contra o head real, S03 ainda fica com um schema que opera mas não conta a mesma história em banco novo e banco existente.
  - Files: `backend-hormonia/alembic/versions/<s03_audit_history_alignment>.py`, `backend-hormonia/app/models/audit_log.py`, `backend-hormonia/app/models/user_sync_log.py`, `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py`, `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py`, `backend-hormonia/tests/migrations/test_alembic_operability.py`, `backend-hormonia/tests/services/audit/test_audit_service.py`
  - Do: adicionar a revision linear final que cria/backfille `user_role`/`audit_event_type` quando necessário e converte `users.role` e `audit_logs.event_type` para enums canônicos em clean e upgraded paths; remover `firebase_uid` do contrato vivo de `AuditLog` em vez de inventá-lo no head; decidir o destino archival de `supabase_user_id` / `sync_action` / `sync_status` em `firebase_sync_history`; e estender a harness de migrations com fingerprint estrutural para comparar `base -> head` e `S02 head -> head`.
  - Verify: `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py tests/migrations/test_firebase_historical_boundary.py tests/migrations/test_canonical_schema_head_convergence.py tests/services/audit/test_audit_service.py`
  - Done when: banco novo e banco existente chegam ao mesmo head S03 com fingerprint igual para `users`, `audit_logs` e `firebase_sync_history`, com enums/índices honestos e sem expectativa viva de `audit_logs.firebase_uid` ou das colunas transitórias de sync.

## Files Likely Touched

- `backend-hormonia/alembic/versions/<s03_users_alignment>.py`
- `backend-hormonia/alembic/versions/<s03_audit_history_alignment>.py`
- `backend-hormonia/app/models/user.py`
- `backend-hormonia/app/models/audit_log.py`
- `backend-hormonia/app/models/user_sync_log.py`
- `backend-hormonia/app/api/v2/routers/users.py`
- `backend-hormonia/app/api/v2/routers/auth.py`
- `backend-hormonia/app/api/v2/routers/physicians/crud.py`
- `backend-hormonia/app/schemas/v2/auth.py`
- `backend-hormonia/app/schemas/v2/physicians.py`
- `backend-hormonia/tests/api/v2/test_canonical_user_profile_contracts.py`
- `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py`
- `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py`
- `backend-hormonia/tests/services/audit/test_audit_service.py`
