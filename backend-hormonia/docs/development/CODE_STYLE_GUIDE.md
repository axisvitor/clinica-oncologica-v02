# Code Style Guide - Python Backend (PEP 8)

> **Status:** Active | **Last Updated:** 2025-11-16 | **Priority:** P0
> **Related Issues:** LOW-008 (Naming Conventions)

## Table of Contents
1. [Naming Conventions](#naming-conventions)
2. [Code Layout](#code-layout)
3. [Type Hints](#type-hints)
4. [Documentation](#documentation)
5. [Import Organization](#import-organization)
6. [Error Handling](#error-handling)
7. [Testing Standards](#testing-standards)
8. [Pre-commit Enforcement](#pre-commit-enforcement)

---

## Naming Conventions

### Functions and Variables: `snake_case`

**✓ CORRECT:**
```python
def calculate_patient_risk_score(patient_id: int) -> float:
    """Calculate risk score for a patient."""
    user_session = get_user_session()
    total_score = 0.0
    return total_score

# Variables
patient_data = get_patient_data()
risk_assessment_result = calculate_risk()
```

**✗ INCORRECT:**
```python
def CalculatePatientRiskScore(patientId):  # Should be snake_case
    userSession = getUserSession()  # Should be snake_case
    totalScore = 0.0  # Should be snake_case
    return totalScore
```

### Classes: `PascalCase`

**✓ CORRECT:**
```python
class PatientService:
    """Service for managing patient data."""
    pass

class QuizResponseHandler:
    """Handler for quiz response processing."""
    pass

class FlowOrchestrator:
    """Orchestrates patient care flows."""
    pass
```

**✗ INCORRECT:**
```python
class patient_service:  # Should be PascalCase
    pass

class quiz_response_handler:  # Should be PascalCase
    pass
```

### Constants: `UPPER_SNAKE_CASE`

**✓ CORRECT:**
```python
MAX_RETRY_ATTEMPTS = 3
DEFAULT_TIMEOUT = 30
API_VERSION = "v2"
REDIS_KEY_PREFIX = "clinic:"

# Enums are also constants
class UserRole(str, Enum):
    ADMIN = "admin"
    PHYSICIAN = "physician"
    PATIENT = "patient"
```

**✗ INCORRECT:**
```python
maxRetryAttempts = 3  # Should be UPPER_SNAKE_CASE
default_timeout = 30  # Should be UPPER_SNAKE_CASE
ApiVersion = "v2"  # Should be UPPER_SNAKE_CASE
```

### Private/Protected Members: Leading underscore `_`

**✓ CORRECT:**
```python
class DatabaseClient:
    def __init__(self):
        self._connection = None  # Protected
        self.__secret_key = "..."  # Private

    def _internal_helper(self):  # Protected method
        pass

    def __private_method(self):  # Private method (name mangled)
        pass
```

### Module-Level "Private" Functions: Leading underscore `_`

**✓ CORRECT:**
```python
def _validate_input(data: dict) -> bool:
    """Internal validation helper."""
    pass

def process_public_api(data: dict):
    """Public API function."""
    if not _validate_input(data):
        raise ValueError("Invalid data")
```

---

## Code Layout

### Line Length: 120 characters (Black default)

**✓ CORRECT:**
```python
def create_patient_with_full_medical_history(
    patient_data: dict,
    medical_history: List[dict],
    insurance_info: dict
) -> Patient:
    """Create patient with complete data."""
    pass
```

### Indentation: 4 spaces (no tabs)

**✓ CORRECT:**
```python
def example():
    if condition:
        for item in items:
            process(item)
```

### Blank Lines
- **2 blank lines** between top-level functions/classes
- **1 blank line** between methods in a class
- **1 blank line** to separate logical sections

**✓ CORRECT:**
```python
class PatientService:
    """Patient management service."""

    def __init__(self, db: Database):
        self.db = db

    def create_patient(self, data: dict) -> Patient:
        """Create a new patient."""
        # Validate data
        validated_data = self._validate(data)

        # Create patient
        patient = Patient(**validated_data)
        return patient

    def _validate(self, data: dict) -> dict:
        """Internal validation."""
        return data


class QuizService:
    """Quiz management service."""
    pass
```

---

## Type Hints

### Required for All Public Functions (Target: 95% coverage)

**✓ CORRECT:**
```python
from typing import Optional, List, Dict, Any

def get_patient(patient_id: int) -> Optional[Patient]:
    """Retrieve patient by ID."""
    pass

def process_quiz_responses(
    responses: List[Dict[str, Any]],
    session_id: str
) -> Dict[str, float]:
    """Process quiz responses and return scores."""
    pass

# Use TypedDict for structured dicts
from typing import TypedDict

class PatientData(TypedDict):
    name: str
    age: int
    email: str

def create_patient(data: PatientData) -> Patient:
    pass
```

**✗ INCORRECT:**
```python
def get_patient(patient_id):  # Missing type hints
    pass

def process_quiz_responses(responses, session_id):  # Missing type hints
    pass
```

### Type Hints for Class Attributes

**✓ CORRECT:**
```python
from typing import ClassVar

class Config:
    """Configuration class."""
    API_VERSION: ClassVar[str] = "v2"
    timeout: int = 30
    redis_client: Optional[Redis] = None

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
```

---

## Documentation

### Docstrings Required
- **All public modules, classes, functions**
- Use Google-style or NumPy-style docstrings
- Target: 80% docstring coverage

**✓ CORRECT:**
```python
def calculate_risk_score(
    patient_id: int,
    assessment_data: Dict[str, Any]
) -> float:
    """
    Calculate risk score for a patient based on assessment data.

    Args:
        patient_id: The unique identifier for the patient
        assessment_data: Dictionary containing assessment responses

    Returns:
        float: Calculated risk score between 0.0 and 1.0

    Raises:
        ValueError: If patient_id is invalid or assessment_data is incomplete
        DatabaseError: If database query fails

    Examples:
        >>> calculate_risk_score(123, {"symptom1": "high", "symptom2": "low"})
        0.65
    """
    if not patient_id:
        raise ValueError("Invalid patient_id")

    # Implementation
    return 0.0
```

### Module Docstrings

**✓ CORRECT:**
```python
"""
Patient service module.

This module provides services for managing patient data, including
creation, retrieval, updating, and deletion of patient records.

Classes:
    PatientService: Main service class for patient operations
    PatientRepository: Data access layer for patients

Functions:
    validate_patient_data: Validates patient data before persistence
"""

from typing import Optional
```

---

## Import Organization

### Standard Order (enforced by isort)
1. Standard library
2. Third-party libraries
3. Local application imports

**✓ CORRECT:**
```python
# Standard library
import os
import sys
from datetime import datetime
from typing import Optional, List

# Third-party
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Local
from app.core.config import get_settings
from app.db.session import get_db
from app.models.patient import Patient
from app.services.patient import PatientService
```

### Absolute Imports (Preferred)

**✓ CORRECT:**
```python
from app.services.patient import PatientService
from app.models.patient import Patient
```

**✗ AVOID:**
```python
from ..services.patient import PatientService  # Relative import
from .models import Patient  # Relative import
```

---

## Error Handling

### Use Specific Exceptions

**✓ CORRECT:**
```python
from app.core.exceptions import PatientNotFoundError, ValidationError

def get_patient(patient_id: int) -> Patient:
    """Get patient by ID."""
    if not patient_id:
        raise ValidationError("patient_id is required")

    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise PatientNotFoundError(f"Patient {patient_id} not found")

    return patient
```

**✗ INCORRECT:**
```python
def get_patient(patient_id):
    try:
        patient = db.query(Patient).filter_by(id=patient_id).first()
        return patient
    except:  # Bare except - too broad
        pass  # Silent failure - bad
```

### Logging Instead of Print

**✓ CORRECT:**
```python
import logging

logger = logging.getLogger(__name__)

def process_data(data: dict):
    """Process data."""
    logger.debug(f"Processing data: {data}")
    logger.info("Data processing started")

    try:
        result = heavy_computation(data)
        logger.info(f"Processing complete: {result}")
        return result
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        raise
```

**✗ INCORRECT:**
```python
def process_data(data):
    print(f"Processing data: {data}")  # Don't use print in production

    try:
        result = heavy_computation(data)
        print(f"Result: {result}")  # Don't use print
        return result
    except Exception as e:
        print(f"Error: {e}")  # Don't use print for errors
```

---

## Testing Standards

### Test Function Naming: `test_<what>_<condition>_<expected>`

**✓ CORRECT:**
```python
def test_create_patient_with_valid_data_returns_patient():
    """Test patient creation with valid data."""
    pass

def test_get_patient_with_invalid_id_raises_not_found():
    """Test get patient with invalid ID raises exception."""
    pass

def test_calculate_risk_score_with_high_risk_returns_high_score():
    """Test risk calculation for high-risk patient."""
    pass
```

---

## Pre-commit Enforcement

All style rules are enforced via pre-commit hooks:

```bash
# Install pre-commit
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

### Automated Tools
- **Black**: Code formatting (120 char line length)
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **autoflake**: Remove unused imports
- **vulture**: Dead code detection
- **bandit**: Security scanning

---

## Common Violations and Fixes

### ❌ Mixed Naming Styles

**Before:**
```python
class patient_service:  # Wrong: should be PascalCase
    def GetPatient(self, patientId):  # Wrong: should be snake_case
        userSession = self.get_session()  # Wrong: should be snake_case
        return None
```

**After:**
```python
class PatientService:  # Correct: PascalCase
    def get_patient(self, patient_id: int) -> Optional[Patient]:  # Correct: snake_case
        user_session = self._get_session()  # Correct: snake_case
        return None
```

### ❌ Missing Type Hints

**Before:**
```python
def process_data(data):
    return {"result": data}
```

**After:**
```python
def process_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process data and return result."""
    return {"result": data}
```

### ❌ Print Statements

**Before:**
```python
def calculate(x, y):
    print(f"Calculating {x} + {y}")
    return x + y
```

**After:**
```python
import logging

logger = logging.getLogger(__name__)

def calculate(x: float, y: float) -> float:
    """Calculate sum of two numbers."""
    logger.debug(f"Calculating {x} + {y}")
    return x + y
```

---

## Enforcement Checklist

- [ ] All functions/variables use `snake_case`
- [ ] All classes use `PascalCase`
- [ ] All constants use `UPPER_SNAKE_CASE`
- [ ] Type hints on 95%+ of public functions
- [ ] Docstrings on all public functions/classes
- [ ] No `print()` statements (use `logger`)
- [ ] All TODOs linked to GitHub issues: `# TODO(#123): description`
- [ ] No commented-out code blocks (>3 lines)
- [ ] No unused imports
- [ ] Max 50 lines per method
- [ ] Max 300 lines per class
- [ ] Pre-commit hooks passing

---

**Last Review:** 2025-11-16 | **Next Review:** 2025-12-16
**Maintained by:** Backend Team | **Contact:** dev@clinic.com
