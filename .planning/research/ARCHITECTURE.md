# Architecture Research

**Domain:** WhatsApp provider migration (Evolution API -> WuzAPI) in oncology backend
**Researched:** 2026-03-01
**Confidence:** HIGH (official WuzAPI docs fetched + codebase fully read)

---

## Standard Architecture

### Current WhatsApp Integration Map (before migration)

```
Outbound (sending):
  Celery Tasks / API Handlers
       |
       v
  UnifiedWhatsAppService          <- canonical facade (KEEP, adapt)
  app/services/unified_whatsapp_service.py
       |
       +-- direct mode --> EvolutionAPIClient (aiohttp, Stack B)
       |                   app/integrations/whatsapp/services/evolution_client.py
       |
       +-- queue mode  --> WhatsAppMessageService
                           app/integrations/whatsapp/services/message_service.py
                                |
                                v
                           EvolutionAPIClient (same Stack B)
                           + MessageQueue (Redis)

  IdempotentMessageSender         <- secondary send path (ADAPT then tombstone Evolution)
  app/domain/messaging/delivery/idempotent_sender.py
       |
       v
  EvolutionClient (httpx, Stack A, structlog)
  app/integrations/evolution/client.py

Inbound (webhooks):
  POST /webhooks/whatsapp/*
  app/integrations/whatsapp/api/webhooks.py
       |
       +-- HMAC validation --> WebhookHMACValidator
       |
       +-- Message events  --> message_extractor.py
       |                       (parses Evolution Baileys JSON:
       |                        key.remoteJid, key.participant,
       |                        message.conversation, LID resolution)
       |
       +-- Status events   --> StatusWebhookHandler
                               (maps PENDING/SENT/DELIVERED/READ/FAILED)
                               (idempotency via Redis SET NX)
```

### Target WhatsApp Integration Map (after WuzAPI migration)

```
Outbound (sending):
  Celery Tasks / API Handlers
       |
       v
  UnifiedWhatsAppService          <- KEEP, swap internal client reference
  app/services/unified_whatsapp_service.py
       |
       +-- direct mode --> WuzAPIClient (httpx async)       <- NEW
       |                   app/integrations/wuzapi/client.py
       |
       +-- queue mode  --> WhatsAppMessageService           <- ADAPT
                           (swap EvolutionAPIClient -> WuzAPIClient)
                           + MessageQueue (Redis, unchanged)

Inbound (webhooks):
  POST /webhooks/wuzapi                               <- NEW route
  app/integrations/wuzapi/api/webhooks.py
       |
       +-- HMAC validation (header: x-hmac-signature, SHA-256)
       |                    <- WebhookHMACValidator KEEP (header name is the only change)
       |
       +-- type == "Message"    --> WuzAPIMessageExtractor  <- NEW
       |                            (parses WuzAPI JSON:
       |                             event.Info.ID, event.Info.Sender,
       |                             event.Message.Conversation, token field)
       |
       +-- type == "ReadReceipt" --> StatusWebhookHandler   <- ADAPT
                               (map WuzAPI Receipt.Type "read" to MessageStatus.READ)
```

---

## Component Responsibilities

| Component | Current State | Action | Responsibility After Migration |
|-----------|--------------|--------|-------------------------------|
| `UnifiedWhatsAppService` | Uses `EvolutionAPIClient` directly | ADAPT | Facade stays; swaps client reference to `WuzAPIClient` |
| `EvolutionAPIClient` (Stack B) | Canonical send client, aiohttp | TOMBSTONE | Replaced by `WuzAPIClient` |
| `EvolutionClient` (Stack A) | Legacy httpx client, structlog | TOMBSTONE | Dead once `IdempotentMessageSender` is updated |
| `IdempotentMessageSender` | Uses Stack A `EvolutionClient` | ADAPT | Swap import to `WuzAPIClient`; keep idempotency logic intact |
| `WhatsAppMessageService` | Wraps `EvolutionAPIClient` | ADAPT | Constructor injection: accept `WuzAPIClient` |
| `webhooks.py` (Evolution) | Parses Evolution Baileys JSON | TOMBSTONE | Replaced by `wuzapi/api/webhooks.py` |
| `message_extractor.py` | Evolution payload parser | TOMBSTONE | Replaced by `WuzAPIMessageExtractor` |
| `StatusWebhookHandler` | Maps Evolution status strings | ADAPT | Status string mapping update for ReadReceipt event shape |
| `WebhookHMACValidator` | Algorithm-agnostic SHA-256/512 | KEEP | Already handles SHA-256; just change header name in caller |
| `phone_normalizer.py` | E.164 + LID resolution via Evolution | ADAPT | Remove LID resolution (WuzAPI has no LID); keep E.164 normalization |
| `IntegrationsSettings` | `WHATSAPP_EVOLUTION_*` env vars | ADAPT | Add `WHATSAPP_WUZAPI_*` vars; deprecate Evolution vars |
| `MessageRequest` (Pydantic) | Has `instance_name` field | ADAPT | `instance_name` no longer required; WuzAPI identifies session via token |

---

## Recommended Project Structure (after migration)

```
backend-hormonia/app/integrations/
|
+-- evolution/                          # TOMBSTONED (keep files, add ImportError sentinels)
|   +-- client.py                       # Tombstone: "Replaced by wuzapi in v1.6"
|   +-- message_sender.py               # Tombstone
|   +-- request_handler.py              # Tombstone
|   +-- webhook_handler.py              # Tombstone
|
+-- whatsapp/                           # Keep structure, migrate internals
|   +-- api/
|   |   +-- webhooks.py                 # TOMBSTONE: Evolution webhook handler
|   |   +-- routes.py                   # Keep (admin routes, health checks, update health)
|   +-- models/
|   |   +-- message.py                  # ADAPT: remove Evolution-specific field comments
|   +-- services/
|   |   +-- evolution_client.py         # TOMBSTONE
|   |   +-- message_service.py          # ADAPT: inject WuzAPIClient
|   |   +-- mock_evolution.py           # TOMBSTONE (replace with mock_wuzapi.py)
|   +-- security/
|       +-- hmac_validator.py           # KEEP (algorithm-agnostic, unchanged)
|
+-- wuzapi/                             # NEW package
    +-- __init__.py
    +-- client.py                       # NEW: WuzAPIClient (httpx async, Token auth)
    +-- errors.py                       # NEW: WuzAPIError exception hierarchy
    +-- models.py                       # NEW: WuzAPI request/response Pydantic models
    +-- mock_wuzapi.py                  # NEW: mock for testing
    +-- api/
        +-- __init__.py
        +-- webhooks.py                 # NEW: WuzAPI webhook router (/webhooks/wuzapi)
```

```
backend-hormonia/app/services/webhook/
+-- utils/
|   +-- message_extractor.py            # TOMBSTONE (Evolution parser)
|   +-- wuzapi_message_extractor.py     # NEW: WuzAPI payload parser
|   +-- phone_normalizer.py             # ADAPT: remove LID resolution methods
+-- handlers/
    +-- status_handler.py               # ADAPT: add WuzAPI ReadReceipt mapping
```

---

## Architectural Patterns

### Pattern 1: Hard Provider Replace (not abstraction layer)

**What:** Delete the dual-stack complexity. Wire `UnifiedWhatsAppService` directly to `WuzAPIClient` with no `BaseWhatsAppProvider` interface.

**When to use:** When there is exactly one provider and no planned multi-provider future. The project decision confirms "hard cut, no dual-provider hacks."

**Trade-offs:**
- Pro: Zero abstraction overhead, direct error messages, simpler tests
- Pro: Eliminates existing dual-stack problem (Stack A + Stack B) permanently
- Pro: All Evolution-era code goes dark simultaneously
- Con: If WuzAPI fails long-term, a future migration must touch the facade again (same scope of work either way)

**Example:**
```python
# Before (UnifiedWhatsAppService.__init__)
self._queue_client = EvolutionAPIClient(
    base_url=settings.WHATSAPP_EVOLUTION_API_URL,
    api_key=settings.WHATSAPP_EVOLUTION_API_KEY,
    ...
)

# After:
self._queue_client = WuzAPIClient(
    base_url=settings.WHATSAPP_WUZAPI_BASE_URL,
    token=settings.WHATSAPP_WUZAPI_TOKEN,
    timeout_seconds=settings.WHATSAPP_WUZAPI_TIMEOUT_SECONDS,
)
```

### Pattern 2: Constructor Injection for WhatsAppMessageService

**What:** `WhatsAppMessageService.__init__` currently requires `EvolutionAPIClient`. Change the type annotation to accept `WuzAPIClient`. No interface needed — duck-typing is sufficient since there is only one implementation.

**When to use:** Service has one known implementation; injection is for testability only.

**Example:**
```python
class WhatsAppMessageService:
    def __init__(
        self,
        whatsapp_client: WuzAPIClient,  # was: EvolutionAPIClient
        db: AsyncSession,
        message_queue: MessageQueue,
        ...
    ):
```

### Pattern 3: Tombstone Both Evolution Stacks Simultaneously

**What:** On the same commit that introduces the final `WuzAPIClient` wiring, add `ImportError` sentinels to all Evolution files.

**When to use:** Hard-cut migrations where rollback is not required.

**Example:**
```python
# app/integrations/evolution/client.py (tombstoned)
"""
Evolution API client — TOMBSTONED in v1.6.
Replaced by app.integrations.wuzapi.client.WuzAPIClient.
"""
raise ImportError(
    "EvolutionClient removed in v1.6. "
    "Use app.integrations.wuzapi.client.WuzAPIClient instead."
)
```

### Pattern 4: WuzAPI Webhook Extractor as Stateless Function Module

**What:** `wuzapi_message_extractor.py` is a module of pure functions (no class required). Matches the existing `message_extractor.py` pattern.

**WuzAPI incoming Message payload to parse:**
```json
{
  "type": "Message",
  "token": "USER_TOKEN",
  "event": {
    "Info": {
      "ID": "3EB06F9067F80BAB89FF",
      "FromMe": false,
      "Timestamp": "2024-01-20T12:49:08-03:00",
      "Type": "textMessage",
      "PushName": "Patient Name",
      "Sender": "5511987654321@s.whatsapp.net"
    },
    "Message": {
      "Conversation": "Patient reply text",
      "ExtendedTextMessage": null,
      "ImageMessage": null
    }
  }
}
```

**WuzAPI ReadReceipt payload to parse:**
```json
{
  "type": "ReadReceipt",
  "token": "USER_TOKEN",
  "event": {
    "Info": {
      "ID": "3EB06F9067F80BAB89FF",
      "FromMe": true,
      "Timestamp": "2024-01-20T12:49:15-03:00"
    },
    "Receipt": {
      "Type": "read",
      "Timestamp": "2024-01-20T12:49:15-03:00"
    }
  }
}
```

**Key extraction logic:**
```python
def extract_message_data(payload: dict) -> Optional[dict]:
    event = payload.get("event", {})
    info = event.get("Info", {})

    # WuzAPI does not use @lid addressing — no LID resolution needed
    sender = info.get("Sender", "")  # "5511987654321@s.whatsapp.net"
    phone = _clean_phone_from_jid(sender)  # "5511987654321"

    message = event.get("Message", {})
    content, message_type = _extract_content_and_type(message)

    return {
        "phone": phone,
        "content": content,
        "type": message_type,
        "whatsapp_id": info.get("ID"),
        "metadata": {
            "from_me": info.get("FromMe", False),
            "timestamp": info.get("Timestamp"),
            "pushName": info.get("PushName"),
            "token": payload.get("token"),
        }
    }
```

---

## Data Flow

### Outbound Message Flow (after migration)

```
Celery Task: send_whatsapp_message
    |
    v
UnifiedWhatsAppService.send_message(message)
    |
    +-- direct mode (non-prod) --> _send_via_direct_api()
    |       |
    |       v
    |   WuzAPIClient.send_text_message(phone, text)
    |   POST /chat/send/text
    |   Headers: { "Authorization": "{token}", "Content-Type": "application/json" }
    |   Body: { "Phone": "5511987654321", "Body": "message text" }
    |       |
    |       v
    |   WuzAPI returns: { "code": 200, "data": { "Details": "Sent", "Id": "3EB..." } }
    |   message.whatsapp_id = response["data"]["Id"]
    |
    +-- queue mode (prod) --> _send_via_queue()
            |
            v
        WhatsAppMessageService.send_message(MessageRequest)
            |
            v
        MessageQueue (Redis) -> worker -> WuzAPIClient.send_text_message()
```

### Inbound Webhook Flow (after migration)

```
WuzAPI Server
    |
    POST /webhooks/wuzapi
    Headers: { "x-hmac-signature": "sha256=<digest>" }
    Body: { "type": "Message"|"ReadReceipt", "token": "...", "event": {...} }
    |
    v
app/integrations/wuzapi/api/webhooks.py
    |
    +-- Rate limit check (existing limiter)
    +-- HMAC validation: WebhookHMACValidator.validate_signature(
    |       body_bytes,
    |       request.headers["x-hmac-signature"],
    |       settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET
    |   )
    +-- Idempotency: Redis SET NX (same pattern as existing handler)
    |
    +-- type == "Message" --> wuzapi_message_extractor.extract_message_data()
    |       |
    |       v
    |   Returns: { "phone": "5511987654321",
    |              "content": "text", "type": TEXT,
    |              "whatsapp_id": "3EB06F..." }
    |       |
    |       v
    |   PhoneNormalizer.find_patient_by_phone(phone)
    |       |
    |       v
    |   Flow engine processes patient response (unchanged)
    |
    +-- type == "ReadReceipt" --> StatusWebhookHandler._map_wuzapi_status()
            |
            v
        Extract: event.Info.ID as whatsapp_id
                 Receipt.Type as "read"
        Map:     "read" -> MessageStatus.READ
        Update:  message.status via MessageService
        Broadcast: WebSocket event MESSAGE_STATUS_UPDATED (unchanged)
```

### Phone Number Format: Key Difference

| Direction | Evolution API | WuzAPI |
|-----------|--------------|--------|
| Outbound send `to` field | `55119...` digits only | `55119...` digits only (same) |
| Inbound sender JID | `55119...@s.whatsapp.net` or `@lid` | `55119...@s.whatsapp.net` (no LID) |
| Phone strip logic | Split on `@`, take left part | Same: split on `@`, take left part |
| LID addressing | Present (complex `@lid` JIDs) | Absent (whatsmeow resolves internally) |

The existing `_clean_phone_from_jid()` logic is correct and reusable in the new extractor. The LID resolution code in `phone_normalizer.py` (`resolve_phone_from_lid`, `_fetch_evolution_chats`, `_match_phone_jid_for_lid`) must be removed since WuzAPI has no LID concept and those methods make HTTP calls to Evolution API endpoints.

---

## Integration Points

### New vs Modified vs Tombstoned Files

| File | Action | Reason |
|------|--------|--------|
| `app/integrations/wuzapi/__init__.py` | **NEW** | Package init |
| `app/integrations/wuzapi/client.py` | **NEW** | `WuzAPIClient`: httpx async, `Authorization` token header, `/chat/send/text` |
| `app/integrations/wuzapi/models.py` | **NEW** | Pydantic models: `WuzAPISendRequest`, `WuzAPIResponse`, `WuzAPISessionStatus` |
| `app/integrations/wuzapi/errors.py` | **NEW** | `WuzAPIError` hierarchy replacing `EvolutionAPIError` |
| `app/integrations/wuzapi/mock_wuzapi.py` | **NEW** | Test double implementing same interface as `WuzAPIClient` |
| `app/integrations/wuzapi/api/__init__.py` | **NEW** | Package init |
| `app/integrations/wuzapi/api/webhooks.py` | **NEW** | Webhook router at `/webhooks/wuzapi`; handles Message + ReadReceipt |
| `app/services/webhook/utils/wuzapi_message_extractor.py` | **NEW** | Pure-function parser for WuzAPI message event JSON |
| `app/services/unified_whatsapp_service.py` | **MODIFY** | Swap `EvolutionAPIClient` -> `WuzAPIClient`; update config refs; rename circuit breaker |
| `app/integrations/whatsapp/services/message_service.py` | **MODIFY** | Accept `WuzAPIClient` in constructor instead of `EvolutionAPIClient` |
| `app/services/webhook/handlers/status_handler.py` | **MODIFY** | Add `_map_wuzapi_status()`; update `source` field to `"wuzapi"` |
| `app/services/webhook/utils/phone_normalizer.py` | **MODIFY** | Remove 3 LID methods; keep E.164 normalization and patient lookup |
| `app/config/settings/integrations.py` | **MODIFY** | Add `WHATSAPP_WUZAPI_*` vars; deprecate Evolution vars |
| `app/domain/messaging/delivery/idempotent_sender.py` | **MODIFY** | Replace `EvolutionClient` import with `WuzAPIClient`; update send call signature |
| `app/integrations/whatsapp/security/hmac_validator.py` | **KEEP** | Algorithm-agnostic; handles WuzAPI SHA-256 with no changes |
| `app/integrations/evolution/client.py` | **TOMBSTONE** | Stack A (httpx/structlog) eliminated |
| `app/integrations/evolution/message_sender.py` | **TOMBSTONE** | Stack A dependency |
| `app/integrations/evolution/request_handler.py` | **TOMBSTONE** | Stack A dependency |
| `app/integrations/evolution/webhook_handler.py` | **TOMBSTONE** | Stack A dependency |
| `app/integrations/whatsapp/services/evolution_client.py` | **TOMBSTONE** | Stack B (aiohttp) eliminated |
| `app/integrations/whatsapp/services/mock_evolution.py` | **TOMBSTONE** | Replace with `mock_wuzapi.py` |
| `app/integrations/whatsapp/api/webhooks.py` | **TOMBSTONE** | Evolution webhook handler eliminated |
| `app/services/webhook/utils/message_extractor.py` | **TOMBSTONE** | Evolution Baileys parser eliminated |

### External Service Integration Points

| Service | Auth Method | Endpoint | Notes |
|---------|-------------|----------|-------|
| WuzAPI send text | `Authorization: {user_token}` | `POST /chat/send/text` | Phone: raw digits `5511...`; no `@s.whatsapp.net` |
| WuzAPI send image | `Authorization: {user_token}` | `POST /chat/send/image` | Body field with base64 or URL |
| WuzAPI session health | `Authorization: {user_token}` | `GET /session/status` | Returns `{Connected: bool, LoggedIn: bool}` |
| WuzAPI session connect | `Authorization: {user_token}` | `POST /session/connect` | Initiates WhatsApp WebSocket connection |
| WuzAPI admin | `Authorization: {admin_token}` | `POST /admin/users` | `WUZAPI_ADMIN_TOKEN` env var |
| WuzAPI webhooks inbound | `x-hmac-signature: sha256=<hex>` | POST to configured URL | HMAC key: `WUZAPI_GLOBAL_HMAC_KEY` on WuzAPI server |

### Internal Boundary Changes

| Boundary | Before | After |
|----------|--------|-------|
| `UnifiedWhatsAppService` -> client | `EvolutionAPIClient` (aiohttp) | `WuzAPIClient` (httpx) |
| `WhatsAppMessageService` -> client | `EvolutionAPIClient` | `WuzAPIClient` |
| `IdempotentMessageSender` -> client | `EvolutionClient` (Stack A, httpx) | `WuzAPIClient` |
| Webhook URL path | `/webhooks/whatsapp/*` (multiple routes) | `/webhooks/wuzapi` (single route, type in body) |
| HMAC signature header | Evolution-specific (custom per deployment) | `x-hmac-signature` (WuzAPI standard) |
| Status event type | `MESSAGES_UPDATE` with `update.status` string | `ReadReceipt` with `Receipt.Type` string |
| Session identifier | `instance_name` string on every call | Bearer token identifies session; no `instance_name` |
| Connection state check | `GET /instance/connectionState/{instance}` | `GET /session/status` |

---

## Anti-Patterns

### Anti-Pattern 1: Adding an Abstraction Layer "Just in Case"

**What people do:** Create a `BaseWhatsAppProvider` protocol/ABC that both Evolution and WuzAPI implement, keeping Evolution code alive behind an interface.

**Why it's wrong:** The PROJECT.md decision is "hard cut." Maintaining two implementations doubles test surface and leaves Evolution-era bugs alive. The existing dual-stack problem (Stack A vs Stack B) proved the cost of abstraction for a single-provider system.

**Do this instead:** Wire `WuzAPIClient` directly. If a future migration is needed, it will be its own milestone with its own research.

### Anti-Pattern 2: Reusing the Evolution Webhook URL Path

**What people do:** Register WuzAPI webhooks at `/webhooks/whatsapp/` to avoid reconfiguring WuzAPI's webhook destination URL.

**Why it's wrong:** The Evolution handler expects Baileys JSON (`key.remoteJid`, `update.status`, `messages[0].message.conversation`). WuzAPI sends `{"type": "Message", "event": {"Info": {...}, "Message": {...}}}`. Routing WuzAPI payloads to the Evolution handler produces silent parse failures.

**Do this instead:** Create `/webhooks/wuzapi` as a clean endpoint. Configure WuzAPI server's webhook URL to point there. Tombstone the Evolution handler.

### Anti-Pattern 3: Keeping the LID Resolution Logic

**What people do:** Preserve `resolve_phone_from_lid` in `PhoneNormalizer` as a no-op or a conditional that checks for Evolution config.

**Why it's wrong:** The LID (Linked Device) addressing concept is specific to Evolution API's wrapper over Baileys. WuzAPI uses whatsmeow which resolves JIDs internally and always delivers standard `phone@s.whatsapp.net` in webhook payloads. The three LID methods make HTTP calls to `{EVOLUTION_API_URL}/chat/findChats/{instance}` — an endpoint that will not exist post-migration.

**Do this instead:** Delete `resolve_phone_from_lid`, `_fetch_evolution_chats`, and `_match_phone_jid_for_lid` from `PhoneNormalizer`. Add a tombstone comment explaining removal.

### Anti-Pattern 4: Tombstoning Stack A Before Updating IdempotentMessageSender

**What people do:** Tombstone `app/integrations/evolution/client.py` (Stack A) in Phase 5 before updating `IdempotentMessageSender`.

**Why it's wrong:** `IdempotentMessageSender` directly imports `from app.integrations.evolution import EvolutionClient`. Tombstoning Stack A first raises `ImportError` at Celery worker startup, breaking all task processing even before any task runs.

**Do this instead:** Update `IdempotentMessageSender` to import `WuzAPIClient` in the same commit as or before tombstoning Stack A.

### Anti-Pattern 5: Using `instance_name` in WuzAPI Requests

**What people do:** Pass `instance_name` through the `MessageRequest` Pydantic model to `WuzAPIClient`, mirroring the Evolution pattern.

**Why it's wrong:** WuzAPI does not have an instance concept. The `Authorization` token identifies the WhatsApp session. Passing an `instance_name` field to the WuzAPI client requires stripping or ignoring it, which is confusing and error-prone.

**Do this instead:** Remove `instance_name` as a required field from `MessageRequest`. `UnifiedWhatsAppService` reads `WHATSAPP_WUZAPI_TOKEN` from settings; session identity comes from authentication, not from a per-message parameter.

---

## Suggested Build Order

The build order respects import dependencies: nothing can be tombstoned until its callers are updated.

### Phase 1: New Provider Foundation (no existing files changed)

**Goal:** Create `WuzAPIClient` and all supporting infrastructure. Zero existing files modified.

1. Create `app/integrations/wuzapi/__init__.py`
2. Create `app/integrations/wuzapi/errors.py` — `WuzAPIError(Exception)` with `status`, `response`, `method`, `url` attributes
3. Create `app/integrations/wuzapi/models.py` — Pydantic models:
   - `WuzAPISendTextRequest(phone: str, body: str, id: Optional[str])`
   - `WuzAPIResponse(code: int, data: Dict, success: bool)`
   - `WuzAPISessionStatus(connected: bool, logged_in: bool)`
4. Create `app/integrations/wuzapi/client.py` — `WuzAPIClient`:
   - httpx `AsyncClient` with `Authorization: {token}` header
   - `send_text_message(phone: str, text: str) -> WuzAPIResponse`
   - `send_media_message(phone, media_type, ...)` for image/audio/document/video
   - `get_session_status() -> WuzAPISessionStatus`
   - `connect_session()`, `disconnect_session()`
   - `health_check() -> Dict[str, Any]` mapping `Connected+LoggedIn` to `is_connected`
   - Retry via `backoff` (same pattern as `EvolutionAPIClient`)
   - Rate limiter (reuse existing `RateLimiter` class or copy)
5. Create `app/integrations/wuzapi/mock_wuzapi.py` — implements same interface
6. Unit tests for `WuzAPIClient` against mock HTTP (no external calls)

**Why first:** Zero impact on existing code. Can be reviewed independently.

### Phase 2: Webhook Handler (parallel with Phase 1)

**Goal:** WuzAPI can deliver webhooks to a live endpoint. No outbound send changes yet.

1. Create `app/services/webhook/utils/wuzapi_message_extractor.py`:
   - `extract_message_data(payload: dict) -> Optional[dict]`
   - Parse `event.Info.Sender` for phone (strip `@s.whatsapp.net`)
   - Reuse phone-cleaning logic (copy `_clean_phone_from_jid`)
   - Handle message types: `Conversation`, `ExtendedTextMessage.Text`, `ImageMessage`, `AudioMessage`, `VideoMessage`, `DocumentMessage`, `StickerMessage`
   - Return `{phone, content, type, whatsapp_id, metadata}`
2. Create `app/integrations/wuzapi/api/__init__.py`
3. Create `app/integrations/wuzapi/api/webhooks.py`:
   - `POST /webhooks/wuzapi` endpoint (FastAPI router)
   - Read `x-hmac-signature` header; call `WebhookHMACValidator.validate_signature()`
   - Route `type == "Message"` -> `wuzapi_message_extractor`
   - Route `type == "ReadReceipt"` -> adapted `StatusWebhookHandler`
   - Idempotency via Redis SET NX (identical pattern to existing handler)
   - Background task dispatch for flow engine (identical to existing handler)
4. Adapt `app/services/webhook/handlers/status_handler.py`:
   - Add `_map_wuzapi_status(receipt_type: str) -> MessageStatus` method
   - Map `"read"` -> `MessageStatus.READ`
   - Keep `_map_evolution_status` alive until Evolution handler is tombstoned in Phase 5
   - Update `source` field to accept `"wuzapi"` parameter
5. Register new WuzAPI webhook router in application (alongside existing Evolution router temporarily)
6. Integration tests: POST mock WuzAPI JSON to `/webhooks/wuzapi`, verify patient flow triggers

### Phase 3: Update Settings

**Goal:** New environment variables available before outbound code references them.

1. Add to `app/config/settings/integrations.py`:
   ```python
   WHATSAPP_WUZAPI_BASE_URL: str = Field(
       default="http://localhost:8080",
       description="WuzAPI server base URL"
   )
   WHATSAPP_WUZAPI_TOKEN: str = Field(
       default="",
       description="WuzAPI user authentication token"
   )
   WHATSAPP_WUZAPI_TIMEOUT_SECONDS: int = Field(
       default=30, description="WuzAPI request timeout in seconds"
   )
   WHATSAPP_WUZAPI_WEBHOOK_SECRET: Optional[str] = Field(
       default=None,
       description="HMAC secret for validating WuzAPI webhook signatures (x-hmac-signature)"
   )
   WHATSAPP_WUZAPI_USE_MOCK: bool = Field(
       default=False, description="Use mock WuzAPI client for testing"
   )
   ```
2. Mark `WHATSAPP_EVOLUTION_*` fields with deprecation note in description
3. Update `.env.example`: add WuzAPI vars, comment out Evolution vars

### Phase 4: Migrate Outbound Path

**Goal:** All outbound messaging uses `WuzAPIClient`. Both Evolution stacks have zero callers.

1. Update `app/services/unified_whatsapp_service.py`:
   - Replace `from app.integrations.whatsapp.services.evolution_client import EvolutionAPIClient` with `from app.integrations.wuzapi.client import WuzAPIClient`
   - `_get_queue_client()`: construct `WuzAPIClient` from `WHATSAPP_WUZAPI_*` settings
   - Mock client branch: use `MockWuzAPIClient` when `WHATSAPP_WUZAPI_USE_MOCK` is True
   - Circuit breaker name: `"evolution_api"` -> `"wuzapi"` (affects Redis key namespace)
   - `health_check()`: call `WuzAPIClient.get_session_status()` (returns `WuzAPISessionStatus`)
   - `_send_via_direct_api()`: phone format unchanged (digits-only, `+` stripped already)
   - Remove all `WHATSAPP_EVOLUTION_API_URL`, `WHATSAPP_EVOLUTION_API_KEY` references
   - Remove `instance_name` from `_convert_to_queue_request()` return value
2. Update `app/integrations/whatsapp/services/message_service.py`:
   - Type annotation `EvolutionAPIClient` -> `WuzAPIClient`
   - Call `WuzAPIClient.send_text_message(phone, text)` in queue worker loop
3. Update `app/domain/messaging/delivery/idempotent_sender.py`:
   - Replace `from app.integrations.evolution import EvolutionClient` with `from app.integrations.wuzapi.client import WuzAPIClient`
   - `evolution_client` property: instantiate `WuzAPIClient(base_url=..., token=...)`
   - Update `send_text_message` call: keyword args change from `(phone_number=, message=)` to `(phone=, text=)` per WuzAPI models
   - Extract `whatsapp_id` from `response.data["Id"]` instead of `response["key"]["id"]`

### Phase 5: Tombstone Evolution Code

**Goal:** All Evolution files raise `ImportError`. No silent dead code.

Execute after Phase 4 tests pass. Do all tombstones in a single commit.

1. Tombstone `app/integrations/evolution/client.py` (Stack A root)
2. Tombstone `app/integrations/evolution/message_sender.py`
3. Tombstone `app/integrations/evolution/request_handler.py`
4. Tombstone `app/integrations/evolution/webhook_handler.py`
5. Tombstone `app/integrations/whatsapp/services/evolution_client.py` (Stack B)
6. Tombstone `app/integrations/whatsapp/services/mock_evolution.py`
7. Tombstone `app/integrations/whatsapp/api/webhooks.py` (Evolution webhook router)
8. Tombstone `app/services/webhook/utils/message_extractor.py` (Evolution payload parser)
9. Remove deprecated `WHATSAPP_EVOLUTION_*` fields from `IntegrationsSettings`
10. Remove LID methods from `phone_normalizer.py`: `resolve_phone_from_lid`, `_fetch_evolution_chats`, `_match_phone_jid_for_lid`
11. Deregister Evolution webhook router from application
12. Verify: `grep -r "evolution" backend-hormonia/app/ --include="*.py" -i` returns only tombstone docstrings

### Phase 6: Tests and CI Validation

**Goal:** Full test coverage for WuzAPI paths; no regressions in WebSocket, Celery, or saga behavior.

1. Update all fixtures that instantiate `EvolutionClient` or `EvolutionAPIClient`
2. Update `tests/integrations/` to use `MockWuzAPIClient`
3. Verify circuit breaker tests pass (breaker logic identical; name string changed)
4. Verify `IdempotentMessageSender` tests pass with `WuzAPIClient`
5. End-to-end webhook tests: POST valid WuzAPI JSON to `/webhooks/wuzapi`; verify patient flow triggers
6. HMAC validation test: correct `x-hmac-signature` header passes; wrong header rejected
7. ReadReceipt test: `StatusWebhookHandler` correctly maps `Receipt.Type: "read"` to `MessageStatus.READ`
8. Run `scripts/check_async_isolation.py` — Celery tasks remain sync Session, unchanged
9. Run `scripts/check_agent_run_calls.py` — AI agent usage unchanged

---

## WuzAPI Client Design Specification

### Authentication Summary

| Context | Header | Value | Env Var |
|---------|--------|-------|---------|
| User operations | `Authorization` | `{user_token}` | `WHATSAPP_WUZAPI_TOKEN` |
| Admin operations | `Authorization` | `{admin_token}` | `WUZAPI_ADMIN_TOKEN` |

The user token maps to the WuzAPI user that owns the WhatsApp session. This replaces the `instance_name` concept entirely.

### Key API Endpoint Differences

| Operation | Evolution API | WuzAPI |
|-----------|--------------|--------|
| Send text | `POST /message/sendText/{instance}` | `POST /chat/send/text` |
| Send image | `POST /message/sendMedia/{instance}` | `POST /chat/send/image` |
| Send audio | `POST /message/sendMedia/{instance}` | `POST /chat/send/audio` |
| Send document | `POST /message/sendMedia/{instance}` | `POST /chat/send/document` |
| Session status | `GET /instance/connectionState/{instance}` | `GET /session/status` |
| Session connect | `POST /instance/connect/{instance}` | `POST /session/connect` |
| Session disconnect | `DELETE /instance/logout/{instance}` | `POST /session/disconnect` |

### Send Text Request/Response

```python
# POST /chat/send/text
# Request body:
{
    "Phone": "5511987654321",   # digits only, no @s.whatsapp.net
    "Body": "message text",
    "Id": "domain-message-id"   # optional; use for correlation
}

# Success response:
{
    "code": 200,
    "data": { "Details": "Sent", "Id": "3EB06F9067F80BAB89FF" },
    "success": true
}
# message.whatsapp_id = response["data"]["Id"]

# Failure response (4xx/5xx):
{
    "code": 400,
    "error": "Number not found",
    "success": false
}
```

### Session Status Mapping

```python
# GET /session/status response:
{
    "code": 200,
    "data": { "Connected": true, "LoggedIn": true },
    "success": true
}

# Maps to internal health check:
# is_connected = data["Connected"] and data["LoggedIn"]
# Replaces Evolution's: state.get("state") == "open"
```

---

## Scaling Considerations

| Scale | Architecture Impact |
|-------|-------------------|
| Current (1 clinic, 1 phone number) | Single WuzAPI user token; no multi-session complexity |
| Multiple clinics (future) | One WuzAPI user per clinic phone; token stored per-tenant in config or DB |
| High volume (>1k msg/min) | WuzAPI supports RabbitMQ output; can bypass Redis queue with AMQP if needed |

The existing Redis-backed queue, circuit breaker (Redis-backed), Celery beat schedule, and WebSocket pub/sub are all unchanged by this migration.

---

## Sources

- [WuzAPI GitHub — asternic/wuzapi](https://github.com/asternic/wuzapi) — MEDIUM confidence (official repo)
- [WuzAPI API.md (raw)](https://raw.githubusercontent.com/asternic/wuzapi/main/API.md) — HIGH confidence (fetched directly; endpoint payloads verified)
- [WuzAPI README.md](https://github.com/asternic/wuzapi/blob/main/README.md) — HIGH confidence (auth model, session vs instance, HMAC config verified)
- Codebase inspection (HIGH confidence — direct reads):
  - `app/services/unified_whatsapp_service.py`
  - `app/integrations/whatsapp/services/evolution_client.py`
  - `app/integrations/evolution/client.py`
  - `app/domain/messaging/delivery/idempotent_sender.py`
  - `app/integrations/whatsapp/api/webhooks.py`
  - `app/services/webhook/handlers/status_handler.py`
  - `app/services/webhook/utils/message_extractor.py`
  - `app/services/webhook/utils/phone_normalizer.py`
  - `app/config/settings/integrations.py`
  - `app/integrations/whatsapp/models/message.py`
  - `app/integrations/whatsapp/security/hmac_validator.py`

---

*Architecture research for: WuzAPI migration in clinica-oncologica-v02-1 backend (v1.6)*
*Researched: 2026-03-01*
