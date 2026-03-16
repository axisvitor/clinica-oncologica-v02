---
id: S03
parent: M006
milestone: M006
provides:
  - dead backend auth/session cluster removed (SessionService, auth_legacy_firebase, dead test consumers)
  - merge-marker conflicts resolved in 5 active test collection files
  - dead frontend compat bridges/barrels and Firebase Hosting residue deleted with contract-test proof
  - session TTL env var renamed FIREBASE_SESSION_TTL_SECONDS → SESSION_TTL_SECONDS (D42)
  - Firebase Hosting CORS origins removed from security.py defaults
  - Cloud Run manifests free of Firebase admin vars and WHATSAPP_EVOLUTION_ naming
  - env templates aligned to canonical WuzAPI/cookie-session runtime
  - workflows and docs updated to canonical auth narrative
  - backward-compatibility inventory auth/session entries marked RETIRED
  - docs/repo/** classified behind HISTORICAL-ARCHIVE.md (D43)
requires:
  - slice: S01
    provides: honest live-vs-retired auth/session boundary enabling dead/historical classification
  - slice: S02
    provides: canonical schema head naming for docs/examples alignment
affects:
  - S04
key_files:
  - backend-hormonia/app/services/session_service.py (deleted)
  - backend-hormonia/app/dependencies/auth_legacy_firebase.py (deleted)
  - backend-hormonia/app/dependencies/auth_session_contract.py (SESSION_TTL_SECONDS rename)
  - backend-hormonia/app/config/settings/security.py (CORS narrowed, TTL field renamed)
  - backend-hormonia/config/cloud-run/service-api.yaml (Firebase admin + Evolution vars removed)
  - backend-hormonia/config/cloud-run/service-whatsapp-worker.yaml (Firebase admin + Evolution vars removed)
  - frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts (extended)
  - backend-hormonia/docs/repo/HISTORICAL-ARCHIVE.md (created)
  - docs/backend/architecture/overview.md (canonical auth narrative)
  - docs/compatibility/backward-compatibility-inventory.md (auth entries RETIRED)
key_decisions:
  - D42 — SESSION_TTL_SECONDS replaces FIREBASE_SESSION_TTL_SECONDS as canonical env var
  - D43 — docs/repo/** classified behind HISTORICAL-ARCHIVE.md boundary marker
  - Kept FIREBASE_ADMIN_* in env templates (still consumed by live security.py and firebase_user_sync_service.py) — removed only from Cloud Run manifests
  - Kept test_auth_dependency_override_contract.py (useful auth contract tests) — resolved merge conflicts rather than deleting
patterns_established:
  - none
observability_surfaces:
  - verify-runtime-residue.sh --check backend (S01 guard green post-cleanup)
  - dead-compat-cleanup.contract.test.ts (6 assertions fail loudly if deleted files reappear)
  - absence scan commands for all deleted backend/frontend files
drill_down_paths:
  - .gsd/milestones/M006/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M006/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M006/slices/S03/tasks/T03-SUMMARY.md
  - .gsd/milestones/M006/slices/S03/tasks/T04-SUMMARY.md
duration: 70m
verification_result: passed
completed_at: 2026-03-15
---

# S03: Purga final de bridges, tombstones, serviços mortos e narrativa operacional errada

**Removed dead backend auth/session cluster, 10 dead frontend bridge/barrel files, Firebase Hosting residue, and aligned config defaults, deployment manifests, workflows, and docs to the canonical cookie-first/WuzAPI runtime — with build/typecheck/import-boundaries/absence/residue-guard proof all green.**

## What Happened

**T01 — Stabilize proof surfaces and delete dead backend cluster.** Resolved merge-marker conflicts in 5 active test collection files (3 frontend, 2 backend) — all kept HEAD/canonical version. Deleted `session_service.py` (dead `SessionService` — `SimpleSessionService` is the live wired implementation), `auth_legacy_firebase.py` (dead legacy Firebase bearer auth with 4 layers of merge conflicts), and `test_auth_dependency_module_split.py` (dead consumer tests). Cleaned `SessionService` imports from 2 surviving test files. Updated S01 residue allowlist to remove stale `auth_legacy_firebase.py` exclude.

**T02 — Delete dead frontend compat bridges and Firebase Hosting residue.** Consumer scan confirmed zero live imports for all 10 target files. Deleted `lib/flow-engine/FlowEngine.ts`, `lib/flow-engine/TemplateManager.ts`, 6 `lib/types/*.ts` barrels, `firebase.json`, and `.firebaserc`. Extended `dead-compat-cleanup.contract.test.ts` with 2 new assertions (10 files + 2 directories stay absent). Build (4758 modules), typecheck, and import-boundaries suite (6/6 tests) all green.

**T03 — Republish config defaults and deployment manifests.** Renamed `FIREBASE_SESSION_TTL_SECONDS` → `SESSION_TTL_SECONDS` in `auth_session_contract.py` and `security.py` (D42). Removed hardcoded Firebase Hosting CORS origins from `security.py` — production CORS now depends entirely on operator-supplied env vars. Cleaned both Cloud Run manifests of `FIREBASE_ADMIN_*` and renamed `WHATSAPP_EVOLUTION_*` → `WHATSAPP_WUZAPI_*`. Updated 4 env templates with canonical WuzAPI naming and placeholder URLs. Kept `FIREBASE_ADMIN_*` in env templates since it's still consumed by live code (`firebase_user_sync_service.py`).

**T04 — Fix workflow and documentation narrative drift.** Updated `rls-api-tests.yml` (removed Supabase + Firebase admin secrets) and `postman-tests.yml` (replaced stale env generation with canonical names). Updated architecture overview, environment validation guide, and CONTRIBUTING.md to describe cookie-session auth instead of Firebase Admin SDK. Marked 3 backend auth/session shim entries + auth-mode-transition row as RETIRED in the backward-compatibility inventory. Created `backend-hormonia/docs/repo/HISTORICAL-ARCHIVE.md` (D43) classifying the generated report directory as milestone-phase snapshots.

## Verification

| Check | Result |
|-------|--------|
| Dead surfaces absent (session_service, auth_legacy_firebase, frontend bridges, firebase.json) | ✅ |
| `FIREBASE_SESSION_TTL_SECONDS` in app code | 0 hits ✅ |
| `WHATSAPP_EVOLUTION_` in Cloud Run manifests | 0 hits ✅ |
| `HISTORICAL-ARCHIVE.md` exists | ✅ |
| Backend imports clean (`from app.service_provider import ServiceProvider`) | ✅ |
| S01 residue guard (`verify-runtime-residue.sh --check backend`) | OK ✅ |
| Frontend import-boundaries contract tests (6/6) | ✅ |
| Merge markers in active test paths | 0 remaining ✅ |
| Firebase Admin in workflow files | 0 hits ✅ |
| Firebase Admin SDK in architecture overview | 0 hits ✅ |

## Requirements Advanced

- R052 — S03 removed dead backend services, dead frontend bridges/barrels, Firebase Hosting residue, and aligned operator-facing config/manifests/workflows/docs to canonical runtime. The remaining gap is S04's closeout pack combining absence scans, final-schema replay, and mounted stack proof.

## Requirements Validated

- none (R052 stays active until S04 closeout pack proves the assembled post-purga state)

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- **Kept `FIREBASE_ADMIN_*` in env templates:** Plan said "remove Firebase admin blocks" from env templates, but `FIREBASE_ADMIN_*` vars are still consumed by live code (`security.py`, `firebase_user_sync_service.py`). Removed only from Cloud Run manifests.
- **Kept `test_auth_dependency_override_contract.py`:** Plan listed it as potential delete, but it contains useful auth contract tests independent of the deleted modules — resolved merge conflicts instead.
- **`ServiceProvider()` diagnostic check cannot run without DB:** The slice plan included `ServiceProvider(); print(type(sp.session_service).__name__)` but `ServiceProvider()` requires a `db` argument. Import-level check passes, confirming no import breakage.

## Known Limitations

- 6 pre-existing TypeScript errors in `tests/e2e/playwright.config.e2e.ts` (TS4111 index signature access) — present before S03, unrelated to cleanup.
- `WHATSAPP_WUZAPI_TOKEN` startup validation fails when token is unset — intentional design (CFG-02), not a regression.
- CORS in production now depends entirely on operator-supplied env vars — no hardcoded fallbacks remain.
- `FIREBASE_ADMIN_*` env vars remain in templates because live code still consumes them; full removal requires deleting `firebase_user_sync_service.py` (explicitly out of scope per S03 plan).

## Follow-ups

- S04 closeout pack must combine the absence scans, final-schema replay, and mounted stack proof to close R052.
- The pre-existing typecheck errors in `playwright.config.e2e.ts` should be fixed in a future pass (trivial `process.env['CI']` syntax).

## Files Created/Modified

- `backend-hormonia/app/services/session_service.py` — deleted (dead SessionService)
- `backend-hormonia/app/dependencies/auth_legacy_firebase.py` — deleted (dead legacy Firebase bearer auth)
- `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` — deleted (dead test consumers)
- `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py` — resolved merge conflicts
- `backend-hormonia/tests/unit/services/test_auth_session_services_async.py` — removed SessionService tests
- `backend-hormonia/tests/integration/test_phase23_service_async_missinggreenlet.py` — removed SessionService usage
- `frontend-hormonia/tests/unit/types-validation.test.ts` — resolved merge conflicts
- `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx` — resolved merge conflicts
- `frontend-hormonia/src/hooks/__tests__/usePatients.test.ts` — resolved merge conflicts
- `frontend-hormonia/lib/flow-engine/FlowEngine.ts` — deleted (dead bridge)
- `frontend-hormonia/lib/flow-engine/TemplateManager.ts` — deleted (dead bridge)
- `frontend-hormonia/lib/types/ai.ts` — deleted (dead barrel)
- `frontend-hormonia/lib/types/api.ts` — deleted (dead barrel)
- `frontend-hormonia/lib/types/flow.ts` — deleted (dead barrel)
- `frontend-hormonia/lib/types/flow-designer.ts` — deleted (dead barrel)
- `frontend-hormonia/lib/types/messages.ts` — deleted (dead barrel)
- `frontend-hormonia/lib/types/message-types.ts` — deleted (dead barrel)
- `frontend-hormonia/firebase.json` — deleted (Firebase Hosting residue)
- `frontend-hormonia/.firebaserc` — deleted (Firebase Hosting residue)
- `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` — extended with 2 new absence assertions
- `backend-hormonia/app/dependencies/auth_session_contract.py` — SESSION_TTL_SECONDS rename
- `backend-hormonia/app/config/settings/security.py` — CORS narrowed, TTL field renamed
- `backend-hormonia/config/cloud-run/service-api.yaml` — Firebase admin + Evolution vars removed
- `backend-hormonia/config/cloud-run/service-whatsapp-worker.yaml` — Firebase admin + Evolution vars removed
- `backend-hormonia/.env` — SESSION_TTL_SECONDS rename
- `backend-hormonia/.env.example` — canonical CORS/TTL
- `backend-hormonia/.env.production.example` — canonical CORS URLs
- `backend-hormonia/.env.production.template` — canonical WuzAPI vars, CORS URLs
- `backend-hormonia/.env.quiz.example` — canonical CORS URLs
- `.github/workflows/rls-api-tests.yml` — removed Firebase/Supabase secrets, canonical auth narrative
- `.github/workflows/postman-tests.yml` — canonical env names
- `docs/backend/architecture/overview.md` — canonical auth/WuzAPI narrative
- `docs/backend/guides/environment-validation.md` — Firebase Admin reframed as optional legacy
- `.github/CONTRIBUTING.md` — canonical deployment variables
- `docs/compatibility/backward-compatibility-inventory.md` — auth/session entries RETIRED
- `backend-hormonia/docs/repo/HISTORICAL-ARCHIVE.md` — created archive boundary marker (D43)
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — stale exclude removed

## Forward Intelligence

### What the next slice should know
- S03 did not delete `firebase_user_sync_service.py` or the pre-commit Firebase API-key scan — both are explicitly preserved and still live.
- `FIREBASE_ADMIN_*` env vars remain in `.env.example` and production templates because `firebase_user_sync_service.py` and `security.py` still consume them. S04 should not treat their presence as residue.
- The `/session/*` tombstone in `auth_session.py` is intentionally preserved — it's the explicit retirement contract, not dead code.
- Cloud Run manifests now use `REPLACE_WITH_*` placeholders for WuzAPI and admin URLs — deployment will fail clearly if not replaced.

### What's fragile
- CORS in production has no hardcoded fallbacks — if `CORS_FRONTEND_URL` and `CORS_ALLOWED_ORIGINS` are unset, no Firebase Hosting domains will auto-inject. This is intentional but could surprise an operator doing first deploy.
- The `ServiceProvider()` requires a `db` argument, so the slice plan's diagnostic check for `SimpleSessionService` wiring cannot run without a database connection. Import-level checks are the practical alternative.

### Authoritative diagnostics
- `verify-runtime-residue.sh --check backend` — proof-only boundary state confirms no anchor drift after all deletions.
- `dead-compat-cleanup.contract.test.ts` — 6 assertions cover all deleted frontend files/directories; any reintroduction fails the test with a descriptive message.
- `grep -r 'FIREBASE_SESSION_TTL_SECONDS' backend-hormonia/` — should return 0; any hit means the old env name leaked back.

### What assumptions changed
- Plan assumed `test_auth_dependency_override_contract.py` might be deletable — it turned out to contain useful auth contract tests independent of the dead modules, so merge conflicts were resolved instead.
- Plan assumed `FIREBASE_ADMIN_*` should be removed from env templates — live code still consumes these vars, so only Cloud Run manifest removal was safe.
