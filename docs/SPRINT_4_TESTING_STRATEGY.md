# Sprint 4 - Testing Strategy for 90% Coverage
## Sistema Hormonia (Clínica Oncológica V02)

**Version**: 1.0  
**Last Updated**: Janeiro 2025  
**Goal**: Expand test coverage from ~70% to 90%+

---

## 📋 Table of Contents

1. [Current State](#current-state)
2. [Target Coverage](#target-coverage)
3. [Testing Pyramid](#testing-pyramid)
4. [Backend Testing Strategy](#backend-testing-strategy)
5. [Frontend Testing Strategy](#frontend-testing-strategy)
6. [Coverage Tools & CI](#coverage-tools--ci)
7. [Best Practices](#best-practices)
8. [Implementation Plan](#implementation-plan)

---

## 📊 Current State

### Backend Coverage (Python)

```
Current: ~70%
Target:  90%+

Breakdown:
├── Services:      65% → Target: 95%
├── Repositories:  75% → Target: 95%
├── API Routes:    80% → Target: 90%
├── Utils:         60% → Target: 95%
├── Models:        85% → Target: 90%
└── Schemas:       90% → Target: 95%
```

**Gaps Identified**:
- ❌ `patient_service.py` - apenas 65% (faltam edge cases)
- ❌ `quiz_service.py` - apenas 60% (faltam validações)
- ❌ `analytics_service.py` - apenas 50% (queries complexas não testadas)
- ❌ `utils/validators.py` - apenas 55% (faltam testes de regex)
- ❌ `utils/encryption.py` - apenas 70% (faltam testes de falhas)

### Frontend Coverage (TypeScript/React)

```
Current: ~65%
Target:  90%+

Breakdown:
├── Components:    60% → Target: 85%
├── Hooks:         55% → Target: 95%
├── Utils:         70% → Target: 95%
├── API Client:    80% → Target: 90%
├── Services:      65% → Target: 90%
└── Store:         75% → Target: 90%
```

**Gaps Identified**:
- ❌ Custom hooks (`usePatients`, `useAuth`, `useQuiz`) - 55%
- ❌ Complex components (`Dashboard`, `PatientList`) - 60%
- ❌ Form validation logic - 50%
- ❌ Error boundaries - 40%
- ❌ Utils (`formatters`, `validators`) - 70%

---

## 🎯 Target Coverage

### Quality Over Quantity

**90% coverage ≠ 90% quality**

Focus on:
- ✅ Business logic (services, repositories)
- ✅ Complex algorithms (validators, calculators)
- ✅ Edge cases and error handling
- ✅ Critical user flows (authentication, quiz submission)

**NOT just**:
- ❌ Trivial getters/setters
- ❌ Configuration files
- ❌ Type definitions
- ❌ Simple pass-through functions

### Coverage Thresholds

```yaml
# Backend (pytest-cov)
coverage_thresholds:
  total: 90%
  services/: 95%
  repositories/: 95%
  api/: 90%
  utils/: 95%
  models/: 90%

# Frontend (vitest)
coverage_thresholds:
  total: 90%
  hooks/: 95%
  components/: 85%
  utils/: 95%
  services/: 90%
```

---

## 🏗️ Testing Pyramid

```
         /\
        /E2E\          10% - End-to-End (Playwright)
       /------\
      /  Int   \       20% - Integration (API, DB)
     /----------\
    /    Unit    \     70% - Unit (Services, Utils, Hooks)
   /--------------\
```

### Distribution

- **70% Unit Tests** - Fast, isolated, granular
- **20% Integration Tests** - API + DB, realistic scenarios
- **10% E2E Tests** - Full user flows, CI-only

---

## 🐍 Backend Testing Strategy

### 1. Service Layer Tests

**File**: `tests/services/test_patient_service.py`

```python
"""
Test suite for PatientService.
Target: 95% coverage.
"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.services.patient_service import PatientService
from app.repositories.patient_repository import PatientRepository
from app.schemas.patient import PatientCreate, PatientUpdate
from app.models import Patient, Doctor
from app.exceptions import ValidationError, NotFoundError

# Fixtures
@pytest.fixture
def patient_service(db_session: Session):
    """Create PatientService instance with repository."""
    repository = PatientRepository(db_session)
    return PatientService(db_session, repository)

@pytest.fixture
def doctor(db_session: Session):
    """Create a test doctor."""
    doctor = Doctor(
        id=uuid4(),
        name="Dr. Silva",
        crm="12345-SP",
        email="silva@example.com"
    )
    db_session.add(doctor)
    db_session.commit()
    return doctor

@pytest.fixture
def patient_data():
    """Valid patient creation data."""
    return PatientCreate(
        name="João Silva",
        email="joao@example.com",
        phone="+5511999999999",
        cpf="12345678901",
        birth_date=datetime(1980, 1, 1)
    )

# Happy Path Tests
def test_create_patient_success(patient_service, doctor, patient_data):
    """
    Test successful patient creation.
    
    Arrange: Valid patient data
    Act: Create patient
    Assert: Patient created with correct data
    """
    # Act
    patient = patient_service.create(patient_data, doctor_id=doctor.id)
    
    # Assert
    assert patient.id is not None
    assert patient.name == "João Silva"
    assert patient.email == "joao@example.com"
    assert patient.doctor_id == doctor.id
    assert patient.status == "active"
    assert patient.created_at is not None

def test_get_patient_by_id_success(patient_service, doctor, patient_data):
    """Test retrieving patient by ID."""
    # Arrange
    created = patient_service.create(patient_data, doctor_id=doctor.id)
    
    # Act
    patient = patient_service.get_by_id(created.id)
    
    # Assert
    assert patient is not None
    assert patient.id == created.id
    assert patient.name == created.name

def test_list_patients_with_pagination(patient_service, doctor):
    """Test patient listing with pagination."""
    # Arrange - Create 50 patients
    for i in range(50):
        data = PatientCreate(
            name=f"Patient {i}",
            email=f"patient{i}@example.com",
            phone="+5511999999999",
            cpf=f"{i:011d}",
            birth_date=datetime(1980, 1, 1)
        )
        patient_service.create(data, doctor_id=doctor.id)
    
    # Act - Page 1
    patients, total = patient_service.list_paginated(page=1, size=20)
    
    # Assert
    assert len(patients) == 20
    assert total == 50

def test_update_patient_success(patient_service, doctor, patient_data):
    """Test patient update."""
    # Arrange
    patient = patient_service.create(patient_data, doctor_id=doctor.id)
    update_data = PatientUpdate(name="João Silva Updated")
    
    # Act
    updated = patient_service.update(patient.id, update_data)
    
    # Assert
    assert updated.name == "João Silva Updated"
    assert updated.email == patient_data.email  # Unchanged

def test_delete_patient_success(patient_service, doctor, patient_data):
    """Test patient deletion (soft delete)."""
    # Arrange
    patient = patient_service.create(patient_data, doctor_id=doctor.id)
    
    # Act
    patient_service.delete(patient.id)
    
    # Assert
    deleted = patient_service.get_by_id(patient.id)
    assert deleted.status == "deleted"
    assert deleted.deleted_at is not None

# Edge Cases & Error Handling
def test_create_patient_duplicate_email(patient_service, doctor, patient_data):
    """
    Test creating patient with duplicate email.
    
    Expected: ValidationError
    """
    # Arrange
    patient_service.create(patient_data, doctor_id=doctor.id)
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        patient_service.create(patient_data, doctor_id=doctor.id)
    
    assert "email already exists" in str(exc_info.value).lower()

def test_create_patient_invalid_cpf(patient_service, doctor):
    """Test creating patient with invalid CPF."""
    # Arrange
    invalid_data = PatientCreate(
        name="João Silva",
        email="joao@example.com",
        phone="+5511999999999",
        cpf="00000000000",  # Invalid CPF
        birth_date=datetime(1980, 1, 1)
    )
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        patient_service.create(invalid_data, doctor_id=doctor.id)
    
    assert "invalid cpf" in str(exc_info.value).lower()

def test_create_patient_invalid_phone(patient_service, doctor):
    """Test creating patient with invalid phone."""
    # Arrange
    invalid_data = PatientCreate(
        name="João Silva",
        email="joao@example.com",
        phone="123",  # Too short
        cpf="12345678901",
        birth_date=datetime(1980, 1, 1)
    )
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        patient_service.create(invalid_data, doctor_id=doctor.id)
    
    assert "invalid phone" in str(exc_info.value).lower()

def test_create_patient_future_birth_date(patient_service, doctor):
    """Test creating patient with future birth date."""
    # Arrange
    future_date = datetime.now() + timedelta(days=1)
    invalid_data = PatientCreate(
        name="João Silva",
        email="joao@example.com",
        phone="+5511999999999",
        cpf="12345678901",
        birth_date=future_date
    )
    
    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        patient_service.create(invalid_data, doctor_id=doctor.id)
    
    assert "birth date cannot be in the future" in str(exc_info.value).lower()

def test_get_patient_not_found(patient_service):
    """Test retrieving non-existent patient."""
    # Act & Assert
    with pytest.raises(NotFoundError):
        patient_service.get_by_id(uuid4())

def test_update_patient_not_found(patient_service):
    """Test updating non-existent patient."""
    # Arrange
    update_data = PatientUpdate(name="Updated")
    
    # Act & Assert
    with pytest.raises(NotFoundError):
        patient_service.update(uuid4(), update_data)

def test_delete_patient_not_found(patient_service):
    """Test deleting non-existent patient."""
    # Act & Assert
    with pytest.raises(NotFoundError):
        patient_service.delete(uuid4())

# Complex Scenarios
def test_patient_with_multiple_quizzes(patient_service, doctor, patient_data, db_session):
    """Test patient with relationship to multiple quizzes."""
    # Arrange
    patient = patient_service.create(patient_data, doctor_id=doctor.id)
    
    # Create quizzes (simplified)
    from app.models import Quiz, QuizResponse
    quiz1 = Quiz(id=uuid4(), title="Quiz 1", month=1, year=2025)
    quiz2 = Quiz(id=uuid4(), title="Quiz 2", month=2, year=2025)
    db_session.add_all([quiz1, quiz2])
    db_session.commit()
    
    response1 = QuizResponse(id=uuid4(), patient_id=patient.id, quiz_id=quiz1.id)
    response2 = QuizResponse(id=uuid4(), patient_id=patient.id, quiz_id=quiz2.id)
    db_session.add_all([response1, response2])
    db_session.commit()
    
    # Act
    patient_with_quizzes = patient_service.get_by_id(patient.id, include_quizzes=True)
    
    # Assert
    assert len(patient_with_quizzes.quiz_responses) == 2

def test_bulk_patient_creation(patient_service, doctor):
    """Test bulk patient creation with transaction rollback on error."""
    # Arrange
    patients_data = [
        PatientCreate(
            name=f"Patient {i}",
            email=f"patient{i}@example.com",
            phone="+5511999999999",
            cpf=f"{i:011d}",
            birth_date=datetime(1980, 1, 1)
        )
        for i in range(10)
    ]
    
    # Add one invalid patient (duplicate email)
    patients_data.append(patients_data[0])
    
    # Act & Assert
    with pytest.raises(ValidationError):
        patient_service.bulk_create(patients_data, doctor_id=doctor.id)
    
    # Assert - No patients created (transaction rolled back)
    total = patient_service.count()
    assert total == 0

# Performance Tests
@pytest.mark.slow
def test_list_patients_performance_large_dataset(patient_service, doctor, benchmark):
    """Test pagination performance with 10k+ patients."""
    # Arrange - Create 10,000 patients
    for i in range(10000):
        data = PatientCreate(
            name=f"Patient {i}",
            email=f"patient{i}@example.com",
            phone="+5511999999999",
            cpf=f"{i:011d}",
            birth_date=datetime(1980, 1, 1)
        )
        patient_service.create(data, doctor_id=doctor.id)
    
    # Act & Assert - Should complete in < 100ms
    result = benchmark(lambda: patient_service.list_paginated(page=1, size=100))
    patients, total = result
    
    assert len(patients) == 100
    assert total == 10000
```

### 2. Repository Layer Tests

**File**: `tests/repositories/test_patient_repository.py`

```python
"""
Test suite for PatientRepository.
Target: 95% coverage.
"""
import pytest
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Session

from app.repositories.patient_repository import PatientRepository
from app.models import Patient, Doctor

@pytest.fixture
def repository(db_session: Session):
    """Create repository instance."""
    return PatientRepository(db_session)

@pytest.fixture
def doctor(db_session: Session):
    """Create test doctor."""
    doctor = Doctor(id=uuid4(), name="Dr. Test", crm="12345-SP", email="test@example.com")
    db_session.add(doctor)
    db_session.commit()
    return doctor

# CRUD Tests
def test_create_patient(repository, doctor):
    """Test creating a patient."""
    # Arrange
    patient_dict = {
        "name": "Test Patient",
        "email": "test@example.com",
        "phone": "+5511999999999",
        "cpf": "12345678901",
        "doctor_id": doctor.id,
        "birth_date": datetime(1980, 1, 1)
    }
    
    # Act
    patient = repository.create(patient_dict)
    
    # Assert
    assert patient.id is not None
    assert patient.name == "Test Patient"

def test_find_by_id(repository, doctor):
    """Test finding patient by ID."""
    # Arrange
    patient = Patient(
        id=uuid4(),
        name="Test",
        email="test@example.com",
        doctor_id=doctor.id
    )
    repository.db.add(patient)
    repository.db.commit()
    
    # Act
    found = repository.find_by_id(patient.id)
    
    # Assert
    assert found is not None
    assert found.id == patient.id

def test_find_by_email(repository, doctor):
    """Test finding patient by email."""
    # Arrange
    patient = Patient(
        id=uuid4(),
        name="Test",
        email="unique@example.com",
        doctor_id=doctor.id
    )
    repository.db.add(patient)
    repository.db.commit()
    
    # Act
    found = repository.find_by_email("unique@example.com")
    
    # Assert
    assert found is not None
    assert found.email == "unique@example.com"

def test_list_paginated(repository, doctor):
    """Test paginated listing."""
    # Arrange - Create 30 patients
    for i in range(30):
        patient = Patient(
            id=uuid4(),
            name=f"Patient {i}",
            email=f"patient{i}@example.com",
            doctor_id=doctor.id
        )
        repository.db.add(patient)
    repository.db.commit()
    
    # Act
    patients, total = repository.list_paginated(page=1, size=10)
    
    # Assert
    assert len(patients) == 10
    assert total == 30

def test_update_patient(repository, doctor):
    """Test updating a patient."""
    # Arrange
    patient = Patient(
        id=uuid4(),
        name="Original",
        email="test@example.com",
        doctor_id=doctor.id
    )
    repository.db.add(patient)
    repository.db.commit()
    
    # Act
    repository.update(patient.id, {"name": "Updated"})
    
    # Assert
    updated = repository.find_by_id(patient.id)
    assert updated.name == "Updated"

def test_delete_patient_soft_delete(repository, doctor):
    """Test soft delete."""
    # Arrange
    patient = Patient(
        id=uuid4(),
        name="Test",
        email="test@example.com",
        doctor_id=doctor.id
    )
    repository.db.add(patient)
    repository.db.commit()
    
    # Act
    repository.soft_delete(patient.id)
    
    # Assert
    deleted = repository.find_by_id(patient.id)
    assert deleted.status == "deleted"
    assert deleted.deleted_at is not None

# Query Tests
def test_filter_by_status(repository, doctor):
    """Test filtering by status."""
    # Arrange
    active = Patient(id=uuid4(), name="Active", email="active@example.com", doctor_id=doctor.id, status="active")
    inactive = Patient(id=uuid4(), name="Inactive", email="inactive@example.com", doctor_id=doctor.id, status="inactive")
    repository.db.add_all([active, inactive])
    repository.db.commit()
    
    # Act
    actives = repository.filter_by_status("active")
    
    # Assert
    assert len(actives) == 1
    assert actives[0].status == "active"

def test_search_by_name(repository, doctor):
    """Test full-text search by name."""
    # Arrange
    patient1 = Patient(id=uuid4(), name="João Silva", email="joao@example.com", doctor_id=doctor.id)
    patient2 = Patient(id=uuid4(), name="Maria Santos", email="maria@example.com", doctor_id=doctor.id)
    repository.db.add_all([patient1, patient2])
    repository.db.commit()
    
    # Act
    results = repository.search("Silva")
    
    # Assert
    assert len(results) == 1
    assert results[0].name == "João Silva"

def test_count_by_doctor(repository, doctor):
    """Test counting patients by doctor."""
    # Arrange
    for i in range(5):
        patient = Patient(
            id=uuid4(),
            name=f"Patient {i}",
            email=f"patient{i}@example.com",
            doctor_id=doctor.id
        )
        repository.db.add(patient)
    repository.db.commit()
    
    # Act
    count = repository.count_by_doctor(doctor.id)
    
    # Assert
    assert count == 5
```

### 3. Utils Tests

**File**: `tests/utils/test_validators.py`

```python
"""
Test suite for validation utilities.
Target: 95% coverage.
"""
import pytest
from app.utils.validators import (
    validate_cpf,
    validate_phone,
    validate_email,
    validate_password_strength,
    sanitize_html
)

# CPF Validation
def test_validate_cpf_valid():
    """Test valid CPF."""
    assert validate_cpf("12345678909") is True
    assert validate_cpf("123.456.789-09") is True  # With formatting

def test_validate_cpf_invalid_format():
    """Test invalid CPF format."""
    assert validate_cpf("123") is False
    assert validate_cpf("abc12345678") is False

def test_validate_cpf_invalid_checksum():
    """Test CPF with invalid checksum."""
    assert validate_cpf("12345678900") is False

def test_validate_cpf_all_same_digits():
    """Test CPF with all same digits (invalid)."""
    assert validate_cpf("11111111111") is False
    assert validate_cpf("00000000000") is False

# Phone Validation
def test_validate_phone_brazilian_mobile():
    """Test valid Brazilian mobile phone."""
    assert validate_phone("+5511999999999") is True
    assert validate_phone("11999999999") is True
    assert validate_phone("(11) 99999-9999") is True

def test_validate_phone_invalid():
    """Test invalid phone numbers."""
    assert validate_phone("123") is False
    assert validate_phone("abcdefghijk") is False

# Email Validation
def test_validate_email_valid():
    """Test valid email addresses."""
    assert validate_email("user@example.com") is True
    assert validate_email("user+tag@example.co.uk") is True

def test_validate_email_invalid():
    """Test invalid email addresses."""
    assert validate_email("invalid") is False
    assert validate_email("@example.com") is False
    assert validate_email("user@") is False

# Password Strength
def test_validate_password_strong():
    """Test strong password."""
    result = validate_password_strength("StrongPass123!")
    assert result["is_valid"] is True
    assert result["strength"] == "strong"

def test_validate_password_weak():
    """Test weak password."""
    result = validate_password_strength("weak")
    assert result["is_valid"] is False
    assert "too short" in result["errors"]

def test_validate_password_no_numbers():
    """Test password without numbers."""
    result = validate_password_strength("NoNumbers!")
    assert result["is_valid"] is False
    assert "must contain at least one digit" in result["errors"]

# HTML Sanitization
def test_sanitize_html_removes_scripts():
    """Test that script tags are removed."""
    dirty = "<p>Hello</p><script>alert('xss')</script>"
    clean = sanitize_html(dirty)
    assert "<script>" not in clean
    assert "<p>Hello</p>" in clean

def test_sanitize_html_preserves_safe_tags():
    """Test that safe tags are preserved."""
    html = "<p><strong>Bold</strong> and <em>italic</em></p>"
    clean = sanitize_html(html)
    assert clean == html
```

---

## ⚛️ Frontend Testing Strategy

### 1. Custom Hooks Tests

**File**: `src/__tests__/hooks/usePatients.test.tsx`

```typescript
/**
 * Test suite for usePatients hook.
 * Target: 95% coverage.
 */
import { renderHook, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { usePatients } from '@/hooks/usePatients'
import { apiClient } from '@/lib/api-client'

// Mock API client
vi.mock('@/lib/api-client')

// Test wrapper with React Query
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}

describe('usePatients', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // Happy Path
  it('should fetch patients successfully', async () => {
    // Arrange
    const mockPatients = [
      { id: '1', name: 'Patient 1', email: 'p1@example.com' },
      { id: '2', name: 'Patient 2', email: 'p2@example.com' },
    ]
    vi.mocked(apiClient.patients.list).mockResolvedValue({
      data: mockPatients,
      meta: { total: 2 },
    })

    // Act
    const { result } = renderHook(() => usePatients(), {
      wrapper: createWrapper(),
    })

    // Assert - Loading state
    expect(result.current.isLoading).toBe(true)

    // Assert - Success state
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })
    expect(result.current.data).toEqual(mockPatients)
    expect(result.current.isError).toBe(false)
  })

  // Error Handling
  it('should handle fetch error', async () => {
    // Arrange
    const error = new Error('Network error')
    vi.mocked(apiClient.patients.list).mockRejectedValue(error)

    // Act
    const { result } = renderHook(() => usePatients(), {
      wrapper: createWrapper(),
    })

    // Assert
    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })
    expect(result.current.error).toEqual(error)
    expect(result.current.data).toBeUndefined()
  })

  // Pagination
  it('should handle pagination', async () => {
    // Arrange
    const page1 = [{ id: '1', name: 'Patient 1' }]
    const page2 = [{ id: '2', name: 'Patient 2' }]
    
    vi.mocked(apiClient.patients.list)
      .mockResolvedValueOnce({ data: page1, meta: { total: 2 } })
      .mockResolvedValueOnce({ data: page2, meta: { total: 2 } })

    // Act
    const { result } = renderHook(() => usePatients({ page: 1 }), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.data).toEqual(page1))

    // Change page
    const { result: result2 } = renderHook(() => usePatients({ page: 2 }), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result2.current.data).toEqual(page2))
  })

  // Filtering
  it('should filter patients by status', async () => {
    // Arrange
    const activePatients = [{ id: '1', name: 'Active', status: 'active' }]
    vi.mocked(apiClient.patients.list).mockResolvedValue({
      data: activePatients,
      meta: { total: 1 },
    })

    // Act
    const { result } = renderHook(
      () => usePatients({ filters: { status: 'active' } }),
      { wrapper: createWrapper() }
    )

    // Assert
    await waitFor(() => {
      expect(result.current.data).toEqual(activePatients)
    })
    expect(apiClient.patients.list).toHaveBeenCalledWith({
      filters: { status: 'active' },
    })
  })

  // Mutation - Create Patient
  it('should create patient successfully', async () => {
    // Arrange
    const newPatient = { name: 'New Patient', email: 'new@example.com' }
    const createdPatient = { id: '3', ...newPatient }
    vi.mocked(apiClient.patients.create).mockResolvedValue(createdPatient)

    // Act
    const { result } = renderHook(() => usePatients(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    result.current.createPatient(newPatient)

    // Assert
    await waitFor(() => {
      expect(apiClient.patients.create).toHaveBeenCalledWith(newPatient)
    })
  })

  // Optimistic Update
  it('should handle optimistic update', async () => {
    // Arrange
    const patients = [{ id: '1', name: 'Old Name' }]
    vi.mocked(apiClient.patients.list).mockResolvedValue({
      data: patients,
      meta: { total: 1 },
    })
    vi.mocked(apiClient.patients.update).mockResolvedValue({
      id: '1',
      name: 'New Name',
    })

    // Act
    const { result } = renderHook(() => usePatients(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.data).toEqual(patients))

    // Optimistic update
    result.current.updatePatient('1', { name: 'New Name' })

    // Assert - Immediately shows new name (optimistic)
    expect(result.current.data[0].name).toBe('New Name')

    // Assert - Server confirms
    await waitFor(() => {
      expect(apiClient.patients.update).toHaveBeenCalled()
    })
  })
})
```

### 2. Component Tests

**File**: `src/__tests__/components/PatientList.test.tsx`

```typescript
/**
 * Test suite for PatientList component.
 * Target: 85% coverage.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { PatientList } from '@/components/PatientList'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const mockPatients = [
  { id: '1', name: 'João Silva', email: 'joao@example.com', status: 'active' },
  { id: '2', name: 'Maria Santos', email: 'maria@example.com', status: 'inactive' },
]

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return ({ children }: { children: React.ReactNode }) => (