# WhatsApp Integration Guide - Hormonia Oncology System

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Evolution API Integration](#evolution-api-integration)
4. [Webhook Handling](#webhook-handling)
5. [Message Types](#message-types)
6. [Delivery Status Tracking](#delivery-status-tracking)
7. [Rate Limiting and Queuing](#rate-limiting-and-queuing)
8. [Error Handling](#error-handling)
9. [Configuration Guide](#configuration-guide)
10. [Security Considerations](#security-considerations)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The Hormonia oncology system integrates with WhatsApp through the **Evolution API**, providing bidirectional messaging capabilities for patient communication. This integration supports:

- Automated patient onboarding messages
- Treatment flow communications
- Quiz and survey delivery
- Real-time message status tracking
- Intelligent message queuing with retry logic

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `EvolutionClient` | `app/integrations/evolution/client.py` | Main API client orchestrator |
| `MessageSender` | `app/integrations/evolution/message_sender.py` | Message type handling |
| `WebhookHandler` | `app/integrations/evolution/webhook_handler.py` | Webhook validation/parsing |
| `WhatsAppService` | `app/domain/messaging/whatsapp/whatsapp_service.py` | Unified messaging service |
| `MessageWebhookHandler` | `app/services/webhook/handlers/message_handler.py` | Inbound message processing |
| `StatusWebhookHandler` | `app/services/webhook/handlers/status_handler.py` | Delivery status updates |

---

## Architecture

### System Architecture Diagram

```
+------------------+     +--------------------+     +------------------+
|                  |     |                    |     |                  |
|  WhatsApp User   |<--->|   Evolution API    |<--->|  Hormonia Backend|
|  (Patient)       |     |   (WhatsApp GW)    |     |                  |
|                  |     |                    |     |                  |
+------------------+     +--------------------+     +------------------+
                                  |                         |
                                  |  Webhooks               |
                                  |  (HMAC-SHA256)          |
                                  v                         v
                         +--------------------+     +------------------+
                         |                    |     |                  |
                         |  Webhook Router    |---->|  Message Handler |
                         |  /api/v2/webhooks  |     |                  |
                         |                    |     +------------------+
                         +--------------------+             |
                                                           v
                                                   +------------------+
                                                   |                  |
                                                   |  Flow Engine     |
                                                   |  Quiz Service    |
                                                   |  AI Response     |
                                                   |                  |
                                                   +------------------+
```

### Component Interaction Flow

```
[Outbound Messages]

1. Service Layer (FlowEngine/QuizService)
       |
       v
2. WhatsAppService (Unified Service)
       |
       v
3. IdempotentMessageSender (Deduplication)
       |
       v
4. MessageQueue (Priority/Rate Limiting)
       |
       v
5. EvolutionClient (API Communication)
       |
       v
6. Evolution API -> WhatsApp


[Inbound Messages]

1. WhatsApp -> Evolution API
       |
       v
2. Webhook Endpoint (/api/v2/webhooks/whatsapp)
       |
       v
3. Signature Validation (HMAC-SHA256)
       |
       v
4. Idempotency Check (Redis + DB)
       |
       v
5. MessageWebhookHandler
       |
       v
6. Patient Lookup + Security Check
       |
       v
7. Flow/Quiz/Chat Routing
```

---

## Evolution API Integration

### Client Architecture

The `EvolutionClient` class serves as the main orchestrator, delegating to specialized handlers:

```python
# Location: app/integrations/evolution/client.py

class EvolutionClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        instance_name: Optional[str] = None,
        api_key: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        use_mock: bool = False,
        railway_service: bool = False,
    ):
        # Initializes:
        # - RateLimiter
        # - RequestHandler
        # - MessageSender
        # - WebhookHandler
```

### Request Handler

The `RequestHandler` manages HTTP communication with automatic retry and exponential backoff:

```python
# Location: app/integrations/evolution/request_handler.py

# Retry behavior:
# - 5xx errors: Retry with exponential backoff
# - 429 (rate limit): Retry with exponential backoff
# - 4xx errors: Fail immediately (client error)
# - Timeouts: Retry with exponential backoff
# - Network errors: Retry with exponential backoff

# Backoff formula: delay = retry_delay * (2 ** retry_count)
# Default: 1s, 2s, 4s (max 3 retries)
```

### API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `message/sendText/{instance}` | POST | Send text messages |
| `message/sendButtons/{instance}` | POST | Send button messages |
| `message/sendList/{instance}` | POST | Send list/menu messages |
| `message/sendMedia/{instance}` | POST | Send media (image/video/audio/document) |
| `instance/connectionState/{instance}` | GET | Check instance connection status |
| `chat/findMessages/{instance}` | GET | Get message delivery status |

### Usage Example

```python
from app.integrations.evolution import get_evolution_client

async def send_patient_message(phone: str, message: str):
    client = await get_evolution_client()

    result = await client.send_text_message(
        phone_number=phone,
        message=message,
        delay=1000  # Optional: 1 second typing simulation
    )

    return result.get("data", {}).get("id")  # WhatsApp message ID
```

---

## Webhook Handling

### Webhook Flow Diagram

```
                    Evolution API
                         |
                         | POST /api/v2/webhooks/whatsapp
                         v
              +---------------------+
              |   Rate Limiting     |
              | (1000/min global)   |
              | (100/min per phone) |
              +---------------------+
                         |
                         v
              +---------------------+
              | Signature Validation|
              | X-Webhook-Signature |
              | X-Webhook-Timestamp |
              +---------------------+
                         |
                    Valid?
                   /      \
                  No       Yes
                  |         |
                  v         v
              +------+  +---------------------+
              | 401  |  | Idempotency Check   |
              +------+  | (Redis SET NX EX)   |
                        +---------------------+
                                 |
                            Duplicate?
                           /         \
                          Yes         No
                          |           |
                          v           v
                    +---------+  +------------------+
                    | Return  |  | Process Event    |
                    | Success |  | (message/status) |
                    +---------+  +------------------+
                                        |
                                        v
                                 +------------------+
                                 | WebSocket Event  |
                                 | (Real-time UI)   |
                                 +------------------+
```

### Webhook Endpoint

```python
# Location: app/api/v2/routers/webhooks.py

@router.post("/whatsapp", response_model=WebhookInboundResponse)
@multi_layer_rate_limit(
    global_limit=1000,
    global_window=60,
    identifier_limit=100,
    identifier_window=60,
    identifier_key="data.key.remoteJid",
)
async def receive_whatsapp_webhook(
    request: Request,
    event_data: WebhookInboundEvent,
    verification: dict = Depends(verify_webhook_signature_v2),
    service: WebhookService = Depends(get_webhook_service),
):
    return await service.process_inbound_webhook(event_data, verification)
```

### Signature Validation

```python
# Location: app/integrations/evolution/webhook_handler.py

def validate_signature(
    self, payload: bytes, signature: str, secret: Optional[str] = None
) -> bool:
    """
    Validates webhook signature using HMAC-SHA256 or HMAC-SHA1.

    CRITICAL: In production, webhook_secret MUST be configured.
    In development, validation is bypassed with a warning.

    Signature format supported:
    - sha256=<hex_signature>
    - sha1=<hex_signature>
    - hmac-sha256=<hex_signature>
    - <raw_hex_signature>
    """
```

### Webhook Event Types

| Event Type | Handler | Description |
|------------|---------|-------------|
| `message.received` | `MessageWebhookHandler` | Incoming patient message |
| `message.status` | `StatusWebhookHandler` | Delivery status update |
| `connection.update` | `ConnectionHandler` | Instance connection changes |

### Idempotency Mechanism

The system uses a multi-layer idempotency check to prevent duplicate processing:

```python
# Location: app/services/webhook/handlers/message_handler.py

# Layer 1: Redis Atomic Lock (SET NX EX)
acquired = await redis_client.set(
    f"webhook:message:{whatsapp_id}",
    "processing",
    nx=True,  # Only set if doesn't exist
    ex=CACHE_WEBHOOK_IDEMPOTENCY_TTL_SECONDS  # 2 hours TTL
)

# Layer 2: Database Check (fallback)
existing_message = self.db.query(Message).filter(
    Message.whatsapp_id == whatsapp_id
).first()

# Benefits:
# - Prevents race conditions with atomic Redis operations
# - Database fallback ensures reliability
# - Short TTL prevents Redis memory growth
```

---

## Message Types

### Text Messages

```python
# Simple text message
await client.send_text_message(
    phone_number="5511999999999",
    message="Bom dia! Como voce esta se sentindo hoje?",
    delay=1000  # Typing simulation in ms
)

# Payload format:
{
    "number": "5511999999999",
    "text": "Bom dia! Como voce esta se sentindo hoje?",
    "delay": 1000
}
```

### Button Messages

```python
# Interactive button message
await client.send_button_message(
    phone_number="5511999999999",
    text="Por favor, confirme sua consulta:",
    buttons=[
        {"displayText": "Confirmar", "id": "confirm"},
        {"displayText": "Reagendar", "id": "reschedule"},
        {"displayText": "Cancelar", "id": "cancel"}
    ],
    delay=1000
)

# Payload format:
{
    "number": "5511999999999",
    "buttonMessage": {
        "text": "Por favor, confirme sua consulta:",
        "buttons": [
            {
                "index": 1,
                "urlButton": {
                    "displayText": "Confirmar",
                    "url": "payload:confirm"
                }
            },
            # ... more buttons
        ]
    },
    "delay": 1000
}
```

### List Messages (Menus)

```python
# List/menu message for quiz options
await client.send_list_message(
    phone_number="5511999999999",
    text="Selecione o nivel de dor que voce esta sentindo:",
    title="Nivel de Dor",
    sections=[
        {
            "title": "Opcoes",
            "rows": [
                {"title": "0 - Sem dor", "rowId": "pain_0"},
                {"title": "1-3 - Dor leve", "rowId": "pain_1_3"},
                {"title": "4-6 - Dor moderada", "rowId": "pain_4_6"},
                {"title": "7-10 - Dor intensa", "rowId": "pain_7_10"}
            ]
        }
    ],
    delay=1000
)

# Payload format:
{
    "number": "5511999999999",
    "listMessage": {
        "text": "Selecione o nivel de dor...",
        "title": "Nivel de Dor",
        "sections": [...]
    },
    "delay": 1000
}
```

### Media Messages

```python
# Image message
await client.send_media_message(
    phone_number="5511999999999",
    media_url="https://example.com/instructions.jpg",
    media_type="image",
    caption="Instrucoes para o proximo tratamento",
    delay=1000
)

# Supported media types: image, video, audio, document
# Payload format:
{
    "number": "5511999999999",
    "mediaMessage": {
        "mediatype": "image",
        "media": "https://example.com/instructions.jpg",
        "caption": "Instrucoes para o proximo tratamento"
    },
    "delay": 1000
}
```

---

## Delivery Status Tracking

### Status Flow

```
PENDING --> SENT --> DELIVERED --> READ
    |         |          |
    v         v          v
  FAILED   FAILED     FAILED
```

### Status Definitions

| Status | Description | Evolution API Status |
|--------|-------------|---------------------|
| `PENDING` | Message created, not yet sent | N/A |
| `SENT` | Message sent to WhatsApp servers | `SENT` |
| `DELIVERED` | Message delivered to recipient device | `DELIVERED` |
| `READ` | Message read by recipient | `READ` |
| `FAILED` | Delivery failed | `FAILED`, `ERROR` |

### Status Handler

```python
# Location: app/services/webhook/handlers/status_handler.py

class StatusWebhookHandler:
    """
    Processes message status updates from Evolution API.

    Features:
    - Atomic idempotency check (prevents duplicate updates)
    - Audit trail via MessageStatusEvent
    - Real-time WebSocket notifications
    """

    async def process_status(self, event_data: dict) -> bool:
        # Extract status data
        whatsapp_id = event_data.get("key", {}).get("id")
        status = event_data.get("update", {}).get("status")

        # Atomic idempotency check
        acquired = await redis_client.set(
            f"webhook:status:{whatsapp_id}:{status}",
            "processing",
            nx=True,
            ex=TTL_SECONDS
        )

        if not acquired:
            return True  # Already processed

        # Update message status
        # Create audit event
        # Broadcast WebSocket notification
```

### WebSocket Events

Status updates are broadcast in real-time:

```python
await websocket_events.publish_message_event(
    event_type=WebSocketEventType.MESSAGE_STATUS_UPDATED,
    message_id=message.id,
    patient_id=message.patient_id,
    status=message.status.value,
    metadata={"whatsapp_id": whatsapp_id}
)
```

---

## Rate Limiting and Queuing

### Rate Limiting Architecture

```
                   +------------------------+
                   |    API Rate Limiter    |
                   |   (10 req/sec global)  |
                   +------------------------+
                             |
                             v
               +---------------------------+
               | Per-Patient Rate Limiter  |
               |  10/min, 50/hour, 200/day |
               +---------------------------+
                             |
                             v
                   +-------------------+
                   |   Message Queue   |
                   | (Priority-based)  |
                   +-------------------+
                             |
                 +-----------+-----------+
                 |           |           |
              URGENT      HIGH       NORMAL
              (P4)        (P3)        (P2)
```

### API Rate Limiter

```python
# Location: app/integrations/evolution/rate_limiter.py

class RateLimiter:
    """
    Sliding window rate limiter for Evolution API requests.

    Default: 10 requests per second
    Configurable via: EVOLUTION_RATE_LIMIT env variable
    """

    def __init__(self, requests_per_second: int = 10):
        self.requests_per_second = requests_per_second
        self.request_times: List[float] = []

    def check_rate_limit(self) -> bool:
        """
        Returns True if request is allowed.
        Blocks if rate limit exceeded (logs warning).
        """
```

### Per-Patient Rate Limiter

```python
# Location: app/utils/whatsapp_queue.py

class PerPatientRateLimiter:
    """
    Prevents message flooding per patient.

    Limits (configurable):
    - 10 messages per minute
    - 50 messages per hour
    - 200 messages per day

    Uses Redis for distributed rate limiting.
    """

    async def check_rate_limit(self, patient_id: str) -> Dict[str, Any]:
        """
        Returns:
        {
            "allowed": True/False,
            "retry_after": seconds_to_wait,
            "reason": "minute_limit" | "hour_limit" | "day_limit"
        }
        """
```

### Priority Queue

```python
# Location: app/utils/whatsapp_queue.py

class Priority(Enum):
    LOW = 1      # Non-urgent notifications
    NORMAL = 2   # Regular flow messages
    HIGH = 3     # Quiz questions, reminders
    URGENT = 4   # Emergency alerts

class OrderedMessageQueue:
    """
    Per-patient ordered queue with FIFO guarantee.

    Features:
    - Redis sorted sets for ordering
    - Sequence numbers for FIFO within priority
    - Per-patient processing locks
    - Dead Letter Queue (DLQ) for failed messages
    """

    async def enqueue(
        self,
        patient_id: str,
        request: MessageRequest,
        priority: Priority = Priority.NORMAL
    ) -> OrderedMessage:
        # Score = (5 - priority.value) * 1000000 + sequence
        # Ensures higher priority messages are processed first
        # Within same priority, maintains FIFO order
```

### Message Queue Processing

```
+------------------+     +-------------------+     +------------------+
| enqueue()        | --> | Sorted Set (ZADD) | --> | dequeue()        |
| score = priority |     | (per patient)     |     | ZPOPMIN          |
+------------------+     +-------------------+     +------------------+
                                                          |
                                                   Success?
                                                  /        \
                                                Yes         No
                                                |           |
                                                v           v
                                         +---------+  +-----------+
                                         | Complete|  | requeue() |
                                         +---------+  | or DLQ    |
                                                      +-----------+
```

---

## Error Handling

### Error Categories

| Error Type | Handling Strategy | Retry |
|------------|-------------------|-------|
| `EvolutionAPIError` | Log + Retry (if server error) | Yes (5xx, 429) |
| `TimeoutException` | Exponential backoff retry | Yes |
| `RequestError` (network) | Exponential backoff retry | Yes |
| `RateLimitExceeded` | Wait and retry | Yes |
| `InvalidPhoneNumber` | Mark as failed | No |
| `PatientNotFound` | Log security event | No |

### Retry Configuration

```python
# Default retry policies
retry_policies = {
    "default": {
        "max_retries": 3,
        "backoff_factor": 2,
        "base_delay": 300,  # 5 minutes
    },
    "flow_message": {
        "max_retries": 5,
        "backoff_factor": 1.5,
        "base_delay": 180,  # 3 minutes
    },
    "quiz_message": {
        "max_retries": 3,
        "backoff_factor": 2,
        "base_delay": 300,  # 5 minutes
    }
}
```

### Dead Letter Queue (DLQ)

Messages that exceed max retries are moved to a Dead Letter Queue:

```python
async def _move_to_dlq(self, message: OrderedMessage) -> None:
    """
    Moves failed message to DLQ for manual review.

    DLQ retention: 7 days
    Key format: dlq:patient:{patient_id}
    """
    dlq_key = f"dlq:patient:{message.patient_id}"
    await self.redis.lpush(dlq_key, message.id)
    await self.redis.expire(dlq_key, 604800)  # 7 days
```

### Error Response Examples

```python
# API Error Response
{
    "status": "error",
    "error_type": "EvolutionAPIError",
    "message": "HTTP 401: Invalid API key",
    "retry_scheduled": False
}

# Transient Error (will retry)
{
    "status": "error",
    "error_type": "TimeoutException",
    "message": "Request timeout after 30s",
    "retry_scheduled": True,
    "retry_count": 2,
    "next_retry_at": "2024-01-15T10:30:00Z"
}
```

---

## Configuration Guide

### Environment Variables

```bash
# ============================================
# WHATSAPP - EVOLUTION API (Required)
# ============================================

# Enable/disable WhatsApp integration
WHATSAPP_ENABLE_SERVICE=true

# Evolution API connection
WHATSAPP_EVOLUTION_API_URL=http://localhost:8080
WHATSAPP_EVOLUTION_INSTANCE_NAME=clinica_oncologica
WHATSAPP_EVOLUTION_API_KEY=your-evolution-api-key-here

# Webhook configuration
# CRITICAL: Set a strong secret in production!
WHATSAPP_EVOLUTION_WEBHOOK_SECRET=generate-with-secrets.token_urlsafe(32)
WHATSAPP_EVOLUTION_WEBHOOK_URL=https://your-backend.com/api/v2/webhooks/whatsapp

# ============================================
# WHATSAPP - SETTINGS (Optional)
# ============================================

# Auto-send welcome message on patient registration
WHATSAPP_ENABLE_ON_REGISTRATION=true
WHATSAPP_ENABLE_WELCOME_MESSAGE=true

# Retry configuration
WHATSAPP_MAX_RETRIES=3
WHATSAPP_RETRY_DELAY_SECONDS=60

# Clinic information (shown in messages)
WHATSAPP_CLINIC_NAME=Neoplasias Litoral
WHATSAPP_CLINIC_SUPPORT_PHONE=+5511999999999

# ============================================
# RATE LIMITING
# ============================================

# Evolution API rate limit (requests per second)
EVOLUTION_RATE_LIMIT=10

# ============================================
# WEBHOOK SETTINGS
# ============================================

WEBHOOK_MAX_RETRIES=5
WEBHOOK_RETRY_MIN_WAIT=2
WEBHOOK_RETRY_MAX_WAIT=60
WEBHOOK_TIMEOUT=30
WEBHOOK_SIGNATURE_REQUIRED=true
```

### Evolution API Setup

1. **Install Evolution API**:
   ```bash
   docker pull atendai/evolution-api
   docker run -d --name evolution-api \
     -p 8080:8080 \
     -e AUTHENTICATION_API_KEY=your-api-key \
     atendai/evolution-api
   ```

2. **Create WhatsApp Instance**:
   ```bash
   curl -X POST "http://localhost:8080/instance/create" \
     -H "apikey: your-api-key" \
     -H "Content-Type: application/json" \
     -d '{
       "instanceName": "clinica_oncologica",
       "webhook": "https://your-backend.com/api/v2/webhooks/whatsapp",
       "webhookEvents": ["MESSAGES_UPSERT", "MESSAGES_UPDATE", "CONNECTION_UPDATE"]
     }'
   ```

3. **Connect WhatsApp**:
   ```bash
   # Get QR Code
   curl "http://localhost:8080/instance/connect/clinica_oncologica" \
     -H "apikey: your-api-key"

   # Scan QR code with WhatsApp mobile app
   ```

4. **Verify Connection**:
   ```bash
   curl "http://localhost:8080/instance/connectionState/clinica_oncologica" \
     -H "apikey: your-api-key"

   # Expected response:
   # {"instance": {"state": "open"}}
   ```

---

## Security Considerations

### Webhook Security

1. **HMAC Signature Validation**:
   - All production webhooks MUST have signature validation enabled
   - Use `WHATSAPP_EVOLUTION_WEBHOOK_SECRET` with a strong random value
   - Generate with: `python -c 'import secrets; print(secrets.token_urlsafe(32))'`

2. **Timestamp Validation**:
   - Webhooks older than 5 minutes are rejected
   - Prevents replay attacks

3. **Rate Limiting**:
   - Global: 1000 requests/minute
   - Per-phone: 100 requests/minute
   - Prevents flooding attacks

### Patient Security

1. **Unauthorized Access Detection**:
   ```python
   # Location: app/services/webhook/handlers/message_handler.py

   # Security flow for unknown phone numbers:
   # 1. Log security event
   # 2. Check if phone should be blocked (repeated attempts)
   # 3. Send escalating warning messages (1-3 attempts)
   # 4. Block after 3 attempts
   ```

2. **Phone Number Validation**:
   - Numbers are normalized and validated
   - Only registered patients can interact with the system

### API Key Protection

- API keys are stored in environment variables, never in code
- Keys are added to headers automatically by the client
- Supports both `apikey` header and `Authorization: Bearer` formats

---

## Troubleshooting

### Common Issues

#### 1. Messages Not Being Sent

**Symptoms**: Messages stuck in PENDING status

**Checklist**:
- [ ] Verify Evolution API is running: `curl http://localhost:8080/health`
- [ ] Check instance connection: `GET /instance/connectionState/{instance}`
- [ ] Verify API key is correct
- [ ] Check rate limits haven't been exceeded
- [ ] Review logs for `EvolutionAPIError`

```bash
# Check Evolution API logs
docker logs evolution-api --tail 100

# Check backend logs
grep "Evolution" logs/app.log | tail -50
```

#### 2. Webhooks Not Being Received

**Symptoms**: Inbound messages not appearing in system

**Checklist**:
- [ ] Webhook URL is accessible from Evolution API
- [ ] HTTPS certificate is valid (if using HTTPS)
- [ ] Webhook secret matches in both systems
- [ ] Check webhook endpoint returns 200

```bash
# Test webhook endpoint manually
curl -X POST "https://your-backend.com/api/v2/webhooks/whatsapp" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: test" \
  -d '{"event": "test", "data": {}}'
```

#### 3. Duplicate Messages

**Symptoms**: Same message delivered multiple times

**Causes**:
- Redis not available (idempotency fallback to DB only)
- TTL too short for idempotency keys

**Fix**:
```bash
# Check Redis connection
redis-cli ping

# Verify idempotency keys exist
redis-cli keys "webhook:*" | head -20
```

#### 4. Rate Limit Exceeded

**Symptoms**: `429 Too Many Requests` errors

**Solution**:
```bash
# Check current rate limit quota
# In application code:
remaining = client.rate_limiter.get_remaining_quota()
print(f"Remaining requests: {remaining}")

# Increase rate limit if needed
export EVOLUTION_RATE_LIMIT=20
```

#### 5. Connection Drops

**Symptoms**: Instance shows as disconnected

**Recovery**:
```bash
# Restart instance connection
curl -X POST "http://localhost:8080/instance/restart/clinica_oncologica" \
  -H "apikey: your-api-key"

# If that fails, reconnect with QR code
curl "http://localhost:8080/instance/connect/clinica_oncologica" \
  -H "apikey: your-api-key"
```

### Health Check Endpoint

The system provides a health check for WhatsApp integration:

```python
# Location: app/integrations/evolution/client.py

async def health_check(self) -> Dict[str, Any]:
    """
    Returns:
    {
        "service": "evolution_api",
        "healthy": true/false,
        "timestamp": "2024-01-15T10:00:00Z",
        "details": {
            "instance_name": "clinica_oncologica",
            "base_url": "http://localhost:8080",
            "connected": true/false,
            "rate_limit_remaining": 8
        }
    }
    """
```

### Logging

Key log patterns to monitor:

```bash
# Successful message send
grep "Text message sent" logs/app.log

# Message delivery status updates
grep "Updated message .* status" logs/app.log

# Webhook processing
grep "Parsing webhook event" logs/app.log

# Rate limit warnings
grep "Rate limit" logs/app.log

# API errors
grep "Evolution API error" logs/app.log
```

---

## Related Documentation

- [Flow Engine Documentation](../flows/FLOW_ENGINE.md)
- [Quiz System Guide](../quizzes/QUIZ_SYSTEM.md)
- [Security Policies](../security/SECURITY_POLICIES.md)
- [API Reference](../api/API_REFERENCE.md)

---

*Last updated: December 2024*
*Version: 1.0.0*
