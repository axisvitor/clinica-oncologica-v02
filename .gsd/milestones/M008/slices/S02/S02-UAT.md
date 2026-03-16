# S02: WuzAPI conectado e enviando — UAT

**Milestone:** M008
**Written:** 2026-03-16

## UAT Type

- UAT mode: live-runtime
- Why this mode is sufficient: This slice proves real WhatsApp message delivery via WuzAPI — the entire value is in live integration, not artifacts. User must verify messages arrive on a real phone.

## Preconditions

1. Docker Desktop (or equivalent) running
2. WuzAPI container `wuzapi_hormonia` running: `docker ps --filter name=wuzapi_hormonia` shows healthy
3. WhatsApp number connected (QR code previously scanned). If session expired, re-pair via `POST http://localhost:8081/session/connect -H 'Token: <token>'` and scan the returned QR code
4. Backend running on `localhost:8000` (from S01)
5. `.env` has `WHATSAPP_WUZAPI_USE_MOCK=false`, `WHATSAPP_WUZAPI_BASE_URL=http://localhost:8081`, valid `WHATSAPP_WUZAPI_TOKEN`

## Smoke Test

```bash
curl -s http://localhost:8081/session/status -H 'Token: <WHATSAPP_WUZAPI_TOKEN>' | python3 -m json.tool
```
**Expected:** JSON with `"connected": true` and `"loggedIn": true`. If either is `false`, re-pair the number via QR code before proceeding.

## Test Cases

### 1. WuzAPI container health

1. Run `docker ps --filter name=wuzapi_hormonia --format '{{.Status}}'`
2. **Expected:** Output shows `Up` with `(healthy)` status

### 2. Session status via API

1. Run:
   ```bash
   curl -s http://localhost:8081/session/status -H 'Token: <WHATSAPP_WUZAPI_TOKEN>'
   ```
2. **Expected:** JSON response with:
   - `"connected": true`
   - `"loggedIn": true`
   - `"jid"` contains a valid WhatsApp JID (e.g., `5531...@s.whatsapp.net`)

### 3. Auth header contract (Token, not Authorization)

1. Run with WRONG header:
   ```bash
   curl -s http://localhost:8081/session/status -H 'Authorization: <WHATSAPP_WUZAPI_TOKEN>'
   ```
2. **Expected:** Returns 401 or error — WuzAPI does NOT accept `Authorization` header
3. Run with CORRECT header:
   ```bash
   curl -s http://localhost:8081/session/status -H 'Token: <WHATSAPP_WUZAPI_TOKEN>'
   ```
4. **Expected:** Returns 200 with connected status

### 4. Direct API message send

1. Run:
   ```bash
   curl -s -X POST http://localhost:8081/chat/send/text \
     -H 'Token: <WHATSAPP_WUZAPI_TOKEN>' \
     -H 'Content-Type: application/json' \
     -d '{"Phone": "<test_phone_number>", "Body": "UAT S02 - teste direto via API"}'
   ```
2. **Expected:** JSON response with a message ID
3. **Expected:** Message "UAT S02 - teste direto via API" arrives on the test WhatsApp phone

### 5. WuzAPIClient.send_text() via Python script

1. Run from `backend-hormonia/`:
   ```bash
   cd backend-hormonia
   WHATSAPP_WUZAPI_BASE_URL=http://localhost:8081 \
   WHATSAPP_WUZAPI_TOKEN=<token> \
   python3 scripts/test_wuzapi_send.py
   ```
2. **Expected:** Script output shows:
   - `Connected: True`
   - `Logged In: True`
   - `Success: True`
   - A valid `Message ID`
   - `🎉 Test PASSED`
3. **Expected:** Message arrives on the test WhatsApp phone

### 6. Webhook configuration

1. Run:
   ```bash
   curl -s http://localhost:8081/webhook -H 'Token: <WHATSAPP_WUZAPI_TOKEN>'
   ```
2. **Expected:** Response shows webhook URL containing `host.docker.internal:8000/api/v2/webhooks/wuzapi`

### 7. docker-compose.yml has wuzapi service

1. Run:
   ```bash
   grep -A 5 'wuzapi:' backend-hormonia/docker-compose.yml
   ```
2. **Expected:** Shows `wuzapi` service definition with:
   - Image: `asternic/wuzapi:latest`
   - Container name: `wuzapi_hormonia`
   - Port mapping to 8081
   - Health check configured

## Edge Cases

### Session expired / phone disconnected

1. Disconnect the WhatsApp phone from internet for an extended period (or force-close WhatsApp app)
2. Check `curl http://localhost:8081/session/status -H 'Token: ...'`
3. **Expected:** `"loggedIn": false` — clearly indicates the session needs re-pairing
4. Re-pair via `POST /session/connect` and scan QR code
5. **Expected:** After re-pairing, status returns `"loggedIn": true` and sends work again

### Invalid token

1. Run:
   ```bash
   curl -s http://localhost:8081/session/status -H 'Token: invalid_token_here'
   ```
2. **Expected:** Returns 401 or unauthorized error — does not leak session data

### Send to invalid phone number

1. Using the Python client or curl, attempt to send a message to an obviously invalid number (e.g., "000000")
2. **Expected:** WuzAPI returns an error response, does not crash. Client handles gracefully.

## Failure Signals

- `docker ps --filter name=wuzapi_hormonia` shows no container or unhealthy status
- `session/status` returns `connected: false` or `loggedIn: false`
- Test script exits with error code or shows `Success: False`
- No message arrives on the test phone within 30 seconds of send
- `Authorization` header works (means the client fix was reverted)
- `.env` still has `WHATSAPP_WUZAPI_USE_MOCK=true` (mock mode active)

## Requirements Proved By This UAT

- R068 — WuzAPI conectado e enviando mensagens reais. Proven by test cases 1-6 covering container health, session connectivity, auth contract, real message delivery via both direct API and Python client, and webhook configuration.

## Not Proven By This UAT

- Webhook **receipt** processing (incoming messages from patient → backend) — that is S05's scope
- Welcome message or daily flow message delivery — that is S04's scope
- Long-term session stability (days/weeks of uptime) — requires extended observation
- WuzAPI behavior under high load or rate limiting — not in scope for this slice

## Notes for Tester

- **Phone required:** You need physical access to the WhatsApp phone that was paired via QR code.
- **Real messages:** Test cases 4 and 5 send real WhatsApp messages. Use your own test number to avoid messaging unintended recipients.
- **Token values:** Replace `<WHATSAPP_WUZAPI_TOKEN>` and `<test_phone_number>` with actual values from `.env`. Do not commit real tokens.
- **QR code re-pairing:** If the session expired since S02 was executed, you'll need to re-pair before running tests. This is a manual step — use `POST /session/connect` and scan the QR from the response.
- **Port 8081:** WuzAPI is on 8081, not the default 8080. The `evolution_api` container occupies 8080.
