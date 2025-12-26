# Database Models Analysis - Messaging & Notification Tables

## Overview
This document provides a comprehensive analysis of the database models used for messaging and notification functionality in the backend-hormonia project. These tables support WhatsApp integration via Evolution API and internal notification systems.

---

## 1. Messages Table (`messages`)

### Purpose/Utility
Primary table for storing all WhatsApp messages, both inbound and outbound. Handles message lifecycle, delivery tracking, scheduling, retry logic, and idempotency control.

### Table Name
`messages`

### Key Columns

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key (inherited from BaseModel) |
| `patient_id` | UUID | Foreign key to patients table |
| `direction` | Enum | Message direction: `inbound` or `outbound` |
| `type` | Enum | Message type (text, button, list, media, location, quiz types, monthly quiz types) |
| `content` | Text | Message content/body |
| `message_metadata` | JSONB | Additional metadata for buttons, media URLs, etc. |
| `priority` | Enum | Message priority: `critical`, `high`, `normal`, `low` |
| `idempotency_key` | String(255) | Unique key to prevent duplicate sends |
| `whatsapp_id` | String(255) | WhatsApp message identifier |
| `status` | Enum | Current message status (pending, scheduled, sending, sent, delivered, read, failed, cancelled) |
| `scheduled_for` | DateTime(TZ) | When message should be sent |
| `sent_at` | DateTime(TZ) | When message was sent |
| `delivered_at` | DateTime(TZ) | When message was delivered |
| `read_at` | DateTime(TZ) | When message was read |
| `delivery_status` | Enum | Detailed delivery tracking (scheduled, queued, sending, sent, delivered, read, failed, cancelled) |
| `retry_count` | Integer | Number of retry attempts |
| `last_retry_at` | DateTime(TZ) | Timestamp of last retry |
| `failure_reason` | Text | Reason for failure |
| `next_retry_at` | DateTime(TZ) | Scheduled next retry time |
| `created_at` | DateTime(TZ) | Record creation timestamp |
| `updated_at` | DateTime(TZ) | Record update timestamp |

### Relationships (Foreign Keys)

**Outgoing:**
- `patient_id` → `patients.id` (CASCADE delete)

**Incoming:**
- `messages.status_events` ← `MessageStatusEvent.message_id` (one-to-many, cascade delete)
- `messages.dlq_entries` ← `FailedMessage.original_message_id` (one-to-many)

### Integration Points

**WhatsApp Integration:**
- Uses `whatsapp_id` to track messages in Evolution API
- Supports multiple message types including quiz flows
- Tracks full delivery lifecycle (sent → delivered → read)
- Handles retry logic with exponential backoff

**Key Features:**
- Idempotency protection via `idempotency_key`
- Priority-based message queuing
- Comprehensive delivery status tracking
- Support for scheduled messages
- Retry mechanism with failure tracking

### Enumerations

**MessageDirection:**
- `INBOUND` - Received from patient
- `OUTBOUND` - Sent to patient

**MessageType:**
- `TEXT` - Plain text message
- `BUTTON` - Interactive button message
- `LIST` - List selection message
- `MEDIA` - Media message (image, video, etc.)
- `LOCATION` - Location message
- `QUIZ_INTRO` - Quiz introduction
- `QUIZ_QUESTION` - Quiz question
- `QUIZ_ENCOURAGEMENT` - Quiz encouragement message
- `QUIZ_COMPLETION` - Quiz completion message
- `MONTHLY_QUIZ_LINK` - Monthly quiz link
- `MONTHLY_QUIZ_REMINDER` - Monthly quiz reminder
- `MONTHLY_QUIZ_EXPIRED` - Monthly quiz expiration notice
- `MONTHLY_QUIZ_COMPLETED` - Monthly quiz completion notice

**MessageStatus:**
- `PENDING` - Waiting to be sent
- `SCHEDULED` - Scheduled for future delivery
- `SENDING` - Currently being sent by Celery worker
- `SENT` - Successfully sent
- `DELIVERED` - Delivered to recipient
- `READ` - Read by recipient
- `FAILED` - Delivery failed
- `CANCELLED` - Message cancelled

**MessagePriority:**
- `CRITICAL` - Highest priority
- `HIGH` - High priority
- `NORMAL` - Normal priority
- `LOW` - Low priority

---

## 2. Message Status Events Table (`message_status_events`)

### Purpose/Utility
Audit trail table tracking all status transitions for WhatsApp messages. Provides detailed history of message lifecycle events, errors, and Evolution API interactions.

### Table Name
`message_status_events`

### Key Columns

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `message_id` | UUID | Foreign key to messages table |
| `status` | String(50) | Status at this event (sent, delivered, read, failed) |
| `previous_status` | String(50) | Previous status for audit trail |
| `whatsapp_id` | String(255) | WhatsApp message identifier |
| `whatsapp_timestamp` | DateTime(TZ) | Timestamp from WhatsApp event |
| `error_code` | String(50) | Error code from Evolution API |
| `error_message` | Text | Detailed error message |
| `retry_count` | Integer | Retry count at time of event |
| `event_metadata` | JSONB | Additional event data (column name: `metadata`) |
| `evolution_event_type` | String(100) | Raw Evolution API event type |
| `evolution_payload` | JSONB | Full Evolution API payload for debugging |
| `created_at` | DateTime(TZ) | Event timestamp (indexed) |

### Relationships (Foreign Keys)

**Outgoing:**
- `message_id` → `messages.id` (CASCADE delete)

### Integration Points

**Evolution API Integration:**
- Captures all webhook events from Evolution API
- Stores complete payload for debugging
- Maps Evolution API events to internal status

**Key Features:**
- Complete audit trail of status changes
- Error tracking with codes and messages
- WhatsApp ID correlation
- Event replay capability for debugging

### Database Indexes

**Performance Indexes:**
- `idx_msg_status_msg_created` - (message_id, created_at) - Query message timeline
- `idx_msg_status_type_time` - (status, created_at) - Query recent status changes
- `idx_msg_status_error_time` - (error_code, created_at) WHERE error_code IS NOT NULL - Track errors
- `idx_msg_status_whatsapp` - (whatsapp_id, status) - WhatsApp ID lookup

### Helper Properties

**`is_error_state`**: Returns true if status is "failed" or error_code exists
**`is_final_state`**: Returns true if status is "read" or "failed"

---

## 3. Evolution Webhook Events Table (`webhook_events`)

### Purpose/Utility
Dead Letter Queue (DLQ) for Evolution API webhook events. Stores all incoming webhook events for debugging, replay, audit trail, and retry mechanism.

### Table Name
`webhook_events`

### Key Columns

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `event_type` | String(100) | Event type (message.sent, message.delivered, etc.) |
| `source` | String(100) | Event source (evolution_api, whatsapp, system) |
| `payload` | JSONB | Complete event payload (required) |
| `processed` | Boolean | Has event been processed (default: false) |
| `processed_at` | DateTime(TZ) | When event was processed |
| `retry_count` | Integer | Number of retry attempts (default: 0) |
| `max_retries` | Integer | Maximum retry attempts (default: 3) |
| `next_retry_at` | DateTime(TZ) | Scheduled retry time (indexed) |
| `error_message` | Text | Processing error details |
| `error_stack_trace` | Text | Full error stack trace |
| `related_message_id` | UUID | Related message if identified |
| `related_patient_id` | UUID | Related patient if identified |
| `event_hash` | String(64) | SHA-256 hash for deduplication (unique) |
| `is_duplicate` | Boolean | Marked as duplicate (default: false) |
| `original_event_id` | UUID | Reference to original if duplicate |
| `created_at` | DateTime(TZ) | Event received timestamp (indexed) |

### Relationships (Foreign Keys)

**Outgoing:**
- None (uses nullable UUIDs for loose coupling)

**References (Not Enforced):**
- `related_message_id` → `messages.id`
- `related_patient_id` → `patients.id`
- `original_event_id` → `webhook_events.id`

### Integration Points

**Evolution API Integration:**
- Captures ALL webhook events from Evolution API
- Event deduplication via SHA-256 hashing
- Retry mechanism with exponential backoff
- Error tracking with full stack traces

**Key Features:**
- Event replay for testing
- Audit trail for compliance
- Performance monitoring
- Deduplication protection
- Automatic retry scheduling

### Database Indexes

**Performance Indexes:**
- `ix_webhook_type_processed` - (event_type, processed, created_at) - Query unprocessed events by type
- `ix_webhook_retry_schedule` - (processed, next_retry_at) - Query events ready for retry
- `ix_webhook_source_time` - (source, created_at) - Query events by source
- `ix_webhook_pending` - (processed, retry_count, created_at) - Query pending events
- `ix_webhook_related_msg` - (related_message_id, event_type) - Query by related message
- `ix_webhook_related_patient` - (related_patient_id, event_type) - Query by related patient

### Helper Properties

**`can_retry`**: Returns true if event can be retried (not processed and retry_count < max_retries)
**`is_failed`**: Returns true if processing permanently failed (max retries exceeded)
**`should_retry_now`**: Returns true if event should be retried now (based on next_retry_at)

---

## 4. Failed Messages Table (`whatsapp_delivery_failures`)

### Purpose/Utility
Dead Letter Queue for failed WhatsApp messages. Stores messages that failed delivery after maximum retry attempts for manual review and resolution.

### Table Name
`whatsapp_delivery_failures`

### Key Columns

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `patient_id` | UUID | Foreign key to patients table |
| `phone_number` | String(20) | Patient phone number |
| `message_type` | String(50) | Type of failed message |
| `message_content` | Text | Original message content |
| `error_message` | Text | Error description (required) |
| `error_code` | String(50) | Error code from API |
| `retry_count` | Integer | Number of retry attempts (default: 0) |
| `max_retries` | Integer | Maximum retry attempts (default: 3) |
| `next_retry_at` | DateTime | Next scheduled retry |
| `last_retry_at` | DateTime | Last retry timestamp |
| `status` | String(20) | DLQ status (default: "pending") |
| `resolved_at` | DateTime | When issue was resolved |
| `dlq_metadata` | JSONB | Additional DLQ metadata |
| `reviewed_by` | UUID | User who reviewed the failure |
| `original_message_id` | UUID | Original message reference |
| `created_at` | DateTime(TZ) | Record creation timestamp |
| `updated_at` | DateTime(TZ) | Record update timestamp |

### Relationships (Foreign Keys)

**Outgoing:**
- `patient_id` → `patients.id` (CASCADE delete)
- `reviewed_by` → `users.id` (SET NULL on delete)
- `original_message_id` → `messages.id` (SET NULL on delete)

**Incoming:**
- Referenced by Message model via backref `dlq_entries`

### Integration Points

**WhatsApp Integration:**
- Captures messages that failed all retry attempts
- Stores error codes and messages from Evolution API
- Links to original message for context

**Key Features:**
- Manual review workflow support
- Retry scheduling with exponential backoff
- Resolution tracking
- Reviewer assignment
- Comprehensive error tracking

### Enumerations

**FailureReason:**
- `NETWORK_ERROR` - Network connectivity issue
- `TIMEOUT` - Request timeout
- `INVALID_PHONE` - Invalid phone number
- `BLOCKED_NUMBER` - Number is blocked
- `RATE_LIMIT` - API rate limit exceeded
- `API_ERROR` - Evolution API error
- `MAX_RETRIES_EXCEEDED` - Exceeded max retry attempts
- `UNKNOWN` - Unknown error

**DLQStatus:**
- `PENDING_REVIEW` - Awaiting review
- `UNDER_REVIEW` - Currently being reviewed
- `RESOLVED` - Issue resolved
- `DISCARDED` - Failure discarded

### Helper Methods

**`dlq_data` property**: Access to DLQ metadata with getter/setter
**`to_dict()`**: Convert to dictionary for API responses with optional sensitive data inclusion

---

## 5. Notifications Table (`notifications`)

### Purpose/Utility
System notifications for users (healthcare providers/staff). Manages in-app notifications with priority levels, read status, archiving, and expiration.

### Table Name
`notifications`

### Key Columns

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `user_id` | UUID | Foreign key to users table (required) |
| `related_patient_id` | UUID | Foreign key to patients table (optional) |
| `notification_type` | Enum | Type of notification (info, warning, error, success, alert, reminder) |
| `priority` | Enum | Priority level (low, medium, high, urgent) |
| `title` | String(200) | Notification title |
| `message` | Text | Notification message content |
| `action_url` | String(500) | Optional action URL |
| `action_label` | String(100) | Label for action button |
| `notification_metadata` | JSONB | Additional metadata (column avoids reserved name) |
| `is_read` | Boolean | Read status (default: false) |
| `read_at` | DateTime(TZ) | When notification was read |
| `is_archived` | Boolean | Archive status (default: false) |
| `archived_at` | DateTime(TZ) | When notification was archived |
| `expires_at` | DateTime(TZ) | Expiration timestamp (indexed) |
| `created_at` | DateTime(TZ) | Notification creation timestamp |
| `updated_at` | DateTime(TZ) | Last update timestamp |

### Relationships (Foreign Keys)

**Outgoing:**
- `user_id` → `users.id` (CASCADE delete)
- `related_patient_id` → `patients.id` (CASCADE delete)

**Incoming:**
- Referenced by User model via `notifications` relationship
- Referenced by Patient model via `notifications` relationship

### Integration Points

**User Interface Integration:**
- Powers in-app notification center
- Supports action buttons with URLs
- Patient context linking
- Expiration for time-sensitive notifications

**Key Features:**
- Read/unread tracking
- Archive functionality
- Priority-based filtering
- Patient-related notifications
- Action URLs for deep linking
- Metadata for extensibility

### Enumerations

**NotificationType:**
- `INFO` - Informational notification
- `WARNING` - Warning notification
- `ERROR` - Error notification
- `SUCCESS` - Success notification
- `ALERT` - Alert notification
- `REMINDER` - Reminder notification

**NotificationPriority:**
- `LOW` - Low priority
- `MEDIUM` - Medium priority (default)
- `HIGH` - High priority
- `URGENT` - Urgent priority

### Performance Indexes

**Indexed Columns:**
- `user_id` - Fast user notification queries
- `related_patient_id` - Patient-related notification queries
- `notification_type` - Filter by type
- `priority` - Filter by priority
- `is_read` - Filter read/unread
- `is_archived` - Filter archived notifications
- `expires_at` - Query expiring notifications

---

## 6. Message Templates Table (`message_templates`)

### Purpose/Utility
Reusable WhatsApp message templates with variable substitution. Supports multiple message types and media URLs for consistent messaging.

### Table Name
`message_templates`

### Key Columns

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `name` | String | Unique template name (indexed) |
| `content` | Text | Message content with placeholders |
| `variables` | JSONB | List of variable names used in content |
| `message_type` | String | Type of message (text, image, document, etc.) |
| `media_url` | String | Optional URL for media messages |
| `is_active` | Boolean | Template active status (default: true) |
| `created_at` | DateTime(TZ) | Template creation timestamp |
| `updated_at` | DateTime(TZ) | Last update timestamp |

### Relationships (Foreign Keys)

**Outgoing:**
- None (standalone reference table)

### Integration Points

**WhatsApp Integration:**
- Provides reusable message templates
- Supports media messages via `media_url`
- Variable substitution for personalization

**Key Features:**
- Template versioning via active/inactive status
- Variable placeholder system
- Media message support
- Python string formatting compatibility

### Helper Methods

**`format(**kwargs)`**: Formats template content with provided variables
- Uses Python string `.format()` method
- Raises `ValueError` if required variable is missing

### Usage Example

```python
template = MessageTemplate(
    name="welcome_message",
    content="Hello {patient_name}, welcome to {clinic_name}!",
    variables=["patient_name", "clinic_name"],
    message_type="text",
    is_active=True
)

formatted = template.format(
    patient_name="John Doe",
    clinic_name="Hormonia Clinic"
)
# Result: "Hello John Doe, welcome to Hormonia Clinic!"
```

---

## Integration Architecture Overview

### WhatsApp Message Flow

```
1. Message Creation
   └─> messages table (status: pending)
       └─> Idempotency check via idempotency_key

2. Message Sending
   └─> Celery worker picks up message
       └─> Evolution API call
           └─> message_status_events (status: sent)
               └─> messages.status updated

3. Webhook Events
   └─> Evolution API sends webhook
       └─> webhook_events table (for audit)
           └─> Event processing
               └─> message_status_events (status: delivered/read)
                   └─> messages.status updated

4. Failure Handling
   └─> Retry logic (up to max_retries)
       └─> If max retries exceeded
           └─> whatsapp_delivery_failures (DLQ)
               └─> Manual review workflow
```

### Key Design Patterns

**1. Idempotency Protection**
- `messages.idempotency_key` prevents duplicate sends
- `webhook_events.event_hash` prevents duplicate event processing

**2. Audit Trail**
- `message_status_events` tracks all status transitions
- `webhook_events` stores all Evolution API events

**3. Dead Letter Queue (DLQ)**
- `whatsapp_delivery_failures` for failed messages
- `webhook_events` for failed event processing

**4. Retry Mechanism**
- Exponential backoff via `next_retry_at`
- Maximum retry limits (`max_retries`)
- Retry count tracking

**5. Relationship Cascade**
- CASCADE deletes for patient/user relationships
- SET NULL for reviewer/message references
- Preserves audit trail while allowing cleanup

### Performance Considerations

**Indexed Columns:**
- All foreign keys are indexed
- Status columns for filtering
- Timestamp columns for time-based queries
- Hash columns for deduplication

**JSONB Usage:**
- `message_metadata` - Flexible message data
- `event_metadata` - Event context
- `dlq_metadata` - DLQ processing data
- `notification_metadata` - Notification extras
- `variables` - Template variables
- Allows schema evolution without migrations

**Composite Indexes:**
- Multi-column indexes for common query patterns
- Partial indexes for conditional queries (e.g., errors only)

---

## Database Schema Relationships Diagram

```
┌─────────────────┐
│    patients     │
└────────┬────────┘
         │
         ├─────────────────────────────────┐
         │                                 │
         ▼                                 ▼
┌─────────────────┐              ┌──────────────────────┐
│    messages     │              │ whatsapp_delivery_   │
│                 │              │     failures         │
│ • patient_id    │              │                      │
│ • whatsapp_id   │◄─────────────┤ • original_message_id│
│ • status        │              │ • patient_id         │
│ • priority      │              │ • reviewed_by        │
└────────┬────────┘              └──────────────────────┘
         │                                 ▲
         │                                 │
         ▼                                 │
┌─────────────────────┐                   │
│ message_status_     │                   │
│      events         │                   │
│                     │                   │
│ • message_id        │                   │
│ • status            │                   │
│ • error_code        │                   │
└─────────────────────┘                   │
                                          │
┌─────────────────────┐                   │
│  webhook_events     │                   │
│                     │                   │
│ • related_message_id├───────────────────┘
│ • related_patient_id│
│ • event_hash        │
└─────────────────────┘

┌─────────────────┐
│      users      │
└────────┬────────┘
         │
         ├─────────────────────────────────┐
         │                                 │
         ▼                                 ▼
┌─────────────────┐              ┌──────────────────────┐
│ notifications   │              │ whatsapp_delivery_   │
│                 │              │     failures         │
│ • user_id       │              │ (reviewed_by)        │
│ • related_      │              └──────────────────────┘
│   patient_id    │
└─────────────────┘

┌─────────────────┐
│ message_        │
│   templates     │
│                 │
│ (standalone)    │
└─────────────────┘
```

---

## Summary Statistics

| Table | Primary Purpose | Key Integration | Foreign Keys |
|-------|----------------|-----------------|--------------|
| `messages` | WhatsApp message storage | Evolution API | patients |
| `message_status_events` | Status audit trail | Evolution API webhooks | messages |
| `webhook_events` | Event DLQ & replay | Evolution API webhooks | None (loose coupling) |
| `whatsapp_delivery_failures` | Failed message DLQ | Evolution API | patients, messages, users |
| `notifications` | System notifications | User interface | users, patients |
| `message_templates` | Reusable templates | WhatsApp messaging | None |

---

## Recommendations for Code Quality

### ✅ Strengths

1. **Comprehensive Audit Trail**: Full lifecycle tracking via `message_status_events`
2. **Idempotency Protection**: Prevents duplicate sends and event processing
3. **Robust Error Handling**: DLQ pattern for failed messages and events
4. **Flexible Metadata**: JSONB columns allow schema evolution
5. **Performance Optimized**: Strategic indexes on high-traffic columns
6. **Type Safety**: Enumerations for status and type fields
7. **Cascade Management**: Proper foreign key cascade behavior

### ⚠️ Areas for Monitoring

1. **JSONB Query Performance**: Monitor queries on JSONB columns as data grows
2. **Webhook Event Growth**: Consider archival strategy for `webhook_events`
3. **Status Event Volume**: High-volume message tracking may need partitioning
4. **Notification Cleanup**: Implement automated cleanup of expired/archived notifications
5. **Template Versioning**: Consider version control for template changes

### 🔧 Potential Improvements

1. **Add Partitioning**: Consider table partitioning for `message_status_events` and `webhook_events` by date
2. **Archive Strategy**: Implement time-based archival for old events
3. **Materialized Views**: Create views for common analytics queries
4. **Monitoring Triggers**: Add database triggers for critical state changes
5. **Template History**: Add template versioning with history table

---

## File Locations

- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/models/message.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/models/message_events.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/models/failed_message.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/models/notification.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/models/template.py`

---

**Document Generated**: 2025-12-22
**Analysis Version**: 1.0
**Backend Version**: Python 3.13 / SQLAlchemy
