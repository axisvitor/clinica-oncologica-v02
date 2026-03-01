# Pitfalls Research

**Domain:** WhatsApp API provider migration — Evolution API to WuzAPI (whatsmeow-backed)
**Researched:** 2026-03-01
**Confidence:** MEDIUM — WuzAPI endpoint/auth format verified from GitHub API.md and README. Evolution API payload shapes verified from production codebase. Brazilian 9th-digit behavior verified from multiple WhatsApp integration provider sources (Zoko, Gupshup, Baileys). LID addressing behavior verified from whatsmeow GitHub issues and Baileys migration docs. Some WuzAPI-specific rate limit numbers are undocumented (flagged LOW confidence where noted).

---

## Critical Pitfalls

### Pitfall 1: Webhook Payload Structure Is Completely Different — Silent Data Loss

**What goes wrong:**
Evolution API sends webhooks with an outer envelope containing `event`, `instance`, and `data` keys. WuzAPI delivers raw whatsmeow event structures where the outer wrapper is `{"Type": "Message", "Data": {...}}` using Go struct naming (PascalCase, not camelCase). Incoming message text does not live at `payload["data"]["message"]["conversation"]` as it does in Evolution — it lives at different nested paths that reflect whatsmeow's native types.

If the existing webhook handler tries to access Evolution-style key paths on a WuzAPI payload, it will get `None` or `KeyError`, silently drop the message, return HTTP 200 to WuzAPI (which will not retry), and the patient's message is lost. This is especially dangerous for incoming STOP commands (opt-out), quiz responses, and patient follow-up replies — all critical clinical data.

**Why it happens:**
Evolution API wraps all events in a unified envelope with a consistent schema. WuzAPI passes through whatsmeow's native Go event types directly. Developers assume API interoperability at the schema level and reuse the existing `WebhookPayload` Pydantic model without checking actual WuzAPI payloads.

**How to avoid:**
1. Before writing any handler code, capture at least 10 real WuzAPI webhook payloads by pointing a test session at a local ngrok/cloudflare tunnel endpoint and triggering every event type: text message, media message, ReadReceipt, connection status.
2. Build WuzAPI-specific Pydantic models (`WuzAPIMessageEvent`, `WuzAPIReadReceiptEvent`) that match the actual captured schema. Do not reuse or extend Evolution API Pydantic models.
3. Add schema validation logging at the handler entry point that logs the raw payload keys and event type before any parsing — keep this active in staging indefinitely.
4. Write integration tests using the real captured payloads stored as JSON fixtures in `tests/fixtures/wuzapi/`. Never test with guessed or fabricated schemas.

**Warning signs:**
- Webhook endpoint returns 200 but no messages appear in the database
- `message.content` is None for all WuzAPI-routed incoming messages
- Opt-out handling (STOP/PARAR/CANCELAR) stops working silently after cutover
- Logs show "Parsing webhook event" but no "Message processed" or "Patient found" entries downstream

**Phase to address:**
Phase 1 (WuzAPIClient + webhook handler rewrite) — capture real payloads BEFORE writing parsers. Do not proceed to production cutover until integration tests use real captured WuzAPI payloads as fixtures.

---

### Pitfall 2: Brazilian 9th-Digit Split — Messages Silently Not Delivered to Some Patients

**What goes wrong:**
WhatsApp created a historical anomaly: mobile numbers in states that adopted the 9th digit before WhatsApp had those contacts registered (especially São Paulo DDD 11-19, Rio de Janeiro DDD 21/22/24, Espírito Santo DDD 27/28) have their WhatsApp account bound to the OLD 8-digit number. The stored patient phone may be `5511987654321` (9-digit) but the correct WhatsApp JID is `5511987654321@s.whatsapp.net` — except the actual JID WhatsApp responds to is `551187654321@s.whatsapp.net` (8-digit, no leading 9 after DDD).

When the system sends to `5511987654321@s.whatsapp.net`, whatsmeow may return a success acknowledgment but WhatsApp backend silently drops it, or returns error 479 ("number not on WhatsApp"). The patient — an oncology patient waiting for a follow-up — never receives the message. The system marks it SENT.

The existing `build_br_phone_variants()` in `app/schemas/validators/phone.py` already generates both 8-digit and 9-digit variants for patient lookup/matching, but this is not wired into the message send path. WuzAPI does not auto-resolve this — it sends to whatever JID you provide.

**Why it happens:**
Developers skip the WhatsApp JID lookup step and use the stored E.164 number directly, assuming it equals the WhatsApp JID. The `format_phone_for_whatsapp()` function in `phone.py` also doesn't resolve the JID — it only formats digits.

**How to avoid:**
1. Add a WuzAPI `/user/check` call (or equivalent WuzAPI endpoint for checking if a number is on WhatsApp) before the first send to each patient. This call accepts both the 8-digit and 9-digit variants and returns which JID is actually registered.
2. Cache the resolved JID in a new database field `patient.whatsapp_jid` (e.g., `551187654321@s.whatsapp.net`). Use this cached JID for all subsequent sends.
3. The existing `build_br_phone_variants()` function already generates both variants — wire its output into the JID resolution step as the input candidates.
4. If resolution fails for both variants, surface a `PhoneValidationError` and route the message to the DLQ rather than sending to an unverified JID.
5. During migration, run a one-time Celery task to resolve JIDs for all existing patients.

**Warning signs:**
- Messages marked SENT but patients (especially in São Paulo/Rio area codes) report never receiving them
- Error 479 appearing in WuzAPI response logs
- Zero incoming patient responses after cutover from São Paulo-based patients

**Phase to address:**
Phase 1 (WuzAPIClient core) — JID resolution must exist before any message sends. Phase 2 (patient data migration) — existing patients need JIDs resolved and cached as part of the cutover.

---

### Pitfall 3: Auth Header Name Change — All API Calls Fail With 401

**What goes wrong:**
Evolution API uses an `apikey` header (lowercase). WuzAPI uses `Authorization: {token}` (or `Token: {token}`) as the auth mechanism. The existing `EvolutionAPIClient` passes `{"apikey": settings.WHATSAPP_EVOLUTION_API_KEY}` in every request. If `WuzAPIClient` is built by refactoring the Evolution client without updating the header name, every API call returns HTTP 401.

Depending on error handling, this either raises `ExternalServiceError` correctly (if the 401 response is parsed), or triggers a retry storm if 401 is treated as a transient network failure. The Redis circuit breaker (`_evolution_breaker` / future `_wuzapi_breaker`) will open after 5 consecutive failures, blocking all sends for 60 seconds per cycle.

**Why it happens:**
Auth header differences are easy to miss in refactoring. The WuzAPI 401 response may not clearly state "wrong header name" — it may just return `{"error": "unauthorized"}`. Because the circuit breaker opens quickly on consecutive failures, the problem surfaces as a closed circuit, not as an obvious auth error.

**How to avoid:**
1. Make the auth header name an explicit constant: `WUZAPI_AUTH_HEADER = "Authorization"` rather than an inline string.
2. Write the WuzAPI health check call as the very first integration smoke test. If auth is broken, the health check fails fast and clearly.
3. Log the response status and body (not sensitive headers) on every failed API call.
4. Verify auth header in the WuzAPI dev instance before writing any other client code.

**Warning signs:**
- Circuit breaker opens immediately after deployment
- All API calls return HTTP 401 with no specific error body
- Health check component shows `wuzapi_session: unhealthy` immediately at startup

**Phase to address:**
Phase 1 (WuzAPIClient implementation) — first test to run in any integration smoke test suite.

---

### Pitfall 4: Message ID Format Differences Break Idempotency and Status Tracking

**What goes wrong:**
The system stores `message.whatsapp_id` for two critical purposes:
1. Idempotent webhook deduplication — `AtomicWebhookIdempotency` uses the message ID as the deduplication key
2. Status update matching — ReadReceipt events are matched to `Message` records by `whatsapp_id`

Evolution API returns message IDs in its own format (base64-encoded strings, e.g., `BAE5...`). WuzAPI returns whatsmeow-native message IDs from the send response JSON. If the WuzAPI client extracts the ID from the wrong JSON field (or the field name differs from what's assumed), `message.whatsapp_id` ends up as `None`.

When WuzAPI fires a `ReadReceipt` webhook for that message, the handler looks up `Message.whatsapp_id == incoming_id`, finds nothing, and silently drops the delivery confirmation. All messages remain in SENT state forever — DELIVERED and READ statuses never update. The dashboard shows all patients as "not read" even after they've read their messages.

**Why it happens:**
Developers check that the send returned HTTP 200 and assume `whatsapp_id` was stored correctly without verifying the field path from the actual WuzAPI response body. The WuzAPI response JSON field for the outbound message ID is inside a `data` sub-object, but the exact field name must be verified from real API responses, not assumed.

**How to avoid:**
1. Log the full send response body in development mode for every send — confirm which JSON field contains the message ID.
2. Write an explicit assertion test: send a test message, capture the response, extract `whatsapp_id`, assert it is non-None and non-empty string.
3. Add a runtime check: if `whatsapp_id` is None after a send that returned HTTP 200, log an ERROR and do not mark the message as SENT (mark as a new intermediate state or flag for investigation).
4. In the ReadReceipt handler, log a WARNING whenever no matching `Message` record is found for an incoming receipt ID — this surfaces idempotency mismatches immediately in production.

**Warning signs:**
- `message.whatsapp_id` is NULL in the database for all WuzAPI-sent messages
- DELIVERED/READ statuses never update after cutover despite messages being received
- ReadReceipt webhook events are processed (HTTP 200 returned) but produce no database changes

**Phase to address:**
Phase 1 (WuzAPIClient — verify send response field extraction). Phase 2 (webhook handler — ReadReceipt lookup tested with captured payloads).

---

### Pitfall 5: HMAC Validation — Wrong Header Name and Wrong Signing Body Cause All Webhooks to 403

**What goes wrong:**
Evolution API and WuzAPI use different HMAC mechanisms:
- **Evolution API:** Header is `X-Webhook-Signature` (or API-key based); current `WebhookValidatorMiddleware` looks for `X-Webhook-Signature` and tries both SHA256 and SHA1; some code uses `X-Signature` prefix stripping
- **WuzAPI:** Header is `x-hmac-signature` (lowercase); algorithm is SHA-256 only; signature is raw hex (no `sha256=` prefix)

The current `WebhookHandler.validate_signature()` in `app/integrations/evolution/webhook_handler.py` strips `sha256=`, `sha1=`, and `hmac-sha256=` prefixes. WuzAPI sends no prefix — stripping logic that expects a prefix on a plain hex value will try to match an empty string against the computed digest and fail.

Additionally: WuzAPI signs the **raw request bytes** (`Content-Type: application/json` → sign the raw JSON body string). FastAPI's `await request.json()` decodes and re-serializes the body, which may alter whitespace or key ordering. If the HMAC is computed against re-serialized JSON, validation fails even with the correct key.

**Why it happens:**
Body reading is a one-time operation in ASGI. If `await request.body()` is called twice (once for HMAC, once for JSON parsing), the second call may return empty bytes on some ASGI implementations. Alternatively, if `await request.json()` is called first (for parsing), the raw bytes are consumed and HMAC validation against the original bytes is impossible.

**How to avoid:**
1. Read raw body exactly once at handler entry: `body: bytes = await request.body()`, then pass bytes to HMAC validator and `json.loads(body)` separately.
2. Create a `WuzAPIHMACValidator` that is separate from `WebhookHMACValidator` — it must look for `x-hmac-signature` (lowercase), compute `hmac.new(key.encode(), body, hashlib.sha256).hexdigest()` with no prefix, and compare with `hmac.compare_digest()`.
3. Remove the SHA1 fallback path in the WuzAPI validator — WuzAPI only uses SHA256.
4. Ensure `WUZAPI_GLOBAL_HMAC_KEY` is at least 32 characters (WuzAPI requirement). Reject shorter keys at startup with a clear error.
5. Write a test: POST a known payload with a known key, compute expected hex, assert the validator returns True. POST with wrong key, assert False.

**Warning signs:**
- All WuzAPI webhooks returning 403
- "Webhook HMAC validation failed" logged for every incoming webhook
- `HMAC_FAILURE_BLOCK_THRESHOLD = 5` triggers blocking of WuzAPI's IP within seconds of deployment

**Phase to address:**
Phase 1 (security/HMAC update) — must be resolved before any production webhook processing. The existing block logic will deny all WuzAPI webhooks within 5 failures if this is wrong.

---

### Pitfall 6: LID Addressing — LGPD Art. 18 Opt-Out Failure Risk

**What goes wrong:**
WhatsApp introduced LID (Link ID) in 2025 as a privacy identifier that replaces phone-number-based JIDs in some contexts. Newer WhatsApp clients may participate in conversations using `sender@lid` format instead of `5511987654321@s.whatsapp.net`. When a patient with a newer WhatsApp client sends STOP/PARAR/CANCELAR, the incoming webhook from WuzAPI will contain `"Sender": "1234567890abcdef@lid"`.

The current opt-out handler, incoming message router, and patient lookup all assume the sender field contains a phone number JID. A `@lid` sender will fail all patient lookups. The result:
- The patient's opt-out request is silently dropped
- The patient continues receiving messages
- This is a LGPD Art. 18 violation (right to object to processing)
- In a healthcare context, this creates regulatory and reputational risk

**Why it happens:**
LID migration is gradual — most accounts don't switch immediately. Testing with a few phones may not trigger `@lid` senders, so the issue is invisible during development. The failure mode produces no error in the system — the webhook returns 200, WuzAPI considers it delivered, and the patient receives no confirmation that their opt-out was registered.

**How to avoid:**
1. When the sender JID ends in `@lid`, call WuzAPI's contact/user info endpoint to resolve the LID to a phone number using whatsmeow's internal LID→JID mapping store.
2. If LID→JID resolution fails (contact not yet in local store because they haven't initiated conversation through a non-LID session), queue the message for retry with exponential backoff.
3. Add a specific log alert at WARNING level for every `@lid` sender — this makes the migration scope visible.
4. Never drop a message from a `@lid` sender silently. If it cannot be resolved, route to DLQ for manual processing.

**Warning signs:**
- "Patient not found" warnings in logs for incoming messages after cutover
- Sender field in webhook event contains `@lid` suffix
- Opt-out commands not taking effect for a subset of patients (those with newer WhatsApp)

**Phase to address:**
Phase 2 (webhook handler — incoming message routing) — LID resolution must be in the incoming message handler from day one of WuzAPI operation. This cannot be deferred because a patient sending STOP with a LID address and not being opted out is a LGPD compliance failure.

---

### Pitfall 7: Instance vs Session Environment Variable Mismatch — Silent Misconfiguration

**What goes wrong:**
Evolution API uses an "instance" model where each WhatsApp number is a named instance. The entire application references `WHATSAPP_EVOLUTION_INSTANCE_NAME`, including `UnifiedWhatsAppService.__init__()` which falls back to `"default"` if the env var is absent. WuzAPI uses a "session" model where a user is identified by a token (`WUZAPI_SESSION_TOKEN`).

After migration, if `WHATSAPP_EVOLUTION_INSTANCE_NAME` is removed from Railway env but the new `WUZAPI_SESSION_TOKEN` is added with a different settings key name, the service silently uses `"default"` as the instance/session identifier. Depending on WuzAPI's multi-user setup, `"default"` may connect to no session, a wrong session, or the system may fail without a clear error.

There are also references to Evolution API settings throughout `health_check()`, `_send_via_direct_api()`, and `_send_via_queue()` that would need updating.

**Why it happens:**
A hard-cut migration tombstones old code but environment variable renaming is easy to miss in Railway's dashboard. The default fallback to `"default"` masks the missing configuration at startup, so the service initializes successfully but fails at first send.

**How to avoid:**
1. Before starting migration: `grep -r "WHATSAPP_EVOLUTION" --include="*.py" backend-hormonia/` to find every reference. Map each to its WuzAPI equivalent.
2. Add `required=True` (or equivalent) validation for the new WuzAPI env vars in `settings.py`. The application must refuse to start if `WUZAPI_SESSION_TOKEN` is missing — not fall back to `"default"`.
3. Add a startup health check that calls WuzAPI's `/session` endpoint and logs CRITICAL + alerts if the session is not connected. In production mode, refuse to process messages until session is verified.
4. Track all env var migrations in a checklist as part of the deployment story.

**Warning signs:**
- Application starts cleanly but all sends fail with "session not found" or "connection refused"
- Health check shows `wuzapi_session: unhealthy` immediately
- Logs contain `instance_name: "default"` in message metadata after migration

**Phase to address:**
Phase 1 (env var audit and startup validation) — must be the first task before any code migration. Phase 3 (cutover) — startup validation must be verified in staging before production deployment.

---

## Moderate Pitfalls

### Pitfall 8: Status Event Mapping — Semantics Differ Between Providers

**What goes wrong:**
Evolution API fires `MESSAGES_UPDATE` events with a `status` field containing values like `PENDING`, `SERVER_ACK`, `DELIVERY_ACK`, `READ`. WuzAPI fires `ReadReceipt` events with whatsmeow-native receipt types: `ServerAck`, `Delivered`, `Read`, `Played`. These are not 1:1 — `SERVER_ACK` maps to `ServerAck`, `DELIVERY_ACK` maps to `Delivered`, `READ` maps to `Read`, and `Played` (audio message played) has no Evolution equivalent.

If the status handler maps all `ReadReceipt` events to `DELIVERED` (a common shortcut to "just get something working"), the `READ` status is never recorded. Audit trails are inaccurate, and the dashboard permanently shows all messages as unread.

**How to avoid:**
Build an explicit mapping constant:
```python
WUZAPI_RECEIPT_TO_STATUS = {
    "ServerAck": MessageStatus.SENT,
    "Delivered": MessageStatus.DELIVERED,
    "Read": MessageStatus.READ,
    "Played": MessageStatus.READ,  # audio played is read-equivalent
}
```
Unknown receipt types should log WARNING and default to SENT (not FAILED). Add a test that sends a mock ReadReceipt event for each type and asserts the correct `MessageStatus` is stored.

**Phase to address:** Phase 2 (webhook handler + ReadReceipt processing).

---

### Pitfall 9: Media Handling — WuzAPI Delivers Media Differently Than Evolution API

**What goes wrong:**
When a patient sends media (image, audio document), Evolution API includes a URL the system can fetch. WuzAPI delivers media as either base64 in the webhook body or an S3 URL, controlled by the `mediaDelivery` setting (`base64`, `s3`, or `both`).

If `mediaDelivery` is `base64` (WuzAPI default if not configured) and the system expects a URL, the inbound media handler receives a large base64 blob it doesn't know how to handle. A single patient audio message (30-60 seconds of voice note) becomes a 0.5-2MB base64 string in the webhook payload — causing webhook handler memory spikes and potential timeout if processing is not fast enough.

**How to avoid:**
1. Configure WuzAPI with `mediaDelivery: s3` and configure an S3 bucket in the WuzAPI deployment. This is required for production.
2. Set S3 retention to 7 days (sufficient for retry windows in this system).
3. Update the inbound media handler to extract the S3 URL from the WuzAPI event, not to decode base64.
4. For the current system (which does not heavily process inbound media), configure graceful degradation: if neither S3 URL nor base64 is available, log WARNING and continue processing the text content of the message.

**Phase to address:** Phase 2 (webhook handler rewrite — media section).

---

### Pitfall 10: Rate Limiter Not Ported — Ban Risk From Sending Too Fast

**What goes wrong:**
The existing `RateLimiter` class in `evolution_client.py` (100 requests/60 seconds) throttles calls to Evolution API. WuzAPI itself applies no rate limiting — it sends to WhatsApp as fast as the client calls it. WhatsApp's backend enforces account-level limits and may flag numbers sending too many messages too quickly as spam, eventually suspending the account.

The existing rate limiter is tightly coupled to `EvolutionAPIClient`. If it is discarded along with the old client code without being ported to `WuzAPIClient`, the new client has no throttling. For a system sending daily follow-ups to an oncology patient cohort (potentially 100-500 messages per send cycle), this is a real ban risk.

Note: whatsmeow-backed tools (including WuzAPI) are unofficial WhatsApp API wrappers, not Meta Business API. The ToS risk is real. The mitigating factor for this system is that all messages are consent-based with active opt-out — which reduces spam detection risk but does not eliminate it.

**How to avoid:**
1. Port the `RateLimiter` class to `WuzAPIClient` unchanged as a starting point.
2. Start with a conservative limit: 60 messages per 60 seconds per session (slightly below the Evolution API limit) until behavior is validated.
3. Add random jitter (0.5–2.0 seconds) between consecutive messages to the same recipient number.
4. Monitor WuzAPI connection status via a Celery Beat task — if the session disconnects unexpectedly, alert immediately (may indicate account action by WhatsApp).

**Phase to address:** Phase 1 (WuzAPIClient) — rate limiter must be included from the first implementation, not added as a follow-up.

---

### Pitfall 11: Session Persistence — WuzAPI Requires Persistent Database or Loses Session on Restart

**What goes wrong:**
WuzAPI stores WhatsApp pairing keys and session state in a database (`DB_HOST` env var, supports PostgreSQL and SQLite). If the Railway deployment uses a default SQLite configuration with an ephemeral filesystem volume, the session data is lost on every container restart, requiring a QR code re-scan to re-link the WhatsApp number. This causes messaging downtime.

Railway's ephemeral storage is lost on deploy or container restart unless explicitly configured with persistent volumes.

**How to avoid:**
1. Configure WuzAPI with PostgreSQL (can use the existing AWS RDS in a dedicated schema, or a separate Railway PostgreSQL add-on).
2. Do not use SQLite in any environment except local development.
3. Test a restart cycle in staging: stop the WuzAPI service, restart it, and verify the session reconnects automatically within 60 seconds without QR re-scan.
4. Add a health check alert if WuzAPI session status shows "disconnected" for more than 5 minutes.

**Phase to address:** Phase 3 (deployment/infrastructure) — must be resolved before production cutover.

---

### Pitfall 12: Opt-Out Endpoint Routing — LGPD Compliance Gap

**What goes wrong:**
The opt-out handler (STOP/PARAR/CANCELAR) is currently registered at the Evolution webhook endpoint path. After migration, the WuzAPI session must be configured to POST webhooks to the new WuzAPI-specific endpoint path. If there is any path mismatch (WuzAPI posts to `/api/v2/webhooks/whatsapp/evolution/{instance_name}` which now returns 410 Gone, or WuzAPI posts to a path that FastAPI doesn't route), opt-out messages never reach the handler.

Patients cannot opt out via WhatsApp, which is a LGPD Art. 18 violation.

**How to avoid:**
1. The WuzAPI webhook URL configured in the WuzAPI session must exactly match the new FastAPI endpoint path.
2. Keep the old Evolution endpoint returning HTTP 410 (Gone) with a log message — this makes misconfiguration visible rather than failing silently.
3. Test opt-out command processing end-to-end in staging using a real WhatsApp send of "STOP" before any production cutover.
4. Add a Celery Beat monitoring job: "If zero opt-out commands were received in the last 48 hours AND the system has sent more than 50 messages in that window, fire an alert." Some opt-outs are expected from any active patient cohort — zero is suspicious.

**Phase to address:** Phase 2 (webhook routing) + Phase 3 (configuration verification and monitoring).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Reuse Evolution API Pydantic models for WuzAPI payloads | Less code to write | Silent field mismatches; data loss on every WuzAPI event type change | Never — WuzAPI schema is different enough to require its own models |
| Skip JID resolution, send to raw phone number | Simpler client code | Silent delivery failures for São Paulo/Rio patients with old 8-digit JIDs | Never in production — test with DDD 11 numbers before first send |
| Use base64 media delivery (`mediaDelivery: base64`) | No S3 setup required | Multi-MB webhook payloads; memory spikes; webhook timeout risk | Acceptable only for local development, never in staging/production |
| Skip HMAC validation in development | Faster local testing | Habit of skipping carries to staging; launches without validation | Acceptable in local dev only, guarded by `APP_ENVIRONMENT != "production"` |
| Port rate limiter but not adjust limits | Fast port from Evolution client | Evolution limits may not be appropriate for whatsmeow; start conservative | Port it, but reduce the limit 30% initially until WhatsApp behavior is validated |
| Keep Evolution circuit breaker name `"evolution_api"` | No Redis key changes | Redis circuit breaker keys are misleading post-migration; confusing during incidents | Functionally works but rename to `"wuzapi"` — low effort, prevents confusion |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| WuzAPI auth | Using `apikey` header copied from Evolution client | Use `Authorization: {token}` header (or `Token: {token}`) |
| WuzAPI webhook HMAC | Looking for `X-Webhook-Signature` or `sha256=` prefix | Look for `x-hmac-signature` (lowercase), raw hex with no prefix |
| WuzAPI HMAC signing | Signing re-parsed/re-serialized JSON | Sign raw request bytes (`await request.body()`) BEFORE any JSON parsing |
| WuzAPI send phone format | Appending `@s.whatsapp.net` manually before calling the API | WuzAPI's send endpoint accepts raw digits; it appends `@s.whatsapp.net` internally. Manually adding the suffix causes double-suffix errors. Verify against API.md. |
| WuzAPI ReadReceipt | Using Evolution-style `MESSAGES_UPDATE` event name in subscription | Subscribe to `ReadReceipt` event type in WuzAPI session configuration |
| WuzAPI media | Expecting a fetchable URL in webhook payload (Evolution behavior) | Configure `mediaDelivery: s3`; extract S3 URL from WuzAPI event |
| WuzAPI session lifecycle | Calling connect/disconnect per message send (Evolution instance pattern) | WuzAPI sessions are long-lived; call `/session/connect` once at startup; monitor connection status via health check |
| Circuit breaker name | Leaving `"evolution_api"` as the breaker name in Redis keys | Rename to `"wuzapi"` — existing keys are stale after migration |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| No JID caching (resolve on every send) | 200-500ms added per send; Celery task timeout risk | Cache resolved JID in `patient.whatsapp_jid`; resolve once, reuse for lifetime | At any scale — immediate latency regression |
| Base64 media in webhook payload | OOM on Railway container from large audio payloads; webhook handler timeout | Use S3 delivery; never base64 in production | At first voice note from a patient (~500KB-2MB base64 JSON body) |
| Missing rate limiter | WhatsApp account flagged for spam; connection drops; eventual ban | Port `RateLimiter` from Evolution client; reduce initial limit | During first large send cycle (100+ messages in one Celery Beat run) |
| HMAC key < 32 characters | WuzAPI rejects HMAC configuration; all webhooks fail | Generate 32-char minimum: `secrets.token_urlsafe(32)` | At WuzAPI startup configuration |
| Synchronous HTTP in async WuzAPIClient called from Celery | Worker blocks; throughput drops significantly | Use `httpx.AsyncClient` + `async_to_sync` bridge (established pattern in codebase) | Immediately at any message volume |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Not validating `x-hmac-signature` in production | Attackers can inject fake messages via webhook URL, including fake STOP commands (force-opting patients out without consent) or fake quiz responses | Validate HMAC in all non-dev environments; fail closed (403) if HMAC secret not configured in production |
| Logging full webhook payload | Webhook payloads contain patient phone numbers (PHI). LGPD Art. 46 violation | Log only event type, timestamp, message ID. Apply existing PII redaction to any log output from webhook handlers. Never log `Sender`, `Phone`, or message content fields. |
| Storing WuzAPI admin token in repository | Admin token controls all WuzAPI sessions; exposure = full WhatsApp account compromise | Store in Railway environment variables only; never in `.env` committed to repo; rotate immediately if leaked |
| Silently continuing when HMAC key is absent | Webhooks accepted without validation in all environments | Raise `StartupError` if `WUZAPI_HMAC_KEY` is absent in staging or production; only allow bypass in `development` environment |
| LID-addressed opt-out dropped silently | Patient who sent STOP via newer WhatsApp client continues receiving oncology follow-up messages (LGPD Art. 18 violation) | Log every `@lid` sender at WARNING; route unresolvable LIDs to DLQ for human review; never drop silently |

---

## "Looks Done But Isn't" Checklist

- [ ] **Webhook payload schema:** Integration test uses REAL captured WuzAPI webhook payloads as JSON fixtures — not mocked/guessed schemas. Verify at least: text message event, ReadReceipt event, connection status event.
- [ ] **JID resolution works for DDD 11 and DDD 21:** Send a test message to a number you control in São Paulo (DDD 11) and Rio (DDD 21). Confirm the message is received. Verify `patient.whatsapp_jid` is populated in the database.
- [ ] **HMAC validation rejects tampered payloads:** POST a known payload with a wrong `x-hmac-signature` — assert HTTP 403. POST with correct signature — assert HTTP 200.
- [ ] **ReadReceipt → READ status transition:** After sending a test message and opening it on WhatsApp, the `message.status` in the database changes to `READ` within 60 seconds.
- [ ] **Opt-out via WhatsApp works:** Send "STOP" from the test WhatsApp number. Verify `patient.messaging_stopped_at` is set and no further messages are sent to that patient.
- [ ] **Session persists across restart:** Stop the WuzAPI service container, wait 30 seconds, restart it. Verify the session reconnects without QR re-scan.
- [ ] **Rate limiter is active:** Trigger 70 message sends in one minute. Verify the system backs off, no HTTP 429 from WuzAPI, no ban signal, no connection drop.
- [ ] **Evolution env vars absent:** `WHATSAPP_EVOLUTION_API_URL`, `WHATSAPP_EVOLUTION_API_KEY`, `WHATSAPP_EVOLUTION_INSTANCE_NAME`, `WHATSAPP_EVOLUTION_WEBHOOK_URL` are NOT present in Railway staging environment after migration.
- [ ] **PII not logged in new handlers:** Inspect structured log output from WuzAPI webhook handler. No `sender`, `phone`, `Jid`, or `From` field values appear in log lines.
- [ ] **Circuit breaker renamed:** The Redis circuit breaker key prefix is `wuzapi` not `evolution_api`. Verify by checking Dragonfly keys after a deliberate circuit trip.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong webhook payload schema (silent data loss) | HIGH | 1. Fix parser. 2. Check DLQ for messages dropped during the bad-schema window. 3. Cross-reference sent messages vs DB to identify gap period. 4. For clinical messages missed: notify medical team, trigger manual re-contact. |
| Brazilian 9th-digit JID mismatch (delivery failure) | MEDIUM | 1. Identify affected patients (DDD 11/21/22/24/27/28 most likely). 2. Run JID resolution Celery task for affected patients. 3. Update `patient.whatsapp_jid`. 4. Re-send failed messages via DLQ retry. |
| HMAC misconfiguration (all webhooks rejected) | LOW | 1. Fix header name or HMAC key in settings. 2. Redeploy. 3. Check WuzAPI retry behavior — if WuzAPI does not retry rejected webhooks, incoming messages during the bad window are lost. |
| Auth header wrong (all sends fail) | LOW | 1. Fix `Authorization` header constant. 2. Redeploy. 3. Celery retry mechanism recovers in-flight messages within ~15 minutes via DLQ. |
| Session loss (QR required for re-auth) | MEDIUM | 1. Access WuzAPI dashboard. 2. Scan QR with the registered clinic WhatsApp number. 3. Reconnection takes ~30 seconds. 4. Messages during downtime go to DLQ and are retried automatically. |
| LID opt-out failure (LGPD violation) | HIGH | 1. Immediately implement LID→JID resolution. 2. Audit all incoming messages from cutover date for `@lid` senders. 3. Manually process any opt-out commands from LID senders. 4. If duration > 24 hours: assess LGPD Art. 48 notification obligation to ANPD. |
| WhatsApp account banned (unofficial API ToS violation) | VERY HIGH | 1. Contact WhatsApp support (no guaranteed resolution). 2. If clinic has a backup number, configure it in WuzAPI. 3. Notify medical team immediately — clinical follow-up is disrupted. 4. Assess whether Meta Business API is required as the permanent solution. |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Wrong webhook payload schema (silent data loss) | Phase 1: webhook handler rewrite | Integration tests use real captured WuzAPI payloads as fixtures; no mocked schemas |
| Brazilian 9th-digit JID mismatch | Phase 1: WuzAPIClient (JID resolution) + Phase 2: patient data migration | Send test message to DDD 11 number; `patient.whatsapp_jid` populated; message received |
| Auth header name change | Phase 1: WuzAPIClient implementation | Smoke test: call WuzAPI `/session` endpoint; assert HTTP 200 |
| Message ID format — idempotency broken | Phase 1: send path field extraction + Phase 2: ReadReceipt handler | After send: assert `message.whatsapp_id` non-null. After read: assert `message.status == READ` |
| HMAC header name and signing body | Phase 1: HMAC validator update | Wrong-signature POST → 403. Correct-signature POST → 200. |
| LID addressing (LGPD opt-out risk) | Phase 2: incoming message handler | Send STOP from newer WhatsApp account; verify `messaging_stopped_at` set within 60s |
| Instance vs session env var mismatch | Phase 1: env var audit + startup validation | Missing `WUZAPI_SESSION_TOKEN` → application refuses to start with clear error |
| Status event mapping (SENT/DELIVERED/READ) | Phase 2: ReadReceipt handler | End-to-end status transition test from send through receipt |
| Media delivery mode | Phase 2: inbound media handler | Patient sends image; system receives and stores correctly; no OOM |
| Rate limiter not ported | Phase 1: WuzAPIClient | 70 sends/minute load test; no ban signal; no connection drop |
| Session persistence | Phase 3: deployment configuration | Stop/start WuzAPI; verify reconnect without QR within 60s |
| Opt-out endpoint routing | Phase 2: webhook routing + Phase 3: config verification | Send STOP → `messaging_stopped_at` set; no further messages to that patient |

---

## Sources

- WuzAPI GitHub repository (asternic/wuzapi): https://github.com/asternic/wuzapi — API.md and README.md (HIGH confidence for endpoint format, auth header, HMAC header name)
- Brazil 9th-digit WhatsApp JID inconsistency (Zoko): https://www.zoko.io/learning-article/whatsapp-id-brazil-mexico (MEDIUM confidence — documented WhatsApp limitation specific to Brazil)
- Brazil 9th-digit WhatsApp inconsistency (Gupshup): https://support.gupshup.io/hc/en-us/articles/4407840924953 (MEDIUM confidence — same issue from different WhatsApp BSP)
- whatsmeow LID issue (#859): https://github.com/tulir/whatsmeow/issues/859 (MEDIUM confidence — real user report, LID error 479)
- LID/JID transition explanation (SprintHub): https://docs.sprinthub.com/en/news/behind-the-scenes-change-on-whatsapp-the-era-of-lid-and-jid-and-the-end-of-exposing-the-cell-phone-n (MEDIUM confidence — industry documentation of LID migration)
- Baileys v7 LID migration docs: https://baileys.wiki/docs/migration/to-v7.0.0/ (MEDIUM confidence — covers LID handling in whatsmeow-equivalent library)
- whatsmeow ban risk discussion (#567): https://github.com/tulir/whatsmeow/discussions/567 (MEDIUM confidence — community discussion on WhatsApp ban behavior with unofficial APIs)
- Production codebase: `app/integrations/evolution/webhook_handler.py`, `app/integrations/whatsapp/api/webhooks.py`, `app/middleware/webhook_validator.py`, `app/services/unified_whatsapp_service.py`, `app/schemas/validators/phone.py` (HIGH confidence — primary source of truth for what exactly needs to change)

---
*Pitfalls research for: Evolution API to WuzAPI migration — oncology clinic WhatsApp backend (v1.6)*
*Researched: 2026-03-01*
