# Evolution API Integration - Quick Reference

## Critical Issues

### 1. CRITICAL: Missing Lifecycle Cleanup
**File**: `client.py` (line 324-330) + `lifespan.py`
**Issue**: `close_evolution_client()` is never called
**Impact**: Connection leaks, resource exhaustion
**Fix**: Add to `lifespan.py` shutdown

```python
# In app/core/lifespan.py _shutdown()
from app.integrations.evolution import close_evolution_client
await close_evolution_client()
```

### 2. CRITICAL: Webhook Security Bypass
**File**: `webhook_handler.py` (lines 59-75)
**Issue**: Signature validation disabled in development mode
**Impact**: Unvalidated webhook injection possible
**Risk**: High - Could inject malicious messages

```python
# Current code
if not validation_secret:
    if self.environment == "production":
        return False
    else:
        return True  # ALLOWS ANY WEBHOOK!

# Fix: Always require validation
if not validation_secret:
    raise ValueError("Webhook secret required for validation")
```

### 3. MEDIUM: Brazil-Only Phone Validation
**File**: `validators.py` (lines 10-30)
**Issue**: Hard-coded for Brazilian numbers only
**Impact**: International numbers will fail
**Fix**: Use `phonenumbers` library

### 4. MEDIUM: No Message Persistence
**File**: All message sending
**Issue**: Failed messages lost on restart
**Impact**: Message delivery not guaranteed
**Fix**: Implement message queue with database

### 5. MEDIUM: Global Client Singleton
**File**: `client.py` (lines 305-330)
**Issue**: Only one Evolution client instance allowed
**Impact**: Can't support multiple WhatsApp instances
**Fix**: Use dependency injection

---

## Architecture Quick View

```
EvolutionClient (Main)
├── RequestHandler (HTTP)
│   ├── Rate Limiter
│   └── Retry Logic (3x, exponential backoff)
├── MessageSender (4 types)
│   ├── Text
│   ├── Button
│   ├── List
│   └── Media
└── WebhookHandler
    ├── HMAC Validation
    └── Event Parsing
```

---

## Key Statistics

| Metric | Value |
|--------|-------|
| Total Lines | 1,174 |
| Files | 7 |
| Quality Score | 7.5/10 |
| Test Coverage | 0% |
| Critical Issues | 2 |
| Medium Issues | 3 |

---

## Configuration

```python
# Environment variables required
WHATSAPP_EVOLUTION_API_URL = "http://evolution-api:8080"
WHATSAPP_EVOLUTION_API_KEY = "your-api-key"
WHATSAPP_EVOLUTION_INSTANCE_NAME = "meuwhatsapp"
WHATSAPP_EVOLUTION_WEBHOOK_SECRET = "webhook-secret"
EVOLUTION_RATE_LIMIT = 10  # requests per second

# Optional - Railway service
WHATSAPP_EVOLUTION_RAILWAY_URL = "http://evolution-api:8080"
```

---

## Usage Example

```python
from app.integrations.evolution import get_evolution_client, EvolutionAPIError

# Get client
client = await get_evolution_client()

# Send text message
try:
    response = await client.send_text_message(
        phone_number="5511999999999",
        message="Hello!"
    )
    message_id = response["data"]["id"]
except EvolutionAPIError as e:
    print(f"Failed: {e.status_code} - {e}")

# Send with button
await client.send_button_message(
    phone_number="5511999999999",
    text="Choose an option:",
    buttons=[
        {"displayText": "Option 1", "id": "opt1"},
        {"displayText": "Option 2", "id": "opt2"},
    ]
)

# Check instance status
status = await client.get_instance_status()
is_connected = status["data"]["connected"]

# Health check
health = await client.health_check()
```

---

## Webhook Integration

```python
from app.integrations.evolution import EvolutionClient

client = await get_evolution_client()

# Validate webhook signature (required for production)
is_valid = client.validate_webhook_signature(
    payload=request.body,
    signature=request.headers.get("X-Signature")
)

if is_valid:
    # Parse and process
    event = client.parse_webhook_event(request.json())
    # event.event = "message.received" | "message.status" | etc
    # event.instance = instance name
    # event.data = event-specific data
```

---

## Rate Limiting

- **Default**: 10 requests/second
- **Algorithm**: Sliding window
- **Behavior**: Returns error when exceeded (doesn't queue)
- **Retry**: Handled by RequestHandler (3x with exponential backoff)

```python
# Check remaining quota
remaining = client.rate_limiter.get_remaining_quota()
print(f"Can make {remaining} more requests this second")
```

---

## Error Handling

```python
from app.integrations.evolution import EvolutionAPIError

try:
    await client.send_text_message(...)
except EvolutionAPIError as e:
    # e.status_code: HTTP status (int)
    # e.response_data: API error response (dict)
    # e.message: Error message (str)
    logger.error(f"API Error {e.status_code}: {e}")
```

---

## Message Types

```python
# Text
{"number": "551199999", "text": "Hello"}

# Button
{
    "number": "551199999",
    "buttonMessage": {
        "text": "Choose:",
        "buttons": [
            {
                "index": 1,
                "urlButton": {
                    "displayText": "Click me",
                    "url": "payload:btn_id"
                }
            }
        ]
    }
}

# List
{
    "number": "551199999",
    "listMessage": {
        "text": "Select option",
        "title": "Menu",
        "sections": [...]
    }
}

# Media
{
    "number": "551199999",
    "mediaMessage": {
        "media": "https://example.com/image.jpg",
        "mediatype": "image",
        "caption": "Optional caption"
    }
}
```

---

## Production Checklist

- [ ] Fix lifecycle cleanup
- [ ] Fix webhook validation security
- [ ] Add unit tests (target: 80% coverage)
- [ ] Add integration tests
- [ ] Set up monitoring/alerting
- [ ] Document API endpoints
- [ ] Load test rate limiting
- [ ] Security audit
- [ ] Create operational runbook
- [ ] Test failover scenarios

---

## Monitoring Points

1. **API Connectivity**: Health check endpoint
2. **Rate Limiting**: Track remaining quota
3. **Message Delivery**: Monitor success/failure rates
4. **Webhook Processing**: Monitor event processing latency
5. **Connection State**: Monitor instance connection status

---

## Dependencies

```
httpx>=0.23.0  # Async HTTP client
structlog>=23.0  # Structured logging
pydantic>=1.10.0  # Data validation
```

---

## Files Overview

| File | Purpose | Status |
|------|---------|--------|
| `client.py` | Main orchestrator | ✓ Good |
| `message_sender.py` | Message dispatch | ✓ Good |
| `request_handler.py` | HTTP requests | ⚠ Minor issues |
| `webhook_handler.py` | Webhook handling | ⚠ CRITICAL SECURITY |
| `rate_limiter.py` | Request throttling | ✓ Good |
| `validators.py` | Input validation | ⚠ Limited scope |
| `models.py` | Data types | ✓ Good |

---

## Last Updated

2025-12-22

## See Also

- Full Analysis: `EVOLUTION_API_INTEGRATION_ANALYSIS.md`
- App Code: `/backend-hormonia/app/integrations/evolution/`
- Usage Examples: `/backend-hormonia/app/domain/messaging/`

