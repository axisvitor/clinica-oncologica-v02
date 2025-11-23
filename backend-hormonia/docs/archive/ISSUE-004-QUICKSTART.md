# ISSUE-004: Dependency Injection - Quick Reference

## What Changed

`PatientOnboardingService` now uses **Dependency Injection** for `MessageService` and `UnifiedWhatsAppService`.

## For Developers

### Creating PatientOnboardingService

**Before**:
```python
service = PatientOnboardingService(
    db=db,
    integrity_service=integrity_service,
    flow_service=flow_service,
)
# MessageService and UnifiedWhatsAppService created internally
```

**After**:
```python
# Create dependencies first
message_service = MessageService(db)
whatsapp_service = UnifiedWhatsAppService(db=db, messaging_mode=MessagingMode.LEGACY)

# Inject into constructor
service = PatientOnboardingService(
    db=db,
    integrity_service=integrity_service,
    flow_service=flow_service,
    message_service=message_service,      # ✅ NOW REQUIRED
    whatsapp_service=whatsapp_service,    # ✅ NOW REQUIRED
)
```

### For Testing (Mocking)

```python
# Easy mocking with dependency injection
mock_message_service = MagicMock(spec=MessageService)
mock_whatsapp_service = MagicMock(spec=UnifiedWhatsAppService)

service = PatientOnboardingService(
    db=mock_db,
    integrity_service=mock_integrity,
    flow_service=mock_flow,
    message_service=mock_message_service,     # ✅ MOCK
    whatsapp_service=mock_whatsapp_service,   # ✅ MOCK
)

# Configure mock behavior
mock_message_service.schedule_message.return_value = Mock(id=123)
mock_whatsapp_service.send_message.return_value = True
```

## Migration Guide

### If using PatientService (Recommended)
**No changes needed!** The facade handles everything:
```python
patient_service = PatientService(db, saga_orchestrator)
# patient_service.onboarding already has dependencies injected
```

### If creating directly
Update your code to inject dependencies:
```python
# Add these imports
from app.services.message import MessageService
from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode

# Create services
message_service = MessageService(db)
whatsapp_service = UnifiedWhatsAppService(db=db, messaging_mode=MessagingMode.LEGACY)

# Inject when creating PatientOnboardingService
onboarding = PatientOnboardingService(
    db=db,
    integrity_service=integrity_service,
    flow_service=flow_service,
    message_service=message_service,      # ✅ ADD THIS
    whatsapp_service=whatsapp_service,    # ✅ ADD THIS
    saga_orchestrator=saga_orchestrator,
)
```

## Files Changed
- `app/services/patient/onboarding_service.py`
- `app/services/patient_service.py`
- `tests/integration/test_saga_fallback_race_condition.py`

## Benefits
- ✅ Easier testing (mock dependencies)
- ✅ Better SOLID compliance
- ✅ Reduced coupling
- ✅ No breaking changes (facade pattern)

## Questions?
See full documentation:
- `docs/ISSUE-004-IMPLEMENTATION-REPORT.md` - Complete implementation details
- `docs/ISSUE-004-VALIDATION-SUMMARY.md` - Validation results
