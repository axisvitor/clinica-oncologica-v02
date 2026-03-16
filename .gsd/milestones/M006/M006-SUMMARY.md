---
id: M006
provides:
  - Dead backend auth/session cluster removed (SessionService, auth_legacy_firebase)
  - Firebase-prefixed users columns dropped from canonical schema head
  - Dead frontend compat bridges/barrels and Firebase Hosting residue deleted
  - Config defaults, Cloud Run manifests, workflows, docs aligned to canonical cookie-first/WuzAPI runtime
  - Backend staff auth resolves only through canonical cookie-session contract
  - Replayable closeout proof (M006-VERIFY.json) with 10 phases all green
key_files:
  - .gsd/milestones/M006/M006-VERIFY.json
  - backend-hormonia/alembic/versions/m006_s02_t03_drop_users_firebase_residue.py
  - backend-hormonia/app/dependencies/auth_dependencies.py
  - backend-hormonia/app/dependencies/auth_session_cache.py
  - backend-hormonia/app/models/user.py
  - backend-hormonia/app/api/v2/routers/admin/activity.py
  - backend-hormonia/app/api/v2/routers/admin/stats.py
  - backend-hormonia/app/config/settings/security.py
  - frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts
  - .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh
  - .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh
key_decisions:
  - D42 — SESSION_TTL_SECONDS replaces FIREBASE_SESSION_TTL_SECONDS as canonical env var
  - D43 — docs/repo/** classified behind HISTORICAL-ARCHIVE.md boundary marker
  - Live staff session restore accepts only canonical user_id/id; Firebase-only session payloads fail closed
  - Admin audit/activity reads normalize dirty historical uppercase event labels at read surface instead of new audit-schema migration
  - Reset logger.disabled flag in test rather than changing alembic env.py or production code (caplog blocker fix)
  - Kept FIREBASE_ADMIN_* in env templates (still consumed by live security.py and firebase_user_sync_service.py)
duration: multi-slice milestone across 4 slices (S01-S04)
verification_result: passed
completed_at: 2026-03-15
---

# M006: Purga Final de Código Morto e Resíduo Legado

**Closed the M004→M006 convergence arc by removing all in-scope dead code, Firebase schema residue, legacy bridges, and operational narrative drift — with a 10-phase replayable proof showing the post-purge canonical state is honest and green.**

## What Happened

### S01 — Fechar a costura auth/session legado ainda "viva"

Retired the lazy bearer/Firebase fallback from `get_current_user()` so backend staff auth resolves only through the canonical cookie-session contract. Legacy transport (bearer, `X-Session-ID`, query `session_id`) is still observed for stable rejection diagnostics, never acceptance. Republished the S01 residue guard with zero approved backend auth/session hits and explicit proof-only boundaries.

### S02 — Remover o resíduo de schema que ainda prende o runtime ao passado

Dropped `users.firebase_uid`, remaining Firebase-prefixed `users` columns, `last_firebase_sync`, and `ix_users_firebase_uid` via `m006_s02_t03_drop_users_firebase_residue`. Republished auth/session/cache resolvers, user profile, physician CRUD, and admin serializers onto canonical `id`/`user_id`/`last_login`/`display_name` storage. Fixed admin audit/activity read surfaces to normalize dirty historical uppercase `audit_logs.event_type` labels instead of 500ing.

### S03 — Purga final de bridges, tombstones, serviços mortos e narrativa operacional errada

Deleted `SessionService`, `auth_legacy_firebase.py`, 10 dead frontend bridge/barrel files, `firebase.json`, and `.firebaserc`. Renamed `FIREBASE_SESSION_TTL_SECONDS` → `SESSION_TTL_SECONDS` (D42). Cleaned Cloud Run manifests of `FIREBASE_ADMIN_*` and `WHATSAPP_EVOLUTION_*`. Updated workflows, architecture docs, and backward-compatibility inventory to canonical auth narrative. Created `HISTORICAL-ARCHIVE.md` (D43) for docs/repo classifying.

### S04 — Publicar o closeout final e provar o sistema montado pós-purga

T01 fixed the caplog blocker (`test_get_current_user_from_session_db_timeout_logs_error` under Postgres) by resetting `logger.disabled` set by alembic's `fileConfig(disable_existing_loggers=True)`. T02 replayed the full proof topology: S01 residue guards (backend+frontend), S02 focused backend packs (91 tests), S02 schema convergence under Postgres, S03 absence/build/import-boundary scans, and final-schema proof `--fresh`/`--existing` — all 10 phases passed.

## Verification

| Phase | Status | Tests/Checks |
|-------|--------|-------------|
| S01 residue guard backend | ✅ passed | 0 approved, proof-only documented |
| S01 residue guard frontend | ✅ passed | 0 approved, 0 proof-only |
| S02 auth/session pack | ✅ passed | 25 tests |
| S02 profile/admin pack | ✅ passed | 66 tests |
| S02 schema convergence (Postgres) | ✅ passed | 1 test |
| S03 absence scans | ✅ passed | 5 checks (2 files absent, 3 grep zero-hit) |
| S03 frontend import-boundary | ✅ passed | 4 tests |
| S03 frontend build | ✅ passed | 4758 modules |
| Final-schema proof --fresh | ✅ passed | canonical head + S02 packs + mounted backend + live auth probe |
| Final-schema proof --existing | ✅ passed | existing upgrade + S02 packs + mounted backend + live auth probe |

Machine-readable proof: `.gsd/milestones/M006/M006-VERIFY.json` — all 10 phases report `status: "passed"`.

## Requirements Validated

- **R052** — Código morto e compatibilidades restantes são removidos com prova. Validated by the combined M006 proof: dead backend services/auth cluster removed, Firebase-prefixed users schema dropped, dead frontend bridges/barrels deleted, config/manifests/workflows/docs aligned to canonical runtime, and the assembled post-purge state proven green by residue guards, focused test packs, absence scans, schema convergence under Postgres, and final-schema proof with mounted backend replay.

## Known Limitations

- 6 pre-existing TS4111 errors in `tests/e2e/playwright.config.e2e.ts` — present before M006, unrelated to cleanup, documented as accepted non-blocking diagnostic.
- `FIREBASE_ADMIN_*` env vars remain in env templates because `firebase_user_sync_service.py` and `security.py` still consume them — removal requires deleting that service (out of scope).
- CORS in production has no hardcoded fallbacks — depends entirely on operator-supplied env vars (intentional post-S03 design).
- `firebase_sync_history` table and `audit_logs.firebase_uid` column preserved as explicit historical boundaries (M005 decision).
- The `/session/*` tombstone in `auth_session.py` is intentionally preserved as explicit retirement contract.

## Forward Intelligence

### What future maintainers should know
- The M004→M006 convergence arc is closed. The repository's auth/session, schema, and operational surfaces describe only the canonical cookie-first/WuzAPI runtime.
- `FIREBASE_ADMIN_*` vars are the last live Firebase dependency — they feed `firebase_user_sync_service.py`. Removing that service would complete the full Firebase exit.
- The S01 residue guard (`verify-runtime-residue.sh`) is the primary regression surface — rerun it to detect auth/session drift.
- `dead-compat-cleanup.contract.test.ts` guards against reintroduction of deleted frontend files.
- `run-final-schema-proof.sh --fresh|--existing` is the most complete assembled proof — it covers migration, focused packs, mounted backend, and live auth probe.

### What's fragile
- `test_get_current_user_from_session_db_timeout_logs_error` requires the `logger.disabled` reset in its setup; if alembic's `fileConfig` runs again (e.g. fixture change), the fix needs to re-apply.
- Admin audit/activity reads normalize dirty historical uppercase event labels at the read surface — if new event types are added with unexpected casing, the normalization logic in `admin/utils.py` needs updating.

### Authoritative diagnostics
- `.gsd/milestones/M006/M006-VERIFY.json` — top-level proof record with all phase commands and diagnostic pointers.
- `/tmp/gsd-m005-s04-final-schema-proof/*/status.json` — per-history final-schema proof status.
- `verify-runtime-residue.sh --report backend|frontend` — detailed residue inventory.

## Files Created/Modified (milestone scope)

### S01
- `backend-hormonia/app/dependencies/auth_dependencies.py` — cookie-only staff auth resolution
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` — canonical admin auth
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — zero-approved guard

### S02
- `backend-hormonia/alembic/versions/m006_s02_t03_drop_users_firebase_residue.py` — schema drop migration
- `backend-hormonia/app/models/user.py` — removed Firebase-prefixed ORM fields
- `backend-hormonia/app/dependencies/auth_session_cache.py` — canonical-only session hydration
- `backend-hormonia/app/api/v2/routers/physicians/crud.py` — canonical physician reads
- `backend-hormonia/app/api/v2/routers/admin/utils.py` — audit label normalization
- `backend-hormonia/app/api/v2/routers/admin/activity.py` — safe audit listing
- `backend-hormonia/app/api/v2/routers/admin/stats.py` — safe activity stats
- `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py` — post-drop head contract

### S03
- `backend-hormonia/app/services/session_service.py` — deleted
- `backend-hormonia/app/dependencies/auth_legacy_firebase.py` — deleted
- `frontend-hormonia/lib/flow-engine/FlowEngine.ts` — deleted
- `frontend-hormonia/lib/flow-engine/TemplateManager.ts` — deleted
- `frontend-hormonia/lib/types/*.ts` (6 files) — deleted
- `frontend-hormonia/firebase.json`, `.firebaserc` — deleted
- `backend-hormonia/app/dependencies/auth_session_contract.py` — SESSION_TTL_SECONDS rename
- `backend-hormonia/app/config/settings/security.py` — CORS narrowed, TTL renamed
- `backend-hormonia/config/cloud-run/service-api.yaml` — Firebase/Evolution vars removed
- `backend-hormonia/config/cloud-run/service-whatsapp-worker.yaml` — Firebase/Evolution vars removed
- `.github/workflows/rls-api-tests.yml` — canonical auth narrative
- `.github/workflows/postman-tests.yml` — canonical env names
- `docs/backend/architecture/overview.md` — canonical auth/WuzAPI narrative
- `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` — extended

### S04
- `backend-hormonia/tests/api/v2/test_auth_timeout.py` — caplog blocker fix
- `.gsd/milestones/M006/M006-VERIFY.json` — closeout proof
- `.gsd/milestones/M006/M006-SUMMARY.md` — this file
