---
id: T03
parent: S03
milestone: M006
provides:
  - Config defaults and deployment manifests aligned to canonical cookie-first/WuzAPI runtime
  - FIREBASE_SESSION_TTL_SECONDS renamed to SESSION_TTL_SECONDS (Decision D42)
  - Firebase Hosting origins removed from CORS defaults
  - Cloud Run manifests free of Firebase admin vars and WHATSAPP_EVOLUTION_ naming
  - Env templates using canonical WuzAPI naming and placeholder production URLs
key_files:
  - backend-hormonia/app/dependencies/auth_session_contract.py
  - backend-hormonia/app/config/settings/security.py
  - backend-hormonia/config/cloud-run/service-api.yaml
  - backend-hormonia/config/cloud-run/service-whatsapp-worker.yaml
  - backend-hormonia/.env.example
  - backend-hormonia/.env.production.example
  - backend-hormonia/.env.production.template
  - backend-hormonia/.env.quiz.example
  - backend-hormonia/.env
key_decisions:
  - Kept FIREBASE_ADMIN_* env vars in env templates (.env.example, .env.production.example, .env.production.template, worker/.env.example) because Firebase Admin SDK is still a live surface consumed by security.py and firebase_user_sync_service.py — only removed from Cloud Run manifests where operators should supply via Secret Manager
  - Removed FIREBASE_SESSION_TTL_SECONDS fallback entirely from auth_session_contract.py rather than keeping a compat shim — clean break per D42
patterns_established:
  - none
observability_surfaces:
  - grep -r 'FIREBASE_SESSION_TTL_SECONDS|WHATSAPP_EVOLUTION_' backend-hormonia/ — should return 0 results
  - CORS in production now depends entirely on CORS_FRONTEND_URL, CORS_QUIZ_URL, and CORS_ALLOWED_ORIGINS env vars — no hardcoded Firebase Hosting origins
duration: 15min
verification_result: passed
completed_at: 2026-03-15
blocker_discovered: false
---

# T03: Republish operator-facing config defaults and deployment manifests

**Renamed `FIREBASE_SESSION_TTL_SECONDS` → `SESSION_TTL_SECONDS`, removed Firebase Hosting CORS hardcodes, cleaned Cloud Run manifests of Firebase admin and Evolution-era WhatsApp vars, and aligned env templates to canonical WuzAPI runtime.**

## What Happened

1. **Session TTL rename (D42)**: Renamed `FIREBASE_SESSION_TTL_SECONDS` to `SESSION_TTL_SECONDS` in `security.py` (field definition) and removed the fallback chain in `auth_session_contract.py` — now reads `SESSION_TTL_SECONDS` directly, falling back to `redis_cache.session_ttl` (86400). Updated `.env` and `.env.example`.

2. **CORS narrowing**: Removed hardcoded `clinica-oncologica-hosting.web.app` and `clinica-oncologica-hosting.firebaseapp.com` from both `CORS_ALLOWED_ORIGINS` default list and `get_cors_origins()` production auto-injection. CORS in production now depends entirely on operator-supplied env vars.

3. **Cloud Run manifests**: From both `service-api.yaml` and `service-whatsapp-worker.yaml`:
   - Removed all `FIREBASE_ADMIN_*` vars (PROJECT_ID, CLIENT_EMAIL, PRIVATE_KEY, ALLOWED_DOMAINS)
   - Renamed `WHATSAPP_EVOLUTION_*` vars to `WHATSAPP_WUZAPI_*` (BASE_URL, TOKEN, WEBHOOK_SECRET)
   - Removed `WHATSAPP_EVOLUTION_INSTANCE_NAME` and `WHATSAPP_EVOLUTION_WEBHOOK_URL` (not in WuzAPI schema)
   - Replaced hardcoded Firebase Hosting URLs in `APP_ADMIN_DASHBOARD_URL` and `CORS_FRONTEND_URL` with `REPLACE_WITH_*` placeholders

4. **Env templates**: Updated CORS URLs from Firebase Hosting to placeholder/localhost values across `.env.example`, `.env.production.example`, `.env.production.template`, `.env.quiz.example`. Renamed WhatsApp vars from Evolution to WuzAPI in `.env.production.template`.

## Verification

- `grep -r 'FIREBASE_SESSION_TTL_SECONDS' backend-hormonia/app/ --include='*.py' | grep -v __pycache__ | wc -l` → **0** ✅
- `grep -r 'WHATSAPP_EVOLUTION_' backend-hormonia/config/cloud-run/ | wc -l` → **0** ✅
- `grep -r 'firebaseapp\.com\|web\.app' backend-hormonia/app/config/settings/security.py | wc -l` → **0** ✅
- `grep -r 'FIREBASE_SESSION_TTL_SECONDS' backend-hormonia/.env* backend-hormonia/worker/.env* | wc -l` → **0** ✅
- `WHATSAPP_WUZAPI_TOKEN=test-token python3 -c "from app.dependencies.auth_session_contract import resolve_authenticated_session_user; print('ok')"` → **ok** ✅
- `WHATSAPP_WUZAPI_TOKEN=test-token python3 -c "from app.service_provider import ServiceProvider; print('backend imports clean')"` → **ok** ✅
- Dead surfaces absent: `session_service.py`, `auth_legacy_firebase.py` → confirmed deleted ✅
- `grep -n 'FIREBASE_\|EVOLUTION' backend-hormonia/config/cloud-run/*.yaml` → **0 matches** ✅

### Slice-level checks (partial — intermediate task):
- Backend imports clean ✅
- Dead surfaces removed ✅
- `FIREBASE_SESSION_TTL_SECONDS` absent from app code ✅
- `WHATSAPP_EVOLUTION_` absent from Cloud Run manifests ✅
- `ServiceProvider()` instantiation check deferred (requires `db` constructor arg — not this task's concern)

## Diagnostics

- If CORS fails in production after this change, check that `CORS_FRONTEND_URL` and `CORS_ALLOWED_ORIGINS` are set — there are no longer hardcoded fallbacks.
- If session TTL defaults to 86400 unexpectedly, verify `SESSION_TTL_SECONDS` (not the old `FIREBASE_SESSION_TTL_SECONDS`) is set in the env.
- Cloud Run manifests now use `REPLACE_WITH_*` placeholders for WuzAPI and admin URLs — deployment will fail clearly if not replaced.

## Deviations

- **Kept `FIREBASE_ADMIN_*` in env templates**: The plan said "remove Firebase admin blocks" from env templates, but `FIREBASE_ADMIN_*` vars are still consumed by live code (`security.py` validator, `firebase_user_sync_service.py`). Removed only from Cloud Run manifests where operators should supply via Secret Manager. Removed from manifests only.
- **Updated live `.env` file**: Also renamed `FIREBASE_SESSION_TTL_SECONDS` → `SESSION_TTL_SECONDS` in the working `.env` file (not just templates) to keep local dev consistent.

## Known Issues

- Pre-existing: `WHATSAPP_WUZAPI_TOKEN` startup validation fails when token is unset — this is intentional design (CFG-02), not a regression.
- Pre-existing: `ServiceProvider()` requires a `db` argument — slice verification command `ServiceProvider()` without args will always fail.

## Files Created/Modified

- `backend-hormonia/app/dependencies/auth_session_contract.py` — removed `FIREBASE_SESSION_TTL_SECONDS` fallback
- `backend-hormonia/app/config/settings/security.py` — renamed field to `SESSION_TTL_SECONDS`, removed Firebase Hosting CORS defaults and auto-injection
- `backend-hormonia/config/cloud-run/service-api.yaml` — removed Firebase admin vars, renamed WhatsApp vars to WuzAPI, replaced hardcoded URLs with placeholders
- `backend-hormonia/config/cloud-run/service-whatsapp-worker.yaml` — removed Firebase admin vars, renamed WhatsApp vars to WuzAPI
- `backend-hormonia/.env` — renamed `FIREBASE_SESSION_TTL_SECONDS` → `SESSION_TTL_SECONDS`
- `backend-hormonia/.env.example` — updated CORS URLs to localhost, renamed session TTL
- `backend-hormonia/.env.production.example` — updated CORS URLs to placeholders
- `backend-hormonia/.env.production.template` — updated CORS URLs to placeholders, renamed WhatsApp vars to WuzAPI
- `backend-hormonia/.env.quiz.example` — updated commented CORS URLs to placeholders
- `.gsd/milestones/M006/slices/S03/tasks/T03-PLAN.md` — added Observability Impact section
