# Sprint 2: Code Review Criteria & Standards

**Version**: 1.0
**Applies To**: All Sprint 2 implementations (ISSUE-005, ISSUE-006, Test Coverage)
**Enforcement**: MANDATORY for merge approval

---

## Quality Gates (Must Pass ALL)

### Gate 1: Zero Breaking Changes ✅

**Definition**: Public API contracts unchanged

```python
# ❌ BREAKING CHANGE - Method signature changed
# Before
async def create_patient(patient_data: PatientCreate) -> Patient:

# After - REJECTED
async def create_patient(patient_data: PatientCreate, flags: dict) -> Patient:

# ✅ ACCEPTABLE - Backward compatible default
async def create_patient(patient_data: PatientCreate, flags: dict = None) -> Patient:
```

**Validation**:
- Run existing test suite (must pass 100%)
- Compare API signatures with main branch
- Check for removed methods/classes
- Verify no changed return types

### Gate 2: SOLID Principles Compliance ✅

#### Single Responsibility Principle (SRP)

**Rule**: Each class has ONE reason to change

```python
# ❌ VIOLATION - Multiple responsibilities
class PatientService:
    def create_patient(self): pass  # Patient management
    def send_email(self): pass      # Messaging
    def generate_report(self): pass # Reporting

# ✅ COMPLIANT - Single responsibility
class PatientService:
    def create_patient(self): pass
    def update_patient(self): pass
    def delete_patient(self): pass
```

**Validation**:
- Class has <7 public methods
- Class LOC <200 (target) or <500 (max)
- Clear, single-purpose class name
- No mixed concerns (e.g., data + business logic)

#### Open/Closed Principle (OCP)

**Rule**: Open for extension, closed for modification

```python
# ❌ VIOLATION - Must modify to add new notification type
class NotificationService:
    def send(self, type: str, message: str):
        if type == "email":
            # email logic
        elif type == "sms":
            # sms logic
        # Need to modify for new types

# ✅ COMPLIANT - Extend via strategy pattern
class NotificationService:
    def __init__(self, sender: NotificationSender):
        self.sender = sender

    def send(self, message: str):
        return self.sender.send(message)

# Add new types by creating new senders
class EmailSender(NotificationSender): pass
class SMSSender(NotificationSender): pass
```

**Validation**:
- No large if/elif chains for type checking
- Uses inheritance or composition for variants
- New features added via new classes, not modifications

#### Liskov Substitution Principle (LSP)

**Rule**: Derived classes must be substitutable for base

```python
# ❌ VIOLATION - Derived class changes behavior
class BaseOrchestrator:
    async def execute(self, context: dict) -> dict:
        return {"status": "success"}

class BrokenOrchestrator(BaseOrchestrator):
    async def execute(self, context: dict) -> list:  # Changed return type!
        return []

# ✅ COMPLIANT - Maintains contract
class GoodOrchestrator(BaseOrchestrator):
    async def execute(self, context: dict) -> dict:
        result = await super().execute(context)
        result["extra"] = "data"  # Extends, doesn't break
        return result
```

**Validation**:
- Derived methods match base signatures
- No exceptions thrown that base doesn't declare
- Preconditions not strengthened
- Postconditions not weakened

#### Interface Segregation Principle (ISP)

**Rule**: No fat interfaces with unused methods

```python
# ❌ VIOLATION - Forcing implementation of unused methods
class IAnimalActions:
    def walk(self): pass
    def fly(self): pass
    def swim(self): pass

class Dog(IAnimalActions):
    def walk(self): pass
    def fly(self): raise NotImplementedError  # Forced to implement
    def swim(self): pass

# ✅ COMPLIANT - Specific interfaces
class IWalkable:
    def walk(self): pass

class ISwimmable:
    def swim(self): pass

class Dog(IWalkable, ISwimmable):
    def walk(self): pass
    def swim(self): pass
```

**Validation**:
- No NotImplementedError in production code
- Interfaces <5 methods
- Clients depend only on methods they use

#### Dependency Inversion Principle (DIP)

**Rule**: Depend on abstractions, not concretions

```python
# ❌ VIOLATION - Direct dependency on concrete class
class PatientService:
    def __init__(self):
        self.db = PostgreSQLDatabase()  # Concrete!
        self.cache = RedisCache()       # Concrete!

# ✅ COMPLIANT - Dependency injection
class PatientService:
    def __init__(
        self,
        db: DatabaseInterface,      # Abstract
        cache: CacheInterface       # Abstract
    ):
        self.db = db
        self.cache = cache
```

**Validation**:
- All dependencies injected via constructor
- No `from X import ConcreteClass` in services
- Type hints use protocols/ABCs where possible
- Easy to mock for testing

### Gate 3: Test Coverage Targets ✅

**Minimum Coverage**:
- Critical paths: 90%+
- New services: 90%+
- Modified code: 85%+
- Overall: 70%+

**Test Quality** (not just coverage):

```python
# ❌ BAD TEST - Just for coverage
def test_create_patient():
    service.create_patient(data)  # No assertions!

# ✅ GOOD TEST - Meaningful validation
def test_create_patient_success_creates_record_in_database():
    """
    GIVEN valid patient data
    WHEN create_patient is called
    THEN patient record is created in database with correct attributes
    """
    # Arrange
    patient_data = PatientCreate(name="Test", email="test@example.com")

    # Act
    result = service.create_patient(patient_data)

    # Assert
    assert result.id is not None
    assert result.name == "Test"
    assert result.email == "test@example.com"

    # Verify in database
    db_patient = db.query(Patient).filter_by(id=result.id).first()
    assert db_patient is not None
    assert db_patient.status == "active"
```

**Validation**:
- Every test has assertions
- Tests follow AAA pattern (Arrange, Act, Assert)
- Descriptive test names (what/when/then)
- Edge cases covered
- Error paths tested

### Gate 4: Documentation Complete ✅

**Required Documentation**:

1. **Docstrings** (Google style):
```python
def create_patient(
    self,
    patient_data: PatientCreate,
    doctor_id: UUID
) -> Patient:
    """
    Create a new patient in the system.

    Args:
        patient_data: Patient information to create
        doctor_id: UUID of the assigned doctor

    Returns:
        Created Patient instance with assigned ID

    Raises:
        ValidationError: If patient data invalid
        DuplicateError: If patient already exists
        DatabaseError: If creation fails

    Example:
        >>> patient = service.create_patient(
        ...     PatientCreate(name="John Doe"),
        ...     doctor_id=uuid4()
        ... )
        >>> patient.id
        UUID('...')
    """
```

2. **Module-level documentation**:
```python
"""
Patient Onboarding Coordinator.

This module provides the coordination logic for patient onboarding,
orchestrating calls to specialized services for validation, creation,
messaging, and flow initialization.

File: app/domain/patient/onboarding/coordinator.py
LOC: ~100
Responsibility: Orchestrate patient onboarding workflow

Dependencies:
- PatientCreationService: Direct patient creation
- SagaIntegrationService: Saga pattern coordination
- OnboardingNotificationService: Welcome messages
- OnboardingCompletionService: Partial onboarding completion

Example:
    >>> coordinator = OnboardingCoordinator(...)
    >>> patient = await coordinator.create_patient(data, doctor_id)
"""
```

3. **README updates** for major changes
4. **Migration guide** if breaking changes (none allowed!)
5. **API documentation** for new endpoints

**Validation**:
- All public methods have docstrings
- All classes have module docstrings
- Type hints on all parameters/returns
- Raises section documents exceptions
- Examples provided for complex logic

---

## Architecture-Specific Criteria

### ISSUE-005: OnboardingService Refactoring

#### Target Architecture Compliance

**Expected Structure**:
```
app/domain/patient/onboarding/
├── __init__.py               (exports)
├── coordinator.py            (100 LOC) ✅
├── creation_service.py       (150 LOC) ✅
├── saga_integration_service.py (120 LOC) ✅
├── notification_service.py   (100 LOC) ✅
├── completion_service.py     (120 LOC) ✅
└── executor_manager.py       (50 LOC) ✅
```

**Validation Checklist**:
- [ ] All 6 services created
- [ ] LOC targets met (±20%)
- [ ] `OnboardingCoordinator` orchestrates (no business logic)
- [ ] Each service has single responsibility
- [ ] Backward compatibility wrapper exists
- [ ] All services use dependency injection

#### Service Responsibility Matrix

| Service | Responsibility | LOC | Dependencies |
|---------|---------------|-----|--------------|
| **OnboardingCoordinator** | Orchestrate workflow | ~100 | All 4 services below |
| **PatientCreationService** | Database operations | ~150 | ExecutorManager, IntegrityService |
| **SagaIntegrationService** | Saga pattern | ~120 | SagaOrchestrator, ExecutorManager |
| **OnboardingNotificationService** | Welcome messages | ~100 | MessageService, WhatsAppService |
| **OnboardingCompletionService** | Partial completion | ~120 | CreationService, NotificationService |
| **ExecutorManager** | Async/sync bridge | ~50 | ThreadPoolExecutor |

**Review Focus**:
- Each service stays within LOC budget
- No overlap in responsibilities
- Clear interfaces between services
- No circular dependencies

### ISSUE-006: Orchestrator Consolidation

#### Base Class Design Compliance

**Expected Hierarchy**:
```python
BaseOrchestrator (Abstract, 180 LOC)
├── Provides: db, logging, health_check, metrics
├── Abstract: execute(), validate()

ResilientOrchestrator (Mixin, 220 LOC)
├── Provides: circuit_breakers, retry_logic, fallback
├── Uses: BaseOrchestrator.logger

StateAwareOrchestrator (Mixin, 150 LOC)
├── Provides: state_persistence, transitions, cache
├── Uses: BaseOrchestrator.db
```

**Validation Checklist**:
- [ ] BaseOrchestrator is abstract
- [ ] Mixins don't have circular dependencies
- [ ] Inheritance depth ≤3 levels
- [ ] Method Resolution Order (MRO) clear
- [ ] super() calls correct

#### Code Reduction Targets

| Orchestrator | Before | After | Target Reduction |
|--------------|--------|-------|------------------|
| FlowOrchestrator | 218 LOC | ~120 LOC | 45% |
| SagaOrchestrator | 1,967 LOC | ~1,200 LOC | 40% |
| **Overall** | **2,185 LOC** | **~1,320 LOC** | **40%+** |

**Review Focus**:
- Duplicate code eliminated
- Common patterns extracted to base
- No feature loss
- Performance maintained

---

## Automated Validation Tools

### Pre-Commit Hooks

```bash
# Run before every commit
pytest tests/ --cov=app --cov-fail-under=70
mypy app/ --strict
flake8 app/ --max-line-length=100
bandit -r app/ -ll
```

### CI/CD Pipeline

```yaml
- name: Quality Gates
  run: |
    # Test coverage
    pytest --cov=app --cov-report=xml --cov-fail-under=70

    # Type checking
    mypy app/ --strict --no-error-summary 2>&1 | tee mypy_errors.txt
    if [ -s mypy_errors.txt ]; then exit 1; fi

    # Linting
    flake8 app/ --count --max-line-length=100 --statistics

    # Security
    bandit -r app/ -f json -o bandit_report.json

    # Complexity
    radon cc app/ -a -nb --total-average

    # Breaking changes detection
    python scripts/detect_breaking_changes.py
```

### Manual Review Checklist

**For Every Pull Request**:

1. **Code Review** (30 min per PR)
   - [ ] Read full diff
   - [ ] Check SOLID principles
   - [ ] Verify dependency injection
   - [ ] Validate error handling
   - [ ] Check resource cleanup

2. **Test Review** (20 min per PR)
   - [ ] Coverage report analysis
   - [ ] Test quality inspection
   - [ ] Edge case verification
   - [ ] Mock usage appropriate
   - [ ] No flaky tests

3. **Architecture Review** (15 min per PR)
   - [ ] Matches design document
   - [ ] LOC targets met
   - [ ] No god classes
   - [ ] Dependencies acceptable
   - [ ] Performance considerations

4. **Documentation Review** (10 min per PR)
   - [ ] Docstrings complete
   - [ ] README updated
   - [ ] Migration guide (if needed)
   - [ ] Changelog entry

**Total Review Time**: ~75 minutes per major PR

---

## Scoring Rubric

### Overall Quality Score Calculation

```python
def calculate_quality_score(pr):
    scores = {
        "code_quality": score_code_quality(pr),      # 0-100
        "breaking_changes": score_breaking_changes(pr),  # 0-100
        "test_quality": score_test_quality(pr),      # 0-100
        "architecture": score_architecture(pr)       # 0-100
    }

    weights = {
        "code_quality": 0.30,
        "breaking_changes": 0.25,
        "test_quality": 0.25,
        "architecture": 0.20
    }

    total = sum(scores[k] * weights[k] for k in scores)

    # Breaking changes veto
    if scores["breaking_changes"] < 100:
        total = min(total, 79)  # Cap at NEEDS_WORK

    return round(total, 1)
```

### Score Interpretation

| Range | Status | Action |
|-------|--------|--------|
| 90-100 | ✅ **APPROVED** | Merge immediately |
| 80-89 | ✅ **APPROVED (Notes)** | Merge with minor fixes |
| 70-79 | ⚠️ **NEEDS_WORK** | Revise and resubmit |
| <70 | 🚫 **BLOCKED** | Major issues, reject |

### Breaking Changes Override

**ANY breaking change** = Automatic 🚫 **BLOCKED** status

Exception: If architectural approval obtained AND migration guide complete

---

## Review Templates

### Template: Service Review

```markdown
# Code Review: [ServiceName]

**File**: app/domain/[domain]/[service].py
**LOC**: [actual] (Target: [target])
**Reviewer**: Code Review Agent
**Date**: [YYYY-MM-DD]

## Quality Score: [score]/100 ([status])

### Breakdown
- Code Quality: [score]/100 ([weight])
- Breaking Changes: [score]/100 ([weight])
- Test Quality: [score]/100 ([weight])
- Architecture: [score]/100 ([weight])

## SOLID Compliance

**Single Responsibility**: ✅/⚠️/❌
- [Comments]

**Open/Closed**: ✅/⚠️/❌
- [Comments]

**Liskov Substitution**: ✅/⚠️/❌
- [Comments]

**Interface Segregation**: ✅/⚠️/❌
- [Comments]

**Dependency Inversion**: ✅/⚠️/❌
- [Comments]

## Issues Found

### BLOCKER (P0): [count]
1. [Description]
   - File: [path]:[line]
   - Fix: [recommendation]

### CRITICAL (P1): [count]
1. [Description]

### MAJOR (P2): [count]
1. [Description]

### MINOR (P3): [count]
1. [Description]

## Test Coverage

- Unit Tests: [count] tests, [coverage]%
- Integration Tests: [count] tests
- Edge Cases: [covered/total]

**Quality**: ✅/⚠️/❌
- [Comments on test meaningfulness]

## Architecture Validation

**Matches Design**: ✅/⚠️/❌
**LOC Target Met**: ✅/⚠️/❌
**Dependencies Acceptable**: ✅/⚠️/❌

## Recommendations

1. [Recommendation]
2. [Recommendation]

## Approval Status

**Status**: APPROVED / NEEDS_WORK / BLOCKED
**Next Steps**: [action items]
```

---

## Review Sign-Off

Every implementation MUST have:

1. ✅ Automated checks passing (CI/CD green)
2. ✅ Manual review complete (this document)
3. ✅ Quality score ≥80
4. ✅ Zero breaking changes
5. ✅ Documentation complete
6. ✅ Approved by 2 reviewers (code review agent + senior dev)

**Final Approval Required From**:
- Code Review Agent (this system)
- Senior Backend Developer
- (For major changes) Architecture Lead

---

**This document is the source of truth for Sprint 2 code review standards.**
