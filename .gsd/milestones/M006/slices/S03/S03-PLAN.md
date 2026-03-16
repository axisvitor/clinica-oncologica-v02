# S03: Purga final de bridges, tombstones, serviços mortos e narrativa operacional errada

**Goal:** Repo surfaces — dead backend services, frontend compat bridges, config defaults, deployment manifests, workflows, env templates, and docs — describe only the canonical cookie-first / WuzAPI runtime, or are classified as explicit historical archive.
**Demo:** `npm run build`, `npm run typecheck`, focused backend import proof, absence scans for deleted bridges/services, and the S01 residue guard all pass on the post-cleanup tree. `docs/repo/**` is behind an explicit `HISTORICAL-ARCHIVE.md` marker. Workflows, env templates, and Cloud Run manifests no longer advertise Firebase admin/hosting or `WHATSAPP_EVOLUTION_*` as live operator surfaces.

## Must-Haves

- Merge-marker files in active pytest/vitest collection paths are resolved or deleted so broad verification is trustworthy.
- Dead backend `SessionService`, `auth_legacy_firebase.py`, and their broken/dead test consumers are removed with proof.
- Root frontend compat bridges (`lib/flow-engine/*`, `lib/types/*`) and Firebase Hosting residue files (`firebase.json`, `.firebaserc`) are deleted with import-absence proof.
- `auth_session_contract.py` session TTL env var renamed from `FIREBASE_SESSION_TTL_SECONDS` to `SESSION_TTL_SECONDS` (Decision D42).
- `security.py` CORS defaults narrowed to stop advertising Firebase Hosting origins.
- Cloud Run manifests, env templates, and workflows updated to reflect canonical runtime (WuzAPI, cookie-session, no Firebase admin).
- `docs/backend/**`, `.github/CONTRIBUTING.md`, and `docs/compatibility/backward-compatibility-inventory.md` auth/session sections updated to canonical narrative.
- `backend-hormonia/docs/repo/**` classified behind `HISTORICAL-ARCHIVE.md` (Decision D43).
- `firebase_user_sync_service.py` and the Firebase API-key scan in `pre-commit-validation.yml` are NOT deleted.
- The root `/session/*` tombstone in `auth_session.py` is NOT deleted (intentional retirement contract).

## Proof Level

- This slice proves: operational
- Real runtime required: no
- Human/UAT required: no

## Verification

- `cd frontend-hormonia && npm run build && npm run typecheck` — frontend still compiles without the deleted bridges.
- `cd frontend-hormonia && npx vitest run tests/unit/import-boundaries/` — existing and new contract tests pass, asserting deleted compat files stay deleted.
- `cd backend-hormonia && python3 -c "from app.service_provider import ServiceProvider; print('backend imports clean')"` — backend still imports cleanly after dead service removal.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend` — S01 guard still green (proof-only anchors updated as needed for deleted files).
- Absence scan: `! test -f frontend-hormonia/lib/flow-engine/FlowEngine.ts && ! test -f frontend-hormonia/lib/types/flow.ts && ! test -f backend-hormonia/app/services/session_service.py && ! test -f backend-hormonia/app/dependencies/auth_legacy_firebase.py && echo "dead surfaces removed"` — deleted files stay deleted.
- `grep -r 'FIREBASE_SESSION_TTL_SECONDS' backend-hormonia/app/ | grep -v __pycache__ | wc -l` returns 0 — old TTL env name gone from app code.
- `grep -r 'WHATSAPP_EVOLUTION_' backend-hormonia/config/cloud-run/ | wc -l` returns 0 — dead WhatsApp env names gone from deployment manifests.
- `test -f backend-hormonia/docs/repo/HISTORICAL-ARCHIVE.md && echo "archive marker exists"` — historical boundary is explicit.
- `cd backend-hormonia && python3 -c "from app.service_provider import ServiceProvider; sp = ServiceProvider(); print(type(sp.session_service).__name__)"` — confirms `SimpleSessionService` is the wired session implementation (diagnostic: if this prints anything other than `SimpleSessionService`, the dead-cluster removal broke wiring).
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend 2>&1 | head -20` — inspectable proof-only boundary state after cleanup (diagnostic: shows which anchors remain and whether any are stale).

## Observability / Diagnostics

- Runtime signals: none (this slice is static cleanup, no runtime behavior change beyond the TTL rename).
- Inspection surfaces: `verify-runtime-residue.sh --report backend` for proof-only boundary state; absence-scan commands above.
- Failure visibility: merge-marker cleanup makes broad `pytest`/`vitest` collection trustworthy again — previously poisoned by conflict text.
- Redaction constraints: none.

## Integration Closure

- Upstream surfaces consumed: S01 honest live-vs-retired auth/session boundary; S02 canonical schema head (for docs/naming alignment where docs reference storage terms).
- New wiring introduced in this slice: `SESSION_TTL_SECONDS` env var replaces `FIREBASE_SESSION_TTL_SECONDS` in `auth_session_contract.py`.
- What remains before the milestone is truly usable end-to-end: S04 closeout pack combining absence scans, final-schema replay, and mounted stack proof.

## Tasks

- [x] **T01: Stabilize proof surfaces and delete dead backend auth/session cluster** `est:45m`
  - Why: Merge-marker files in active test collection paths make broad pytest/vitest noisy and untrustworthy. The dead `SessionService` and broken `auth_legacy_firebase.py` cluster are confirmed non-runtime by `ServiceProvider` wiring and S01 hard cut — remove them and their dead test consumers to unblock honest verification.
  - Files: `backend-hormonia/app/services/session_service.py`, `backend-hormonia/app/dependencies/auth_legacy_firebase.py`, `backend-hormonia/tests/unit/test_auth_dependency_module_split.py`, `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py`, `frontend-hormonia/tests/unit/types-validation.test.ts`, `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx`, `frontend-hormonia/src/hooks/__tests__/usePatients.test.ts`
  - Do: (1) Delete or fix merge-marker files in both backend and frontend test paths — delete files whose only remaining content is broken conflict text, fix files that contain useful test logic buried under markers. (2) Delete `session_service.py` and its dead test consumers (`test_auth_session_services_async.py`, the integration greenlet test's `SessionService` import site). (3) Delete `auth_legacy_firebase.py` and `test_auth_dependency_module_split.py`. (4) Update the S01 residue verifier proof-only anchors if any deleted file was an anchor. (5) Verify backend import chain and S01 guard.
  - Verify: `cd backend-hormonia && python3 -c "from app.service_provider import ServiceProvider; print('ok')"` + `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend` + `rg -l '^<<<<<<<|^=======$|^>>>>>>>' backend-hormonia/tests frontend-hormonia/tests frontend-hormonia/src --glob '!**/node_modules/**' | wc -l` returns 0.
  - Done when: dead backend cluster removed, merge markers gone from active test paths, S01 guard still green, backend imports clean.

- [x] **T02: Delete dead frontend compatibility barrels and Firebase Hosting residue** `est:30m`
  - Why: Root `lib/flow-engine/*` bridges and `lib/types/*` barrels have zero repo consumers and are not covered by build/typecheck inclusion. `firebase.json` and `.firebaserc` are Firebase Hosting residue with no in-repo usage. Deleting them with contract-test proof closes the frontend compat surface.
  - Files: `frontend-hormonia/lib/flow-engine/FlowEngine.ts`, `frontend-hormonia/lib/flow-engine/TemplateManager.ts`, `frontend-hormonia/lib/types/ai.ts`, `frontend-hormonia/lib/types/api.ts`, `frontend-hormonia/lib/types/flow.ts`, `frontend-hormonia/lib/types/flow-designer.ts`, `frontend-hormonia/lib/types/messages.ts`, `frontend-hormonia/lib/types/message-types.ts`, `frontend-hormonia/firebase.json`, `frontend-hormonia/.firebaserc`, `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts`
  - Do: (1) Final consumer scan for each file to confirm zero live imports. (2) Delete the bridge/barrel files and Firebase Hosting files. (3) Extend `dead-compat-cleanup.contract.test.ts` to assert the newly deleted files stay absent. (4) Run `npm run build`, `npm run typecheck`, and the import-boundaries test suite.
  - Verify: `cd frontend-hormonia && npm run build && npm run typecheck && npx vitest run tests/unit/import-boundaries/` all green + absence assertions for deleted files.
  - Done when: all listed compat bridges/barrels and Firebase Hosting files deleted, contract tests extended and green, build/typecheck green.

- [x] **T03: Republish operator-facing config defaults and deployment manifests** `est:45m`
  - Why: Code defaults and deployment manifests still advertise the Firebase/Evolution-era operator story even though the runtime has moved to cookie-session + WuzAPI. The story is dishonest if only docs are cleaned but `security.py` still hardcodes Firebase Hosting CORS origins, `auth_session_contract.py` still falls back to `FIREBASE_SESSION_TTL_SECONDS`, and Cloud Run manifests still inject `WHATSAPP_EVOLUTION_*`.
  - Files: `backend-hormonia/app/dependencies/auth_session_contract.py`, `backend-hormonia/app/config/settings/security.py`, `backend-hormonia/config/cloud-run/service-api.yaml`, `backend-hormonia/config/cloud-run/service-whatsapp-worker.yaml`, `backend-hormonia/.env.example`, `backend-hormonia/.env.production.example`, `backend-hormonia/.env.production.template`, `backend-hormonia/.env.quiz.example`
  - Do: (1) Rename `FIREBASE_SESSION_TTL_SECONDS` → `SESSION_TTL_SECONDS` in `auth_session_contract.py` (Decision D42). (2) Narrow `security.py` CORS defaults — remove `clinica-oncologica-hosting.web.app` / `firebaseapp.com` hardcoded origins from `get_cors_origins()` and the default list. (3) Update Cloud Run manifests: drop Firebase admin env vars and Firebase-hosted frontend URLs, rename `WHATSAPP_EVOLUTION_*` → `WHATSAPP_WUZAPI_*`. (4) Update env templates: remove Firebase admin blocks, update WhatsApp var names, update any `web.app` URLs. (5) Verify backend imports, grep for old names, confirm no runtime breakage.
  - Verify: `grep -r 'FIREBASE_SESSION_TTL_SECONDS' backend-hormonia/app/ --include='*.py' | grep -v __pycache__ | wc -l` = 0 + `grep -r 'WHATSAPP_EVOLUTION_' backend-hormonia/config/cloud-run/ | wc -l` = 0 + `cd backend-hormonia && python3 -c "from app.dependencies.auth_session_contract import get_session_config; print('ok')"`.
  - Done when: session TTL renamed, CORS narrowed, manifests and env templates reflect canonical runtime, backend still imports cleanly.

- [x] **T04: Fix workflow and documentation narrative drift, classify historical archive** `est:45m`
  - Why: Workflows, docs, and the compatibility inventory still describe Firebase Admin / `X-Session-ID` / session-as-Bearer / Evolution-era WhatsApp as current behavior. `docs/repo/**` is a large cluster of generated reports that still advertise Firebase login as live. Cleaning individual reports is fragile — an explicit archive marker (Decision D43) is more honest.
  - Files: `.github/workflows/rls-api-tests.yml`, `.github/workflows/postman-tests.yml`, `docs/backend/architecture/overview.md`, `docs/backend/guides/environment-validation.md`, `.github/CONTRIBUTING.md`, `docs/compatibility/backward-compatibility-inventory.md`, `backend-hormonia/docs/repo/HISTORICAL-ARCHIVE.md`
  - Do: (1) Update `rls-api-tests.yml` and `postman-tests.yml` — remove Firebase admin secret injection and stale env names (`JWT_SECRET`, `CSRF_SECRET_KEY`, etc.), update narrative to cookie-session auth. Keep the pre-commit Firebase API-key scan untouched. (2) Update `docs/backend/architecture/overview.md` and `docs/backend/guides/environment-validation.md` — replace Firebase Admin SDK narrative with canonical auth description. (3) Update `.github/CONTRIBUTING.md` — remove Firebase/Supabase from deployment variable list. (4) Update `docs/compatibility/backward-compatibility-inventory.md` — mark auth/session fallback entries as retired, keep non-auth entries that may still be valid. (5) Create `backend-hormonia/docs/repo/HISTORICAL-ARCHIVE.md` with explicit boundary marker explaining these are generated snapshots from prior milestone phases and do not describe current system behavior.
  - Verify: `test -f backend-hormonia/docs/repo/HISTORICAL-ARCHIVE.md` + `grep -l 'Firebase Admin' .github/workflows/rls-api-tests.yml .github/workflows/postman-tests.yml 2>/dev/null | wc -l` = 0 + `grep -c 'Firebase Admin SDK' docs/backend/architecture/overview.md` = 0.
  - Done when: workflows describe canonical runtime, docs describe canonical auth, compatibility inventory auth sections retired, `docs/repo/**` behind explicit archive boundary.

## Files Likely Touched

- `backend-hormonia/app/services/session_service.py` (delete)
- `backend-hormonia/app/dependencies/auth_legacy_firebase.py` (delete)
- `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` (delete)
- `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py` (fix or delete)
- `backend-hormonia/tests/unit/services/test_auth_session_services_async.py` (modify/delete dead imports)
- `frontend-hormonia/tests/unit/types-validation.test.ts` (fix or delete)
- `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx` (fix or delete)
- `frontend-hormonia/src/hooks/__tests__/usePatients.test.ts` (fix or delete)
- `frontend-hormonia/lib/flow-engine/FlowEngine.ts` (delete)
- `frontend-hormonia/lib/flow-engine/TemplateManager.ts` (delete)
- `frontend-hormonia/lib/types/*.ts` (delete)
- `frontend-hormonia/firebase.json` (delete)
- `frontend-hormonia/.firebaserc` (delete)
- `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` (extend)
- `backend-hormonia/app/dependencies/auth_session_contract.py` (rename TTL env var)
- `backend-hormonia/app/config/settings/security.py` (narrow CORS defaults)
- `backend-hormonia/config/cloud-run/service-api.yaml` (update)
- `backend-hormonia/config/cloud-run/service-whatsapp-worker.yaml` (update)
- `backend-hormonia/.env.example` (update)
- `backend-hormonia/.env.production.example` (update)
- `backend-hormonia/.env.production.template` (update)
- `backend-hormonia/.env.quiz.example` (update)
- `.github/workflows/rls-api-tests.yml` (update)
- `.github/workflows/postman-tests.yml` (update)
- `docs/backend/architecture/overview.md` (update)
- `docs/backend/guides/environment-validation.md` (update)
- `.github/CONTRIBUTING.md` (update)
- `docs/compatibility/backward-compatibility-inventory.md` (update auth sections)
- `backend-hormonia/docs/repo/HISTORICAL-ARCHIVE.md` (create)
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` (update anchors if needed)
