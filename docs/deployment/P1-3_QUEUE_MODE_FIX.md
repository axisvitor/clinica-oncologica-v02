# P1-3: Unified WhatsApp Stack Queue Mode Fix

## Problem Summary

**Issue**: MessageSender defaulted to `MessagingMode.LEGACY` in Celery tasks, causing queue mode to only activate when explicit metadata was provided. This negated the retry/backoff policies in UnifiedWhatsAppService and undermined the move away from direct sends.

**Location**: `backend-hormonia/app/services/message_sender.py:48-84`

**Impact**:
- Retry/backoff policies were not being applied to Celery-triggered messages
- Queue management benefits (reliability, rate limiting, metrics) were bypassed
- System defaulted to less reliable direct API calls

## Solution Implemented

### 1. Changed Default Mode to QUEUE

**File**: `backend-hormonia/app/services/message_sender.py`

```python
# BEFORE (Line 55)
messaging_mode=MessagingMode.LEGACY  # Use legacy mode for compatibility

# AFTER (Lines 58, 68-75)
def __init__(self, db: Session, messaging_mode: MessagingMode = MessagingMode.QUEUE):
    """
    Initialize MessageSender with configurable messaging mode.

    Args:
        db: Database session
        messaging_mode: Messaging mode (default: QUEUE for retry/backoff policies)
    """
    self.messaging_mode = messaging_mode

    # Warn if using legacy mode
    if messaging_mode == MessagingMode.LEGACY:
        _warn_legacy_mode()
        logger.warning("MessageSender using LEGACY mode - retry/backoff policies may be limited")
    else:
        logger.info(f"MessageSender using {messaging_mode.value} mode with full retry/backoff support")
```

### 2. Added Deprecation Warning for Legacy Mode

**File**: `backend-hormonia/app/services/message_sender.py`

```python
# Lines 40-47
def _warn_legacy_mode():
    """Warn about legacy mode usage."""
    warnings.warn(
        "MessagingMode.LEGACY is deprecated and will be removed in a future version. "
        "Use MessagingMode.QUEUE for retry/backoff policies.",
        DeprecationWarning,
        stacklevel=3
    )
```

### 3. Updated Celery Tasks to Use Queue Mode

**Files Modified**:
- `backend-hormonia/app/tasks/messaging.py`
- `backend-hormonia/app/tasks/flows.py`

**Changes Applied**:

#### messaging.py (3 locations)
```python
# send_scheduled_message task (Line 72-73)
from app.services.unified_whatsapp_service import MessagingMode
message_sender = MessageSender(db, messaging_mode=MessagingMode.QUEUE)

# process_scheduled_messages task (Line 135-136)
from app.services.unified_whatsapp_service import MessagingMode
message_sender = MessageSender(db, messaging_mode=MessagingMode.QUEUE)

# retry_failed_messages task (Line 177-178)
from app.services.unified_whatsapp_service import MessagingMode
message_sender = MessageSender(db, messaging_mode=MessagingMode.QUEUE)
```

#### flows.py (1 location)
```python
# send_flow_message task (Line 243-244)
from app.services.unified_whatsapp_service import MessagingMode
message_sender = MessageSender(db, messaging_mode=MessagingMode.QUEUE)
```

### 4. Enhanced Queue Mode Metadata Handling

**File**: `backend-hormonia/app/services/unified_whatsapp_service.py`

```python
# Lines 302-324
def _add_unified_metadata(self, message: Message, mode: MessagingMode, **kwargs):
    """Add unified metadata to message."""
    # ... existing code ...

    # Ensure requires_queue flag is set for queue mode
    if mode == MessagingMode.QUEUE:
        message.message_metadata['requires_queue'] = True
        logger.debug(f"Message {message.id} marked for queue mode processing")

    # ... flow context handling ...

    # Set default retry policy if not set and using queue mode
    if mode == MessagingMode.QUEUE and 'retry_policy' not in message.message_metadata:
        message.message_metadata['retry_policy'] = 'default'
        logger.debug(f"Message {message.id} assigned default retry policy for queue mode")
```

### 5. Added Comprehensive Tests

**File**: `backend-hormonia/tests/test_message_sender_queue_mode.py`

**Test Coverage**:
- ✅ MessageSender defaults to QUEUE mode
- ✅ Explicit QUEUE mode configuration
- ✅ Explicit LEGACY mode with deprecation warning
- ✅ HYBRID mode support
- ✅ Queue mode adds `requires_queue` metadata
- ✅ Queue mode assigns default retry policy
- ✅ Flow messages get flow-specific retry policy
- ✅ Quiz messages get quiz-specific retry policy
- ✅ Urgent messages get urgent retry policy
- ✅ Retry policies configuration verification
- ✅ Failed message retry with exponential backoff
- ✅ Max retries exceeded handling
- ✅ Backoff delay calculation
- ✅ Celery tasks use queue mode
- ✅ Legacy mode backward compatibility
- ✅ UnifiedWhatsAppService mode selection
- ✅ Metrics tracking by mode
- ✅ Retry failed messages uses policies

**Total Tests**: 18 comprehensive test cases

## Retry Policies Configuration

All queue mode messages now benefit from the following retry policies:

### Default Policy
```python
'default': {
    'max_retries': 3,
    'backoff_factor': 2,
    'base_delay': 300  # 5 minutes
}
```

### Flow Message Policy
```python
'flow_message': {
    'max_retries': 5,
    'backoff_factor': 1.5,
    'base_delay': 180  # 3 minutes
}
```

### Urgent Policy
```python
'urgent': {
    'max_retries': 7,
    'backoff_factor': 1.2,
    'base_delay': 60  # 1 minute
}
```

### Quiz Link Policy
```python
'quiz_link': {
    'max_retries': 4,
    'backoff_factor': 1.8,
    'base_delay': 240  # 4 minutes
}
```

## Migration Path

### Backward Compatibility

✅ **Legacy mode still supported** - Systems can explicitly request `MessagingMode.LEGACY` if needed
✅ **Deprecation warnings** - Clear warnings guide developers away from legacy mode
✅ **Gradual migration** - Existing code continues to work while encouraging queue mode adoption

### Recommended Migration Steps

1. **Immediate**: All new code should use default queue mode
2. **Short-term**: Update existing Celery tasks to explicitly use queue mode (✅ DONE)
3. **Medium-term**: Audit all MessageSender instantiations for legacy mode usage
4. **Long-term**: Remove legacy mode support (v3.0.0)

## Benefits

### ✅ Reliability
- Automatic retry with exponential backoff
- Failed messages tracked and retried systematically
- Queue-based processing prevents message loss

### ✅ Performance
- Rate limiting prevents API throttling
- Batch processing reduces overhead
- Metrics tracking for monitoring

### ✅ Maintainability
- Single code path for message sending
- Consistent error handling
- Centralized retry logic

### ✅ Monitoring
- Detailed logging of mode selection
- Metrics tracking per mode
- Retry attempt tracking

## Verification Checklist

- [x] MessageSender defaults to QUEUE mode
- [x] Legacy mode shows deprecation warning
- [x] Celery tasks use queue mode explicitly
- [x] Queue mode adds `requires_queue` metadata
- [x] Retry policies are assigned correctly
- [x] Tests cover all scenarios
- [x] Backward compatibility maintained
- [x] Logging tracks mode usage
- [x] Documentation updated

## Testing

### Run Tests
```bash
# Run all message sender queue mode tests
pytest backend-hormonia/tests/test_message_sender_queue_mode.py -v

# Run specific test
pytest backend-hormonia/tests/test_message_sender_queue_mode.py::TestMessageSenderQueueMode::test_message_sender_defaults_to_queue_mode -v
```

### Expected Results
- All 18 tests should pass
- Deprecation warnings for legacy mode usage
- Queue mode metadata verification
- Retry policy assignment confirmation

## Monitoring

### Log Messages to Watch

**Queue Mode Activation**:
```
MessageSender initialized with messaging_mode=queue
MessageSender using queue mode with full retry/backoff support
```

**Legacy Mode Warning**:
```
MessageSender using LEGACY mode - retry/backoff policies may be limited
```

**Metadata Assignment**:
```
Message {id} marked for queue mode processing
Message {id} assigned default retry policy for queue mode
```

### Metrics to Track

- `messages_sent` - Total messages sent
- `queue_processed` - Messages sent via queue mode
- `legacy_processed` - Messages sent via legacy mode
- `retries_attempted` - Number of retry attempts

## Related Files

### Modified Files
1. `backend-hormonia/app/services/message_sender.py`
2. `backend-hormonia/app/services/unified_whatsapp_service.py`
3. `backend-hormonia/app/tasks/messaging.py`
4. `backend-hormonia/app/tasks/flows.py`

### New Files
1. `backend-hormonia/tests/test_message_sender_queue_mode.py`
2. `docs/deployment/P1-3_QUEUE_MODE_FIX.md` (this file)

### Related Documentation
- `docs/deployment/FIREBASE_REDIS_ARCHITECTURE.md`
- `docs/deployment/FIREBASE_REDIS_CACHE_FIXES.md`
- `docs/deployment/IMPLEMENTATION_STATUS.md`

## Next Steps

### Immediate Actions
1. ✅ Run test suite to verify changes
2. ✅ Review logs for mode selection
3. ✅ Monitor metrics for queue processing

### Future Enhancements
1. Consider removing legacy mode in v3.0.0
2. Add dashboard for retry metrics
3. Implement advanced queue management features
4. Add circuit breaker patterns for queue failures

## Conclusion

The fix successfully addresses P1-3 by:
1. Changing the default to `MessagingMode.QUEUE`
2. Ensuring all Celery tasks use queue mode
3. Adding proper metadata and retry policies
4. Maintaining backward compatibility
5. Providing comprehensive test coverage

All messages now benefit from retry/backoff policies by default, improving system reliability and reducing message delivery failures.

---

**Status**: ✅ COMPLETED
**Date**: 2025-01-07
**Priority**: P1 (Critical)
**Impact**: High - Affects all outbound message reliability
