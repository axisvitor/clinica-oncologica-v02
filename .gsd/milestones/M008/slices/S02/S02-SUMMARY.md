---
id: S02
parent: M008
milestone: M008
provides:
  - WuzAPI Docker container running on port 8081 with health check
  - WhatsApp number connected via QR code scan (JID 5531****2216)
  - WuzAPIClient auth header fixed (Token instead of Authorization)
  - WuzAPIClient.send_text() verified delivering real WhatsApp messages
  - Webhook URL configured pointing to backend (host.docker.internal:8000)
  - HMAC webhook security configured with 64-char key
  - WHATSAPP_WUZAPI_BASE_URL and WHATSAPP_WUZAPI_TOKEN in .env
  - WHATSAPP_WUZAPI_USE_MOCK=false in .env
  - Test script for repeatable send verification
requires:
  - slice: S01
    provides: Backend running on localhost:8000 with health check, .env with base config, Docker infrastructure
affects:
  - S04
  - S05
key_files:
  - backend-hormonia/app/integrations/wuzapi/client.py
  - backend-hormonia/docker-compose.yml
  - backend-hormonia/scripts/test_wuzapi_send.py
  - backend-hormonia/.env
key_decisions:
  - "#66: WuzAPI auth uses Token header, not Authorization"
  - "#67: WuzAPI on port 8081 (port 8080 taken by evolution_api)"
patterns_established:
  - WuzAPI user auth via `Token` header (not `Authorization`)
  - WuzAPI admin auth via `Authorization` header with WUZAPI_ADMIN_TOKEN
  - WuzAPI user created via admin API with webhook + events config
  - Test script pattern: get session status → extract phone from JID → send_text()
observability_surfaces:
  - "curl -s http://localhost:8081/session/status -H 'Token: <user_token>' → connected/loggedIn"
  - "docker logs wuzapi_hormonia"
  - "curl -s http://localhost:8081/admin/users -H 'Authorization: <admin_token>'"
  - "python3 scripts/test_wuzapi_send.py — end-to-end send verification"
drill_down_paths:
  - .gsd/milestones/M008/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M008/slices/S02/tasks/T02-SUMMARY.md
duration: 25m
verification_result: passed
completed_at: 2026-03-16
---

# S02: WuzAPI conectado e enviando

**WuzAPI running on Docker port 8081, WhatsApp number connected via QR code, auth header fixed from Authorization to Token, webhook + HMAC configured, test messages delivered to real WhatsApp and confirmed by user**

## What Happened

Started WuzAPI Docker container (`asternic/wuzapi:latest`) on port 8081 — port 8080 was already occupied by `evolution_api`. Created the WuzAPI admin token and "hormonia" user via the admin API, configured with webhook URL `http://host.docker.internal:8000/api/v2/webhooks/wuzapi` and events `Message,ReadReceipt`. Connected the session via QR code scan — user paired their WhatsApp number successfully.

During the first send attempt, discovered a **critical pre-existing bug**: `WuzAPIClient` was sending `Authorization: <token>` but WuzAPI only reads the `Token` header. Fixed the header in `client.py`. Configured HMAC webhook security with a 64-char key. Updated `.env` with real credentials (`USE_MOCK=false`, `BASE_URL=http://localhost:8081`, real token and HMAC secret). Added the `wuzapi` service to `docker-compose.yml` for reproducibility.

Sent multiple test messages — all delivered to the real WhatsApp phone. Final verification with "Teste M008 - sistema funcionando ✅" confirmed by user visual check on the phone.

## Verification

- ✅ `curl http://localhost:8081/session/status -H 'Token: ...'` → `connected: true, loggedIn: true`
- ✅ Direct API `POST /chat/send/text` with Token header → message delivered
- ✅ Python `WuzAPIClient.send_text()` → message delivered (multiple message IDs confirmed)
- ✅ User confirmed test messages arrived on WhatsApp phone (visual confirmation)
- ✅ Webhook URL configured: `GET /webhook` returns correct URL
- ✅ HMAC webhook security configured
- ✅ WuzAPI container healthy: `docker ps --filter name=wuzapi_hormonia` shows running

## Requirements Advanced

- R068 — WuzAPI running via Docker, number connected, test message sent and delivered to real WhatsApp. All S02 criteria met.

## Requirements Validated

- R068 — WuzAPI conectado e enviando mensagens reais. Proven by: (1) WuzAPI container running on port 8081, (2) WhatsApp number connected via QR code scan, (3) `WuzAPIClient.send_text()` delivered messages to real WhatsApp, (4) user visual confirmation of message receipt, (5) webhook URL and HMAC security configured for downstream webhook processing.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- **Auth header fix (D#66):** WuzAPIClient was using `Authorization: <token>` but WuzAPI requires `Token: <token>`. This was a pre-existing bug in the client code — not a plan deviation, but a critical discovery during execution.
- **Port 8081 instead of 8080 (D#67):** `evolution_api` already occupies port 8080. WuzAPI mapped to 8081 on the host.
- **HMAC key length:** WuzAPI requires minimum 32 chars. Generated 64-char key to replace the 43-char one from `.env`. Field name is `hmac_key` not `HmacKey`.

## Known Limitations

- WuzAPI auto-generates `WUZAPI_GLOBAL_ENCRYPTION_KEY` and `WUZAPI_GLOBAL_HMAC_KEY` on first run. These are stored in the Docker volume but not persisted in `.env` — data loss if volume is deleted.
- Webhook URL uses `host.docker.internal` which works on Docker Desktop (WSL2) but may need adjustment in Linux production environments.
- QR code pairing is a manual user step — cannot be automated. Session may expire and need re-pairing.

## Follow-ups

- S04 will consume the connected WuzAPI to send welcome messages and daily flow messages to real patients.
- S05 will consume the webhook configuration to process incoming patient responses.

## Files Created/Modified

- `backend-hormonia/app/integrations/wuzapi/client.py` — Fixed auth header from `Authorization` to `Token`
- `backend-hormonia/docker-compose.yml` — Added `wuzapi` service with health check, persistent volume, TZ config
- `backend-hormonia/.env` — Updated WUZAPI settings (USE_MOCK=false, BASE_URL=8081, real token, HMAC secret)
- `backend-hormonia/scripts/test_wuzapi_send.py` — Repeatable test script for WuzAPIClient.send_text() verification

## Forward Intelligence

### What the next slice should know
- WuzAPI is live on port 8081 with `WHATSAPP_WUZAPI_USE_MOCK=false`. All downstream code that sends WhatsApp messages will hit a real phone.
- The `Token` header (not `Authorization`) is the correct auth mechanism. This is already fixed in the client — no further action needed.
- Webhook URL is `http://host.docker.internal:8000/api/v2/webhooks/wuzapi` — S05 needs the backend webhook handler to accept and process incoming messages at this endpoint.
- HMAC validation must use the key from `WHATSAPP_WUZAPI_WEBHOOK_SECRET` in `.env`.

### What's fragile
- **QR code session** — WhatsApp sessions can expire if the phone loses connectivity for extended periods. If `session/status` shows `loggedIn: false`, user must re-scan QR code via `POST /session/connect`.
- **host.docker.internal** — works on Docker Desktop / WSL2 but not guaranteed on native Linux Docker. S04/S05 may need to adjust if running on a different environment.

### Authoritative diagnostics
- `curl -s http://localhost:8081/session/status -H 'Token: <token>'` — the single source of truth for WuzAPI connectivity. If `connected: false` or `loggedIn: false`, nothing downstream will work.
- `docker logs wuzapi_hormonia` — shows all API calls, webhook deliveries, and connection events.
- `python3 scripts/test_wuzapi_send.py` — end-to-end smoke test that covers session check + message send.

### What assumptions changed
- **Auth header:** Original code assumed `Authorization` header. Actual WuzAPI contract is `Token` header — fixed in T01.
- **Port:** Plan assumed port 8080 available. Actually 8080 is taken by evolution_api — using 8081.
- **HMAC field name:** `.env` had `HmacKey` format. WuzAPI uses `hmac_key` with minimum 32 chars.
