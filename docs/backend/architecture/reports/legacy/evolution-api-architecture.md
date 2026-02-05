# Evolution API Integration - Architecture & Data Flow

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Application                          │
│  (app/core/application_factory.py + lifespan.py)                │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     │ Creates/Manages
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│              EvolutionClient (Main Orchestrator)                 │
│ - Singleton instance via get_evolution_client()                 │
│ - Configuration: base_url, instance_name, api_key, webhook_secret
│ - Timeout: 30s, MaxRetries: 3, RetryDelay: 1.0s                 │
└──────┬──────────┬────────────┬─────────────┬────────────────────┘
       │          │            │             │
       ▼          ▼            ▼             ▼
   ┌────────┐ ┌──────────┐ ┌─────────┐ ┌──────────────┐
   │Request │ │MessageSender
   │Handler │ │(4 types)     │ WebhookHandler  Health Check
   └────────┘ └──────────┘ │ │(Validation)    │(Instance + API)
       │          │         │ └──────────────┘ └─────────────┘
       │          │         │
       ├─────────┼─────────┼─ Delegates to
       │         │         │
       ▼         ▼         ▼
   ┌───────────────────────────────────────────────────┐
   │              RateLimiter                          │
   │  - Sliding window: 10 req/sec (configurable)     │
   │  - Tracks request times in last 1s window        │
   └───────────────────────────────────────────────────┘
```

## Request Flow - Text Message

```
User Code
   │
   │ client.send_text_message(phone, "Hello")
   │
   ▼
┌──────────────────────────────────────────┐
│ MessageSender.send_text_message()        │
│ - Validate phone (format_phone_number)   │
│ - Validate message (validate_message_content)
│ - Build payload: {number, text, delay?}  │
└──────────────┬─────────────────────────────┘
               │
               │ Delegates to
               ▼
┌──────────────────────────────────────────┐
│ RequestHandler.make_request()            │
│ endpoint: "message/sendText/{instance}"  │
│ data: {number, text}                     │
└──────────────┬─────────────────────────────┘
               │
               │ Check rate limit
               ▼
┌──────────────────────────────────────────┐
│ RateLimiter.check_rate_limit()           │
│ ✓ Within quota? → Proceed                │
│ ✗ Over quota? → Sleep + Retry            │
└──────────────┬─────────────────────────────┘
               │
               │ HTTP POST
               ▼
┌──────────────────────────────────────────┐
│ httpx.AsyncClient.request()              │
│ URL: http://evolution-api:8080/...       │
│ Headers: apikey, Authorization, Content-Type
│ Timeout: 30s                             │
└──────────────┬─────────────────────────────┘
               │
         ┌─────┴─────┐
         │            │
    Success        Error (4xx/5xx/timeout/network)
         │            │
         ▼            ▼
    ┌────────┐   ┌──────────────────┐
    │Parse   │   │Check if retriable │
    │JSON    │   │ - 5xx: YES        │
    │Response│   │ - 429: YES        │
    └────────┘   │ - Timeout: YES    │
         │       │ - Network: YES    │
         │       │ - 4xx: NO         │
         │       └──────┬───────────┘
         │              │
         │         ┌────┴────┐
         │         │          │
         │      Retry?    Fail
         │         │          │
         │    ┌────▼────┐    │
         │    │Backoff  │    │
         │    │(exp 2^n)│    │
         │    │+ sleep  │    │
         │    └────┬────┘    │
         │         │         │
         │    Retry count    │
         │         │         │
         │    ┌────┴────┐    │
         │    │< 3?     │    │
         │    └────┬────┘    │
         │    Y    N   │     │
         │    │    │   │     │
         │    │    └───┼─────┘
         │    │        │
         └────┼───┬────┘
              │   │
              ▼   ▼
          Response Error
```

## Webhook Flow

```
Evolution API Server
         │
         │ POST http://your-app/whatsapp/webhooks
         │ Headers: X-Signature or similar
         │ Body: {"event": "message.received", "data": {...}}
         │
         ▼
┌──────────────────────────────────────────────────────┐
│ Webhook Endpoint                                     │
│ (app/integrations/whatsapp/api/webhooks.py)          │
└────────────┬─────────────────────────────────────────┘
             │
             │ Get signature from headers
             │ Get payload as bytes
             │
             ▼
┌──────────────────────────────────────────────────────┐
│ client.validate_webhook_signature(payload, sig)      │
└────────────┬─────────────────────────────────────────┘
             │
             │ HMAC-SHA256 or SHA1 validation
             │
        ┌────┴─────┐
        │           │
    Valid      Invalid
        │           │
        ▼           ▼
    ┌────┐    ┌────────┐
    │✓   │    │✗ Log   │
    │OK  │    │Reject  │
    └────┘    └────────┘
        │
        ├─ Dev mode: Always accept (ISSUE!)
        ├─ Prod mode: Reject if secret missing (CORRECT)
        │
        ▼
┌──────────────────────────────────────────────────────┐
│ client.parse_webhook_event(payload)                  │
│ - Extract event type (message.received, etc)         │
│ - Create WebhookEvent object                         │
│ - Validate with Pydantic model                       │
└────────────┬─────────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────────┐
│ Process Event                                        │
│ - Store message in database                          │
│ - Update delivery status                             │
│ - Emit WebSocket event to client                     │
│ - Trigger any callbacks                              │
└──────────────────────────────────────────────────────┘
```

## State Diagram - Message Lifecycle

```
                    ┌─────────────────────────────────┐
                    │  Not Yet Sent                   │
                    │  (In queue or being processed)  │
                    └────────┬────────────────────────┘
                             │
                    client.send_text_message()
                             │
                    ┌────────▼────────────────┐
                    │      SENDING            │
                    │  (In progress to API)   │
                    └────────┬────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         Success        Timeout         Network Error
              │              │              │
              ▼              ▼              ▼
         ┌─────────────────────────────────────┐
         │ Auto-Retry Logic (up to 3 times)    │
         │ Exponential backoff: 1s, 2s, 4s     │
         └──────┬──────────────────────────────┘
                │
         ┌──────┴──────┐
         │             │
    Success         Failure
         │             │
         ▼             ▼
  ┌──────────────┐  ┌──────────────┐
  │SENT (ID)     │  │FAILED        │
  │Message ID    │  │Error code    │
  │assigned      │  │Error message │
  └──────┬───────┘  └──────────────┘
         │
         │ (Webhook from Evolution API)
         │ event: "message.status"
         │
    ┌────┴────┬─────────┬──────────┐
    │          │         │          │
    ▼          ▼         ▼          ▼
  SENT    DELIVERED   READ      FAILED
    │          │         │          │
    └──────────┴─────────┴──────────┘
              │
           Final State
```

## Configuration Hierarchy

```
Environment Startup
         │
         ├─ Railway environment detected?
         │  └─ WHATSAPP_EVOLUTION_RAILWAY_URL → Use internal service
         │
         ├─ Else check WHATSAPP_EVOLUTION_API_URL → Use external URL
         │
         ├─ Else use default → http://localhost:8080
         │
         │ Similarly for:
         │ - API Key (WHATSAPP_EVOLUTION_API_KEY)
         │ - Instance name (WHATSAPP_EVOLUTION_INSTANCE_NAME)
         │ - Webhook secret (WHATSAPP_EVOLUTION_WEBHOOK_SECRET)
         │ - Rate limit (EVOLUTION_RATE_LIMIT)
         │
         ▼
  EvolutionClient configured
         │
         ├─ HTTP Client Setup
         │  ├─ Headers: apikey, Authorization (Bearer), Content-Type
         │  ├─ Timeout: 30s (connect: 10s)
         │  ├─ Connection Pool:
         │  │  ├─ max_keepalive_connections: 20
         │  │  ├─ max_connections: 100
         │  │  └─ keepalive_expiry: 30s
         │  └─ Follow redirects: True
         │
         ├─ Rate Limiter: 10 req/sec
         ├─ Request Handler: Max retries 3
         ├─ Message Sender: 4 message types
         └─ Webhook Handler: HMAC validation
```

## Error Handling Decision Tree

```
                    API Request
                         │
                    ┌────▼────┐
                    │ Success? │
                    └────┬─────┘
                    N    │     Y
                    │    │     │
        ┌───────────┼────┘     └─────┐
        │           │                │
        ▼           ▼                ▼
   ┌─────────┐ ┌─────────┐      ┌─────────┐
   │HTTP Err │ │Timeout  │      │ Parse   │
   │ 4xx/5xx │ │Network  │      │ JSON    │
   └────┬────┘ └────┬────┘      └────┬────┘
        │           │                │
   ┌────┴───┐   ┌───┴────┐      ┌────┴─────┐
   │4xx?    │   │Retry   │      │Success?  │
   └────┬───┘   │able?   │      └────┬─────┘
   Y    │    N  └───┬────┘      Y    │    N
   │    │          │  N         │    │    │
   │    │     ┌────┴──────┐     │    │    │
   │    │     │ Retry     │     │    │    │
   │    │     │ Count<3?  │     │    │    │
   │    │     └────┬──────┘     │    │    │
   │    │     Y    │    N       │    │    │
   │    │     │    │            │    │    │
   │    ▼     ▼    ▼            ▼    │    │
   │  FAIL   SLEEP FAIL        OK    │    │
   │  (Err) BACKOFF       RETURN    │    │
   │        RETRY         DATA      │    │
   │                      │         │    │
   └──────────────────────┴─────────┴────┘
```

## Data Structures

### Message Payload - Text

```json
{
  "number": "5511999999999",
  "text": "Hello World",
  "delay": 0  // optional, milliseconds
}
```

### Message Payload - Button

```json
{
  "number": "5511999999999",
  "buttonMessage": {
    "text": "Choose an option:",
    "buttons": [
      {
        "index": 1,
        "urlButton": {
          "displayText": "Option 1",
          "url": "payload:btn_1"
        }
      },
      {
        "index": 2,
        "urlButton": {
          "displayText": "Option 2",
          "url": "payload:btn_2"
        }
      }
    ]
  },
  "delay": 0  // optional
}
```

### Message Payload - Media

```json
{
  "number": "5511999999999",
  "mediaMessage": {
    "media": "https://example.com/image.jpg",
    "mediatype": "image",
    "caption": "Optional caption"
  },
  "delay": 0  // optional
}
```

### API Response - Success

```json
{
  "status": "success",
  "data": {
    "id": "msg_123456789",
    "status": "pending",
    "timestamp": 1703254800000
  }
}
```

### API Response - Error

```json
{
  "status": "error",
  "message": "Invalid phone number",
  "code": "INVALID_PHONE"
}
```

### Webhook Payload - Message Received

```json
{
  "event": "message.received",
  "instance": "meuwhatsapp",
  "data": {
    "message": {
      "id": "msg_from_api",
      "body": "User message text",
      "timestamp": 1703254800000,
      "from": "5511987654321",
      "fromMe": false
    }
  },
  "timestamp": "2025-12-22T16:00:00.000Z"
}
```

### Webhook Payload - Message Status

```json
{
  "event": "message.status",
  "instance": "meuwhatsapp",
  "data": {
    "messageId": "msg_123456789",
    "status": "delivered",
    "timestamp": 1703254800000
  },
  "timestamp": "2025-12-22T16:00:00.000Z"
}
```

## Dependency Graph

```
application_factory.py
    │
    └─▶ lifespan.py
            │
            └─▶ (MISSING) close_evolution_client()
                    │
                    └─▶ client.py ──▶ close()

health_check routes
    │
    └─▶ client.py
            │
            ├─▶ health_check()
            │
            └─▶ get_instance_status()

whatsapp_service.py
    │
    ├─▶ client.py ──▶ send_text_message()
    │
    └─▶ message_sender.py

webhook_handler.py
    │
    └─▶ client.py
            │
            ├─▶ validate_webhook_signature()
            │
            └─▶ parse_webhook_event()
```

## Metrics & Monitoring Points

```
┌─────────────────────────────────────────┐
│         EvolutionClient                 │
└─────────────────────────────────────────┘
         │
    ┌────┴────┬──────────┬──────────┐
    │          │          │          │
    ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│Success │ │Failure │ │Latency │ │RateLimit
│Count   │ │Count   │ │(p50,p99)
│Bytes   │ │Retry   │ │Request  │ │Queue
│Sent    │ │Count   │ │Time     │ │Depth
└────────┘ └────────┘ └────────┘ └────────┘

┌─────────────────────────────────────────┐
│        WebhookHandler                   │
└─────────────────────────────────────────┘
    │
    ├─ Signature validation
    │  ├─ Valid count
    │  ├─ Invalid count
    │  └─ Rejection rate
    │
    └─ Event processing
       ├─ Events/sec
       ├─ Processing latency
       └─ Error rate
```

## Lifecycle

```
Application Startup
    │
    ├─ Load environment variables
    ├─ Create EvolutionClient singleton
    │  └─ Initialize HTTP client
    │  └─ Setup rate limiter
    │  └─ Create handlers
    │
    └─ Application ready
         │
         └─ Accept requests

Application Shutdown
    │
    ├─ (MISSING) Call close_evolution_client()
    │  └─ Close HTTP client
    │  └─ Cleanup connections
    │
    └─ Application stopped
```

## Evolution API Endpoints Used

```
Instance Management:
  GET  /instance/connectionState/{instance}
       → Check connection status

Message Sending:
  POST /message/sendText/{instance}
  POST /message/sendButtons/{instance}
  POST /message/sendList/{instance}
  POST /message/sendMedia/{instance}

Message Status:
  GET  /chat/findMessages/{instance}
       → Query message status
```

