# M015 DB Seam Evidence Summary

- Command: `./scripts/security/verify-m015-runtime-security.sh --seam db`
- Probe command: `python /m015-runtime/db_seam.py`
- Correlation ID: `m015-20260514T054818Z-1191750`
- Started: `2026-05-14T05:49:22Z`
- Completed: `2026-05-14T05:49:27Z`
- Redaction: `passed`
- Teardown: `complete`

## Migration Proof

- Command: `python -m alembic -c alembic.ini upgrade head`
- Exit code: `0`
- Duration: `4567 ms`
- Expected heads: `m013_s04_upload_deleted_at`
- Current revisions: `m013_s04_upload_deleted_at`
- Ran as role: `hormonia_app`
- Superuser bypass: `False`

## FastAPI Runtime Proof

- `/health` status: `healthy`
- `/health/ready` status: `ready`
- Database dependency: `healthy`
- Runtime DB TLS posture: `FastAPI readiness used the application DATABASE_URL configured for verify-full TLS; DSN not persisted.`

## TLS Proof

- PostgreSQL SSL setting: `on`
- Current connection SSL: `passed`
- Protocol: `TLSv1.3`
- Cipher: `TLS_AES_256_GCM_SHA384`
- Evidence scope: `current_probe_backend_pid`

## RLS Catalog Proof

- `patients`: exists=True, status=present, rls=True, force=True, public_revoked=True, policies=rls_patients_current_user_all
- `messages`: exists=True, status=present, rls=True, force=True, public_revoked=True, policies=rls_messages_current_user_all
- `quiz_sessions`: exists=True, status=present, rls=True, force=True, public_revoked=True, policies=rls_quiz_sessions_current_user_all
- `quiz_responses`: exists=True, status=present, rls=True, force=True, public_revoked=True, policies=rls_quiz_responses_current_user_all
- `lgpd_audit_logs`: exists=True, status=present, rls=True, force=True, public_revoked=True, policies=rls_lgpd_audit_logs_current_user_all
- `lgpd_data_access_requests`: exists=True, status=present, rls=True, force=True, public_revoked=True, policies=rls_lgpd_data_access_requests_current_user_all
- `consents`: exists=False, status=not_present_in_current_alembic_head, rls=None, force=None, public_revoked=None, policies=

## RLS Allow/Deny Proof

- App role insert: `allowed`
- Synthetic patient evidence: `ba97303410e87c2f19f4034509fa761218cca53a2d9237bf8c4c7fb2c45ce576`
- Denied role: `m015_rls_denied`
- Denied select: `blocked_by_rls` with visible rows `0`
- Denied insert: `blocked_by_rls` with SQLSTATE `42501`

## Service Versions

- PostgreSQL image: `postgres:16-alpine`
- Dragonfly image: `docker.dragonflydb.io/dragonflydb/dragonfly:latest`
- Backend image context: `backend-hormonia/Dockerfile`
- PostgreSQL server: `PostgreSQL 16.13`
- FastAPI app version: `1.0.0`
- Python runtime: `3.13.12`

## Non-goals

- S02 cache/Redis runtime abuse seam is not proven by this DB seam.
- S03 provider/webhook runtime seam is not proven by this DB seam.
- S04 file/artifact runtime seam is not proven by this DB seam.
- S05 cross-seam evidence aggregation is not proven by this DB seam.
