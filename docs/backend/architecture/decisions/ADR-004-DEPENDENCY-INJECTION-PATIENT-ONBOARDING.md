# ADR-004: Dependency Injection in PatientOnboardingService

**Status:** Accepted
**Date:** 2025-11-15
**Deciders:** System Architect, Backend Team
**Related Issues:** ISSUE-004 (Dependency Injection)

---

## Context and Problem Statement

The `PatientOnboardingService` was creating dependencies (`MessageService` and `UnifiedWhatsAppService`) internally, violating the **Dependency Inversion Principle** and making the code:

1. **Hard to test** - Cannot easily mock dependencies for unit tests
2. **Tightly coupled** - Service directly depends on concrete implementations
3. **Difficult to maintain** - Changes to dependency construction require modifying service internals

### Problematic Code

```python
class PatientOnboardingService:
    def __init__(self, db, integrity_service, flow_service, saga_orchestrator=None):
        self.db = db
        # ... other dependencies

    async def _send_welcome_message(self, patient, current_user):
        # ❌ PROBLEM: Creating dependency internally
        message_service = MessageService(self.db)

        # ❌ PROBLEM: Creating dependency internally
        unified_service = UnifiedWhatsAppService(db=self.db, messaging_mode=MessagingMode.LEGACY)
```

**Issues:**
- Line 314: `message_service = MessageService(self.db)` - internal instantiation
- Line 332: `unified_service = UnifiedWhatsAppService(...)` - internal instantiation
- Cannot inject mocks for testing
- Violates SOLID principles (Dependency Inversion Principle)

---

## Decision Drivers

1. **Testability** - Need to inject mock services for unit testing
2. **SOLID Principles** - Follow Dependency Inversion Principle
3. **Maintainability** - Centralize dependency creation
4. **Flexibility** - Allow different service implementations
5. **Consistency** - Align with other refactored services

---

## Considered Options

### Option 1: Constructor Injection (Selected ✅)

**Description:** Inject `MessageService` and `UnifiedWhatsAppService` via constructor

**Pros:**
- ✅ Explicit dependencies visible in constructor
- ✅ Easy to test with mocks
- ✅ Follows Dependency Inversion Principle
- ✅ Consistent with modern service patterns
- ✅ Compile-time safety

**Cons:**
- ❌ Requires updating all instantiation points
- ❌ Slightly more verbose constructor

### Option 2: Service Locator Pattern

**Description:** Use a global service locator to retrieve dependencies

**Pros:**
- ✅ No constructor changes needed
- ✅ Easy to add new dependencies

**Cons:**
- ❌ Hidden dependencies (not visible in signature)
- ❌ Runtime errors if service not registered
- ❌ Difficult to test
- ❌ Anti-pattern in modern architectures

### Option 3: Property Injection

**Description:** Set services as properties after construction

**Pros:**
- ✅ Flexible initialization

**Cons:**
- ❌ Services may be None (optional dependencies)
- ❌ Easy to forget setting properties
- ❌ Runtime errors

---

## Decision Outcome

**Chosen option:** **Option 1 - Constructor Injection**

### Implementation

#### 1. Updated PatientOnboardingService Constructor

```python
class PatientOnboardingService:
    def __init__(
        self,
        db: Session,
        integrity_service: "PatientIntegrityService",
        flow_service: "PatientFlowService",
        message_service: MessageService,  # ✅ INJECTED
        whatsapp_service: UnifiedWhatsAppService,  # ✅ INJECTED
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
        self.message_service = message_service  # ✅ STORED
        self.whatsapp_service = whatsapp_service  # ✅ STORED
        self.saga_orchestrator = saga_orchestrator
```

#### 2. Updated `_send_welcome_message` Method

```python
async def _send_welcome_message(self, patient, current_user):
    # Generate welcome message content
    welcome_text = get_welcome_message(...)

    # ✅ USE INJECTED SERVICE: self.message_service
    message = self.message_service.schedule_message(
        patient_id=patient.id,
        content=welcome_text,
        scheduled_for=now_sao_paulo(),
        message_type=MessageType.TEXT,
        message_metadata={...},
    )

    # ✅ USE INJECTED SERVICE: self.whatsapp_service
    success = await self.whatsapp_service.send_message(message)
```

#### 3. Updated PatientService (Facade)

```python
# app/services/patient_service.py
class PatientService:
    def __init__(self, db, patient_repository, integrity_service, flow_engine, saga_orchestrator=None):
        self.db = db
        # ... other dependencies

        # ✅ CREATE DEPENDENCIES ONCE
        message_service = MessageService(db)
        whatsapp_service = UnifiedWhatsAppService(db=db, messaging_mode=MessagingMode.LEGACY)

        # ✅ INJECT INTO ONBOARDING SERVICE
        self.onboarding = PatientOnboardingService(
            db=db,
            integrity_service=integrity_service,
            flow_service=self.flow_service,
            message_service=message_service,  # ✅ INJECTED
            whatsapp_service=whatsapp_service,  # ✅ INJECTED
            saga_orchestrator=saga_orchestrator,
        )
```

#### 4. Updated API Endpoint (`patients_crud.py`)

```python
# app/api/v2/patients_crud.py
@router.post("", response_model=PatientV2Response, status_code=status.HTTP_201_CREATED)
async def create_patient(patient_data: PatientV2Create, db: Session = Depends(get_db), ...):
    # Instantiate dependencies
    patient_repo = PatientRepository(db)
    integrity_service = PatientIntegrityService(db, patient_repo)
    flow_engine = FlowEngine(db)

    # ✅ CREATE MESSAGE AND WHATSAPP SERVICES
    message_service = MessageService(db)
    whatsapp_service = UnifiedWhatsAppService(db=db, messaging_mode=MessagingMode.LEGACY)

    # Create SagaOrchestrator (optional)
    saga_orchestrator = SagaOrchestrator(...) if available else None

    # ✅ INJECT ALL DEPENDENCIES INTO PatientService
    service = PatientService(
        db=db,
        patient_repository=patient_repo,
        integrity_service=integrity_service,
        flow_engine=flow_engine,
        saga_orchestrator=saga_orchestrator
    )
    # PatientService internally creates and injects message_service and whatsapp_service

    # Create patient
    created = await service.create_patient(patient_data, doctor_id, current_user)
    return _serialize_patient(created)
```

#### 5. Updated Integration Tests

```python
# tests/integration/test_saga_fallback_race_condition.py
@pytest.fixture
def onboarding_service(db: Session) -> PatientOnboardingService:
    """Create onboarding service with all dependencies."""
    from app.repositories.patient import PatientRepository

    patient_repo = PatientRepository(db)
    integrity_service = PatientIntegrityService(db, patient_repo)
    flow_service = PatientFlowService(db)

    # ✅ CREATE AND INJECT MESSAGE AND WHATSAPP SERVICES
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

## Consequences

### Positive Consequences ✅

1. **Testability Improved**
   - Can now inject mock services for unit tests
   - No need to patch internal service creation
   - Tests run faster (no real service initialization)

2. **SOLID Compliance**
   - Follows Dependency Inversion Principle
   - High-level modules depend on abstractions
   - Easier to swap implementations

3. **Reduced Coupling**
   - `PatientOnboardingService` no longer knows how to construct dependencies
   - Clear separation of concerns
   - Single Responsibility Principle enforced

4. **Maintainability**
   - Centralized dependency creation in facade/endpoint
   - Easier to change service implementations
   - Clear dependency graph

5. **Consistency**
   - Aligns with other refactored services
   - Standard pattern across codebase

### Negative Consequences ❌

1. **Migration Effort**
   - Must update all instantiation points
   - Tests need to be updated
   - Documentation needs updates

2. **Constructor Verbosity**
   - More parameters in constructor
   - Longer service initialization code

3. **Breaking Changes**
   - Existing code instantiating `PatientOnboardingService` will break
   - Requires coordinated deployment

---

## Validation and Testing

### Test Cases

#### 1. Unit Test - Mock Dependencies

```python
def test_send_welcome_message_with_mocks():
    # Arrange
    mock_message_service = Mock(spec=MessageService)
    mock_whatsapp_service = Mock(spec=UnifiedWhatsAppService)

    onboarding_service = PatientOnboardingService(
        db=mock_db,
        integrity_service=mock_integrity,
        flow_service=mock_flow,
        message_service=mock_message_service,
        whatsapp_service=mock_whatsapp_service,
        saga_orchestrator=None
    )

    # Act
    await onboarding_service._send_welcome_message(patient, None)

    # Assert
    mock_message_service.schedule_message.assert_called_once()
    mock_whatsapp_service.send_message.assert_called_once()
```

#### 2. Integration Test - Real Dependencies

```python
async def test_create_patient_sends_welcome_message(db, doctor_user, patient_data):
    # Real services
    message_service = MessageService(db)
    whatsapp_service = UnifiedWhatsAppService(db=db, messaging_mode=MessagingMode.LEGACY)

    onboarding_service = PatientOnboardingService(
        db=db,
        integrity_service=integrity_service,
        flow_service=flow_service,
        message_service=message_service,
        whatsapp_service=whatsapp_service,
        saga_orchestrator=None
    )

    patient = await onboarding_service.create_patient(patient_data, doctor_user.id)

    # Verify message was sent
    messages = db.query(Message).filter(Message.patient_id == patient.id).all()
    assert len(messages) == 1
    assert messages[0].message_type == MessageType.TEXT
```

### Validation Checklist

- [x] All instantiation points updated
- [x] Constructor signature updated
- [x] Internal service creation removed
- [x] Tests updated with dependency injection
- [ ] Integration tests pass
- [ ] Unit tests pass
- [ ] API endpoints functional
- [ ] No services created internally
- [ ] Documentation updated

---

## Related Decisions

- **P0.2 Patient Service Refactoring** - Overall service layer refactoring
- **ADR-001: Service Layer Architecture** - Service layer patterns
- **ADR-002: Repository Pattern** - Data access patterns

---

## References

1. [SOLID Principles - Dependency Inversion](https://en.wikipedia.org/wiki/Dependency_inversion_principle)
2. [Dependency Injection in Python](https://python-dependency-injector.ets-labs.org/)
3. [Testing with Dependency Injection](https://martinfowler.com/articles/injection.html)
4. [Backend Service Refactoring Plan](../P0.2_PATIENT_SERVICE_REFACTORING.md)

---

## Appendix: Affected Files

### Modified Files

1. `app/services/patient/onboarding_service.py` - Added dependency injection
2. `app/services/patient_service.py` - Updated facade to inject dependencies
3. `app/api/v2/patients_crud.py` - Updated endpoint to create dependencies
4. `tests/integration/test_saga_fallback_race_condition.py` - Updated test fixtures

### Key Changes

| File | Line(s) | Before | After |
|------|---------|--------|-------|
| `onboarding_service.py` | 57-73 | Constructor without services | Constructor with injected services |
| `onboarding_service.py` | 314 | `MessageService(self.db)` | `self.message_service` |
| `onboarding_service.py` | 332 | `UnifiedWhatsAppService(...)` | `self.whatsapp_service` |
| `patient_service.py` | 79-84 | No service injection | Inject message + whatsapp services |
| `patients_crud.py` | 418-457 | Create PatientService only | Create all dependencies first |
| `test_saga_fallback_race_condition.py` | 63-72 | No service injection | Inject all services |

---

**End of ADR-004**
