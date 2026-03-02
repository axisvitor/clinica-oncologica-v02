# Phase 34: Webhook Handler - Research

**Researched:** 2026-03-02
**Domain:** FastAPI webhook endpoint, HMAC-SHA256 validation, WuzAPI event parsing, Redis SET NX idempotency, LGPD opt-out
**Confidence:** HIGH (all critical patterns verified from project codebase; WuzAPI payload structure MEDIUM — inferred from whatsmeow Go types + WuzAPI API.md; no real payload capture yet)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| WH-01 | New webhook endpoint at `/webhooks/wuzapi` routes by `type` field (Message, ReadReceipt) | FastAPI router pattern in `app/integrations/whatsapp/api/webhooks.py`; register in `app/api/v2/router.py`; WuzAPI event type field is `type` |
| WH-02 | Inbound message parser extracts sender phone, message text, media info, and message ID from WuzAPI `Message` event payload | WuzAPI sends whatsmeow `events.Message`: `event.Info.ID` is message ID, `event.Info.Sender` is JID (e.g. `5511987654321@s.whatsapp.net`), text in `event.Message.Conversation` or `event.Message.ExtendedTextMessage.Text` |
| WH-03 | ReadReceipt parser maps WuzAPI receipt types to internal `MessageStatus` (SENT, DELIVERED, READ, PLAYED) | whatsmeow `ReceiptType`: `""` (Delivered), `"read"` (Read), `"played"` (Played), `"sender"` (Sent). Map to existing `MessageStatus` enum |
| WH-04 | HMAC validation uses `x-hmac-signature` header with SHA-256 on raw request body bytes | `WebhookHMACValidator` exists at `app/integrations/whatsapp/security/hmac_validator.py`; reuse it; critical: read `await request.body()` BEFORE `json.loads()` |
| WH-05 | LGPD opt-out handler detects STOP/PARAR/CANCELAR keywords in WuzAPI inbound message payloads | `is_opt_out_message()` and `_handle_opt_out()` already implemented in `app/services/webhook/handlers/message_handler.py`; wire to new extractor output |
| WH-06 | Webhook idempotency uses WuzAPI `event.Info.ID` as deduplication key in Redis SET NX | `AtomicWebhookIdempotency.try_acquire()` exists at `app/services/webhook/idempotency.py`; use `event_id = event.Info.ID`, `event_type = "wuzapi:message"` or `"wuzapi:receipt"` |
</phase_requirements>

---

## Summary

Phase 34 creates a new WuzAPI webhook endpoint at `/webhooks/wuzapi` that is independent of the existing Evolution API webhook infrastructure at `/webhooks/whatsapp/evolution/`. The existing project already has all the building blocks: HMAC validation (`WebhookHMACValidator`), Redis idempotency (`AtomicWebhookIdempotency`), opt-out logic (`is_opt_out_message` + `_handle_opt_out`), and the DLQ handler (`DLQHandler`). The primary new work is: (1) a thin FastAPI POST endpoint that reads raw body bytes first, then validates HMAC, then routes by `type`; (2) a `WuzAPIMessageExtractor` Pydantic-based parser that maps the WuzAPI/whatsmeow payload structure to internal types; and (3) wiring idempotency, opt-out, and LID DLQ routing into the event processing pipeline.

The WuzAPI payload format is based on the whatsmeow Go library. WuzAPI serializes whatsmeow events to JSON using their native Go field names (PascalCase). For `Message` events: `type` = `"Message"`, message ID at `event.Info.ID`, sender JID at `event.Info.Sender` (e.g. `"5511987654321@s.whatsapp.net"`), text at `event.Message.Conversation`. For `ReadReceipt` events: `type` = `"ReadReceipt"`, `event.Receipt.Type` is a string matching whatsmeow ReceiptType constants. The HMAC signature in the `x-hmac-signature` header is a plain hex-encoded SHA-256 HMAC of the raw JSON body bytes — no prefix like `sha256=`.

The most important implementation constraint (documented in STATE.md) is: **read the raw body bytes first with `await request.body()`, then call `json.loads()`. Never call `await request.json()` before computing the HMAC — it consumes the body stream and makes raw bytes unavailable.**

**Primary recommendation:** Create `app/integrations/wuzapi/webhook.py` for the endpoint + extractor in the existing wuzapi package, wire it via `app/api/v2/router.py`. Reuse `WebhookHMACValidator`, `AtomicWebhookIdempotency`, and the existing opt-out handler. New code is < 300 lines total.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastapi` | installed | POST endpoint, `Request` object, `HTTPException` | Project-wide API framework |
| `pydantic` v2 | installed | WuzAPIMessageExtractor models, type-safe payload parsing | Project-wide model standard |
| `hashlib` + `hmac` (stdlib) | — | SHA-256 HMAC computation for `x-hmac-signature` | Already used in `WebhookHMACValidator` |
| `redis.asyncio` | installed | Redis SET NX via `AtomicWebhookIdempotency` | Project canonical Redis client |
| `structlog` / `logging` | installed | Structured event logging | Existing pattern in webhook handlers |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sqlalchemy.ext.asyncio.AsyncSession` | installed | DB session for opt-out `patient.messaging_stopped_at` update | All FastAPI route handlers use async DB per v1.4 migration |
| `app.integrations.whatsapp.security.hmac_validator.WebhookHMACValidator` | project | HMAC SHA-256 validation against `x-hmac-signature` | Reuse — don't hand-roll |
| `app.services.webhook.idempotency.AtomicWebhookIdempotency` | project | Redis SET NX deduplication by `event.Info.ID` | Reuse — don't hand-roll |
| `app.services.webhook.handlers.message_handler.is_opt_out_message` | project | Keyword detection (STOP/PARAR/CANCELAR) | Import and reuse — already LGPD-compliant |
| `app.services.dlq.*` | project | Route LID senders to DLQ | Use `app/integrations/whatsapp/queue/dlq.py`'s `DLQHandler` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Reuse `WebhookHMACValidator` | Custom HMAC logic | Don't re-implement — the validator handles prefix parsing, `compare_digest`, and error logging |
| Reuse `AtomicWebhookIdempotency` | Direct `redis.set(key, nx=True)` | The existing service handles metrics, TTL selection, DB fallback — all needed here |
| New `WuzAPIMessageExtractor` class | Adapt Evolution extractor | Evolution extractor is deeply coupled to Evolution JID format (with `@lid` LID detection, alternate JIDs) — too much to adapt; create a focused new extractor |

---

## Architecture Patterns

### Recommended Project Structure

```
backend-hormonia/app/integrations/wuzapi/
├── __init__.py          # Existing — add webhook exports
├── client.py            # Existing
├── mock.py              # Existing
├── models.py            # Existing — add WuzAPIWebhookEvent, WuzAPIMessageEvent, WuzAPIReceiptEvent
├── errors.py            # Existing
├── media.py             # Existing
└── webhook.py           # NEW: endpoint router + WuzAPIMessageExtractor

backend-hormonia/tests/integrations/wuzapi/
├── test_wuzapi_client.py   # Existing
├── test_wuzapi_media.py    # Existing
├── test_wuzapi_mock.py     # Existing
└── test_wuzapi_webhook.py  # NEW: webhook handler tests
```

The router is registered in `app/api/v2/router.py` with `prefix="/api/v2"`. The new WuzAPI endpoint becomes `POST /api/v2/webhooks/wuzapi`.

### Pattern 1: Raw Body Read Before HMAC (Critical)

**What:** FastAPI's `Request.body()` returns raw bytes that can be awaited multiple times (FastAPI caches the body). Always call it first before `json.loads()`.

**When to use:** Every webhook endpoint that requires HMAC validation.

**Example (from existing `app/integrations/whatsapp/api/webhooks.py`):**

```python
# Source: app/integrations/whatsapp/api/webhooks.py line 312
@router.post("/wuzapi")
async def wuzapi_webhook(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    # STEP 1: Read raw body FIRST — before json.loads()
    raw_body = await request.body()

    # STEP 2: Validate HMAC against raw bytes
    signature = request.headers.get("x-hmac-signature", "")
    if not WebhookHMACValidator.validate_signature(
        raw_body, signature, settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET
    ):
        raise HTTPException(status_code=403, detail="Invalid HMAC signature")

    # STEP 3: Parse JSON after HMAC validated
    payload = json.loads(raw_body)
    ...
```

### Pattern 2: WuzAPI Webhook Payload Shape

**What:** WuzAPI serializes whatsmeow events to JSON. The top-level `type` field discriminates event type. All other fields mirror the Go struct field names (PascalCase in JSON).

**Confidence:** MEDIUM — inferred from whatsmeow Go types + WuzAPI API.md. Real payload capture needed in staging before finalizing parser field paths.

**Message event structure (inferred):**

```json
{
  "type": "Message",
  "token": "user-token",
  "event": {
    "Info": {
      "ID": "3EB0ABC123DEF456",
      "Sender": "5511987654321@s.whatsapp.net",
      "Chat": "5511987654321@s.whatsapp.net",
      "Timestamp": "2026-03-02T00:00:00Z",
      "PushName": "João",
      "IsFromMe": false
    },
    "Message": {
      "Conversation": "STOP",
      "ExtendedTextMessage": null,
      "ImageMessage": null,
      "AudioMessage": null,
      "VideoMessage": null,
      "DocumentMessage": null
    }
  }
}
```

**ReadReceipt event structure (inferred):**

```json
{
  "type": "ReadReceipt",
  "token": "user-token",
  "event": {
    "Info": {
      "ID": "3EB0ABC123DEF456",
      "Sender": "5511987654321@s.whatsapp.net",
      "Chat": "5511987654321@s.whatsapp.net",
      "Timestamp": "2026-03-02T00:00:00Z"
    },
    "Receipt": {
      "Type": "read",
      "MessageIDs": ["3EB0ABC123DEF456"],
      "Timestamp": "2026-03-02T00:00:00Z"
    }
  }
}
```

**WARNING — Low confidence on exact nesting:** The `event` key wrapping the whatsmeow struct is inferred from WuzAPI's pattern (it wraps events in a top-level object). Real payloads may have different nesting. The parser MUST use `dict.get()` with fallbacks and log unknown structures.

### Pattern 3: HMAC Validation (Reuse WebhookHMACValidator)

**What:** `WebhookHMACValidator` in `app/integrations/whatsapp/security/hmac_validator.py` already implements SHA-256 HMAC with `hmac.compare_digest`. It handles both plain hex and `sha256=<hex>` prefixes.

**WuzAPI specifics:** The `x-hmac-signature` header contains a plain hex-encoded HMAC-SHA256 digest of the raw JSON body bytes. No `sha256=` prefix — but `WebhookHMACValidator._parse_signature()` handles that transparently.

```python
# Source: app/integrations/whatsapp/security/hmac_validator.py
from app.integrations.whatsapp.security.hmac_validator import WebhookHMACValidator

# In the endpoint:
signature = request.headers.get("x-hmac-signature", "")
secret = settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET
if secret:  # HMAC only enforced when secret is configured
    if not WebhookHMACValidator.validate_signature(raw_body, signature, secret):
        raise HTTPException(status_code=403, detail="Invalid HMAC signature")
```

### Pattern 4: Redis Idempotency (Reuse AtomicWebhookIdempotency)

**What:** `AtomicWebhookIdempotency.try_acquire(event_type, event_id)` does Redis `SET NX EX` atomically. Returns `(True, "acquired")` for new events, `(False, "duplicate")` for already-seen events.

**WuzAPI event ID:** `event["Info"]["ID"]` — the whatsmeow MessageID (hex string like `"3EB0ABC123DEF456"`).

```python
# Source: app/services/webhook/idempotency.py
from app.services.webhook.idempotency import AtomicWebhookIdempotency
from app.core.redis_manager import get_async_redis_client

redis = await get_async_redis_client()
idempotency = AtomicWebhookIdempotency(redis_client=redis)

event_id = payload.get("event", {}).get("Info", {}).get("ID", "")
if not event_id:
    # Unknown ID — generate hash of full payload as fallback
    event_id = hashlib.sha256(raw_body).hexdigest()

event_type_key = "wuzapi:message"  # or "wuzapi:receipt"
acquired, reason = await idempotency.try_acquire(event_type_key, event_id)
if not acquired:
    # Return 200 OK for duplicates — WuzAPI expects 200 for all processed events
    return {"status": "duplicate", "event_id": event_id}
```

**TTL:** `AtomicWebhookIdempotency` uses 86400s (24h) for `message` events; 7200s (2h) for other events. The `event_type_key = "wuzapi:message"` will get the 24h TTL. This is correct for deduplication.

### Pattern 5: WuzAPIMessageExtractor

**What:** A new Pydantic-based extractor that maps the WuzAPI JSON payload to an internal representation. Should return a typed `InboundMessage` object (or dict with `phone`, `text`, `message_id`, `is_lid`).

**Responsibilities:**
1. Parse `event.Info.Sender` → extract phone digits (strip `@s.whatsapp.net` or detect `@lid`)
2. Extract text from `event.Message.Conversation` or `event.Message.ExtendedTextMessage.Text`
3. Detect `@lid` in sender JID — route to DLQ instead of patient lookup
4. Return `message_id = event.Info.ID`

**Implementation:**

```python
# Source: Pattern derived from app/services/webhook/utils/message_extractor.py
import re
from dataclasses import dataclass
from typing import Any

@dataclass
class WuzAPIInboundMessage:
    message_id: str
    phone: str  # raw digits, e.g. "5511987654321"
    text: str   # normalized text content
    is_lid: bool  # True if sender uses @lid addressing

class WuzAPIMessageExtractor:
    @classmethod
    def extract_message(cls, payload: dict[str, Any]) -> WuzAPIInboundMessage | None:
        """Extract inbound message data from WuzAPI Message event payload."""
        event = payload.get("event") or payload  # Handle both wrapped and flat
        info = event.get("Info", {})
        message_id = info.get("ID", "")
        if not message_id:
            return None

        sender_jid = info.get("Sender", "")
        is_lid = sender_jid.endswith("@lid") or sender_jid.endswith("@hosted.lid")
        phone = cls._jid_to_phone(sender_jid)

        msg = event.get("Message", {}) or {}
        text = (
            msg.get("Conversation")
            or (msg.get("ExtendedTextMessage") or {}).get("Text")
            or ""
        )

        return WuzAPIInboundMessage(
            message_id=message_id,
            phone=phone,
            text=text,
            is_lid=is_lid,
        )

    @classmethod
    def _jid_to_phone(cls, jid: str) -> str:
        """Strip @server suffix and return raw digits."""
        user = jid.split("@")[0] if "@" in jid else jid
        # Handle AD JIDs: user.agent:device@server -> take user part before .
        user = user.split(".")[0] if "." in user else user
        return re.sub(r"[^\d]", "", user)
```

### Pattern 6: ReadReceipt → MessageStatus Mapping

**What:** WuzAPI sends `Receipt.Type` with whatsmeow string values. The internal `MessageStatus` enum has SENT, DELIVERED, READ, PLAYED.

**Mapping (HIGH confidence — from whatsmeow types package):**

```python
# Source: go.mau.fi/whatsmeow/types (verified from pkg.go.dev)
RECEIPT_TYPE_TO_STATUS: dict[str, str] = {
    "":           "delivered",    # ReceiptTypeDelivered = "" (empty string)
    "sender":     "sent",         # ReceiptTypeSender = "sender"
    "read":       "read",         # ReceiptTypeRead = "read"
    "played":     "played",       # ReceiptTypePlayed = "played"
    "read-self":  "read",         # ReceiptTypeReadSelf = "read-self" (treat as read)
    "played-self":"played",       # ReceiptTypePlayedSelf (treat as played)
    # Unknown types → drop silently or log
}
```

**Note on `MessageStatus.PLAYED`:** The existing `MessageStatus` enum in `app/integrations/whatsapp/models/message.py` does NOT have a `PLAYED` value (only PENDING, SENT, DELIVERED, READ, FAILED, EXPIRED). The plan must decide whether to add `PLAYED` to the enum or map `"played"` → `READ`. Requirements say map to `PLAYED` — so the enum must be extended by Plan 34-02.

### Pattern 7: LID Sender → DLQ Routing

**What:** If `is_lid = True`, route the event to the DLQ instead of processing normally. Per STATE.md decision: "LID (@lid) senders routed to DLQ from day one — never silently dropped (LGPD Art. 18 risk)."

**How:** Use `app/integrations/whatsapp/queue/dlq.py`'s `DLQHandler.route_to_dlq()` or the simpler Redis-backed `app/services/webhook_dlq.WebhookDLQ` if the LID event has no patient_id yet. The key is to preserve the event for manual review.

**Implementation decision for planner:** Since a LID sender has no patient lookup possible, the DLQ entry should use `patient_id=None` OR be a raw Redis DLQ entry. Recommend checking `app/services/webhook_dlq.py` for a lighter-weight alternative.

### Pattern 8: WHATSAPP_WUZAPI_WEBHOOK_SECRET in Settings

**What:** The WuzAPI webhook secret is not yet in `IntegrationsSettings`. It must be added as `WHATSAPP_WUZAPI_WEBHOOK_SECRET: Optional[str]`. This is a Phase 35 requirement (CFG-01), but the Phase 34 endpoint needs to read it.

**Resolution:** Phase 34 reads the setting via `os.environ.get("WHATSAPP_WUZAPI_WEBHOOK_SECRET")` directly (not from `settings`) until Phase 35 adds it to the settings class. This avoids a cross-phase dependency.

**Alternative:** Add `WHATSAPP_WUZAPI_WEBHOOK_SECRET` to `IntegrationsSettings` in Phase 34 (minor scope creep but cleaner). The planner should choose based on simplicity.

### Pattern 9: Router Registration

**What:** The existing `app/api/v2/router.py` registers all sub-routers. The new WuzAPI webhook router should be registered similarly to the WhatsApp Evolution webhook router.

```python
# In app/api/v2/router.py (new addition)
from app.integrations.wuzapi.webhook import router as wuzapi_webhook_router
api_v2_router.include_router(wuzapi_webhook_router, tags=["wuzapi-webhooks-v2"])
```

The router itself sets `prefix="/api/v2/webhooks"` and the endpoint is `/wuzapi`, giving full path `POST /api/v2/webhooks/wuzapi`.

### Anti-Patterns to Avoid

- **Calling `await request.json()` before HMAC validation:** Destroys raw bytes needed for HMAC. Always `raw_body = await request.body()` first, then `json.loads(raw_body)`.
- **Silently dropping LID senders:** STATE.md decision is explicit — `@lid` senders go to DLQ, not silent ignore.
- **Returning 4xx for duplicate events:** WuzAPI expects 200 for all events it delivers. Return `{"status": "duplicate"}` with HTTP 200 for already-processed event IDs.
- **Using `request.headers.get("X-HMAC-Signature")` (capital case):** FastAPI normalizes headers to lowercase. Use `request.headers.get("x-hmac-signature")`.
- **Re-implementing HMAC:** `WebhookHMACValidator` handles edge cases (prefix stripping, `compare_digest`, algorithm fallback). Don't hand-roll.
- **Hard-coding `"stop"` only for opt-out:** The existing `OPT_OUT_KEYWORDS` frozenset in `message_handler.py` already covers STOP, PARAR, CANCELAR, and 10+ Portuguese variants. Import and reuse it.
- **Importing `MessageWebhookHandler` directly in the new endpoint:** The `MessageWebhookHandler` class is deeply coupled to Evolution API payload shapes. Extract only `is_opt_out_message()` and `_handle_opt_out()` functions.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HMAC SHA-256 validation | Custom `hmac.new()` inline | `WebhookHMACValidator.validate_signature()` | Handles prefix stripping, `compare_digest` (timing attack safe), error logging |
| Redis SET NX idempotency | Direct `redis.set(key, nx=True)` | `AtomicWebhookIdempotency.try_acquire()` | DB fallback, TTL selection, metrics recording |
| Opt-out keyword detection | Custom `in` check | `is_opt_out_message()` from `message_handler.py` | 12+ Portuguese/English variants already defined; LGPD-compliant |
| Opt-out DB write | Custom `patient.messaging_stopped_at = now()` | `_handle_opt_out()` from `message_handler.py` | Handles consent revocation, error recovery, audit log |
| Phone extraction from JID | String split | `_clean_phone_from_jid()` pattern from `message_extractor.py` | Handles digit extraction, leading zero stripping |

**Key insight:** This phase is primarily wiring, not invention. The heavy lifting (HMAC, idempotency, opt-out, DLQ) is already built. The new code is a thin FastAPI endpoint + a Pydantic-based payload extractor specific to WuzAPI's whatsmeow-derived JSON shape.

---

## Common Pitfalls

### Pitfall 1: Body Stream Consumed Before HMAC

**What goes wrong:** Developer calls `payload = await request.json()` at the top of the handler, then tries to compute HMAC — but the stream is already consumed.
**Why it happens:** FastAPI's `Request.json()` is a convenience method that reads and parses in one step.
**How to avoid:** Always `raw_body = await request.body()` first. FastAPI caches the body internally after first read, so subsequent `await request.body()` calls return the same bytes.
**Warning signs:** HMAC validation always fails even with correct secret; `await request.body()` after `await request.json()` returns `b""`.

### Pitfall 2: WuzAPI Payload Nesting Uncertainty

**What goes wrong:** Parser assumes `payload["event"]["Info"]["ID"]` but real payload uses `payload["Info"]["ID"]` (flat structure), or vice versa.
**Why it happens:** WuzAPI's Go serialization of whatsmeow events is not fully documented with examples.
**How to avoid:** (1) Use defensive `payload.get("event") or payload` to handle both flat and wrapped; (2) Log the raw payload at DEBUG level for the first 10 events in staging; (3) Write tests against both payload shapes.
**Warning signs:** `message_id` extracts as `None` or `""` consistently.

### Pitfall 3: Empty String ReceiptType

**What goes wrong:** `receipt_type = event["Receipt"]["Type"]` evaluates to `""` (empty string, meaning Delivered), but developer treats empty string as "unknown/missing" and drops the event.
**Why it happens:** `ReceiptTypeDelivered = ""` in whatsmeow — this is the zero value. `if not receipt_type:` would incorrectly filter out Delivered receipts.
**How to avoid:** Use explicit key lookup: `RECEIPT_TYPE_TO_STATUS.get(receipt_type)` where the dict has `"": "delivered"`. Check `receipt_type is not None` not `bool(receipt_type)`.
**Warning signs:** DELIVERED status never recorded in the database.

### Pitfall 4: PLAYED Missing from MessageStatus

**What goes wrong:** `MessageStatus.PLAYED` doesn't exist in the enum — `MessageStatus("played")` raises `ValueError`.
**Why it happens:** The existing `MessageStatus` enum was defined before WuzAPI and doesn't include PLAYED.
**How to avoid:** Plan 34-02 must extend `MessageStatus` with `PLAYED = "played"` in `app/integrations/whatsapp/models/message.py`. Or map `"played"` → `MessageStatus.READ` as a safe approximation.
**Warning signs:** `ValueError: 'played' is not a valid MessageStatus` in production logs.

### Pitfall 5: LID Sender Silently Dropped

**What goes wrong:** Developer checks `if is_lid: return` without DLQ routing.
**Why it happens:** LID resolution is complex; early exit seems simpler.
**How to avoid:** STATE.md and WH-02 requirements explicitly mandate DLQ routing for LID. Implement: `if is_lid: await _route_lid_to_dlq(event_data, db); return {"status": "queued_for_review"}`.
**Warning signs:** Patient complaints about unreceived messages; no DLQ entries for `@lid` events in monitoring.

### Pitfall 6: HMAC Validation Not Bypassed When Secret Not Set

**What goes wrong:** Endpoint raises 403 for all requests because `WHATSAPP_WUZAPI_WEBHOOK_SECRET` is not yet configured.
**Why it happens:** Strict HMAC enforcement when secret is `None`.
**How to avoid:** Mirror the existing evolution webhook pattern: if `secret` is `None` (not configured), log a warning and skip HMAC check. In production, the secret must be set (Phase 35 startup validation enforces this). In development/testing, allow bypass.
**Warning signs:** All webhook events rejected with 403 even in development.

### Pitfall 7: Event ID Missing or Empty

**What goes wrong:** `event.Info.ID` is absent in some WuzAPI event shapes (e.g., system events, status updates).
**Why it happens:** Not all WuzAPI events carry a message ID.
**How to avoid:** If `event_id` is empty, compute a SHA-256 hash of the raw body as fallback ID. Log a warning. Do not reject the event.
**Warning signs:** Idempotency check skipped for some events; possible duplicate processing.

---

## Code Examples

### Endpoint Skeleton

```python
# Source: Pattern adapted from app/integrations/whatsapp/api/webhooks.py + new WuzAPI requirements
import hashlib
import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.async_engine import get_async_db
from app.core.redis_manager import get_async_redis_client
from app.integrations.whatsapp.security.hmac_validator import WebhookHMACValidator
from app.integrations.wuzapi.extractor import WuzAPIMessageExtractor
from app.services.webhook.idempotency import AtomicWebhookIdempotency

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["wuzapi-webhooks"])


@router.post("/wuzapi")
async def wuzapi_webhook(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    # 1. Read raw body FIRST (required for HMAC)
    try:
        raw_body = await request.body()
    except Exception as exc:
        logger.warning("Failed to read WuzAPI webhook body: %s", exc)
        raise HTTPException(status_code=499, detail="Client closed connection")

    # 2. HMAC validation
    secret = os.environ.get("WHATSAPP_WUZAPI_WEBHOOK_SECRET")
    if secret:
        signature = request.headers.get("x-hmac-signature", "")
        if not WebhookHMACValidator.validate_signature(raw_body, signature, secret):
            logger.warning("WuzAPI webhook HMAC validation failed")
            raise HTTPException(status_code=403, detail="Invalid HMAC signature")
    else:
        logger.warning("WHATSAPP_WUZAPI_WEBHOOK_SECRET not configured; skipping HMAC")

    # 3. Parse JSON
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}")

    # 4. Extract event ID and deduplicate
    event_id = _extract_event_id(payload, raw_body)
    event_type = payload.get("type", "unknown")
    redis = await get_async_redis_client()
    idempotency = AtomicWebhookIdempotency(redis_client=redis)
    acquired, reason = await idempotency.try_acquire(f"wuzapi:{event_type.lower()}", event_id)
    if not acquired:
        return {"status": "duplicate", "event_id": event_id}

    # 5. Route by type
    if event_type == "Message":
        return await _handle_message_event(payload, db)
    elif event_type == "ReadReceipt":
        return await _handle_receipt_event(payload, db)
    else:
        logger.debug("WuzAPI webhook: unhandled event type %r", event_type)
        return {"status": "ignored", "type": event_type}


def _extract_event_id(payload: dict, raw_body: bytes) -> str:
    event = payload.get("event") or payload
    info = event.get("Info") or {}
    event_id = info.get("ID") or ""
    if not event_id:
        event_id = hashlib.sha256(raw_body).hexdigest()[:32]
        logger.warning("WuzAPI event missing ID, using body hash: %s", event_id)
    return event_id
```

### WuzAPIMessageExtractor

```python
# Source: Pattern adapted from app/services/webhook/utils/message_extractor.py
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class WuzAPIInboundMessage:
    message_id: str
    phone: str       # Raw digits: "5511987654321"
    text: str        # Normalized text content
    is_lid: bool     # True if sender uses @lid addressing


@dataclass
class WuzAPIReceiptEvent:
    message_ids: list[str]
    receipt_type: str   # whatsmeow ReceiptType string (e.g. "", "read", "played")
    sender_phone: str


# whatsmeow ReceiptType → internal MessageStatus value
# Source: go.mau.fi/whatsmeow/types ReceiptType constants
RECEIPT_TYPE_TO_STATUS = {
    "":           "delivered",
    "sender":     "sent",
    "read":       "read",
    "read-self":  "read",
    "played":     "played",
    "played-self":"played",
    "retry":      "delivered",  # retry delivery receipt
}


class WuzAPIMessageExtractor:
    @classmethod
    def extract_message(cls, payload: dict[str, Any]) -> WuzAPIInboundMessage | None:
        event = payload.get("event") or payload
        info = event.get("Info") or {}
        message_id = info.get("ID") or ""
        if not message_id:
            return None

        sender_jid = info.get("Sender") or ""
        is_lid = "@lid" in sender_jid
        phone = cls._jid_to_phone(sender_jid)
        if not phone:
            return None

        msg = event.get("Message") or {}
        text = (
            msg.get("Conversation")
            or ((msg.get("ExtendedTextMessage") or {}).get("Text"))
            or ""
        )
        return WuzAPIInboundMessage(
            message_id=message_id, phone=phone, text=text, is_lid=is_lid
        )

    @classmethod
    def extract_receipt(cls, payload: dict[str, Any]) -> WuzAPIReceiptEvent | None:
        event = payload.get("event") or payload
        info = event.get("Info") or {}
        receipt = event.get("Receipt") or {}

        sender_jid = info.get("Sender") or ""
        phone = cls._jid_to_phone(sender_jid)
        receipt_type = receipt.get("Type", "")  # Empty string = Delivered
        message_ids = receipt.get("MessageIDs") or [info.get("ID")] or []
        message_ids = [m for m in message_ids if m]

        if not message_ids:
            return None
        return WuzAPIReceiptEvent(
            message_ids=message_ids,
            receipt_type=receipt_type,
            sender_phone=phone,
        )

    @classmethod
    def _jid_to_phone(cls, jid: str) -> str:
        user = jid.split("@")[0] if "@" in jid else jid
        # AD JID format: user.agent:device — take only user part
        user = user.split(".")[0] if "." in user and ":" not in user else user.split(":")[0]
        return re.sub(r"[^\d]", "", user)
```

### Opt-Out Wiring

```python
# Source: app/services/webhook/handlers/message_handler.py — reuse existing functions
from app.services.webhook.handlers.message_handler import is_opt_out_message, _handle_opt_out

async def _handle_message_event(payload: dict, db: AsyncSession) -> dict:
    extractor = WuzAPIMessageExtractor()
    msg = extractor.extract_message(payload)
    if msg is None:
        return {"status": "skipped", "reason": "unextractable"}

    if msg.is_lid:
        await _route_lid_to_dlq(payload, db)
        return {"status": "queued_for_review", "reason": "lid_sender"}

    if is_opt_out_message(msg.text):
        patient = await _find_patient_by_phone(msg.phone, db)
        if patient:
            await _handle_opt_out(patient)  # sets messaging_stopped_at
            # Note: _handle_opt_out takes the patient object and uses its own db session
            # May need adaptation if MessageWebhookHandler.db is unavailable
        return {"status": "opt_out_processed"}

    # Route to flow engine / message handler (downstream of Phase 34)
    return {"status": "processed", "message_id": msg.message_id}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Evolution API webhook at `/webhooks/whatsapp/evolution/{instance}` | WuzAPI webhook at `/webhooks/wuzapi` | Phase 34 (v1.6) | Single fixed endpoint, no instance name parameter |
| Evolution `X-Webhook-Signature` or `X-Evolution-Hmac` header | WuzAPI `x-hmac-signature` header | Phase 34 | Header name change; same SHA-256 algorithm |
| Evolution payload: `event` top-level field, Baileys JID format | WuzAPI payload: `type` top-level field, whatsmeow JID format | Phase 34 | New extractor needed; existing `extract_message_data()` NOT reusable |
| Evolution LID handling: `@lid` alternate JID fields | WuzAPI LID: `@lid` in `Sender` JID only (no alternate JIDs) | Phase 34 | Simpler detection — just check if `@lid` is in Sender JID |
| `MessageStatus` without PLAYED | `MessageStatus` needs PLAYED = "played" | Phase 34 | Enum extension needed |

**Deprecated for Phase 34:**
- Evolution `extract_message_data()` from `app/services/webhook/utils/message_extractor.py` — NOT used for WuzAPI events; the JID field structure is different
- Evolution `WebhookHandler.parse_event()` from `app/integrations/evolution/webhook_handler.py` — Evolution-specific, NOT reused

---

## Open Questions

1. **WuzAPI webhook payload exact nesting (flat vs wrapped)**
   - What we know: WuzAPI API.md confirms `type`, `token`, and `event` fields at top level when using JSON webhook format
   - What's unclear: Whether `event` is the key that wraps the whatsmeow struct, or if whatsmeow fields are at the top level
   - Recommendation: Build the extractor to handle BOTH (try `payload.get("event") or payload`); log the first 10 incoming payloads in staging to confirm

2. **`MessageStatus.PLAYED` — extend enum or map to READ?**
   - What we know: Requirements WH-03 says "map to PLAYED". Existing enum doesn't have PLAYED.
   - What's unclear: Whether adding PLAYED to the enum requires a DB migration (the DB column is `VARCHAR`; no migration needed for adding enum values in Python only)
   - Recommendation: Add `PLAYED = "played"` to `MessageStatus` in Plan 34-02. No DB migration required since the column is a string.

3. **`_handle_opt_out()` function signature compatibility**
   - What we know: `_handle_opt_out(patient: Patient)` is an async method of `MessageWebhookHandler` — it uses `self.db`
   - What's unclear: Whether we need to instantiate the full `MessageWebhookHandler` to call it, or extract `_handle_opt_out` as a standalone function
   - Recommendation: Extract opt-out logic into a standalone `handle_opt_out(patient, db)` async function in `message_handler.py` during Plan 34-03. The existing method body is self-contained (uses `self.db` but this can be parameterized).

4. **LID DLQ routing — which DLQ service to use**
   - What we know: `DLQHandler.route_to_dlq()` requires `patient_id` (UUID), which we don't have for LID senders
   - What's unclear: Whether `app/services/webhook_dlq.WebhookDLQ` or `app/services/dlq/service.py` is the right lightweight alternative
   - Recommendation: Check `app/services/webhook_dlq.py` for a Redis-backed DLQ that doesn't require patient_id. If it exists and accepts raw event data, use it. Otherwise, write a minimal Redis LPUSH to a `dlq:wuzapi:lid` key.

5. **WuzAPI x-hmac-signature format: hex vs base64**
   - What we know: WuzAPI uses SHA-256 HMAC; the header is `x-hmac-signature`
   - What's unclear: Whether the digest is hex-encoded or base64-encoded in the header value
   - Recommendation: `WebhookHMACValidator` generates hex via `.hexdigest()`. If WuzAPI sends base64, the validator will fail. Plan 34-01 should test against a real WuzAPI instance early. As a fallback, add base64 decoding to the validator for the first few staging events.

---

## Validation Architecture

The `.planning/config.json` has `"research": true` but no `nyquist_validation` key — skip Nyquist section per agent instructions. However, the test requirements (TEST-02, TEST-03) explicitly mandate webhook handler tests. Those are assigned to Phase 38, but Phase 34 should create the test file as Wave 0 setup.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-asyncio (`asyncio_mode = "auto"`) |
| Config file | `backend-hormonia/pyproject.toml` |
| Quick run command | `cd backend-hormonia && python3 -m pytest tests/integrations/wuzapi/test_wuzapi_webhook.py -x -q` |
| Full suite command | `cd backend-hormonia && python3 -m pytest tests/integrations/wuzapi/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WH-01 | POST `/webhooks/wuzapi` with valid payload + correct HMAC returns 200; invalid HMAC returns 403 | unit | `pytest tests/integrations/wuzapi/test_wuzapi_webhook.py::test_hmac_valid_returns_200 -x` | ❌ Wave 0 |
| WH-02 | `WuzAPIMessageExtractor.extract_message()` returns correct phone, text, message_id from Message payload | unit | `pytest tests/integrations/wuzapi/test_wuzapi_webhook.py::test_extract_message -x` | ❌ Wave 0 |
| WH-03 | `WuzAPIMessageExtractor.extract_receipt()` maps receipt types to correct MessageStatus | unit | `pytest tests/integrations/wuzapi/test_wuzapi_webhook.py::test_receipt_type_mapping -x` | ❌ Wave 0 |
| WH-04 | HMAC validation rejects tampered payload (body modified after HMAC computed) | unit | `pytest tests/integrations/wuzapi/test_wuzapi_webhook.py::test_hmac_tampered_rejects -x` | ❌ Wave 0 |
| WH-05 | Message with text "STOP" triggers opt-out; `patient.messaging_stopped_at` set | unit | `pytest tests/integrations/wuzapi/test_wuzapi_webhook.py::test_stop_sets_opt_out -x` | ❌ Wave 0 |
| WH-06 | Repeated event with same `event.Info.ID` deduped via Redis SET NX; processed only once | unit | `pytest tests/integrations/wuzapi/test_wuzapi_webhook.py::test_idempotency_dedup -x` | ❌ Wave 0 |

### Wave 0 Gaps

- [ ] `tests/integrations/wuzapi/test_wuzapi_webhook.py` — covers WH-01 through WH-06
- [ ] `tests/integrations/wuzapi/fixtures/` — WuzAPI Message and ReadReceipt payload JSON fixtures (both flat and wrapped formats)
- [ ] `fakeredis` for AtomicWebhookIdempotency in tests (already installed per INTEGRATIONS.md)

*(No new framework installs required — pytest, pytest-asyncio, fakeredis all installed.)*

---

## Sources

### Primary (HIGH confidence)

- Project codebase: `app/integrations/whatsapp/security/hmac_validator.py` — SHA-256 HMAC validation pattern to reuse
- Project codebase: `app/services/webhook/idempotency.py` — `AtomicWebhookIdempotency` Redis SET NX API
- Project codebase: `app/services/webhook/handlers/message_handler.py` — `is_opt_out_message()`, `OPT_OUT_KEYWORDS`, `_handle_opt_out()` ready to import
- Project codebase: `app/integrations/whatsapp/api/webhooks.py` — raw body read pattern (`await request.body()` first), HMAC check flow
- Project codebase: `app/api/v2/router.py` — router registration pattern
- Project codebase: `app/integrations/whatsapp/models/message.py` — `MessageStatus` enum (missing PLAYED)
- `.planning/STATE.md` — locked decisions: LID to DLQ, HMAC body-read order
- `go.mau.fi/whatsmeow/types` (pkg.go.dev) — ReceiptType constants with exact string values verified

### Secondary (MEDIUM confidence)

- `github.com/asternic/wuzapi/blob/main/API.md` — confirms `x-hmac-signature` header name, SHA-256 algorithm, event type names (Message, ReadReceipt), JSON webhook format
- `github.com/asternic/wuzapi/blob/main/handlers.go` — confirms WuzAPI uses whatsmeow library for event structures
- `github.com/tulir/whatsmeow/blob/main/types/events/events.go` — Message and Receipt struct definitions

### Tertiary (LOW confidence)

- WuzAPI webhook JSON payload nesting (flat vs `event`-wrapped) — inferred from API.md and whatsmeow patterns; not confirmed with real payload capture. Flag in blockers.
- `x-hmac-signature` encoding format (hex vs base64) — SHA-256 is hex per WebhookHMACValidator convention; WuzAPI may differ. Needs staging test to confirm.

---

## Metadata

**Confidence breakdown:**
- Standard stack (FastAPI, pydantic, hmac, redis): HIGH — all project-standard
- Architecture (endpoint pattern, HMAC reuse, idempotency reuse, opt-out reuse): HIGH — direct adaptation of proven project patterns
- WuzAPI payload schema (field names, nesting): MEDIUM — inferred from whatsmeow Go types; needs staging validation
- ReceiptType string values: HIGH — verified from official go.mau.fi/whatsmeow/types package docs
- LID detection: HIGH — `@lid` in JID Server field confirmed from whatsmeow JID types

**Research date:** 2026-03-02
**Valid until:** 2026-04-02 (WuzAPI and whatsmeow APIs are stable; internal project patterns don't change without milestones)

---

## Blockers/Concerns Inherited from STATE.md

These pre-existing concerns from STATE.md affect Phase 34 planning:

1. **WuzAPI webhook payload JSON schema is MEDIUM confidence** (inferred from Go source) — real payload capture required before Phase 34 parser code is finalized. The extractor MUST be defensive with `.get()` calls and should log raw payloads in staging.

2. **LID resolution mechanism in WuzAPI not fully documented** — spike needed if `@lid` senders appear in staging during Phase 34. The Phase 34 plan should include a LID detection + DLQ routing path, but the exact LID JID format in WuzAPI output should be verified against real events.
