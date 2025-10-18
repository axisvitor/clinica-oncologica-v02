# WhatsApp Messaging Architecture

## Overview

The WhatsApp messaging system uses a **consolidated architecture** where all message sending paths eventually converge to a single Evolution API client. This ensures consistent delivery tracking, rate limiting, and error handling.

## Architecture Layers

### Layer 1: Entry Points (Multiple)
Different parts of the application can initiate WhatsApp messages:

- **MessageSender** (`app/services/message_sender.py`) - Used by Celery tasks and flow engine
- **FlowEngine** (`app/services/flow_engine.py`) - Sends flow-related messages
- **MonthlyQuizService** (`app/services/monthly_quiz_service.py`) - Sends quiz links
- **PatientService** (`app/services/patient.py`) - Sends welcome messages

### Layer 2: Unified Routing
All entry points route through:

**UnifiedWhatsAppService** (`app/services/unified_whatsapp_service.py`)
- Determines messaging mode (QUEUE vs LEGACY)
- Adds unified metadata for tracking
- Routes to appropriate pipeline
- Tracks metrics

**Messaging Modes:**
- `QUEUE` - For bulk messages, scheduled messages, high-priority flows
- `LEGACY` - For immediate simple messages

### Layer 3: Queue Processing (QUEUE mode only)
**WhatsAppMessageService** (`app/integrations/whatsapp/services/message_service.py`)
- Creates message records in database
- Enqueues messages for delivery
- Handles message status updates

**WhatsAppHelper** (`app/utils/whatsapp_helper.py`)
- Processes queued messages
- Applies rate limiting
- Manages delivery reports
- Executes callbacks

### Layer 4: API Client (Final Convergence Point)
**EvolutionAPIClient** (`app/integrations/whatsapp/services/evolution_client.py`)
- **Single source of truth** for WhatsApp API communication
- Implements retry logic with exponential backoff
- Handles rate limiting at API level
- Manages instance connections
- Processes webhooks

## Message Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Entry Points (Layer 1)                    │
│  MessageSender │ FlowEngine │ QuizService │ PatientService  │
└────────────────┬────────────┬─────────────┬─────────────────┘
                 │            │             │
                 └────────────┴─────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              UnifiedWhatsAppService (Layer 2)                │
│         • Determines mode (QUEUE/LEGACY)                     │
│         • Adds metadata                                      │
│         • Routes to pipeline                                 │
└────────────────┬────────────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
┌──────────────┐  ┌──────────────┐
│ QUEUE Mode   │  │ LEGACY Mode  │
│ (Layer 3)    │  │ (Direct)     │
└──────┬───────┘  └──────┬───────┘
       │                 │
       ▼                 │
┌──────────────┐         │
│ WhatsApp     │         │
│ MessageSvc   │         │
└──────┬───────┘         │
       │                 │
       ▼                 │
┌──────────────┐         │
│ WhatsApp     │         │
│ Helper       │         │
└──────┬───────┘         │
       │                 │
       └────────┬────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│           EvolutionAPIClient (Layer 4)                       │
│         • Single API communication point                     │
│         • Retry logic & backoff                              │
│         • Rate limiting                                      │
│         • Webhook processing                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    Evolution WhatsApp API
```

## Key Benefits of This Architecture

### 1. **Single Source of Truth**
- All WhatsApp API calls go through `EvolutionAPIClient`
- Consistent error handling and retry logic
- Centralized rate limiting

### 2. **Flexible Routing**
- `UnifiedWhatsAppService` intelligently routes based on message characteristics
- QUEUE mode for reliability (bulk, scheduled, high-priority)
- LEGACY mode for speed (immediate, simple messages)

### 3. **Consistent Tracking**
- All messages tracked in `messages` table
- Status updates via `message_status_events` table
- Webhook events stored in `webhook_events` table

### 4. **Resilience**
- Circuit breaker pattern in `UnifiedWhatsAppService`
- Exponential backoff in `EvolutionAPIClient`
- Queue-based retry in `WhatsAppHelper`
- Celery task retry in `MessageTask`

## Message Status Lifecycle

```
PENDING → SCHEDULED → SENDING → SENT → DELIVERED → READ
                         ↓
                      FAILED (with retry)
```

Status updates are tracked via:
- `messages.status` field
- `message_status_events` table (full history)
- `webhook_events` table (Evolution API webhooks)

## Configuration

### Environment Variables
```bash
# Evolution API
EVOLUTION_API_URL=https://your-evolution-api.com
EVOLUTION_API_KEY=your-api-key
EVOLUTION_INSTANCE_NAME=your-instance

# WhatsApp Features
ENABLE_WHATSAPP_ON_REGISTRATION=true
WHATSAPP_WELCOME_MESSAGE_ENABLED=true
WHATSAPP_MAX_RETRIES=3
WHATSAPP_RETRY_DELAY_SECONDS=60

# Rate Limiting
WHATSAPP_RATE_LIMIT_PER_MINUTE=20
WHATSAPP_RATE_LIMIT_PER_HOUR=100
```

## Usage Examples

### Sending a Simple Message
```python
from app.services.message_sender import MessageSender
from app.services.unified_whatsapp_service import MessagingMode

message_sender = MessageSender(db, messaging_mode=MessagingMode.LEGACY)
success = await message_sender.send_message(message)
```

### Sending a Scheduled Message
```python
from app.services.message_sender import MessageSender
from app.services.unified_whatsapp_service import MessagingMode

message_sender = MessageSender(db, messaging_mode=MessagingMode.QUEUE)
success = await message_sender.send_message(message)
```

### Sending via Celery Task
```python
from app.tasks.messaging import send_scheduled_message

# Schedule message for delivery
task = send_scheduled_message.apply_async(
    args=[str(message.id)],
    eta=message.scheduled_for
)
```

## Monitoring

### Health Checks
- Worker health: `celery -A app.celery_app inspect active`
- Queue status: Check Redis queue length
- Evolution API: `GET /instance/connectionState/{instance}`

### Metrics
- `messages_sent` - Total messages sent
- `queue_processed` - Messages processed via queue
- `legacy_processed` - Messages sent directly
- `failed_messages` - Failed message count

### Logs
```python
# Enable debug logging
LOG_LEVEL=debug

# Key log patterns
"Message sent successfully"
"Message queued due to rate limiting"
"Failed to send message"
"Retrying message send"
```

## Troubleshooting

### Messages Not Sending
1. Check Evolution API connection: `GET /instance/connectionState`
2. Verify Celery worker is running: `celery -A app.celery_app inspect active`
3. Check Redis queue: `redis-cli LLEN whatsapp:queue`
4. Review message status: `SELECT * FROM messages WHERE status = 'FAILED'`

### Rate Limiting Issues
1. Check rate limit settings in config
2. Review `whatsapp_helper.py` rate limiter
3. Monitor Evolution API rate limit responses
4. Adjust `WHATSAPP_RATE_LIMIT_PER_MINUTE` if needed

### Webhook Not Working
1. Verify webhook URL is accessible from Evolution API
2. Check webhook events configuration
3. Review `webhook_events` table for incoming events
4. Ensure webhook signature validation is correct

## Future Improvements

1. **Message Templates** - Pre-defined templates for common messages
2. **Media Optimization** - Automatic image compression and format conversion
3. **Delivery Analytics** - Enhanced reporting on delivery rates and timing
4. **Multi-Instance Support** - Load balancing across multiple WhatsApp instances
5. **Message Scheduling UI** - Frontend interface for scheduling messages

## Related Files

- `app/services/unified_whatsapp_service.py` - Unified routing layer
- `app/integrations/whatsapp/services/evolution_client.py` - Evolution API client
- `app/integrations/whatsapp/services/message_service.py` - Message service
- `app/utils/whatsapp_helper.py` - Queue processing helper
- `app/services/message_sender.py` - Message sender service
- `app/tasks/messaging.py` - Celery messaging tasks
- `app/models/message.py` - Message data models

