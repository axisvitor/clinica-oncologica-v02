# M006/S03 — Research

**Date:** 2026-03-15

## Summary

S03 supports **R052** and should stay tightly focused on evidence-backed repo-surface cleanup after S01 and S02: remove dead bridges and dead backend service clusters, then republish workflows, env templates, deployment manifests, and operator docs so they describe the canonical cookie-first runtime instead of Firebase/header/bearer-era behavior. Repo evidence already supports a strong first deletion wave. `backend-hormonia/app/services/session_service.py` is not on the canonical runtime path because `ServiceProvider.session_service` already returns `SimpleSessionService`; `backend-hormonia/app/dependencies/auth_legacy_firebase.py` is no longer a live seam after S01 and now survives mainly as a broken compatibility island; `frontend-hormonia/lib/flow-engine/FlowEngine.ts` and `TemplateManager.ts` are pure root-level re-export bridges; and the root `frontend-hormonia/lib/types/*` barrels look even weaker than expected, with zero repo consumers and one file (`lib/types/flow.ts`) apparently re-exporting from non-existent relative targets.

The biggest surprise is that S03 is blocked as much by **broken proof surfaces** as by stale code. Active backend/frontend test files still contain unresolved merge markers: `backend-hormonia/app/dependencies/auth_legacy_firebase.py`, `backend-hormonia/tests/unit/test_auth_dependency_module_split.py`, `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py`, `frontend-hormonia/tests/unit/types-validation.test.ts`, `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx`, and `frontend-hormonia/src/hooks/__tests__/usePatients.test.ts`. Because `backend-hormonia/pyproject.toml` collects from `tests/` and frontend Vitest includes both `src/**/*.{test,spec}` and `tests/**/*.{test,spec}`, broad pytest/vitest runs are currently noisy for repo damage, not trustworthy proof.

The other surprise is that the operational story drift is not limited to markdown. `backend-hormonia/app/config/settings/security.py` still hardcodes Firebase Hosting origins into CORS defaults and `get_cors_origins()`, `backend-hormonia/app/dependencies/auth_session_contract.py` still falls back to `FIREBASE_SESSION_TTL_SECONDS`, and active Cloud Run manifests still export `WHATSAPP_EVOLUTION_*` while the runtime now validates `WHATSAPP_WUZAPI_*` in `backend-hormonia/app/config/settings/integrations.py`. That means S03 cannot honestly “clean docs” by deleting Firebase names alone; some small config/manifests republishes are likely required so the shipped operator/config story matches the canonical runtime.

## Recommendation

Take S03 in six passes:

1. **Stabilize proof surfaces before trusting verification.**  
   Resolve or delete merge-marker files that sit inside active pytest/vitest collection paths. Otherwise broad verification will fail for leftover conflict text, not because the slice cleanup is wrong.

2. **Delete the dead backend auth/session cluster first.**  
   Remove `backend-hormonia/app/services/session_service.py` and its direct dead-test consumers after preserving any still-useful assertions elsewhere. Treat `auth_legacy_firebase.py` plus its split-module tests as one dead/broken cluster: it is no longer the live seam and only broken tests still reach for it.

3. **Delete root frontend compatibility barrels with exact import proof.**  
   The clearest first cuts are `frontend-hormonia/lib/flow-engine/FlowEngine.ts`, `frontend-hormonia/lib/flow-engine/TemplateManager.ts`, and the root `frontend-hormonia/lib/types/*` barrels. Prioritize `frontend-hormonia/lib/types/flow.ts`: it appears internally broken in the current repo layout and has no external repo consumers. `lib/types/ai.ts`, `api.ts`, `flow-designer.ts`, `messages.ts`, and `message-types.ts` also look deletion-ready once their zero-consumer scans are captured.

4. **Republish operator-facing config defaults, not just prose.**  
   If S03 removes Firebase Hosting/admin guidance from env templates and docs, it should also narrow `backend-hormonia/app/config/settings/security.py` defaults (`web.app` / `firebaseapp.com`) and the `auth_session_contract.py` Firebase TTL fallback so the code no longer advertises the old operator story.

5. **Fix active deployment/workflow narrative drift.**  
   Update `.github/workflows/*.yml`, `backend-hormonia/.env*`, `backend-hormonia/config/cloud-run/*.yaml`, and `.github/CONTRIBUTING.md` so they describe the current runtime. The Cloud Run manifests are especially important because they still mix Firebase Hosting URLs and `WHATSAPP_EVOLUTION_*` env names against a WuzAPI-based runtime.

6. **Classify or quarantine active-looking historical report trees.**  
   `backend-hormonia/docs/repo/**` contains many generated reports that still describe Firebase login, `/api/v2/auth/firebase/verify`, websocket token auth, or `X-Session-ID` as current behavior. A historical/archive boundary may be safer than piecemeal edits, because the path currently looks operational rather than archival.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Distinguish live backend auth/session residue from retired proof-only boundaries | `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` + the republished allowlist | S01 already turned backend auth/session residue into zero approved hits plus proof-only boundaries; S03 should consume that contract instead of re-litigating runtime truth with ad hoc grep. |
| Decide whether `SessionService` is still runtime-relevant | `backend-hormonia/app/service_provider.py` + `backend-hormonia/app/services/simple_session_service.py` | These files define the actual runtime session provider, so dead-code decisions can be anchored in live wiring instead of comments inside `session_service.py`. |
| Prove frontend compat cleanup stays cut | `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` and `usePatients-canonical-import.contract.test.ts` | These tests already encode “deleted compat files stay deleted” and “hooks stop importing compat barrels”; reuse them instead of inventing one-off grep notes. |
| Preserve the intentional root `/session/*` retirement boundary | `backend-hormonia/app/routers/auth_session.py` + the S01 proof model | This surface is an explicit tombstone, not generic dead code. S03 should keep it named and deliberate rather than deleting it accidentally. |
| Keep useful Firebase string retention that is security-only | `.github/workflows/pre-commit-validation.yml` | The Firebase API-key scan is a secret-leak guard, not a live Firebase runtime dependency. Keeping it prevents over-cleaning. |
| Decide the canonical WhatsApp operator surface | `backend-hormonia/app/config/settings/integrations.py` | This is the runtime truth: startup validation now hard-requires `WHATSAPP_WUZAPI_TOKEN` outside tests, so manifests/workflows should be aligned to it instead of preserving dead Evolution-era env names. |
| Canonical flow-engine implementation | `frontend-hormonia/src/lib/flow-engine/FlowEngine.ts` and `TemplateManager.ts` | These are the live implementations, so S03 should delete root bridge wrappers rather than creating fresh re-export indirection. |

## Existing Code and Patterns

- `backend-hormonia/app/service_provider.py` — `session_service` returns `SimpleSessionService`, confirming the canonical runtime already bypasses `SessionService`.
- `backend-hormonia/app/services/simple_session_service.py` — surviving canonical session behavior for quiz/session storage.
- `backend-hormonia/app/services/session_service.py` — legacy Firebase-centric session facade that still advertises Firebase token validation and `FirebaseRedisCache` behavior.
- `backend-hormonia/tests/unit/services/test_auth_session_services_async.py` — direct `SessionService` import site; useful proof that the remaining references are tests, not runtime wiring.
- `backend-hormonia/tests/integration/test_phase23_service_async_missinggreenlet.py` — second direct `SessionService` import site and a reminder that not every Firebase-named service is dead.
- `backend-hormonia/app/dependencies/auth_legacy_firebase.py` — retired/broken compatibility seam with unresolved merge markers.
- `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` — split-module auth contract test still reaching into `auth_legacy_firebase`; also contains unresolved merge markers.
- `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py` — active backend auth test file with unresolved merge markers, making broad pytest collection unreliable.
- `backend-hormonia/tests/unit/test_auth_dependencies.py` — useful regression proof that the live auth dependency source retired the legacy bearer/Firebase seam without importing the broken compat module.
- `backend-hormonia/app/config/settings/security.py` — still publishes Firebase Admin/security/cache env surface, hardcoded Firebase Hosting CORS defaults, and production auto-origins.
- `backend-hormonia/app/dependencies/auth_session_contract.py` — canonical cookie-first staff auth contract, but still falls back to `FIREBASE_SESSION_TTL_SECONDS` for session TTL resolution.
- `backend-hormonia/app/config/settings/integrations.py` — runtime truth for WhatsApp ops now uses `WHATSAPP_WUZAPI_*` and hard-fails without `WHATSAPP_WUZAPI_TOKEN` outside tests.
- `backend-hormonia/app/services/firebase_user_sync_service.py` — important counterexample: still has active unit/integration tests and settings hooks, so not every Firebase-named service is safe to auto-delete in S03.
- `frontend-hormonia/lib/flow-engine/FlowEngine.ts` — pure backward-compatible re-export bridge into `../../src/lib/flow-engine/FlowEngine`.
- `frontend-hormonia/lib/flow-engine/TemplateManager.ts` — same bridge pattern for `TemplateManager`.
- `frontend-hormonia/src/hooks/useFlowEngine.ts` — imports `../lib/flow-engine/*` from inside `src/hooks`; that resolves to `frontend-hormonia/src/lib/flow-engine/*`, not the root bridge barrels.
- `frontend-hormonia/lib/types/ai.ts` — deprecated compatibility barrel for AI types.
- `frontend-hormonia/lib/types/api.ts`, `flow-designer.ts`, `messages.ts`, `message-types.ts` — additional root compat/deprecated type barrels that currently show zero repo consumers beyond self/documentation references.
- `frontend-hormonia/lib/types/flow.ts` — strongest frontend deletion candidate: zero repo consumers and relative re-export targets that do not appear to exist in the current repo layout.
- `frontend-hormonia/src/types/api.ts` — canonical owner for the advanced AI types previously carried by `lib/types/ai.ts`.
- `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` — already guards previously deleted compat files and asserts type validation stops importing compat barrels.
- `frontend-hormonia/tests/unit/import-boundaries/usePatients-canonical-import.contract.test.ts` — focused proof that `usePatients.ts` stays off the compat barrel.
- `frontend-hormonia/tsconfig.json` and `tsconfig.build.json` — exclude tests and also omit the root `lib/**` compat files from normal typecheck/build inclusion.
- `frontend-hormonia/vite.config.ts` and `package.json` — Vitest includes both `src/**/*.{test,spec}` and `tests/**/*.{test,spec}`, so merge markers in test files poison `npm test` even if `npm run typecheck` stays green.
- `.github/workflows/rls-api-tests.yml` — still injects Firebase admin secrets, also carries Supabase-era env assumptions, and narrates JWT-token auth flow through middleware/RLS as if current.
- `.github/workflows/postman-tests.yml` — still writes Firebase admin vars into `.env.test` and uses older env names like `JWT_SECRET`, `CSRF_SECRET_KEY`, and `ENCRYPTION_KEY` instead of the current security naming.
- `.github/workflows/pre-commit-validation.yml` — useful keep-surface: Firebase API-key scanning here is secret-leak detection, not runtime dependence.
- `backend-hormonia/.env.example`, `.env.production.example`, `.env.production.template`, `.env.quiz.example`, `worker/.env.example` — still publish Firebase admin blocks and/or Firebase Hosting `web.app` URLs as normal configuration.
- `backend-hormonia/config/cloud-run/service-api.yaml` and `service-whatsapp-worker.yaml` — active deployment manifests still include Firebase admin env vars, Firebase-hosted frontend URLs, and dead `WHATSAPP_EVOLUTION_*` env names.
- `docs/backend/architecture/overview.md` — still says backend auth/security uses Firebase Admin SDK and shows `API -> Firebase Auth` in the architecture diagram.
- `docs/backend/guides/environment-validation.md` — still documents Firebase Admin SDK as a live runtime config path.
- `.github/CONTRIBUTING.md` — still lists Firebase/Supabase among normal deployment variables.
- `docs/compatibility/backward-compatibility-inventory.md` — mixed document: some route/payload compatibility entries may still be valid, but auth/session sections still describe retired fallback behavior as current.
- `backend-hormonia/docs/repo/**` — large cluster of active-looking generated reports; many still describe Firebase login, websocket token auth, or `X-Session-ID` as current integration behavior.
- `frontend-hormonia/firebase.json` and `.firebaserc` — Firebase Hosting residue files remain in the frontend repo and appear unreferenced by current code/workflow surfaces.

## Constraints

- **R052 is the only active requirement this slice supports.** S03 must remove or classify residue with evidence, not because the repo merely looks cleaner.
- **S01 already hard-cut live backend auth/session compatibility.** S03 should consume that boundary and treat remaining auth/session legacy text as proof-only, dead, or historical — not maybe-live runtime.
- **S02 already owns the schema-side Firebase drop.** S03 should not reopen Alembic/model convergence unless a supposedly dead repo surface proves a real post-S02 dependency.
- **Broad pytest/vitest is currently untrustworthy until merge markers are fixed.** `backend-hormonia/pyproject.toml` collects from `tests`, and frontend Vitest includes both `src` and `tests` test files.
- **Frontend build/typecheck and frontend tests do not cover the same files.** Root `frontend-hormonia/lib/**` compat files are not meaningfully protected by the current `tsc`/build inclusion rules, so exact import/path scans are mandatory.
- **Import resolution matters.** `@/lib/*` points into `frontend-hormonia/src/lib/*`, and `../lib/...` from inside `src/**` often does too; that does not prove the root `frontend-hormonia/lib/**` bridge barrels are needed.
- **Not every Firebase-named surface is dead.** `firebase_user_sync_service.py` and the Firebase security settings still have active tests/runtime-adjacent hooks.
- **Not every `FIREBASE_*` env name is removable by docs cleanup alone.** `auth_session_contract.py` still falls back to `FIREBASE_SESSION_TTL_SECONDS`, and `security.py` still validates/publishes Firebase Admin settings if any Firebase admin var is set.
- **Operational cleanup reaches code defaults, not just markdown.** `security.py` still hardcodes Firebase Hosting CORS origins, and `integrations.py` establishes WuzAPI as the live WhatsApp config contract.
- **Cloud Run/operator cleanup crosses dead-service naming.** The active manifests still use `WHATSAPP_EVOLUTION_*`, so S03 may need small deployment-manifest republishes rather than doc-only cleanup.
- **Not every `TOMBSTONE` file is in scope.** There are still many `TOMBSTONE` files under `backend-hormonia/app`, including AI/langgraph areas that touch deferred R041/R042 territory.
- **The root `/session/*` island remains an intentional retirement contract.** Do not treat it as generic dead code.
- **`docs/compatibility/backward-compatibility-inventory.md` is mixed-content.** Some entries are still real compatibility boundaries, so S03 should update/authenticate sections, not assume whole-file deletion.

## Common Pitfalls

- **Misclassifying `useFlowEngine.ts` as a consumer of the root flow-engine bridges** — confirm relative import resolution before preserving root `frontend-hormonia/lib/flow-engine/*`.
- **Assuming `npm run build` or `npm run typecheck` proves root compat barrels are needed** — the TS configs do not include those root files in the same way Vitest or repo scans do.
- **Running broad pytest/vitest before clearing merge markers** — active test files already contain conflict text, so failures will be noisy and misleading.
- **Deleting every Firebase mention blindly** — keep useful security-only checks such as the Firebase API-key scan in `.github/workflows/pre-commit-validation.yml`.
- **Deleting the whole `docs/compatibility` inventory** — that file still contains non-auth compat entries that may remain valid; update the retired auth/session narrative instead of flattening the entire document.
- **Treating every Firebase-named or Evolution-named backend surface as dead** — `firebase_user_sync_service.py` is still active, while WhatsApp runtime truth now lives under WuzAPI settings; classify carefully.
- **Cleaning env templates/docs but leaving `security.py`, `auth_session_contract.py`, or `integrations.py` untouched** — the operator story will still be wrong if code defaults and startup validation contradict the docs.
- **Deleting `frontend-hormonia/firebase.json` / `.firebaserc` without checking external deploy habits** — repo scans show no current in-repo usage, but unpublished manual deploy habits may still exist.
- **Over-widening S03 into repo-wide AI/langgraph tombstone purges** — many tombstones sit in deferred or sensitive areas without direct dead-code proof.

## Open Risks

- `backend-hormonia/docs/repo/**` contains many active-looking generated reports that still advertise Firebase login/session behavior; a historical quarantine strategy may be safer than one-off edits.
- `frontend-hormonia/firebase.json` and `.firebaserc` look unreferenced inside the repo, but they may still reflect unpublished manual deploy habits outside the repository.
- Deleting `SessionService` and the `auth_legacy_firebase` cluster may expose forgotten imports or stale test assumptions currently hidden by broken files.
- Env/workflow cleanup may require small code-level republishes in `backend-hormonia/app/config/settings/security.py`, `auth_session_contract.py`, and Cloud Run manifests, not just markdown edits.
- Some Firebase Admin/security env settings are still represented in active settings validators and tests; S03 must separate “official runtime story” from “still-present support/test boundary” carefully.
- The `WHATSAPP_EVOLUTION_*` vs `WHATSAPP_WUZAPI_*` drift may require an operator decision if external infra still injects the old env names outside the repo.
- Merge-marker cleanup itself may consume non-trivial slice effort because those files sit directly in active verification paths.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| GitHub Actions | `github-workflows` | installed in `<available_skills>`; directly relevant for workflow cleanup |
| React | `vercel-labs/agent-skills@vercel-react-best-practices` | available via `npx skills find "React"` (highest install count in search: 211.7K) |
| TypeScript | `wshobson/agents@typescript-advanced-types` | available via `npx skills find "TypeScript"` (highest install count in search: 13.8K) |
| FastAPI | `wshobson/agents@fastapi-templates` | available via `npx skills find "FastAPI"` (highest install count in search: 6.5K) |

## Sources

- `backend-hormonia/app/service_provider.py` wires `session_service` to `SimpleSessionService`, not to `SessionService`. (source: `backend-hormonia/app/service_provider.py`)
- The only direct `SessionService` import sites found in the repo are `backend-hormonia/tests/unit/services/test_auth_session_services_async.py` and `backend-hormonia/tests/integration/test_phase23_service_async_missinggreenlet.py`; no runtime provider import site was found. (source: local repo scan `rg -n "from app\.services\.session_service import SessionService|create_session_service\(|SessionService\(" backend-hormonia --glob '!**/test_output.txt'`)
- `backend-hormonia/app/dependencies/auth_legacy_firebase.py` still contains unresolved merge markers, and the only non-self refs are broken split-module tests plus the source-inspection regression in `tests/unit/test_auth_dependencies.py`. (source: local repo scan `rg -n 'auth_legacy_firebase|authenticate_legacy_bearer_user|initialize_firebase_service' backend-hormonia --glob '!**/test_output.txt'` plus the file itself)
- Active backend/frontend proof files still contain merge markers: `backend-hormonia/tests/unit/test_auth_dependency_module_split.py`, `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py`, `frontend-hormonia/tests/unit/types-validation.test.ts`, `frontend-hormonia/tests/integration/admin-auth-flow.test.tsx`, and `frontend-hormonia/src/hooks/__tests__/usePatients.test.ts`. (source: local repo scan `rg -n '^<<<<<<<|^=======$|^>>>>>>>' backend-hormonia frontend-hormonia --glob '!**/node_modules/**'`)
- `frontend-hormonia/lib/flow-engine/FlowEngine.ts` and `TemplateManager.ts` are pure bridge barrels, while `frontend-hormonia/src/hooks/useFlowEngine.ts` imports the canonical `src/lib/flow-engine/*` path via relative resolution, not the root bridges. (source: those three files)
- The root `frontend-hormonia/lib/types/*` barrels show zero repo consumers beyond self/documentation references, and `frontend-hormonia/lib/types/flow.ts` appears to target non-existent relative modules in the current repo layout. (source: local repo scans for `lib/types/*` refs, the barrel files themselves, and repo file scan `rg --files frontend-hormonia | rg '/types/.*\.tsx?$'`)
- `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` and `usePatients-canonical-import.contract.test.ts` already encode focused compat-cleanup proof for previously cut frontend barrels. (source: those two test files)
- Frontend `tsc` excludes tests and root compat files, while Vitest includes both `src/**/*.{test,spec}` and `tests/**/*.{test,spec}`. (source: `frontend-hormonia/tsconfig.json`, `frontend-hormonia/tsconfig.build.json`, `frontend-hormonia/vite.config.ts`, `frontend-hormonia/package.json`)
- `.github/workflows/rls-api-tests.yml` still injects Firebase admin secrets, also carries Supabase-era env assumptions, and narrates a JWT-token auth path through FastAPI middleware/RLS in its summary. (source: `.github/workflows/rls-api-tests.yml`)
- `.github/workflows/postman-tests.yml` still writes Firebase admin vars into `.env.test` and uses older env names like `JWT_SECRET`, `CSRF_SECRET_KEY`, and `ENCRYPTION_KEY`. (source: `.github/workflows/postman-tests.yml`)
- `.github/workflows/pre-commit-validation.yml` still uses Firebase API-key scanning as a secret-leak guard; that string retention is useful security behavior, not live runtime dependency. (source: `.github/workflows/pre-commit-validation.yml`)
- `backend-hormonia/.env.example`, `.env.production.example`, `.env.production.template`, `.env.quiz.example`, and `worker/.env.example` still publish Firebase admin blocks and/or Firebase Hosting `web.app` URLs as normal configuration. (source: those env template files plus local repo scans)
- `backend-hormonia/app/config/settings/security.py` still defaults CORS origins to `clinica-oncologica-hosting.web.app` / `firebaseapp.com`, validates Firebase Admin settings when any Firebase admin var is set, and publishes Firebase security/cache settings as active config. (source: `backend-hormonia/app/config/settings/security.py`)
- `backend-hormonia/app/dependencies/auth_session_contract.py` still falls back to `FIREBASE_SESSION_TTL_SECONDS` when resolving session TTL. (source: `backend-hormonia/app/dependencies/auth_session_contract.py`)
- `backend-hormonia/app/config/settings/integrations.py` now makes `WHATSAPP_WUZAPI_*` the canonical runtime/operator contract and hard-fails startup when `WHATSAPP_WUZAPI_TOKEN` is absent outside tests. (source: `backend-hormonia/app/config/settings/integrations.py`)
- `backend-hormonia/config/cloud-run/service-api.yaml` and `service-whatsapp-worker.yaml` still include Firebase admin env vars, Firebase-hosted frontend URLs, and `WHATSAPP_EVOLUTION_*` deployment vars. (source: those two Cloud Run files plus local repo scan `rg -n 'WHATSAPP_(EVOLUTION|WUZAPI)_' backend-hormonia/app backend-hormonia/config backend-hormonia/tests`)
- `docs/backend/architecture/overview.md`, `docs/backend/guides/environment-validation.md`, and `.github/CONTRIBUTING.md` still describe Firebase Admin or Firebase/Supabase-era deployment narrative as current. (source: those files)
- `docs/compatibility/backward-compatibility-inventory.md` still claims cookie + `X-Session-ID` + `Authorization` fallback and live `/session/*` compatibility even after S01 retired those paths. (source: `docs/compatibility/backward-compatibility-inventory.md`)
- `backend-hormonia/docs/repo/**` contains many active-looking integration/login/security reports that still advertise Firebase login, `/api/v2/auth/firebase/verify`, websocket token auth, or `X-Session-ID` as current behavior. (source: local `find` + `rg` scans over `backend-hormonia/docs/repo`)
- `backend-hormonia/app/services/firebase_user_sync_service.py` still has active unit/integration tests and settings hooks, so not every Firebase-named backend service belongs in the S03 auto-delete bucket. (source: local repo scan `rg -n 'FirebaseUserSyncService|firebase_user_sync_service' backend-hormonia --glob '!**/test_output.txt'`)
- `frontend-hormonia/firebase.json` and `.firebaserc` remain in the repo, and current repo searches found no direct operational references to those filenames beyond the files themselves and planning/history notes. (source: those files plus local filename/path searches)
