# Quick Reference: P0-1 Fix

## What Changed?

### NEW METHOD (Use This)
```python
# Schedule existing message
result = await message_scheduler.schedule_existing_message(
    message_id=message.id,
    send_time=datetime.utcnow() + timedelta(hours=1),
    priority='normal'  # 'low', 'normal', 'high', 'urgent'
)
```

### OLD METHOD (Still Works)
```python
# Create and schedule new message
result = await message_scheduler.schedule_message(
    patient_id=patient_id,
    message_content="Hello",
    scheduling_window=SchedulingWindow.BUSINESS_HOURS
)
```

## When to Use Which?

| Scenario | Method | Why |
|----------|--------|-----|
| Message already exists in DB | `schedule_existing_message()` | Updates existing record |
| Create new message | `schedule_message()` | Creates + schedules |
| Flow messages | `schedule_existing_message()` | Message created in flow logic |
| Follow-up messages | `schedule_existing_message()` | Message created separately |

## Error Handling

```python
from app.exceptions import NotFoundError, ValidationError

try:
    result = await message_scheduler.schedule_existing_message(
        message_id=message_id,
        send_time=send_time,
        priority='high'
    )
    if result:
        print("✓ Scheduled successfully")
    else:
        print("✗ Scheduling failed (check logs)")

except NotFoundError:
    print("✗ Message not found")

except ValidationError as e:
    print(f"✗ Invalid message state: {e}")
```

## Priority Levels

| Priority | Use Case | Example |
|----------|----------|---------|
| `low` | Non-urgent notifications | Monthly reminders |
| `normal` | Regular flow messages | Daily check-ins |
| `high` | Important follow-ups | Response to patient concern |
| `urgent` | Critical alerts | Emergency notifications |

## Common Patterns

### Pattern 1: Create Then Schedule
```python
# 1. Create message
message = Message(
    patient_id=patient_id,
    content="Your message",
    status=MessageStatus.PENDING
)
db.add(message)
db.flush()  # Get ID without committing

# 2. Schedule it
scheduled = await message_scheduler.schedule_existing_message(
    message_id=message.id,
    send_time=send_time,
    priority='normal'
)

# 3. Commit only if scheduling succeeded
if scheduled:
    db.commit()
else:
    db.rollback()
```

### Pattern 2: Reschedule Existing
```python
# Reschedule already scheduled message
result = await message_scheduler.schedule_existing_message(
    message_id=existing_message_id,
    send_time=new_time,  # New send time
    priority='high'       # Can change priority
)
```

### Pattern 3: Immediate Delivery
```python
# Schedule for immediate delivery (within 1 minute)
result = await message_scheduler.schedule_existing_message(
    message_id=message_id,
    send_time=datetime.utcnow() + timedelta(minutes=1),
    priority='urgent'
)
```

## Valid Message States

Only these states can be scheduled:
- ✅ `MessageStatus.PENDING` - Not yet scheduled
- ✅ `MessageStatus.SCHEDULED` - Rescheduling allowed

These states **cannot** be scheduled:
- ❌ `MessageStatus.SENT` - Already sent
- ❌ `MessageStatus.DELIVERED` - Already delivered
- ❌ `MessageStatus.READ` - Already read
- ❌ `MessageStatus.FAILED` - Failed delivery
- ❌ `MessageStatus.CANCELLED` - Cancelled

## Troubleshooting

### "Message not found"
```python
# Check message exists
message = db.query(Message).filter(Message.id == message_id).first()
if not message:
    print("Message doesn't exist in database")
```

### "Cannot schedule message with status X"
```python
# Check and fix message status
message = db.query(Message).filter(Message.id == message_id).first()
print(f"Current status: {message.status}")

# Fix: Set to PENDING
message.status = MessageStatus.PENDING
db.commit()
```

### "Send time is in the past"
```python
# This is auto-fixed with warning in logs
# Send time adjusted to: now + 1 minute
# Check logs for: "Send time is in the past, adjusting..."
```

### Scheduling returns False
```python
# Check message metadata for error
message = db.query(Message).filter(Message.id == message_id).first()
if message.message_metadata.get('scheduling_status') == 'failed':
    error = message.message_metadata.get('scheduling_error')
    print(f"Celery error: {error}")
```

## Testing

```python
# Run specific test
pytest tests/test_message_scheduler_signature_fix.py::TestScheduleExistingMessage::test_schedule_existing_message_success -v

# Run all tests
pytest tests/test_message_scheduler_signature_fix.py -v

# Run with coverage
pytest tests/test_message_scheduler_signature_fix.py --cov=app.services.message_scheduler
```

## Monitoring

```sql
-- Check scheduling success rate
SELECT
    COUNT(*) FILTER (WHERE message_metadata->>'scheduling_status' = 'success') as successful,
    COUNT(*) FILTER (WHERE message_metadata->>'scheduling_status' = 'failed') as failed,
    COUNT(*) as total
FROM messages
WHERE created_at > NOW() - INTERVAL '1 day';

-- Check priority distribution
SELECT
    message_metadata->>'priority' as priority,
    COUNT(*) as count
FROM messages
WHERE message_metadata->>'priority' IS NOT NULL
GROUP BY priority;
```

## Migration Notes

### From Old Code
```python
# BEFORE (Won't work anymore)
await self.message_scheduler.schedule_message(
    message_id=message.id,  # ❌ Wrong parameter
    send_time=send_time,     # ❌ Wrong parameter
    priority='normal'        # ❌ Wrong parameter
)

# AFTER (Correct)
await self.message_scheduler.schedule_existing_message(
    message_id=message.id,   # ✅ Correct
    send_time=send_time,     # ✅ Correct
    priority='normal'        # ✅ Correct
)
```

## Files Changed

| File | Line | What Changed |
|------|------|--------------|
| `app/services/message_scheduler.py` | 630-720 | Added `schedule_existing_message()` |
| `app/services/flow.py` | 438 | Updated method call |
| `app/services/flow.py` | 834 | Updated method call |
| `app/models/message.py` | 39 | Added `SCHEDULED` status |
| `app/models/message.py` | 44 | Added `CANCELLED` status |

## Quick Links

- 📄 [Full Documentation](P0-1_MESSAGE_SCHEDULER_SIGNATURE_FIX.md)
- 📊 [Implementation Summary](IMPLEMENTATION_SUMMARY_P0-1.md)
- 🧪 [Test Suite](../../tests/test_message_scheduler_signature_fix.py)

---

**Last Updated**: 2025-10-07
**Status**: ✅ PRODUCTION READY
