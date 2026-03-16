---
estimated_steps: 5
estimated_files: 8
---

# T03: Republish operator-facing config defaults and deployment manifests

**Slice:** S03 — Purga final de bridges, tombstones, serviços mortos e narrativa operacional errada
**Milestone:** M006

## Description

The operator story is dishonest if docs are cleaned but code defaults and deployment manifests still advertise the Firebase/Evolution-era runtime. This task renames `FIREBASE_SESSION_TTL_SECONDS` → `SESSION_TTL_SECONDS` (Decision D42), narrows Firebase Hosting CORS defaults in `security.py`, updates Cloud Run manifests to drop Firebase admin vars and rename `WHATSAPP_EVOLUTION_*` → `WHATSAPP_WUZAPI_*`, and aligns env templates to the canonical runtime.

## Steps

1. **Rename session TTL env var** in `backend-hormonia/app/dependencies/auth_session_contract.py` — replace all references to `FIREBASE_SESSION_TTL_SECONDS` with `SESSION_TTL_SECONDS`. Check if other files in `backend-hormonia/app/` also reference this env name and update them.
2. **Narrow CORS defaults** in `backend-hormonia/app/config/settings/security.py` — remove hardcoded `clinica-oncologica-hosting.web.app` and `firebaseapp.com` origins from the default CORS list and `get_cors_origins()`. Keep any legitimate production/localhost origins. Do NOT touch the Firebase Admin settings validator or the Firebase API-key security scan — those are still-live surfaces.
3. **Update Cloud Run manifests** — in `backend-hormonia/config/cloud-run/service-api.yaml` and `service-whatsapp-worker.yaml`: remove Firebase admin env vars (`FIREBASE_*`), remove Firebase-hosted frontend URLs, rename `WHATSAPP_EVOLUTION_*` env names to `WHATSAPP_WUZAPI_*` to match `integrations.py` runtime truth.
4. **Update env templates** — in `backend-hormonia/.env.example`, `.env.production.example`, `.env.production.template`, `.env.quiz.example`, and `backend-hormonia/worker/.env.example`: remove Firebase admin blocks, update WhatsApp var names from `EVOLUTION` to `WUZAPI`, remove `web.app` / Firebase Hosting URLs. Keep any comments that explain the transition if useful.
5. **Verify** — grep for removed names to confirm clean removal, verify backend imports still work, confirm `auth_session_contract` still loadable.

## Must-Haves

- [ ] `FIREBASE_SESSION_TTL_SECONDS` renamed to `SESSION_TTL_SECONDS` in `auth_session_contract.py` and any other app-code references.
- [ ] Firebase Hosting origins removed from `security.py` CORS defaults.
- [ ] Cloud Run manifests free of Firebase admin vars and `WHATSAPP_EVOLUTION_*` names.
- [ ] Env templates updated to canonical runtime naming.
- [ ] Backend imports still clean after changes.

## Verification

- `grep -r 'FIREBASE_SESSION_TTL_SECONDS' backend-hormonia/app/ --include='*.py' | grep -v __pycache__ | wc -l` returns 0.
- `grep -r 'WHATSAPP_EVOLUTION_' backend-hormonia/config/cloud-run/ | wc -l` returns 0.
- `grep -r 'firebaseapp\.com\|web\.app' backend-hormonia/app/config/settings/security.py | wc -l` returns 0.
- `cd backend-hormonia && python3 -c "from app.dependencies.auth_session_contract import get_session_config; print('ok')"` succeeds (or equivalent importability check).
- `grep -r 'FIREBASE_SESSION_TTL_SECONDS' backend-hormonia/.env* backend-hormonia/worker/.env* | wc -l` returns 0.

## Inputs

- Decision D42: rename `FIREBASE_SESSION_TTL_SECONDS` → `SESSION_TTL_SECONDS`.
- `backend-hormonia/app/dependencies/auth_session_contract.py` — current session TTL resolution.
- `backend-hormonia/app/config/settings/security.py` — current CORS defaults.
- `backend-hormonia/app/config/settings/integrations.py` — canonical WhatsApp runtime truth (WuzAPI).
- `backend-hormonia/config/cloud-run/*.yaml` — deployment manifests.
- `backend-hormonia/.env*` — env templates.

## Expected Output

- `auth_session_contract.py` using `SESSION_TTL_SECONDS`.
- `security.py` with narrowed CORS defaults (no Firebase Hosting origins).
- Cloud Run manifests using canonical env naming.
- Env templates aligned with current runtime.
