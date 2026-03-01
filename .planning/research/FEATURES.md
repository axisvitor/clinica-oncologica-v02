# Feature Research

**Domain:** WhatsApp Provider Migration — Evolution API to WuzAPI (v1.6)
**Researched:** 2026-03-01
**Confidence:** MEDIUM overall (WuzAPI official API.md + routes.go HIGH confidence; webhook payload JSON structure MEDIUM — inferred from wmiau.go Go source; buttons/lists deprecation HIGH confidence from whatsmeow maintainer statement)

---

## Context

This research maps the existing Evolution API feature set (already built) against WuzAPI endpoints and
capabilities to surface: what maps directly, what needs adaptation, what is broken (gap), and what
WuzAPI adds that Evolution API does not have.

This is a **hard-cut migration** — no dual-provider mode, no feature toggles. The project is a
Brazilian oncology clinic backend. The WhatsApp layer is used exclusively for outbound patient
follow-up messages and inbound patient replies (STOP/opt-out, quiz answers). There is no live chat,
no group messaging, no broadcast lists in active production use.

---

## WuzAPI vs Evolution API: Authentication and Model Differences (Critical)

| Aspect | Evolution API | WuzAPI |
|--------|---------------|--------|
| Auth header | `apikey: <key>` (primary) | `Token: <key>` (primary) OR `Authorization: Bearer <key>` |
| Multi-tenancy unit | **Instance** (named, e.g. `"clinic-prod"`) | **User** (admin-created, token-per-user stored in SQLite/Postgres) |
| Instance/session in URL | `/{instance_name}` path segment on every endpoint | No instance name in URL; user identified by Token header |
| Backend runtime | Node.js + Baileys (WhatsApp Web emulation) | Go + whatsmeow (direct WebSocket to WhatsApp servers) |
| Memory / CPU footprint | High (Node.js + Puppeteer-era overhead) | Low (Go binary, direct protocol) |
| Config env vars (current) | `WHATSAPP_EVOLUTION_API_KEY`, `WHATSAPP_EVOLUTION_INSTANCE_NAME` | `WUZAPI_BASE_URL`, `WUZAPI_TOKEN` (user token) |

**Migration impact on service layer:** `default_instance_name` in `UnifiedWhatsAppService` becomes
unused. All API paths drop the `/{instance_name}` segment. The `Token` header replaces `apikey`.

---

## Feature Landscape

### Table Stakes (Must Work for Migration to be Complete)

These existing capabilities MUST have working equivalents in WuzAPI. Missing any = migration is broken.

| Feature | Evolution API | WuzAPI | Status | Complexity | Notes |
|---------|--------------|--------|--------|------------|-------|
| Send text message | `POST /message/sendText/{instance}` body: `{number, text}` | `POST /chat/send/text` body: `{Phone, Body}` | DIRECT MAP | LOW | Field rename only. Response ID at `data.Id` (WuzAPI) vs `message.key.id` (Evolution). |
| Send image | `POST /message/sendMedia/{instance}` body: `{mediaMessage: {mediatype, media: URL}}` | `POST /chat/send/image` body: `{Phone, Image: "data:image/jpeg;base64,...", Caption}` | ADAPTED | MEDIUM | WuzAPI requires base64 data URI. Evolution accepted URL. Download + encode step needed. |
| Send audio | `POST /message/sendMedia/{instance}` | `POST /chat/send/audio` body: `{Phone, Audio: "data:audio/ogg;base64,..."}` | ADAPTED | MEDIUM | Same base64 data URI requirement. |
| Send document | `POST /message/sendMedia/{instance}` | `POST /chat/send/document` body: `{Phone, Document: "data:application/...;base64,...", FileName}` | ADAPTED | MEDIUM | `FileName` field required for documents. |
| Send video | `POST /message/sendMedia/{instance}` | `POST /chat/send/video` body: `{Phone, Video: "data:video/mp4;base64,...", Caption}` | ADAPTED | MEDIUM | Same base64 requirement. |
| Inbound message webhook | Event: `MESSAGES_UPSERT`, endpoint: `/webhooks/whatsapp/evolution/{instance}` | Event: `type=Message`, single endpoint registered via `POST /webhook` | REWRITE | HIGH | Payload structure completely different. See webhook section below. |
| Delivery/read receipt webhook | Event: `MESSAGES_UPDATE` | Event: `type=ReadReceipt` | REWRITE | HIGH | Different event name, different payload shape. See webhook section below. |
| HMAC webhook validation | Header: `X-Webhook-Signature` or `X-Evolution-Signature`, SHA-256 | Header: `x-hmac-signature`, SHA-256 | ADAPTED | LOW | `WebhookHMACValidator.validate_signature()` logic unchanged. Header lookup key changes. HMAC key set via `POST /session/hmac/config`. |
| QR code for session | `GET /instance/qrcode/{instance}` → `qrcode.code` | `GET /session/qr` → `data.QRCode` (base64 PNG) | ADAPTED | LOW | Response field path changes. |
| Session status | `GET /instance/connectionState/{instance}` → `instance.state == "open"` | `GET /session/status` → `data.Connected` (bool) + `data.LoggedIn` (bool) | ADAPTED | LOW | Different response shape; same semantics. |
| Session connect | `POST /instance/create` + QR scan | `POST /session/connect` body: `{Subscribe: ["Message","ReadReceipt"], Immediate: false}` | ADAPTED | LOW | Subscribe list sets which events trigger webhooks. Required at startup. |
| Session disconnect / logout | `PUT /instance/restart/{instance}` + `DELETE /instance/logout/{instance}` | `POST /session/disconnect` + `POST /session/logout` | ADAPTED | LOW | Different verbs. Disconnect keeps session; logout removes pairing. |
| WhatsApp number check | `POST /chat/whatsappNumbers/{instance}` body: `{numbers: [...]}` | `POST /user/check` body: `{Phone: ["5511..."]}` | ADAPTED | LOW | Different endpoint and field name. |
| LGPD opt-out handler (STOP/PARAR) | Parsed from `MESSAGES_UPSERT` payload `message.conversation` field | Parsed from `type=Message` event `event.Message.conversation` field | ADAPTED | LOW | Same logic; different extraction path in new payload parser. |
| Idempotency (Redis SET NX) | Keyed on `key.id` from Evolution payload | Keyed on `event.Info.ID` from WuzAPI payload | ADAPTED | LOW | Same Redis pattern; extraction path changes. |
| Circuit breaker on API calls | `_evolution_breaker` wrapping `EvolutionAPIClient` | Same pattern wrapping `WuzAPIClient` | REUSE | LOW | Rename breaker to `"wuzapi_api"`. Thresholds unchanged. |
| Message queue + DLQ | Redis queue + DLQ, provider-agnostic layer | Unchanged | REUSE | LOW | No change needed in queue or DLQ. |
| Phone normalization | `normalize_phone()` → E.164 raw digits (e.g. `5511999887766`) | Same raw digit format for send requests | REUSE | LOW | Phone format for send is identical. JID extraction from webhook differs (see below). |

---

### Webhook Payload: Evolution API vs WuzAPI (Critical Detail)

**Evolution API — `MESSAGES_UPSERT` payload (what the current code parses):**
```json
{
  "event": "MESSAGES_UPSERT",
  "instance": "clinic-prod",
  "data": {
    "messages": [
      {
        "key": {
          "id": "3EB0XABCDEF1234",
          "fromMe": false,
          "remoteJid": "5511999887766@s.whatsapp.net"
        },
        "message": {
          "conversation": "PARAR"
        },
        "messageTimestamp": 1706500000
      }
    ]
  }
}
```

**WuzAPI — `Message` event payload (MEDIUM confidence — inferred from wmiau.go source code):**
```json
{
  "type": "Message",
  "event": {
    "Info": {
      "ID": "3EB0XABCDEF1234",
      "Chat": { "User": "5511999887766", "Server": "s.whatsapp.net" },
      "Sender": { "User": "5511999887766", "Server": "s.whatsapp.net" },
      "IsFromMe": false,
      "IsGroup": false,
      "PushName": "Joao Silva",
      "Timestamp": "2024-01-29T10:30:00Z",
      "Type": "text"
    },
    "Message": {
      "conversation": "PARAR"
    }
  }
}
```
For media messages, `event.Message` contains `imageMessage`, `audioMessage`, `documentMessage`,
or `videoMessage` instead of (or in addition to) `conversation`. Media binary is NOT included
in the webhook payload by default — must call download endpoints or configure S3 delivery.

**WuzAPI — `ReadReceipt` event payload (MEDIUM confidence — inferred from wmiau.go source):**
```json
{
  "type": "ReadReceipt",
  "state": "Read",
  "event": {
    "MessageIDs": ["3EB0XABCDEF1234"],
    "Timestamp": "2024-01-29T10:31:00Z",
    "Chat": { "User": "5511999887766", "Server": "s.whatsapp.net" },
    "Sender": { "User": "5511999887766", "Server": "s.whatsapp.net" },
    "Type": "read"
  }
}
```
`state` values: `"Read"` (recipient read), `"ReadSelf"` (sender read their own), `"Delivered"`.
Maps to Evolution's `update.status` values (2=DELIVERED, 3=READ).

**Key structural differences to handle in new webhook handler:**
- WuzAPI uses a single callback URL for ALL events (not per-event path like Evolution's `/{instance}/{event_name}`)
- Event type discriminated via top-level `type` field (`"Message"`, `"ReadReceipt"`, `"Presence"`, `"HistorySync"`, `"ChatPresence"`)
- No `instance` field in payload — instance implicit per user token
- Message ID: `event.Info.ID` (not `data.messages[0].key.id`)
- Phone: `event.Info.Chat.User` (digits only, not full JID string)
- Text content: `event.Message.conversation` (same field name as Evolution's `message.conversation`)
- The token field was removed from payloads in a recent security fix (issue #160 + issue #232)

---

### Phone Number Format

| Context | Evolution API | WuzAPI |
|---------|---------------|--------|
| Send request body | Raw digits: `"5511999887766"` | Raw digits: `"5511999887766"` (identical) |
| Webhook inbound (JID) | String: `"5511999887766@s.whatsapp.net"` | Object: `{"User": "5511999887766", "Server": "s.whatsapp.net"}` |
| Phone extraction from webhook | `key.remoteJid.split("@")[0]` | `event.Info.Chat.User` (already digits, no split needed) |

**Migration impact:** `normalize_phone()` and the BR phone validation pipeline are unchanged. Only
the extraction path from the incoming webhook payload changes (object field vs string split).

---

### Message ID in Send Response

| Provider | Response Path | Example |
|----------|--------------|---------|
| Evolution API | `response["message"]["key"]["id"]` | `"3EB0XABCDEF1234"` |
| WuzAPI | `response["data"]["Id"]` | `"90B2F8B13FAC8A9CF6B06E99C7834DC5"` |

The existing code in `evolution_client.send_text_message()` extracts via `message_data.get("key", {}).get("id")`.
The new `WuzAPIClient.send_text_message()` must extract via `response_data.get("data", {}).get("Id")`.
This propagates to `message.whatsapp_id` assignment in `UnifiedWhatsAppService._send_via_direct_api()`.

---

### Media Sending: URL vs Base64 (Critical Adaptation)

| Provider | Image send method | Document send method |
|----------|--------------------|----------------------|
| Evolution API | URL string: `mediaMessage.media = "https://..."` | URL string: same |
| WuzAPI | Base64 data URI: `"Image": "data:image/jpeg;base64,..."` | Base64 data URI: `"Document": "data:application/pdf;base64,..."` |

**This is the most significant technical adaptation.** The existing code passes URLs directly to
Evolution API. WuzAPI requires downloading the media and base64-encoding it before the API call.

**Required new utility:** `async def fetch_and_encode_media(url: str, max_size_bytes: int = 16_000_000) -> str`
that downloads the URL, validates size, and returns a data URI string. Must propagate `ExternalServiceError`
on download failure so Celery retry logic picks it up.

**Confidence on format requirement:** HIGH (confirmed from API.md examples with explicit base64 data URI strings)

---

### Buttons and List Messages: BROKEN in WuzAPI (Critical Gap)

| Feature | Evolution API | WuzAPI | Status |
|---------|--------------|--------|--------|
| Button messages | `POST /message/sendButtons/{instance}` | `POST /chat/send/buttons` (route exists) | BROKEN |
| List messages | `POST /message/sendList/{instance}` | `POST /chat/send/list` (route exists) | BROKEN |

**Why broken:** WhatsApp deprecated button/list messages for third-party WebSocket clients in 2022.
The whatsmeow library (which WuzAPI is built on) cannot send these messages — the maintainer stated
explicitly: *"Buttons are deprecated by WhatsApp and cannot be sent anymore. You can only send button
messages via the WhatsApp Business Platform API."* The routes exist in WuzAPI but the underlying
library call fails or is silently ignored.

**Impact on this project:** LOW — the current codebase already maps `MessageType.BUTTON` and
`MessageType.LIST` to `WhatsAppMessageType.TEXT` in `UnifiedWhatsAppService._convert_to_queue_request()`.
This fallback is already production behavior. No regression.

---

### Differentiators (WuzAPI Features Evolution API Lacks)

| Feature | Value for This Project | Complexity to Adopt | Notes |
|---------|------------------------|---------------------|-------|
| Direct WebSocket to WhatsApp (no Puppeteer/Chrome) | Lower memory, faster reconnects, fewer disconnections — main reason for migration | LOW (inherent, no code needed) | Stability improvement without code change. |
| Poll messages (`POST /chat/send/poll`) | N/A for oncology follow-up | LOW | Not needed for this use case. |
| React to messages (`POST /chat/react`) | N/A | LOW | Not needed. |
| Mark messages read (`POST /chat/markread`) | Could mark patient replies as read after opt-out processing | LOW | Minor UX improvement, P3. |
| S3 media delivery on inbound webhooks | Inbound patient media (images, audio) auto-uploaded to S3; webhook gets URL | MEDIUM | Useful only if patients send media at scale. Not current use case. |
| RabbitMQ event queue integration | Alternative event delivery mechanism | HIGH | Out of scope. Requires new MQ infrastructure. |
| Per-user SOCKS5 proxy (`POST /session/proxy`) | Route WhatsApp traffic through proxy per number | MEDIUM | Not needed for single-clinic deployment. |
| PairPhone authentication (`POST /session/pairphone`) | Pair without QR scan, useful for automated deployment | LOW | Operational convenience, not required for v1.6. |
| LID resolution (`GET /user/lid/{jid}`) | Resolve WhatsApp privacy LID to phone number | LOW | Edge case; only relevant if patients have privacy-mode contacts. |
| Message editing (`POST /chat/send/edit`) | Edit a previously sent message | LOW | Not needed for template-based follow-ups. |
| Delete sent messages (`POST /chat/delete`) | Retract a sent message | LOW | Not needed. |
| Get message history (`GET /chat/history`) | Retrieve historical messages | LOW | Not needed; messages tracked in PostgreSQL. |

---

### Anti-Features (Do Not Build in v1.6)

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Dual-provider mode (Evolution + WuzAPI simultaneously) | "Safe rollout" | Doubles complexity: two clients, two webhook parsers, two config sets, two test suites. PROJECT.md explicitly forbids this. | Hard-cut as specified. Test coverage handles safety. |
| Interactive buttons via WuzAPI | Replace `MessageType.BUTTON` | Buttons are broken in whatsmeow/WuzAPI (see above). Route exists but call fails. | Keep existing TEXT fallback — already production behavior. |
| Interactive list messages via WuzAPI | Replace `MessageType.LIST` | Same issue as buttons. | Keep existing TEXT fallback. |
| S3 for outbound media encoding | Avoid base64 encoding step | Requires new S3 bucket, IAM policy, WuzAPI S3 config endpoints. Over-engineered for the clinic's low media volume. | Download + base64 encode in `WuzAPIClient` with 16 MB size guard. |
| RabbitMQ event queue | Better event delivery guarantees | New infrastructure dependency not present in current stack. No value over existing Redis DLQ pattern. | Keep Redis webhook HTTP delivery + DLQ. |
| Replacing `UnifiedWhatsAppService` architecture | "Simplify code while migrating" | The unified service is well-tested (v1.4/v1.5 work). Replacing it expands scope and destabilizes existing test suite. | Swap `EvolutionAPIClient` → `WuzAPIClient` inside the existing service. |
| Async aiohttp client in WuzAPIClient | Reuse Evolution's aiohttp pattern | httpx is already in the project's dependency tree (FastAPI async ecosystem). httpx async client is idiomatic for Python 3.13 async. | Use `httpx.AsyncClient` in `WuzAPIClient`. |

---

## Feature Dependencies

```
WuzAPI User Setup (POST /admin/users) [one-time infra step]
    └──required by──> All WuzAPI API calls (no user = no token = 401)

WuzAPI Session Connect (POST /session/connect)
    └──required by──> All send endpoints
    └──sets up──> Webhook event subscriptions (Subscribe: ["Message", "ReadReceipt"])

WuzAPI HMAC Config (POST /session/hmac/config)
    └──required by──> Secure webhook validation
    └──reuses──> WebhookHMACValidator.validate_signature() [unchanged logic]
    └──changes──> Header name: x-hmac-signature (not X-Webhook-Signature)

WuzAPIClient (new)
    └──replaces──> EvolutionAPIClient
    └──uses──> httpx.AsyncClient (not aiohttp)
    └──requires──> fetch_and_encode_media() helper for image/audio/document/video

fetch_and_encode_media() helper (new)
    └──required by──> WuzAPIClient.send_image(), send_audio(), send_document(), send_video()
    └──raises──> ExternalServiceError on download failure (for Celery retry)

WuzAPI Message Webhook Handler (new)
    └──replaces──> handle_message_upsert() + Evolution payload parsing
    └──reuses──> AtomicWebhookIdempotency (extraction path: event.Info.ID)
    └──reuses──> WebhookHMACValidator (header: x-hmac-signature)
    └──reuses──> opt-out handler (extraction path: event.Info.Chat.User + event.Message.conversation)
    └──reuses──> rate limiting, HMAC blocking, IP whitelist logic [unchanged]

WuzAPI ReadReceipt Webhook Handler (new)
    └──replaces──> handle_message_update() + Evolution MESSAGES_UPDATE parsing
    └──reuses──> MessageStatusHandler (maps state: "Read"→READ, "Delivered"→DELIVERED)

Environment Variables Migration
    └──removes──> WHATSAPP_EVOLUTION_API_URL, WHATSAPP_EVOLUTION_API_KEY, WHATSAPP_EVOLUTION_INSTANCE_NAME
    └──adds──> WHATSAPP_WUZAPI_BASE_URL, WHATSAPP_WUZAPI_TOKEN, WHATSAPP_WUZAPI_WEBHOOK_SECRET

Evolution API Tombstone
    └──requires──> WuzAPIClient complete and tested
    └──tombstones──> evolution_client.py, mock_evolution.py
    └──updates shim──> unified_whatsapp_service.py (EvolutionAPIClient import → WuzAPIClient)
```

### Dependency Notes

- **Session must be connected before sends:** Unlike Evolution which uses named instances that can
  persist across restarts, WuzAPI requires an explicit `POST /session/connect` call (with Subscribe list)
  after each process restart. Health check and startup logic must include this reconnect step.
- **Media base64 adds latency to send path:** For each media message, the system downloads the URL and
  base64-encodes it synchronously before calling WuzAPI. For a 1 MB PDF, this is ~100-200ms of extra latency.
  This is acceptable for the clinic's async Celery task pipeline but must be surfaced in monitoring.
- **HMAC key is per-user in WuzAPI:** Call `POST /session/hmac/config` once at startup or during session
  setup. The key should match `WHATSAPP_WUZAPI_WEBHOOK_SECRET` (same value as former `WHATSAPP_EVOLUTION_WEBHOOK_SECRET`).
- **Single webhook URL for all event types:** WuzAPI sends all events (Message, ReadReceipt, Presence)
  to the same webhook URL. The new handler must switch on `payload["type"]` at the top, unlike the current
  Evolution handler that uses path-based event routing (`/evolution/{instance}/{event_name}`).

---

## MVP Definition (v1.6 Scope)

### Launch With (v1.6 — Hard Cut Required)

- [ ] `WuzAPIClient` replacing `EvolutionAPIClient` — httpx async, all send endpoints
- [ ] Send text: `POST /chat/send/text` with `Phone` + `Body` fields, response ID from `data.Id`
- [ ] Send media (image/audio/document/video): base64 data URI via respective endpoints
- [ ] `fetch_and_encode_media()` utility with 16 MB size guard and `ExternalServiceError` propagation
- [ ] Inbound message webhook: parse `type=Message`, extract phone from `event.Info.Chat.User`, text from `event.Message.conversation`
- [ ] ReadReceipt webhook: parse `type=ReadReceipt`, map `state` to `MessageStatus.DELIVERED|READ`
- [ ] HMAC validation: use existing `WebhookHMACValidator` with `x-hmac-signature` header
- [ ] Single webhook endpoint (not per-event-path) registered with WuzAPI via `POST /webhook`
- [ ] Session status: `GET /session/status` → `data.Connected`
- [ ] QR code: `GET /session/qr` → `data.QRCode`
- [ ] Session connect/disconnect/logout: adapted to WuzAPI paths and response shapes
- [ ] Opt-out handler adapted to WuzAPI phone extraction
- [ ] Idempotency: extraction of message ID from `event.Info.ID`
- [ ] Auth: `Token: <key>` header in all WuzAPI requests
- [ ] Environment variables: `WHATSAPP_WUZAPI_BASE_URL`, `WHATSAPP_WUZAPI_TOKEN`, `WHATSAPP_WUZAPI_WEBHOOK_SECRET`
- [ ] Settings: remove `WHATSAPP_EVOLUTION_*` config class, add `WHATSAPP_WUZAPI_*`
- [ ] Evolution API code tombstoned: `evolution_client.py`, `mock_evolution.py`
- [ ] Tests: updated for WuzAPI payload contracts (send response, webhook payloads)

### Add After Validation (v1.x)

- [ ] `POST /chat/markread` — mark patient messages read after processing (minor UX)
- [ ] S3 delivery for inbound patient media — only if patients send images/audio at scale
- [ ] LID resolution — only if `@lid` JIDs appear in production payloads

### Future Consideration (v2+)

- [ ] PairPhone auth (`POST /session/pairphone`) — automated QR-less session setup
- [ ] RabbitMQ integration — only if HTTP webhook delivery proves unreliable at scale
- [ ] Multi-user WuzAPI support — only if clinic expands to multiple WhatsApp numbers

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Text message send | HIGH (core function) | LOW | P1 |
| Auth header update (`Token` not `apikey`) | HIGH (nothing works without) | LOW | P1 |
| Inbound message webhook parser | HIGH (STOP/opt-out + replies) | HIGH | P1 |
| ReadReceipt webhook parser | HIGH (delivery tracking) | MEDIUM | P1 |
| Media send with base64 adaptation | HIGH (PDF reports to patients) | MEDIUM | P1 |
| `fetch_and_encode_media()` utility | HIGH (required for media) | MEDIUM | P1 |
| HMAC validation update | HIGH (security) | LOW | P1 |
| Session management (connect, status, QR) | HIGH (health checks, reconnect) | LOW | P1 |
| Environment variable migration | HIGH (deployment blocker) | LOW | P1 |
| Evolution tombstone | MEDIUM (code hygiene) | LOW | P1 |
| Test suite update | HIGH (regression safety) | HIGH | P1 |
| Mark-read endpoint | LOW (minor UX) | LOW | P3 |
| S3 inbound media delivery | LOW (edge case) | MEDIUM | P3 |
| Buttons/lists via WuzAPI | NONE (broken in whatsmeow) | N/A | SKIP |

---

## Known Gaps: Evolution Features Not Available or Broken in WuzAPI

| Gap | Current Evolution Usage | Impact | Mitigation |
|-----|------------------------|--------|------------|
| **Button messages** | `MessageType.BUTTON` mapped to TEXT already in `_convert_to_queue_request()` | NONE — fallback exists | Keep existing TEXT fallback. |
| **List messages** | `MessageType.LIST` mapped to TEXT already | NONE — fallback exists | Keep existing TEXT fallback. |
| **Instance health endpoint with `phone_number` + `profile_name`** | `health_check()` returns `phone_number`, `profile_name` fields (informational) | LOW | WuzAPI `GET /session/status` returns only `Connected` + `LoggedIn`. Remove those optional fields from health result dict. |
| **URL-based media sending** | Media URLs passed directly to Evolution | MEDIUM — requires new download step | `fetch_and_encode_media()` utility. |
| **Per-event-path webhook routing** | `/evolution/{instance}/{event_name}` path routing | LOW — architecture only | New single-endpoint handler switching on `payload["type"]`. |
| **`MESSAGES_DELETE` event** | Not actively used (unhandled, logged as unknown) | NONE | WuzAPI has no equivalent DELETE event in standard mode. |
| **`CONTACTS_UPSERT`, `CHATS_UPSERT`** | Handled but low production value | LOW | WuzAPI does not emit these as webhook events in standard config. Events not subscribed. |

---

## Sources

- [WuzAPI GitHub repository](https://github.com/asternic/wuzapi) — official source (HIGH confidence)
- [WuzAPI API.md](https://github.com/asternic/wuzapi/blob/main/API.md) — send text, send image, send audio, send document, send video request/response format (HIGH confidence)
- [WuzAPI routes.go](https://github.com/asternic/wuzapi/blob/main/routes.go) — complete route list including /chat/send/buttons and /chat/send/list (HIGH confidence)
- [WuzAPI wmiau.go](https://github.com/asternic/wuzapi/blob/main/wmiau.go) — webhook event dispatch code, postmap structure for Message and ReadReceipt events (MEDIUM confidence — inferred from Go source inspection)
- [whatsmeow events package](https://pkg.go.dev/go.mau.fi/whatsmeow/types/events) — `events.Message` and `events.Receipt` struct definitions with field names (HIGH confidence)
- [whatsmeow discussion #534: buttons deprecated](https://github.com/tulir/whatsmeow/discussions/534) — maintainer: "Buttons are deprecated by WhatsApp and cannot be sent anymore" (HIGH confidence)
- [DEV.to: buttons deprecated by WhatsApp Web libraries](https://dev.to/purpshell/buttons-and-lists-get-deprecated-by-many-libraries-54h) — timeline: Aug 2021 initial block, Apr 2022 second patch, May 2022 final block (HIGH confidence)
- [WuzAPI issue #160](https://github.com/asternic/wuzapi/issues/160) — token removed from webhook payloads for security (MEDIUM confidence)
- [WuzAPI issue #232](https://github.com/asternic/wuzapi/issues/232) — confirms token field removed from webhook JSON (MEDIUM confidence)
- Codebase: `backend-hormonia/app/integrations/whatsapp/services/evolution_client.py` — current Evolution API send patterns, header format, response parsing (HIGH confidence)
- Codebase: `backend-hormonia/app/integrations/whatsapp/api/webhooks.py` — current webhook handler, HMAC validation, idempotency, event routing (HIGH confidence)
- Codebase: `backend-hormonia/app/services/unified_whatsapp_service.py` — service layer contracts, circuit breaker, retry policies (HIGH confidence)
- Codebase: `backend-hormonia/app/integrations/whatsapp/security/hmac_validator.py` — existing HMAC validator (HIGH confidence)

---

*Feature research for: WuzAPI migration — Evolution API replacement (oncology WhatsApp backend v1.6)*
*Researched: 2026-03-01*
