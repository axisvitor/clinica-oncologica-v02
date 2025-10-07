# P0-4: Message Duplication Fix - Flow Diagrams

## Before Fix (BROKEN) ❌

```
┌─────────────────────────────────────────────────────────────────┐
│ MessageScheduler.schedule_message()                             │
├─────────────────────────────────────────────────────────────────┤
│ 1. message = Message(status=SCHEDULED)                          │
│ 2. db.add(message)  # message_id = ABC-123                      │
│ 3. db.commit()                                                  │
│ 4. task = send_flow_message.apply_async(                        │
│       args=[patient_id, message_data]  # ❌ No message_id!      │
│    )                                                            │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ Celery Task: send_flow_message(patient_id, message_data)       │
├─────────────────────────────────────────────────────────────────┤
│ 1. message = Message(  # ❌ CREATES DUPLICATE!                  │
│       patient_id=patient_id,                                    │
│       content=message_data['content'],                          │
│       status=PENDING  # message_id = XYZ-789                    │
│    )                                                            │
│ 2. db.add(message)  # ❌ Second message created!                │
│ 3. db.commit()                                                  │
│ 4. send_via_whatsapp(message)                                   │
│ 5. message.status = SENT                                        │
│ 6. db.commit()                                                  │
└─────────────────────────────────────────────────────────────────┘

RESULT IN DATABASE:
┌──────────┬──────────┬─────────────────┬──────────┐
│ ID       │ Status   │ Content         │ Sent?    │
├──────────┼──────────┼─────────────────┼──────────┤
│ ABC-123  │ SCHEDULED│ "Hello patient" │ ❌ Never │  ← ORPHANED!
│ XYZ-789  │ SENT     │ "Hello patient" │ ✅ Yes   │  ← DUPLICATE!
└──────────┴──────────┴─────────────────┴──────────┘

PROBLEMS:
❌ 2 messages in database for 1 send
❌ ABC-123 stuck in SCHEDULED forever
❌ Can't track which scheduled message was sent
❌ Reporting counts duplicates
❌ Impossible to correlate schedule → send
```

## After Fix (WORKING) ✅

```
┌─────────────────────────────────────────────────────────────────┐
│ MessageScheduler.schedule_message()                             │
├─────────────────────────────────────────────────────────────────┤
│ 1. message = Message(status=SCHEDULED)                          │
│ 2. db.add(message)  # message_id = ABC-123                      │
│ 3. db.commit()                                                  │
│ 4. task = send_flow_message.apply_async(                        │
│       args=[patient_id, message_data, str(message.id)]          │
│       #                           ▲                             │
│       #                           └─✅ Pass message_id!          │
│    )                                                            │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ Celery Task: send_flow_message(patient_id, data, message_id)   │
├─────────────────────────────────────────────────────────────────┤
│ 1. if message_id:  # ✅ message_id provided                     │
│       message = repo.get(UUID(message_id))  # Load ABC-123      │
│       # ✅ UPDATE existing message instead of creating new      │
│    else:                                                        │
│       message = Message(...)  # Backward compatibility          │
│       db.add(message)                                           │
│                                                                 │
│ 2. message.status = SENDING  # ✅ Track send in progress        │
│ 3. message.metadata['celery_started'] = now()                   │
│ 4. db.commit()                                                  │
│                                                                 │
│ 5. success = send_via_whatsapp(message)                         │
│                                                                 │
│ 6. if success:                                                  │
│       message.status = SENT  # ✅ Update same message           │
│       message.metadata['execution_status'] = 'success'          │
│    else:                                                        │
│       message.status = FAILED  # ✅ Mark failure                │
│       message.metadata['failure_reason'] = error                │
│                                                                 │
│ 7. db.commit()                                                  │
└─────────────────────────────────────────────────────────────────┘

RESULT IN DATABASE:
┌──────────┬──────────┬─────────────────┬──────────┐
│ ID       │ Status   │ Content         │ Sent?    │
├──────────┼──────────┼─────────────────┼──────────┤
│ ABC-123  │ SENT     │ "Hello patient" │ ✅ Yes   │  ← SINGLE MESSAGE!
└──────────┴──────────┴─────────────────┴──────────┘

BENEFITS:
✅ 1 message in database = 1 actual send
✅ Complete lifecycle: SCHEDULED → SENDING → SENT
✅ Full audit trail in single record
✅ Accurate reporting (no duplicates)
✅ Can track scheduled → sent correlation
```

## Status Transition Flow ✅

```
┌──────────────────────────────────────────────────────────────────┐
│                    MESSAGE LIFECYCLE                             │
└──────────────────────────────────────────────────────────────────┘

MessageScheduler.schedule_message()
        │
        ▼
  ┌──────────┐
  │SCHEDULED │  Message created, Celery task scheduled with ETA
  └──────────┘
        │
        │ Celery worker picks up task at ETA time
        │ (send_flow_message receives message_id)
        ▼
  ┌──────────┐
  │ SENDING  │  Worker updates message, begins WhatsApp send
  └──────────┘
        │
        ├─────────────┬─────────────┐
        │             │             │
        ▼             ▼             ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │   SENT   │  │  FAILED  │  │  RETRY   │
  │          │  │          │  │          │
  │ WhatsApp │  │ Send err │  │ Retry in │
  │ accepted │  │ occurred │  │ 60s, 2m  │
  └──────────┘  └──────────┘  └──────────┘
        │             │             │
        │             │             └──► Back to SENDING
        │             │
        │             └──► (After max retries)
        │                  Mark FAILED, log error
        ▼
  ┌──────────┐
  │DELIVERED │  WhatsApp confirms delivery to device
  └──────────┘
        │
        ▼
  ┌──────────┐
  │   READ   │  User opened/read the message
  └──────────┘

METADATA TRACKING:
├─ celery_task_id: "abc-123-xyz"
├─ celery_execution_started: "2025-10-07T10:00:00Z"
├─ celery_execution_completed: "2025-10-07T10:00:15Z"
├─ execution_status: "success" | "failed"
├─ failure_reason: "WhatsApp API error" (if failed)
├─ retry_count: 2 (if retried)
└─ whatsapp_id: "wamid.xyz..." (after sent)
```

## Error Handling Flow ✅

```
┌──────────────────────────────────────────────────────────────────┐
│            CELERY TASK ERROR HANDLING                            │
└──────────────────────────────────────────────────────────────────┘

send_flow_message(patient_id, data, message_id)
        │
        ├─── Load message from DB
        │
        ├─── Update status to SENDING
        │
        ├─── Try send_via_whatsapp()
        │
        ├──┬─ SUCCESS ✅
        │  │  ├─ Update message.status = SENT
        │  │  ├─ Add metadata: execution_status = "success"
        │  │  └─ Return success result
        │  │
        │  └─ FAILURE ❌
        │     ├─ Update message.status = FAILED
        │     ├─ Add metadata: failure_reason, error details
        │     └─ Return failure result
        │
        └──┬─ EXCEPTION 💥
           │
           ├─ Try to mark message as FAILED:
           │  ├─ Load message by message_id
           │  ├─ Update status = FAILED
           │  ├─ Add error metadata
           │  └─ Commit
           │
           ├─ Check retry count:
           │  ├─ retries < max_retries?
           │  │  ├─ YES: Retry with exponential backoff
           │  │  │       (60s, 120s, 240s)
           │  │  └─ NO: Return final failure result
           │  │
           │  └─ Message stays FAILED with full error details
           │
           └─ Log error and task details

RETRY BACKOFF:
Attempt 1: Immediate
Attempt 2: +60s  (1 minute)
Attempt 3: +120s (2 minutes)
Attempt 4: +240s (4 minutes)
Final: Mark FAILED permanently
```

## Database Schema Changes ✅

```sql
-- BEFORE: Missing SENDING status
CREATE TYPE messagestatus AS ENUM (
    'pending',
    'scheduled',
    -- ❌ Gap between scheduled and sent
    'sent',
    'delivered',
    'read',
    'failed',
    'cancelled'
);

-- AFTER: Complete status progression
CREATE TYPE messagestatus AS ENUM (
    'pending',
    'scheduled',
    'sending',    -- ✅ NEW: Track active send operation
    'sent',
    'delivered',
    'read',
    'failed',
    'cancelled'
);

-- Migration adds SENDING between SCHEDULED and SENT
ALTER TYPE messagestatus ADD VALUE IF NOT EXISTS 'sending' AFTER 'scheduled';
```

## Code Architecture ✅

```
┌────────────────────────────────────────────────────────────┐
│                    COMPONENT FLOW                          │
└────────────────────────────────────────────────────────────┘

┌──────────────────┐
│  API Endpoint    │  POST /api/v1/messages/schedule
│  (FastAPI)       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ MessageScheduler │  schedule_message(patient_id, content, ...)
│  (Service)       │  ├─ Create Message(status=SCHEDULED)
└────────┬─────────┘  ├─ Save to database
         │            └─ Schedule Celery task WITH message_id ✅
         │
         ▼
┌──────────────────┐
│  Celery Task     │  send_flow_message.apply_async(
│  (flows.py)      │    args=[patient_id, data, message_id] ✅
└────────┬─────────┘  )
         │
         │ (at ETA time)
         ▼
┌──────────────────┐
│  Celery Worker   │  send_flow_message(patient_id, data, message_id)
│  (Background)    │  ├─ Load existing message by message_id ✅
└────────┬─────────┘  ├─ Update status: SCHEDULED → SENDING
         │            ├─ Call MessageSender.send_message()
         │            └─ Update status: SENDING → SENT/FAILED
         ▼
┌──────────────────┐
│ MessageSender    │  send_message(message)
│  (Service)       │  ├─ Call WhatsApp API
└────────┬─────────┘  ├─ Handle response
         │            └─ Update message with whatsapp_id
         ▼
┌──────────────────┐
│ WhatsApp API     │  POST /messages
│  (Evolution API) │  └─ Returns: {id: "wamid.xyz..."}
└──────────────────┘

DATABASE UPDATES:
├─ Step 1: INSERT message (SCHEDULED)      [MessageScheduler]
├─ Step 2: UPDATE message (SENDING)        [Celery Worker]
├─ Step 3: UPDATE message (SENT/FAILED)    [MessageSender]
└─ Step 4: UPDATE message (DELIVERED/READ) [Webhook Handler]

✅ Single message row updated through lifecycle
❌ No duplicate message creation
```

---

**Visual Summary**: The fix ensures message_id flows through entire pipeline, enabling UPDATE operations instead of duplicate INSERTs.
