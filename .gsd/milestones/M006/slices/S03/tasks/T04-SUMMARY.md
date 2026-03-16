---
id: T04
parent: S03
milestone: M006
provides:
  - Workflow files free of Firebase admin secret injection and stale env names
  - Architecture and environment docs describing canonical cookie-session auth
  - CONTRIBUTING.md deployment variables aligned to current runtime
  - Backward-compatibility inventory auth/session entries marked RETIRED
  - HISTORICAL-ARCHIVE.md boundary marker for docs/repo/**
key_files:
  - .github/workflows/rls-api-tests.yml
  - .github/workflows/postman-tests.yml
  - docs/backend/architecture/overview.md
  - docs/backend/guides/environment-validation.md
  - .github/CONTRIBUTING.md
  - docs/compatibility/backward-compatibility-inventory.md
  - backend-hormonia/docs/repo/HISTORICAL-ARCHIVE.md
key_decisions:
  - D43 implemented — docs/repo/** classified behind HISTORICAL-ARCHIVE.md marker
patterns_established:
  - none
observability_surfaces:
  - none (static doc/workflow cleanup — no runtime behavior change)
duration: 20m
verification_result: passed
completed_at: 2026-03-15
blocker_discovered: false
---

# T04: Fix workflow and documentation narrative drift, classify historical archive

**Cleaned Firebase/Supabase/Evolution narrative from workflows, docs, and compatibility inventory; classified docs/repo/** as historical archive with explicit boundary marker.**

## What Happened

1. **Workflows updated:**
   - `rls-api-tests.yml` — removed Supabase (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`) and Firebase Admin (`FIREBASE_ADMIN_*`) secret injection. Updated test-strategy summary from "JWT token → FastAPI middleware" to "Cookie-session auth → FastAPI middleware". Kept `DATABASE_URL` and `SECRET_KEY`.
   - `postman-tests.yml` — replaced stale `.env.test` generation: removed `JWT_SECRET`, `CSRF_SECRET_KEY`, `ENCRYPTION_KEY` (dead names), Evolution API vars (`ENABLE_EVOLUTION`, `EVOLUTION_*`), and Firebase Admin vars. Replaced with canonical names (`SECURITY_SECRET_KEY`, `SECURITY_CSRF_SECRET_KEY`, `WHATSAPP_ENABLE_SERVICE=false`).

2. **Architecture and environment docs updated:**
   - `overview.md` — replaced "Firebase Admin SDK" auth line and mermaid diagram arrows (`Firebase Auth`, `Evolution API`) with canonical cookie-session auth and WuzAPI.
   - `environment-validation.md` — reframed Firebase Admin SDK section from "if using Firebase" to "optional — legacy user-sync only", clarifying that canonical auth is cookie-session.

3. **CONTRIBUTING.md updated:** Replaced `SECRET_KEY/JWT_SECRET_KEY, Firebase/Supabase` deployment variables with `SECURITY_SECRET_KEY`, `SECURITY_CSRF_SECRET_KEY`, `SESSION_TTL_SECONDS`.

4. **Compatibility inventory updated:** Marked 3 backend auth/session shim entries (session resolver, session endpoints, legacy token auth) as **RETIRED** with S01/M004 references. Marked the "Auth mode transition" deprecation policy row as RETIRED. Kept frontend medico auth shim and quiz session alias as ACTIVE (unrelated to backend transport cleanup).

5. **Historical archive marker created:** `backend-hormonia/docs/repo/HISTORICAL-ARCHIVE.md` — concise boundary marker explaining the directory contains generated snapshots from M001–M005 and listing canonical doc locations.

## Verification

**Must-have checks — all passed:**
- `test -f backend-hormonia/docs/repo/HISTORICAL-ARCHIVE.md` → exists ✓
- `grep -l 'Firebase Admin' .github/workflows/rls-api-tests.yml .github/workflows/postman-tests.yml 2>/dev/null | wc -l` → 0 ✓
- `grep -c 'Firebase Admin SDK' docs/backend/architecture/overview.md` → 0 ✓
- `grep -c 'Firebase\|Supabase' .github/CONTRIBUTING.md` → 0 ✓
- `grep -c -i 'firebase.*api.*key' .github/workflows/pre-commit-validation.yml` → 4 ✓ (scan preserved)

**Slice-level checks — all passed (final task):**
- Dead surfaces removed (absence scan) ✓
- `FIREBASE_SESSION_TTL_SECONDS` gone from app code ✓
- `WHATSAPP_EVOLUTION_` gone from cloud-run manifests ✓
- Archive marker exists ✓
- Backend imports clean ✓
- S01 residue guard green (`--check backend OK`) ✓
- Frontend import-boundaries contract tests: 2 files, 6 tests, all passed ✓

## Diagnostics

- If a workflow re-introduces Firebase Admin secrets, CI will inject empty strings (missing GitHub secrets), causing silent auth failures. The preserved `pre-commit-validation.yml` scan catches accidental API key commits.
- If backward-compatibility inventory needs new entries, note that the auth/session section now includes a RETIRED status column — new entries should use the same format.
- `backend-hormonia/docs/repo/HISTORICAL-ARCHIVE.md` is the authoritative boundary — any generated report placed in `docs/repo/` is considered historical by convention.

## Deviations

None.

## Known Issues

- `ServiceProvider()` requires a `db` argument, so the slice-level diagnostic check `ServiceProvider(); print(type(sp.session_service).__name__)` cannot run without a DB connection. The import-level check (`from app.service_provider import ServiceProvider; print('ok')`) passes, confirming no import breakage.

## Files Created/Modified

- `.github/workflows/rls-api-tests.yml` — removed Firebase/Supabase secret injection, updated auth narrative to cookie-session
- `.github/workflows/postman-tests.yml` — replaced stale .env.test with canonical env names, removed Firebase admin vars
- `docs/backend/architecture/overview.md` — replaced Firebase Auth/Evolution API with cookie-session/WuzAPI in text and mermaid diagram
- `docs/backend/guides/environment-validation.md` — reframed Firebase Admin SDK as optional legacy user-sync
- `.github/CONTRIBUTING.md` — replaced Firebase/Supabase deployment variables with canonical env surface
- `docs/compatibility/backward-compatibility-inventory.md` — marked 3 auth/session shims and auth-mode-transition entry as RETIRED
- `backend-hormonia/docs/repo/HISTORICAL-ARCHIVE.md` — created archive boundary marker (Decision D43)
- `.gsd/milestones/M006/slices/S03/tasks/T04-PLAN.md` — added Observability Impact section (pre-flight fix)
