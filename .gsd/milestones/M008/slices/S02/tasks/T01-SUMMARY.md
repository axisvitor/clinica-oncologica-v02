---
id: T01
parent: S02
milestone: M008
provides:
  - WuzAPI Docker container running on port 8081
  - WhatsApp number connected via QR code scan
  - WuzAPIClient auth fix (Token header instead of Authorization)
  - Webhook URL configured pointing to backend
  - HMAC webhook security configured
  - WuzAPI service added to docker-compose.yml
key_files:
  - backend-hormonia/docker-compose.yml
  - backend-hormonia/.env
  - backend-hormonia/app/integrations/wuzapi/client.py
  - backend-hormonia/scripts/test_wuzapi_send.py
key_decisions:
  - "#66: WuzAPI auth uses Token header, not Authorization"
  - "#67: WuzAPI on port 8081 (port 8080 taken by evolution_api)"
patterns_established:
  - WuzAPI user auth via `Token` header (not `Authorization`)
  - WuzAPI admin auth via `Authorization` header with WUZAPI_ADMIN_TOKEN
  - WuzAPI user created via admin API with webhook + events config
observability_surfaces:
  - "curl -s http://localhost:8081/session/status -H 'Token: <user_token>' → connected/loggedIn"
  - "docker logs wuzapi_hormonia"
  - "curl -s http://localhost:8081/admin/users -H 'Authorization: <admin_token>'"
duration: 20m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T01: WuzAPI via Docker + conexão de número

**WuzAPI Docker container running on port 8081, WhatsApp number connected via QR code, auth header fixed from Authorization to Token, webhook and HMAC configured, test messages delivered to real WhatsApp**

## What Happened

1. Started WuzAPI Docker container (`asternic/wuzapi:latest`) on port 8081 (port 8080 already taken by `evolution_api`).
2. Created WuzAPI admin token and user "hormonia" via admin API with webhook URL `http://host.docker.internal:8000/api/v2/webhooks/wuzapi` and events `Message,ReadReceipt`.
3. Connected session via `POST /session/connect` and presented QR code for user to scan.
4. User scanned QR code — session now connected and logged in (JID: `5531****2216:34@s.whatsapp.net`).
5. **Critical fix:** Discovered WuzAPI uses `Token` header for auth, not `Authorization` as the client was sending. Fixed `WuzAPIClient` headers from `Authorization: <token>` to `Token: <token>`.
6. Configured HMAC webhook security via `POST /session/hmac/config` with 64-char key.
7. Updated `.env`: `WHATSAPP_WUZAPI_USE_MOCK=false`, `WHATSAPP_WUZAPI_BASE_URL=http://localhost:8081`, real token and HMAC secret.
8. Added `wuzapi` service to `docker-compose.yml` for reproducibility.
9. Sent 2 test messages — both delivered to real WhatsApp (confirmed by user).

## Verification

- ✅ `curl http://localhost:8081/session/status -H 'Token: ...'` → `connected: true, loggedIn: true`
- ✅ Direct API `POST /chat/send/text` with Token header → message delivered (ID: `3EB0B1DCD463B92BBA24FF`)
- ✅ Python `WuzAPIClient.send_text()` → message delivered (ID: `3EB0731676A4D6C1D52AC5`)
- ✅ User confirmed both test messages arrived on WhatsApp phone
- ✅ Webhook URL configured and verified via `GET /webhook`
- ✅ HMAC webhook security configured

### Slice-level checks (T01 partial):
- ✅ `curl http://localhost:8081/session/status` returns connected session
- ✅ Script Python executes `WuzAPIClient.send_text()` and returns success
- ✅ Messages arrived on WhatsApp (user visual confirmation)

## Diagnostics

- **Session status:** `curl -s http://localhost:8081/session/status -H 'Token: RhcchaEy...D4xw'`
- **Container logs:** `docker logs wuzapi_hormonia`
- **Admin users:** `curl -s http://localhost:8081/admin/users -H 'Authorization: kA3TRKRBs5...'`
- **Container health:** `docker ps --filter name=wuzapi_hormonia`
- **Test script:** `cd backend-hormonia && WHATSAPP_WUZAPI_BASE_URL=http://localhost:8081 WHATSAPP_WUZAPI_TOKEN=... python3 scripts/test_wuzapi_send.py`

## Deviations

- **Auth header fix:** WuzAPIClient was using `Authorization: <token>` but WuzAPI requires `Token: <token>` header. This was a pre-existing bug — the client was written against assumed API behavior, not the actual WuzAPI contract.
- **Port 8081:** Used 8081 instead of 8080 because `evolution_api` already occupies port 8080.
- **HMAC key length:** WuzAPI requires minimum 32 characters for HMAC key (field name is `hmac_key` not `HmacKey`). Generated new 64-char key to replace the 43-char one from .env.

## Known Issues

- WuzAPI auto-generates `WUZAPI_GLOBAL_ENCRYPTION_KEY` and `WUZAPI_GLOBAL_HMAC_KEY` on first run. These need to be saved to persist encrypted data across restarts. Currently stored in the Docker volume but not in .env.
- Webhook URL uses `host.docker.internal` which works on Docker Desktop but may need adjustment in Linux production environments.

## Files Created/Modified

- `backend-hormonia/app/integrations/wuzapi/client.py` — Fixed auth header from `Authorization` to `Token`
- `backend-hormonia/docker-compose.yml` — Added `wuzapi` service with health check and persistent volume
- `backend-hormonia/.env` — Updated WUZAPI settings (USE_MOCK=false, BASE_URL=8081, real token, HMAC secret)
- `backend-hormonia/scripts/test_wuzapi_send.py` — Test script for WuzAPIClient.send_text() verification
