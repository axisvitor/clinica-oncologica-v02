# S02: Legado Firebase isolado como histórico explícito

**Goal:** Publicar uma fronteira honesta entre legado Firebase preservado e contrato canônico vivo, deixando `user_sync_log` e `audit_logs.firebase_uid` explicitamente históricos enquanto `users`, `admin` e `physicians` deixam de expor `firebase_uid` como campo oficial.
**Demo:** Um mantenedor consegue provar por migration + API/service tests que o legado Firebase preservado vive atrás de uma superfície histórica explícita, que o caminho canônico de auditoria não grava `firebase_uid`, e que os payloads oficiais deixam `firebase_uid` fora do contrato vivo sem quebrar a compat fallback baseada em `user_id`.

## Must-Haves

- `user_sync_log` deixa de parecer uma entidade viva do domínio e passa a ser uma superfície histórica Firebase explícita, com migration/model/service coerentes.
- `audit_logs` preserva o valor forense escolhido apenas como resíduo histórico/read-only; write/read paths canônicos deixam de anunciar `firebase_uid` como contrato vivo.
- Schemas/serializers oficiais de `users`, `admin` e `physicians` deixam de expor `firebase_uid` como campo canônico, e a prova focada mantém o fallback compatível de sessão centrado em `user_id`.

## Requirement Coverage

- `R051` — active requirement directly advanced by this slice. T01 publishes the explicit sync-history boundary, T02 removes `firebase_uid` from canonical audit/API contracts, and T03 makes the proof and fixtures match the new historical/live split.

## Proof Level

- This slice proves: contract
- Real runtime required: yes
- Human/UAT required: no

## Verification

- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py tests/migrations/test_firebase_historical_boundary.py`
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_firebase_historical_boundary.py -k 'sync_history_surface or named_failure'`
- `cd backend-hormonia && pytest -q tests/unit/test_firebase_sync_history.py tests/services/audit/test_audit_service.py tests/api/v2/test_firebase_boundary_contracts.py`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py`

## Observability / Diagnostics

- Runtime signals: named migration/API/service assertions for `sync_history_surface`, `audit_contract`, and `canonical_payload`; canonical audit writes continue surfacing `firebase_uid=None` in persisted rows.
- Inspection surfaces: `tests/migrations/test_firebase_historical_boundary.py`, `tests/unit/test_firebase_sync_history.py`, `tests/services/audit/test_audit_service.py`, and `tests/api/v2/test_firebase_boundary_contracts.py`.
- Failure visibility: regressions should identify whether the break is in migration replay, historical-sync storage, canonical serialization, or compat fallback identity.
- Redaction constraints: never print preserved Firebase identifiers or user PII; use masked fixtures and structural assertions only.

## Integration Closure

- Upstream surfaces consumed: S01 Alembic operability harness, `FirebaseUserSyncService`, `AuditService` / `AuditLogService`, v2 user/admin/physician schemas and serializers, and the existing `user_id`-first auth/session compatibility tests.
- New wiring introduced in this slice: an explicit Firebase history seam for sync rows plus read/write-side sanitization that keeps `firebase_uid` out of canonical payloads while preserving the chosen archival residue.
- What remains before the milestone is truly usable end-to-end: S03 still needs to converge clean and existing databases to one canonical head, and S04 still needs to boot the backend on that head and replay the critical post-M004 runtime loops.

## Tasks

- [x] **T01: Make Firebase sync history explicit** `est:1h30m`
  - Why: `user_sync_log` is the cleanest place to publish the historical boundary first; until it stops looking like a live model, the slice demo stays ambiguous.
  - Files: `backend-hormonia/alembic/versions/<new_revision>_publish_firebase_history_boundary.py`, `backend-hormonia/app/models/user_sync_log.py`, `backend-hormonia/app/services/firebase_user_sync_service.py`, `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py`, `backend-hormonia/tests/unit/test_firebase_sync_history.py`
  - Do: Add an honest revision that renames or backfills `user_sync_log` into an explicit Firebase history surface, update the ORM/service seam so writes are append-only historical data instead of a live domain contract, and keep both clean replay and existing-db upgrade compatible with the S01 operability rules.
  - Verify: `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_firebase_historical_boundary.py -k sync_history && pytest -q tests/unit/test_firebase_sync_history.py`
  - Done when: clean and existing databases both expose an explicit Firebase sync history surface, and the runtime writer still records history without reviving it as a canonical model.
- [x] **T02: Quarantine `firebase_uid` from canonical audit and API contracts** `est:2h`
  - Why: S02 fails if the official read/write surfaces still advertise `firebase_uid` as live, even if the data was technically preserved somewhere.
  - Files: `backend-hormonia/app/models/audit_log.py`, `backend-hormonia/app/services/audit_log.py`, `backend-hormonia/app/api/v2/routers/users.py`, `backend-hormonia/app/api/v2/routers/physicians/crud.py`, `backend-hormonia/app/schemas/v2/physicians.py`, `backend-hormonia/app/schemas/v2/admin.py`, `backend-hormonia/app/api/v2/routers/admin_extensions/utils.py`, `backend-hormonia/tests/api/v2/test_firebase_boundary_contracts.py`
  - Do: Keep `firebase_uid` only as preserved historical/read-only residue where explicitly chosen, align the legacy audit writer with the canonical null/sanitized behavior, remove `firebase_uid` from official user/admin/physician serializers, and avoid reclassifying still-live Firebase-era fields (`firebase_custom_claims`, `firebase_last_sign_in`, `firebase_display_name`, `firebase_photo_url`, `auth_provider`) as archival before S03.
  - Verify: `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_firebase_boundary_contracts.py -k 'audit or canonical_payload'`
  - Done when: canonical payloads no longer expose `firebase_uid`, canonical audit writes persist `firebase_uid=None`, and any preserved audit residue is accessible only through the chosen historical/read-only boundary.
- [x] **T03: Make the proof pack and fixtures tell the new truth** `est:1h30m`
  - Why: The slice is not real until tests and fixtures stop reconstructing Firebase residue as if it were part of the live contract.
  - Files: `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py`, `backend-hormonia/tests/api/v2/test_firebase_boundary_contracts.py`, `backend-hormonia/tests/conftest.py`, `backend-hormonia/tests/api/critical/conftest.py`, `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py`, `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py`
  - Do: Add focused migration/API/service coverage with named failures for sync history and canonical payloads, remove fixture defaults that recreate `audit_logs.firebase_uid` / `idx_audit_firebase_time` as live schema assumptions, and keep the existing `user_id`-first session tests green so Firebase identity survives only as quarantined fallback compat.
  - Verify: `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py tests/migrations/test_firebase_historical_boundary.py && pytest -q tests/unit/test_firebase_sync_history.py tests/services/audit/test_audit_service.py tests/api/v2/test_firebase_boundary_contracts.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py`
  - Done when: the harness stops lying about Firebase residue being live schema, and the full slice verification pack passes with failures localized to migration boundary, serialization boundary, or compat fallback.

## Files Likely Touched

- `backend-hormonia/alembic/versions/<new_revision>_publish_firebase_history_boundary.py`
- `backend-hormonia/app/models/user_sync_log.py`
- `backend-hormonia/app/services/firebase_user_sync_service.py`
- `backend-hormonia/app/models/audit_log.py`
- `backend-hormonia/app/services/audit_log.py`
- `backend-hormonia/app/api/v2/routers/users.py`
- `backend-hormonia/app/api/v2/routers/physicians/crud.py`
- `backend-hormonia/app/schemas/v2/physicians.py`
- `backend-hormonia/app/schemas/v2/admin.py`
- `backend-hormonia/app/api/v2/routers/admin_extensions/utils.py`
- `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py`
- `backend-hormonia/tests/api/v2/test_firebase_boundary_contracts.py`
