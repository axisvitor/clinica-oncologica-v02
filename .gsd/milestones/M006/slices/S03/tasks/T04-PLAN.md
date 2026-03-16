---
estimated_steps: 5
estimated_files: 7
---

# T04: Fix workflow and documentation narrative drift, classify historical archive

**Slice:** S03 — Purga final de bridges, tombstones, serviços mortos e narrativa operacional errada
**Milestone:** M006

## Description

Workflows, docs, and the compatibility inventory still describe Firebase Admin / `X-Session-ID` / session-as-Bearer / Evolution-era WhatsApp as current behavior. `backend-hormonia/docs/repo/**` is a large cluster of generated reports from prior milestone phases — editing each one is fragile and endless, so an explicit `HISTORICAL-ARCHIVE.md` marker (Decision D43) classifies the entire directory as historical snapshots. This task also updates the two stale GitHub Actions workflows, the architecture/environment docs, `CONTRIBUTING.md`, and the compatibility inventory's auth/session sections.

## Steps

1. **Update workflow files:**
   - `rls-api-tests.yml` — remove Firebase admin secret injection (`FIREBASE_*` env vars), remove Supabase-era env assumptions, update narrative comments to describe cookie-session auth instead of JWT-token/Firebase middleware. Keep the workflow structure and test commands intact.
   - `postman-tests.yml` — remove Firebase admin vars from `.env.test` generation, replace stale env names (`JWT_SECRET`, `CSRF_SECRET_KEY`, `ENCRYPTION_KEY`) with current security naming if equivalents exist, or remove if dead. Keep the pre-commit Firebase API-key scan in `pre-commit-validation.yml` untouched.
2. **Update architecture and environment docs:**
   - `docs/backend/architecture/overview.md` — replace "Firebase Admin SDK" auth narrative and `API -> Firebase Auth` diagram arrows with canonical cookie-session description.
   - `docs/backend/guides/environment-validation.md` — remove Firebase Admin SDK as a live runtime config path, describe canonical session/security config instead.
3. **Update `CONTRIBUTING.md`** — remove Firebase and Supabase from the deployment variable list. Describe canonical env surface briefly.
4. **Update `docs/compatibility/backward-compatibility-inventory.md`** — mark auth/session fallback entries (cookie + `X-Session-ID` + `Authorization` fallback, live `/session/*` compatibility) as **retired** with a brief note referencing S01 and the canonical cookie-only contract. Keep non-auth compatibility entries that may still be valid.
5. **Create `backend-hormonia/docs/repo/HISTORICAL-ARCHIVE.md`** — write a concise boundary marker explaining that files in this directory are generated snapshots from prior milestone phases (M001–M005) and do not describe current system behavior. Reference the canonical docs locations for current architecture/auth/session documentation.

## Must-Haves

- [ ] `rls-api-tests.yml` and `postman-tests.yml` free of Firebase admin secret injection.
- [ ] `docs/backend/architecture/overview.md` describes canonical auth, not Firebase Admin SDK.
- [ ] `.github/CONTRIBUTING.md` does not list Firebase/Supabase as deployment variables.
- [ ] Auth/session entries in `backward-compatibility-inventory.md` marked as retired.
- [ ] `backend-hormonia/docs/repo/HISTORICAL-ARCHIVE.md` exists with explicit archive boundary.
- [ ] `pre-commit-validation.yml` Firebase API-key scan left intact.

## Verification

- `test -f backend-hormonia/docs/repo/HISTORICAL-ARCHIVE.md && echo "archive marker exists"` succeeds.
- `grep -l 'Firebase Admin' .github/workflows/rls-api-tests.yml .github/workflows/postman-tests.yml 2>/dev/null | wc -l` returns 0.
- `grep -c 'Firebase Admin SDK' docs/backend/architecture/overview.md` returns 0.
- `grep -c 'Firebase\|Supabase' .github/CONTRIBUTING.md | head -1` — verify minimal or zero Firebase/Supabase mentions (some historical/migration context may remain, but deployment variable lists should be clean).
- `grep -c 'firebase-api-key' .github/workflows/pre-commit-validation.yml` returns ≥1 (kept).

## Inputs

- S01 summary: cookie-only contract established, legacy transports rejection-only.
- S03 research: specific stale narrative locations in each file.
- Decision D43: `docs/repo/**` classified as historical archive.
- `backend-hormonia/app/config/settings/integrations.py` — canonical WhatsApp runtime (WuzAPI).

## Expected Output

- Updated workflow files without Firebase admin narrative/secrets.
- Updated architecture, environment, and contributing docs describing canonical auth.
- Updated compatibility inventory with retired auth/session entries.
- New `backend-hormonia/docs/repo/HISTORICAL-ARCHIVE.md` boundary marker.

## Observability Impact

- **No runtime signal changes** — this task is static doc/workflow cleanup with no runtime behavior delta.
- **Inspection:** `grep -l 'Firebase Admin' .github/workflows/*.yml 2>/dev/null | wc -l` should return 0 after this task. `grep -c 'RETIRED' docs/compatibility/backward-compatibility-inventory.md` should return ≥3.
- **Future agent diagnostic:** If a workflow re-introduces Firebase Admin secrets, CI env will contain stale/missing secret references that fail silently (empty string). The `pre-commit-validation.yml` Firebase API-key scan is intentionally preserved as a safety net for accidental key commits.
