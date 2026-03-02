# Phase 36: Outbound Migration - Research

**Researched:** 2026-03-02
**Domain:** WhatsApp outbound message routing — swap EvolutionAPIClient/EvolutionClient for WuzAPIClient across three call sites
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| OUT-01 | UnifiedWhatsAppService uses WuzAPIClient instead of EvolutionAPIClient for all outbound messages | WuzAPIClient.send_text() / send_media() API confirmed; circuit breaker rename to `wuzapi`; health check via GET /session/status |
| OUT-02 | WhatsAppMessageService queue pipeline wired to WuzAPIClient | Constructor signature change confirmed: `evolution_client` → `wuzapi_client`; _send_message_impl rewired to send_text/send_media on WuzAPIClient |
| OUT-03 | IdempotentMessageSender updated to use WuzAPIClient instead of legacy EvolutionClient (Stack A) | Import swap confirmed; `evolution_client` property → `wuzapi_client`; response extraction from `response["data"]["Id"]` |
| OUT-04 | Phone format adapted: raw digits sent to WuzAPI (no `@s.whatsapp.net` suffix) | WuzAPIClient.send_text() takes raw Phone string; current code strips `+` prefix via normalize_phone BR_TO_E164 — that produces `+5511...` so stripping the `+` gives `5511...` which is already correct for WuzAPI |
</phase_requirements>

---

## Summary

Phase 36 is a focused swap operation: three existing call sites that currently invoke `EvolutionAPIClient` or `EvolutionClient` for outbound WhatsApp messages must be updated to use the already-complete `WuzAPIClient` (built in Phase 33). No new packages are required. No architectural changes are needed. The entire migration is mechanical substitution with three non-trivial details: (1) the circuit breaker key must change from `"evolution_api"` to `"wuzapi"` in `UnifiedWhatsAppService`, (2) the health check call must change from `evolution_client.health_check(instance_name)` to `wuzapi_client.get_session_status()`, and (3) `IdempotentMessageSender` must extract `whatsapp_id` from `response["data"]["Id"]` instead of `response["key"]["id"]`.

The phone format concern is pre-resolved: `WuzAPIClient.send_text()` accepts a raw `Phone` field (digits only, no `@s.whatsapp.net`). The existing `normalize_phone(phone, mode=PhoneValidationMode.BR_TO_E164)` already produces `+5511NNNNN`; stripping the leading `+` gives `5511NNNNN`, which is exactly the raw-digit format WuzAPI expects.

Phase 37 (tombstoning Evolution files) is blocked on Phase 36 completing. Celery workers import `IdempotentMessageSender` at startup; any import of `EvolutionClient` from a tombstoned file would produce an `ImportError` before Phase 36 finishes the swap.

**Primary recommendation:** Execute this phase as two sequential plans — Plan 36-01 (`UnifiedWhatsAppService` migration) then Plan 36-02 (`WhatsAppMessageService` constructor + `IdempotentMessageSender` update) — keeping each plan to a single coherent commit.

---

## Standard Stack

### Core (already in project, nothing to install)

| Module | Location | Purpose |
|--------|----------|---------|
| `WuzAPIClient` | `app/integrations/wuzapi/client.py` | Real HTTP client for WuzAPI — aiohttp + backoff + RedisCircuitBreaker("wuzapi") |
| `MockWuzAPIClient` | `app/integrations/wuzapi/mock.py` | Drop-in test double; activated by `WHATSAPP_WUZAPI_USE_MOCK=true` |
| `get_wuzapi_client()` | `app/integrations/wuzapi/__init__.py` | Factory that returns real or mock client based on env var |
| `WuzAPISendResponse` | `app/integrations/wuzapi/models.py` | Pydantic model: `.data.Id` is the message ID field |
| `IntegrationsSettings` | `app/config/settings/integrations.py` | `WHATSAPP_WUZAPI_BASE_URL`, `WHATSAPP_WUZAPI_TOKEN`, `WHATSAPP_WUZAPI_USE_MOCK` |
| `RedisCircuitBreaker` | `app/core/redis_circuit_breaker.py` | Circuit breaker already used inside WuzAPIClient (key `"wuzapi"`) |

### No new dependencies required

Installation: none. `aiohttp`, `backoff`, `pydantic` are all already in the project.

---

## Architecture Patterns

### Current State: Three Call Sites

**Call site 1 — `UnifiedWhatsAppService`** (`app/services/unified_whatsapp_service.py`)

- Imports `EvolutionAPIClient` from `app.integrations.whatsapp.services.evolution_client`
- `_get_queue_client()` constructs `EvolutionAPIClient` or `MockEvolutionAPIClient`
- `_get_queue_service()` passes the Evolution client to `WhatsAppMessageService`
- `_send_via_direct_api()` calls `evolution_client.send_text_message(instance_name, phone, content)` — note the `instance_name` first argument that WuzAPI does NOT have
- `_evolution_breaker = CircuitBreaker(name="evolution_api", ...)` — must rename to `"wuzapi"`
- `health_check()` calls `evolution_client.health_check(self.default_instance_name)` — must change to `wuzapi_client.get_session_status()`
- `__init__` receives `default_instance_name` (Evolution concept) — keep param but it becomes irrelevant for sends (WuzAPI is single-session, no instance concept)

**Call site 2 — `WhatsAppMessageService`** (`app/integrations/whatsapp/services/message_service.py`)

- Constructor: `def __init__(self, evolution_client: EvolutionAPIClient, ...)` — must accept `WuzAPIClient`
- `_send_message_impl()` calls `self.evolution_client.send_text_message(instance_name=..., to=..., text=...)` and `send_media_message(instance_name=..., to=..., media_url=..., media_type=..., ...)` — WuzAPI has `send_text(phone, message)` and `send_media(media_type, phone, data_uri, caption, filename)`
- `message.external_id = response.external_id` — WuzAPI does not return an `external_id`; it returns `response["data"]["Id"]`; but note `WhatsAppMessage.external_id` is the queue model field (separate from domain `Message.whatsapp_id`)
- Circuit breaker inside service: `CircuitBreaker(name="evolution_api_queue", ...)` — rename to `"wuzapi_queue"` (or simply `"wuzapi"` — consistent with client-level breaker)

**Call site 3 — `IdempotentMessageSender`** (`app/domain/messaging/delivery/idempotent_sender.py`)

- Imports `from app.integrations.evolution import EvolutionClient` (Stack A — the httpx-based client at `app/integrations/evolution/client.py`)
- `evolution_client` property lazy-loads `EvolutionClient()`
- `send_message()` calls `evolution_client.send_text_message(phone_number=patient.phone, message=content)` — Stack A signature
- `message.whatsapp_id = evolution_response["key"]["id"]` — this is the Evolution response shape; WuzAPI shape is `response["data"]["Id"]`
- Uses `patient.phone` — need to confirm whether this is raw digits already or needs normalization for WuzAPI

### WuzAPIClient API Reference (confirmed from source)

```python
# Text message
response = await client.send_text(phone: str, message: str) -> dict[str, Any]
# response shape: {"code": 200, "data": {"Id": "...", "Details": "..."}, "success": True}

# Media message
response = await client.send_media(
    media_type: str,   # "image", "audio", "video", "document"
    phone: str,
    data_uri: str,     # base64 data URI
    caption: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]

# Session health (replaces evolution_client.health_check())
response = await client.get_session_status() -> dict[str, Any]
# response shape: {"data": {"Connected": bool, "LoggedIn": bool}, "success": True}
```

**Key difference from Evolution:** No `instance_name` argument anywhere in WuzAPI calls. WuzAPI is single-session.

### Response Shape Differences

| Field | Evolution API | WuzAPI |
|-------|--------------|--------|
| Message ID | `response["message"]["key"]["id"]` (Stack B) or `response["key"]["id"]` (Stack A) | `response["data"]["Id"]` |
| Success indicator | HTTP 201 | `response["success"] == True` (client checks internally) |
| Error response | HTTP 4xx/5xx | WuzAPIError raised by client |

### Phone Format for WuzAPI

WuzAPI `Phone` field expects raw digits: e.g. `5511999998888` (country code + DDD + number, no `@s.whatsapp.net` suffix, no `+` prefix).

**Current `UnifiedWhatsAppService._send_via_direct_api()`:**
```python
phone = normalize_phone(patient.phone_decrypted, mode=PhoneValidationMode.BR_TO_E164)
# produces: "+5511999998888"
if phone.startswith("+"):
    phone = phone[1:]
# produces: "5511999998888" ← correct for WuzAPI
```
This stripping logic already produces the correct format. No change needed here.

**`IdempotentMessageSender`:** Currently uses `patient.phone` (not `phone_decrypted`). Must verify if `patient.phone` is encrypted. Based on the `_ensure_patient_loaded` pattern in `UnifiedWhatsAppService` which always accesses `patient.phone_decrypted`, the `phone` column is encrypted at rest. The sender must use `patient.phone_decrypted` and normalize to raw digits.

**`WhatsAppMessageService._send_message_impl()`:** Receives `request.to` which is already a normalized phone number (validated by `validate_phone_number()` in `send_message()`). The existing `validate_phone_number()` returns `5511NNNNN` format (removes `+` if present) — this is already correct for WuzAPI.

### Media Handling Gap (Queue Pipeline)

`WhatsAppMessageService._send_message_impl()` currently passes a `media_url` (HTTP URL) to `EvolutionAPIClient.send_media_message()`. WuzAPIClient.send_media() requires a **base64 data URI**, not a URL. The `fetch_and_encode_media()` utility from `app/integrations/wuzapi/media.py` handles this conversion.

For Plan 36-02, when sending media through the queue pipeline, the implementation must call `fetch_and_encode_media(media_url)` before calling `wuzapi_client.send_media()`. The text path has no such gap.

### Circuit Breaker Rename

`UnifiedWhatsAppService` has `self._evolution_breaker = CircuitBreaker(name="evolution_api", ...)`. This must become `CircuitBreaker(name="wuzapi", ...)` to align with the breaker already embedded in WuzAPIClient itself. Note WuzAPIClient already wraps its own calls in a `RedisCircuitBreaker(name="wuzapi")` — this means there are two circuit breakers in the chain. That is acceptable for now; Phase 37 can consolidate if desired. Do NOT remove the service-level circuit breaker during Phase 36 — breaking that would affect the `_send_via_queue` path.

### Health Check Replacement

`health_check()` in `UnifiedWhatsAppService` currently calls:
```python
instance_health = await evolution_client.health_check(self.default_instance_name)
instance_status = "healthy" if instance_health.get("is_connected") else "degraded"
```

Replace with:
```python
status_resp = await wuzapi_client.get_session_status()
status_data = status_resp.get("data", {})
is_connected = status_data.get("Connected", False) and status_data.get("LoggedIn", False)
instance_status = "healthy" if is_connected else "degraded"
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| HTTP client with retry/backoff | Custom aiohttp wrapper | `WuzAPIClient._make_request()` — already has backoff + rate limit |
| Circuit breaker | Custom state machine | `RedisCircuitBreaker(name="wuzapi")` — already in WuzAPIClient |
| Mock for tests | Custom mock | `MockWuzAPIClient` — factory via `get_wuzapi_client()` |
| Media URL → base64 encoding | Custom downloader | `fetch_and_encode_media(url)` from `app/integrations/wuzapi/media.py` |
| Phone normalization | Custom regex | `normalize_phone(phone, mode=PhoneValidationMode.BR_TO_E164)` then strip `+` |

---

## Common Pitfalls

### Pitfall 1: instance_name argument still passed to WuzAPI
**What goes wrong:** Evolution calls use `instance_name` as the first argument (e.g., `send_text_message(instance_name, phone, text)`). WuzAPI has no such argument. Passing it will cause a `TypeError`.
**How to avoid:** Remove all `instance_name` arguments when calling WuzAPIClient methods. The `default_instance_name` attribute on `UnifiedWhatsAppService` can remain for backward compat but is unused in sends.

### Pitfall 2: Extracting whatsapp_id from wrong response key
**What goes wrong:** Code uses `response["key"]["id"]` (Evolution shape) instead of `response["data"]["Id"]` (WuzAPI shape).
**How to avoid:** Always use `response.get("data", {}).get("Id")` or parse via `WuzAPISendResponse` model: `WuzAPISendResponse(**response).data.Id`.

### Pitfall 3: Sending media_url directly to WuzAPI without encoding
**What goes wrong:** WuzAPIClient.send_media() requires a base64 data URI. Passing an HTTP URL directly will either fail or silently send a broken message.
**How to avoid:** In the queue pipeline's `_send_message_impl`, call `data_uri = await fetch_and_encode_media(request.media_url)` before `wuzapi_client.send_media(media_type, phone, data_uri)`.

### Pitfall 4: Phone with @s.whatsapp.net suffix
**What goes wrong:** WhatsApp JID format `5511NNNNN@s.whatsapp.net` is rejected by WuzAPI — it uses the raw phone number without the suffix.
**How to avoid:** Never add `@s.whatsapp.net`. The existing normalization pipeline produces bare digit strings; verify no code path appends the suffix before calling WuzAPI. The `send_message()` method in `WhatsAppMessageService` sets `chat_id = f"{formatted_number}@s.whatsapp.net"` for the database record — that is fine (it's stored but never sent to WuzAPI).

### Pitfall 5: IdempotentMessageSender using encrypted patient.phone
**What goes wrong:** `patient.phone` is the encrypted column; using it directly produces garbled text sent to WuzAPI.
**How to avoid:** Use `patient.phone_decrypted` (the decrypted property) then apply `normalize_phone(..., mode=PhoneValidationMode.BR_TO_E164)` and strip the `+`.

### Pitfall 6: Forgetting to update the shutdown() method
**What goes wrong:** `UnifiedWhatsAppService.shutdown()` calls `disconnect()` on `self._queue_client`. After migration, the client is a `WuzAPIClient` which has `disconnect()` — this is compatible. But it also calls `evolution_client.health_check()` in `health_check()` — that call is removed (see health check replacement above).
**How to avoid:** Run the full health_check() method and ensure no remaining Evolution references.

---

## Code Examples

### Plan 36-01: Constructing WuzAPIClient in UnifiedWhatsAppService

```python
# app/services/unified_whatsapp_service.py

# New imports
from app.integrations.wuzapi import get_wuzapi_client, WuzAPIClient

# Remove import:
# from app.integrations.whatsapp.services.evolution_client import EvolutionAPIClient

# In __init__:
self._wuzapi_client: Optional[WuzAPIClient] = None

# Circuit breaker rename:
self._evolution_breaker = CircuitBreaker(
    name="wuzapi",  # was "evolution_api"
    failure_threshold=5,
    recovery_timeout=60,
    success_threshold=3,
)

# _get_queue_client() replacement:
async def _get_wuzapi_client(self) -> WuzAPIClient:
    if not self._wuzapi_client:
        token = getattr(settings, "WHATSAPP_WUZAPI_TOKEN", None)
        base_url = getattr(settings, "WHATSAPP_WUZAPI_BASE_URL", "")
        if not token:
            raise ExternalServiceError("WuzAPI not configured: WHATSAPP_WUZAPI_TOKEN missing")
        self._wuzapi_client = get_wuzapi_client(base_url=base_url, token=token)
        await self._wuzapi_client.connect()
    return self._wuzapi_client
```

### Plan 36-01: Direct send path replacement

```python
# _send_via_direct_api() rewrite for WuzAPI
async def _send_via_direct_api(self, message: Message, **kwargs) -> bool:
    patient = await self._ensure_patient_loaded(message)
    if not patient or not patient.phone_decrypted:
        raise ExternalServiceError(f"Patient {message.patient_id} has no phone number")

    phone = normalize_phone(patient.phone_decrypted, mode=PhoneValidationMode.BR_TO_E164)
    if not phone:
        raise ExternalServiceError(f"Patient {message.patient_id} has invalid phone number")
    if phone.startswith("+"):
        phone = phone[1:]  # WuzAPI expects raw digits, no + prefix

    wuzapi_client = await self._get_wuzapi_client()

    if message.type == MessageType.TEXT or not message.type:
        response = await wuzapi_client.send_text(phone=phone, message=message.content or "")
    else:
        # Media: must encode URL to base64 data URI first
        from app.integrations.wuzapi.media import fetch_and_encode_media
        media_url = (message.message_metadata or {}).get("media_url", "")
        data_uri = await fetch_and_encode_media(media_url)
        media_type = (message.message_metadata or {}).get("media_type", "image")
        response = await wuzapi_client.send_media(
            media_type=media_type, phone=phone, data_uri=data_uri
        )

    # Extract ID: WuzAPI returns {"data": {"Id": "..."}, "success": True}
    message.whatsapp_id = response.get("data", {}).get("Id")
    message.status = MessageStatus.SENT
    message.sent_at = now_sao_paulo()
    ...
```

### Plan 36-01: Health check replacement

```python
# health_check() - WuzAPI replacement
async def _check_wuzapi_health(self) -> dict:
    """Check WuzAPI session status (replaces evolution_client.health_check)."""
    wuzapi_client = await self._get_wuzapi_client()
    status_resp = await wuzapi_client.get_session_status()
    status_data = status_resp.get("data", {})
    is_connected = status_data.get("Connected", False) and status_data.get("LoggedIn", False)
    return {
        "is_connected": is_connected,
        "connected": status_data.get("Connected"),
        "logged_in": status_data.get("LoggedIn"),
    }
```

### Plan 36-02: WhatsAppMessageService constructor

```python
# message_service.py - constructor change
class WhatsAppMessageService:
    def __init__(
        self,
        wuzapi_client,  # was: evolution_client: EvolutionAPIClient
        db_session: AsyncSession,
        message_queue: MessageQueue,
        message_status_handler=None,
    ):
        self.wuzapi_client = wuzapi_client  # was: self.evolution_client

        # Circuit breaker rename
        self.evolution_breaker = CircuitBreaker(
            name="wuzapi_queue",  # was "evolution_api_queue"
            ...
        )
```

### Plan 36-02: _send_message_impl rewrite

```python
async def _send_message_impl(self, message: WhatsAppMessage, request_data: dict):
    request = MessageRequest(**request_data)

    async def _send_with_breaker():
        phone = request.to  # already normalized by validate_phone_number()
        # Ensure no @s.whatsapp.net suffix
        if "@" in phone:
            phone = phone.split("@")[0]

        if request.message_type == MessageType.TEXT:
            return await self.wuzapi_client.send_text(
                phone=phone,
                message=request.text or "",
            )
        else:
            from app.integrations.wuzapi.media import fetch_and_encode_media
            data_uri = await fetch_and_encode_media(request.media_url or "")
            media_type = request.message_type.value.lower()  # "image", "audio", etc.
            return await self.wuzapi_client.send_media(
                media_type=media_type,
                phone=phone,
                data_uri=data_uri,
                caption=request.media_caption,
                filename=request.filename,
            )

    response = await self.evolution_breaker.call(_send_with_breaker)

    # Extract WuzAPI message ID
    message.external_id = response.get("data", {}).get("Id")
    message.status = MessageStatus.SENT
    message.sent_at = now_sao_paulo_naive()
```

### Plan 36-02: IdempotentMessageSender swap

```python
# idempotent_sender.py

# Remove:
# from app.integrations.evolution import EvolutionClient

# Add:
from app.integrations.wuzapi import get_wuzapi_client

# Property rename:
@property
def wuzapi_client(self):
    if self._wuzapi_client is None:
        from app.config import settings
        self._wuzapi_client = get_wuzapi_client(
            base_url=getattr(settings, "WHATSAPP_WUZAPI_BASE_URL", ""),
            token=getattr(settings, "WHATSAPP_WUZAPI_TOKEN", ""),
        )
    return self._wuzapi_client

# In send_message():
response = await self.wuzapi_client.send_text(
    phone=phone,   # raw digits from patient.phone_decrypted, normalized
    message=content,
)
# Extract ID from WuzAPI shape:
wuzapi_id = response.get("data", {}).get("Id")
if wuzapi_id:
    message.whatsapp_id = wuzapi_id
    message.status = MessageStatus.SENT
    message.sent_at = now_sao_paulo()
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Evolution API client (httpx/aiohttp) — Stack A + B | WuzAPIClient (aiohttp + backoff) already built in Phase 33 | Swap, not rebuild |
| Circuit breaker key `"evolution_api"` | Circuit breaker key `"wuzapi"` | Redis state key changes; old state auto-expires |
| `response["key"]["id"]` (Evolution message ID) | `response["data"]["Id"]` (WuzAPI message ID) | Extraction path changes |
| HTTP media URL passed directly | base64 data URI required by WuzAPI send_media | fetch_and_encode_media() call inserted |

---

## Open Questions

1. **`WhatsAppMessageService` callers in `UnifiedWhatsAppService._get_queue_service()`**
   - What we know: `_get_queue_service()` currently passes `evolution_client` to `WhatsAppMessageService` constructor
   - What's unclear: After Plan 36-02 changes the constructor signature, `_get_queue_service()` must also be updated in Plan 36-01 to pass `wuzapi_client` instead
   - Recommendation: Plan 36-01 should also update `_get_queue_service()` to use `_get_wuzapi_client()` — both plans touch `unified_whatsapp_service.py` but Plan 36-01 owns the whole file

2. **`patient.phone` vs `patient.phone_decrypted` in `IdempotentMessageSender`**
   - What we know: `IdempotentMessageSender` uses `patient.phone` (line 401), not `patient.phone_decrypted`. The `UnifiedWhatsAppService` always uses `phone_decrypted`.
   - What's unclear: Is `Patient.phone` the encrypted ciphertext or plaintext? Based on `UnifiedWhatsAppService` always using `phone_decrypted`, `phone` is encrypted.
   - Recommendation: Switch to `patient.phone_decrypted` in the IdempotentMessageSender swap. Add `normalize_phone(..., BR_TO_E164)` and strip `+`.

3. **`sync_contacts()` method in `WhatsAppMessageService`**
   - What we know: `sync_contacts()` calls `self.evolution_client.get_contacts(instance_name)` — Evolution-only API, no WuzAPI equivalent
   - What's unclear: Is `sync_contacts()` called anywhere in production?
   - Recommendation: Stub it out in Phase 36 (raise `NotImplementedError` or return empty list with log warning). Full removal in Phase 37.

4. **`WhatsAppMessage.chat_id` still set to `phone@s.whatsapp.net`**
   - What we know: `send_message()` in `WhatsAppMessageService` sets `chat_id = f"{formatted_number}@s.whatsapp.net"` — this is a DB field, never sent to WuzAPI
   - Recommendation: Leave as-is for Phase 36. The JID format is useful for the WhatsApp message model's own identification. Phase 37 can reassess.

---

## Migration Checklist (for planner reference)

**Plan 36-01 (`UnifiedWhatsAppService`):**
- [ ] Remove `EvolutionAPIClient` import and `MockEvolutionAPIClient` import
- [ ] Remove `default_instance_name` usage in send paths (keep param for compat)
- [ ] Add `_get_wuzapi_client()` method using `get_wuzapi_client()` factory
- [ ] Update `_get_queue_service()` to pass WuzAPI client
- [ ] Rename `_evolution_breaker` → keep name or rename to `_wuzapi_breaker`; change `name="wuzapi"`
- [ ] Rewrite `_send_via_direct_api()` to call `send_text()` / `send_media()`
- [ ] Rewrite `health_check()` to call `get_session_status()`
- [ ] Update `shutdown()` to disconnect WuzAPI client
- [ ] Verify no remaining `EvolutionAPIClient` references

**Plan 36-02 (`WhatsAppMessageService` + `IdempotentMessageSender`):**
- [ ] Change `WhatsAppMessageService.__init__` parameter: `evolution_client` → `wuzapi_client`
- [ ] Rename `self.evolution_client` → `self.wuzapi_client`
- [ ] Rename circuit breaker: `"evolution_api_queue"` → `"wuzapi_queue"`
- [ ] Rewrite `_send_message_impl()` to use `send_text()` and `send_media()` (with fetch_and_encode_media for media)
- [ ] Update `message.external_id` extraction: `response["data"]["Id"]`
- [ ] Stub out `sync_contacts()` (NotImplementedError + log)
- [ ] In `IdempotentMessageSender`: remove `EvolutionClient` import
- [ ] Add WuzAPI client lazy-load via `get_wuzapi_client()`
- [ ] Switch `patient.phone` → `patient.phone_decrypted` + normalize + strip `+`
- [ ] Update `message.whatsapp_id` extraction: `response.get("data", {}).get("Id")`

---

## Sources

### Primary (HIGH confidence)
- `backend-hormonia/app/integrations/wuzapi/client.py` — WuzAPIClient API: `send_text(phone, message)`, `send_media(media_type, phone, data_uri, ...)`, `get_session_status()`, circuit breaker config
- `backend-hormonia/app/integrations/wuzapi/models.py` — `WuzAPISendResponse.data.Id` confirmed
- `backend-hormonia/app/integrations/wuzapi/mock.py` — mock response shape: `{"data": {"Id": "mock_...", "Details": "Sent"}, "success": True}`
- `backend-hormonia/app/integrations/wuzapi/__init__.py` — `get_wuzapi_client()` factory confirmed
- `backend-hormonia/app/services/unified_whatsapp_service.py` — full current implementation read
- `backend-hormonia/app/integrations/whatsapp/services/message_service.py` — `WhatsAppMessageService` full implementation read
- `backend-hormonia/app/domain/messaging/delivery/idempotent_sender.py` — `IdempotentMessageSender` full implementation read
- `backend-hormonia/app/config/settings/integrations.py` — settings fields confirmed
- `.planning/REQUIREMENTS.md` — requirements OUT-01 through OUT-04 definitions
- `.planning/STATE.md` — accumulated project decisions

### Secondary (MEDIUM confidence)
- Project memory (MEMORY.md): confirms no dual-provider mode, hard cut decision, Phase 37 depends on Phase 36 completing

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all modules read from source; no assumptions about APIs
- Architecture patterns: HIGH — all three call sites fully read and analyzed
- Pitfalls: HIGH — derived directly from reading actual code differences between Evolution and WuzAPI APIs

**Research date:** 2026-03-02
**Valid until:** Until Phase 37 tombstones Evolution files — these findings remain valid for the duration of Phase 36 work
