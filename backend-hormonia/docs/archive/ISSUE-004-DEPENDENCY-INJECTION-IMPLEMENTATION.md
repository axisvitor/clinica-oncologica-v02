# ISSUE-004: Dependency Injection Implementation Guide

**Status:** Implementation Ready
**Priority:** P1 (High)
**Category:** Code Quality, Testability
**Estimated Time:** 30-45 minutes

---

## Executive Summary

Implement **Constructor Injection** in `PatientOnboardingService` to remove internal service creation and improve testability.

**Current Problem:**
- `MessageService` and `UnifiedWhatsAppService` are created internally (lines 314, 332)
- Violates Dependency Inversion Principle
- Makes testing difficult (cannot inject mocks)

**Solution:**
- Inject both services via constructor
- Update all instantiation points
- Update test fixtures

---

## Files to Modify

### 1. `/app/services/patient/onboarding_service.py`

#### Change 1.1: Update Constructor (Lines 63-73)

**BEFORE:**
```python
def __init__(
    self,
    db: Session,
    integrity_service: "PatientIntegrityService",
    flow_service: "PatientFlowService",
    saga_orchestrator: Optional["SagaOrchestrator"] = None,
):
    self.db = db
    self.integrity_service = integrity_service
    self.flow_service = flow_service
    self.saga_orchestrator = saga_orchestrator
```

**AFTER:**
```python
def __init__(
    self,
    db: Session,
    integrity_service: "PatientIntegrityService",
    flow_service: "PatientFlowService",
    message_service: MessageService,  # ✅ NEW
    whatsapp_service: UnifiedWhatsAppService,  # ✅ NEW
    saga_orchestrator: Optional["SagaOrchestrator"] = None,
):
    """
    Initialize PatientOnboardingService with dependency injection.

    DEPENDENCY INJECTION PATTERN (ISSUE-004):
    All services are injected via constructor to:
    - Enable testability (mock dependencies)
    - Reduce coupling between components
    - Follow Dependency Inversion Principle
    """
    self.db = db
    self.integrity_service = integrity_service
    self.flow_service = flow_service
    self.message_service = message_service  # ✅ NEW
    self.whatsapp_service = whatsapp_service  # ✅ NEW
    self.saga_orchestrator = saga_orchestrator
```

#### Change 1.2: Update `_send_welcome_message` Method (Lines 336-358)

**BEFORE:**
```python
# Schedule message for immediate sending
message_service = MessageService(self.db)  # ❌ REMOVE THIS
message = message_service.schedule_message(...)

# Send via unified WhatsApp service
unified_service = UnifiedWhatsAppService(  # ❌ REMOVE THIS
    db=self.db, messaging_mode=MessagingMode.LEGACY
)
success = await unified_service.send_message(message)
```

**AFTER:**
```python
# Schedule message for immediate sending using injected MessageService
# DEPENDENCY INJECTION FIX (ISSUE-004): Use self.message_service
message = self.message_service.schedule_message(...)

# Send via injected UnifiedWhatsAppService
# DEPENDENCY INJECTION FIX (ISSUE-004): Use self.whatsapp_service
success = await self.whatsapp_service.send_message(message)
```

**Complete updated method:**
```python
async def _send_welcome_message(
    self,
    patient: Patient,
    current_user: Optional[User] = None
) -> None:
    """Send WhatsApp welcome message to newly registered patient."""
    try:
        # Generate welcome message content
        welcome_text = get_welcome_message(
            patient_name=patient.name,
            clinic_name=settings.CLINIC_NAME,
            support_phone=settings.CLINIC_SUPPORT_PHONE,
        )

        # ✅ USE INJECTED SERVICE (no instantiation)
        message = self.message_service.schedule_message(
            patient_id=patient.id,
            content=welcome_text,
            scheduled_for=datetime.utcnow(),
            message_type=MessageType.TEXT,
            message_metadata={
                "patient_id": str(patient.id),
                "patient_name": patient.name,
                "message_type": "welcome",
                "created_by": getattr(current_user, "email", None) if current_user else "system",
                "treatment_type": patient.treatment_type,
            },
        )

        # ✅ USE INJECTED SERVICE (no instantiation)
        success = await self.whatsapp_service.send_message(message)

        logger.info(
            f"Welcome message sent to patient {patient.id} ({patient.name}): "
            f"status={'success' if success else 'failed'}, phone={patient.phone}"
        )

    except ImportError as e:
        logger.error(f"WhatsApp service not available: {e}")
        raise
    except Exception as e:
        logger.error(f"Error sending welcome message to {patient.phone}: {e}", exc_info=True)
        raise
```

---

### 2. `/app/services/patient_service.py`

#### Change 2.1: Update PatientOnboardingService Instantiation (Lines 79-84)

**BEFORE:**
```python
self.onboarding = PatientOnboardingService(
    db=db,
    integrity_service=integrity_service,
    flow_service=self.flow_service,
    saga_orchestrator=saga_orchestrator,
)
```

**AFTER:**
```python
# Create message and whatsapp services for injection (ISSUE-004)
from app.services.message import MessageService
from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode

message_service = MessageService(db)
whatsapp_service = UnifiedWhatsAppService(db=db, messaging_mode=MessagingMode.LEGACY)

# Inject all dependencies into PatientOnboardingService
self.onboarding = PatientOnboardingService(
    db=db,
    integrity_service=integrity_service,
    flow_service=self.flow_service,
    message_service=message_service,  # ✅ INJECTED
    whatsapp_service=whatsapp_service,  # ✅ INJECTED
    saga_orchestrator=saga_orchestrator,
)
```

---

### 3. `/tests/integration/test_saga_fallback_race_condition.py`

#### Change 3.1: Update `onboarding_service` Fixture (Lines 63-72)

**BEFORE:**
```python
@pytest.fixture
def onboarding_service(db: Session) -> PatientOnboardingService:
    """Create onboarding service with dependencies."""
    integrity_service = PatientIntegrityService(db)
    flow_service = PatientFlowService(db)
    return PatientOnboardingService(
        db=db,
        integrity_service=integrity_service,
        flow_service=flow_service,
        saga_orchestrator=None  # No saga for fallback testing
    )
```

**AFTER:**
```python
@pytest.fixture
def onboarding_service(db: Session) -> PatientOnboardingService:
    """Create onboarding service with all dependencies."""
    from app.repositories.patient import PatientRepository
    from app.services.message import MessageService
    from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode

    patient_repo = PatientRepository(db)
    integrity_service = PatientIntegrityService(db, patient_repo)
    flow_service = PatientFlowService(db)

    # Create and inject message and whatsapp services (ISSUE-004)
    message_service = MessageService(db)
    whatsapp_service = UnifiedWhatsAppService(db=db, messaging_mode=MessagingMode.LEGACY)

    return PatientOnboardingService(
        db=db,
        integrity_service=integrity_service,
        flow_service=flow_service,
        message_service=message_service,  # ✅ INJECTED
        whatsapp_service=whatsapp_service,  # ✅ INJECTED
        saga_orchestrator=None  # No saga for fallback testing
    )
```

---

## Implementation Steps

### Step 1: Backup Files (Optional but Recommended)

```bash
cd /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1/backend-hormonia

# Create backup
cp app/services/patient/onboarding_service.py app/services/patient/onboarding_service.py.backup
cp app/services/patient_service.py app/services/patient_service.py.backup
cp tests/integration/test_saga_fallback_race_condition.py tests/integration/test_saga_fallback_race_condition.py.backup
```

### Step 2: Apply Changes Manually

Open each file in your editor and apply the changes described above.

**OR**

Run the automated script:
```bash
cd /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1/backend-hormonia
python scripts/apply_dependency_injection_fix.py
```

### Step 3: Verify Changes

```bash
# Check what changed
git diff app/services/patient/onboarding_service.py
git diff app/services/patient_service.py
git diff tests/integration/test_saga_fallback_race_condition.py
```

### Step 4: Validate No Internal Service Creation

```bash
# Should find ZERO matches (services should be injected, not created)
cd app/services/patient
grep -n "MessageService(self.db)" onboarding_service.py
grep -n "UnifiedWhatsAppService(" onboarding_service.py

# Expected output: (no matches)
```

### Step 5: Run Tests

```bash
# Run integration tests
pytest tests/integration/test_saga_fallback_race_condition.py -v -s

# Expected output: All tests should PASS
```

### Step 6: Run Full Test Suite

```bash
# Run all patient-related tests
pytest tests/ -k patient -v

# Run full suite
pytest tests/ -v
```

### Step 7: Commit Changes

```bash
git add app/services/patient/onboarding_service.py
git add app/services/patient_service.py
git add tests/integration/test_saga_fallback_race_condition.py
git add docs/architecture/ADR-004-DEPENDENCY-INJECTION-PATIENT-ONBOARDING.md
git add docs/ISSUE-004-DEPENDENCY-INJECTION-IMPLEMENTATION.md

git commit -m "fix(patient): implement dependency injection in PatientOnboardingService (ISSUE-004)

- Inject MessageService and UnifiedWhatsAppService via constructor
- Remove internal service instantiation in _send_welcome_message
- Update PatientService facade to create and inject dependencies
- Update test fixtures with proper dependency injection
- Improves testability and follows Dependency Inversion Principle

Related: ISSUE-004
Refs: ADR-004-DEPENDENCY-INJECTION-PATIENT-ONBOARDING.md"
```

---

## Validation Checklist

After implementation, verify:

- [ ] ✅ Constructor accepts `message_service` and `whatsapp_service` parameters
- [ ] ✅ Instance variables `self.message_service` and `self.whatsapp_service` are set
- [ ] ✅ `_send_welcome_message` uses `self.message_service` (not `MessageService(self.db)`)
- [ ] ✅ `_send_welcome_message` uses `self.whatsapp_service` (not `UnifiedWhatsAppService(...)`)
- [ ] ✅ `PatientService` creates and injects both services
- [ ] ✅ Test fixtures create and inject both services
- [ ] ✅ No internal service instantiation remains (`grep` returns zero results)
- [ ] ✅ All integration tests pass
- [ ] ✅ Full test suite passes
- [ ] ✅ Code follows SOLID principles
- [ ] ✅ ADR-004 documentation created

---

## Troubleshooting

### Issue: Tests fail with `TypeError: __init__() missing 2 required positional arguments`

**Cause:** Not all instantiation points were updated with new parameters.

**Fix:** Search for all places creating `PatientOnboardingService`:
```bash
grep -rn "PatientOnboardingService(" app/ tests/ --include="*.py"
```

Update each location to inject `message_service` and `whatsapp_service`.

### Issue: `AttributeError: 'PatientOnboardingService' object has no attribute 'message_service'`

**Cause:** Constructor parameters added but not assigned to `self`.

**Fix:** Ensure constructor has:
```python
self.message_service = message_service
self.whatsapp_service = whatsapp_service
```

### Issue: Circular import when importing services

**Cause:** Importing at module level creates circular dependency.

**Fix:** Move imports inside `__init__` or use `TYPE_CHECKING`:
```python
if TYPE_CHECKING:
    from app.services.message import MessageService
```

---

## Benefits After Implementation

### 1. Testability ✅
```python
# Can now test with mocks
def test_send_welcome_message():
    mock_message_service = Mock(spec=MessageService)
    mock_whatsapp_service = Mock(spec=UnifiedWhatsAppService)

    service = PatientOnboardingService(
        db=db,
        integrity_service=integrity,
        flow_service=flow,
        message_service=mock_message_service,  # ✅ Inject mock
        whatsapp_service=mock_whatsapp_service,  # ✅ Inject mock
        saga_orchestrator=None
    )

    await service._send_welcome_message(patient, None)

    # Verify mocks were called
    mock_message_service.schedule_message.assert_called_once()
    mock_whatsapp_service.send_message.assert_called_once()
```

### 2. SOLID Compliance ✅
- Follows **Dependency Inversion Principle**
- High-level modules depend on abstractions (interfaces)
- Low-level details injected from outside

### 3. Reduced Coupling ✅
- `PatientOnboardingService` doesn't know how to construct `MessageService`
- Easy to swap implementations
- Clear separation of concerns

### 4. Maintainability ✅
- Centralized dependency creation
- Easy to change service initialization
- Clear dependency graph

---

## Related Documents

- [ADR-004: Dependency Injection in PatientOnboardingService](./architecture/ADR-004-DEPENDENCY-INJECTION-PATIENT-ONBOARDING.md)
- [P0.2 Patient Service Refactoring Plan](./architecture/P0.2_PATIENT_SERVICE_REFACTORING.md)
- [SOLID Principles Guide](https://en.wikipedia.org/wiki/SOLID)

---

**Last Updated:** 2025-11-15
**Implemented By:** System Architect
**Reviewed By:** Backend Team
