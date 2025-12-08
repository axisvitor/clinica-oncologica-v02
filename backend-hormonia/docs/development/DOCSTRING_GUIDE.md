# Docstring Style Guide

This document defines the docstring standards for the Hormonia backend codebase.

## Style: Google Style

We use **Google Style** docstrings for consistency and readability.

## Basic Structure

```python
def function_name(arg1: type1, arg2: type2) -> return_type:
    """
    One-line summary.

    Optional longer description providing more context about what the
    function does, how it works, and any important implementation details.

    Args:
        arg1 (type1): Description of arg1
        arg2 (type2): Description of arg2

    Returns:
        return_type: Description of return value

    Raises:
        ExceptionType: Description of when this exception is raised

    Example:
        >>> result = function_name(value1, value2)
        >>> print(result)
        expected_output
    """
```

## Function Docstring

### Required Sections

1. **Summary**: One-line description (imperative mood)
2. **Args**: All parameters (except `self` and `cls`)
3. **Returns**: Return value description (if function returns)

### Optional Sections

4. **Raises**: Exceptions that can be raised
5. **Example**: Usage examples
6. **Note**: Important notes or warnings
7. **Todo**: Planned improvements

### Complete Example

```python
def create_patient(
    patient_data: PatientCreate,
    db: Session,
    current_user: User
) -> Patient:
    """
    Create a new patient in the database.

    Validates patient data, checks for duplicate CPF, creates Firebase
    authentication, and stores the patient record with encrypted PII.

    Args:
        patient_data (PatientCreate): Patient data to create
        db (Session): Database session for transaction
        current_user (User): User creating the patient (for audit)

    Returns:
        Patient: Created patient instance with all fields populated

    Raises:
        DuplicateCPFException: If CPF already exists in database
        ValidationError: If patient data fails validation
        FirebaseError: If Firebase authentication fails

    Example:
        >>> from app.schemas import PatientCreate
        >>> patient_data = PatientCreate(
        ...     name="João Silva",
        ...     cpf="12345678901",
        ...     email="joao@example.com"
        ... )
        >>> patient = create_patient(patient_data, db, current_user)
        >>> print(patient.id)
        UUID('...')

    Note:
        This function creates both database record and Firebase auth account.
        If either fails, the entire transaction is rolled back.

    Todo:
        - Add support for bulk patient creation
        - Implement patient data import from CSV
    """
```

## Class Docstring

```python
class Patient(BaseModel):
    """
    Patient model representing a patient in the oncology clinic.

    This model stores patient demographic information, medical history,
    and treatment records. All PII fields are encrypted at rest.

    Attributes:
        id (UUID): Unique patient identifier
        name (str): Patient full name
        cpf (str): Brazilian CPF (encrypted)
        email (str): Patient email address
        phone (str): Patient phone number
        created_at (datetime): Record creation timestamp
        updated_at (datetime): Last update timestamp

    Example:
        >>> patient = Patient(
        ...     name="João Silva",
        ...     cpf="12345678901"
        ... )
        >>> patient.save()
    """
```

## Method Docstring

```python
class PatientService:
    """Service for patient-related operations."""

    def get_by_cpf(self, cpf: str) -> Optional[Patient]:
        """
        Retrieve patient by CPF.

        Args:
            cpf (str): Patient CPF (formatted or unformatted)

        Returns:
            Optional[Patient]: Patient if found, None otherwise

        Example:
            >>> service = PatientService()
            >>> patient = service.get_by_cpf("123.456.789-01")
        """
```

## Property Docstring

```python
class Patient(BaseModel):
    """Patient model."""

    @property
    def full_name(self) -> str:
        """
        Get patient's full name in title case.

        Returns:
            str: Full name formatted as "First Last"
        """
        return f"{self.first_name} {self.last_name}".title()
```

## Module Docstring

```python
"""
Patient service module.

This module provides services for patient CRUD operations, including
creation, retrieval, updates, and deletion. All operations enforce
HIPAA compliance and audit logging.

Classes:
    PatientService: Main service for patient operations
    PatientRepository: Data access layer for patients

Functions:
    create_patient: Create new patient
    get_patient: Retrieve patient by ID
    update_patient: Update patient data
    delete_patient: Soft delete patient

Example:
    >>> from app.services.patient import PatientService
    >>> service = PatientService()
    >>> patient = service.create_patient(patient_data)
"""
```

## Type Hints

Always use type hints in function signatures. Docstrings should reference these types:

```python
def process_results(
    results: List[Dict[str, Any]],
    filter_func: Callable[[Dict], bool]
) -> List[Dict[str, Any]]:
    """
    Process and filter results.

    Args:
        results: List of result dictionaries
        filter_func: Function to filter results

    Returns:
        Filtered list of results
    """
```

## Edge Cases and Special Scenarios

### Async Functions

```python
async def fetch_patient_data(patient_id: UUID) -> Patient:
    """
    Asynchronously fetch patient data.

    Args:
        patient_id: Patient UUID

    Returns:
        Patient data from database

    Raises:
        NotFoundError: If patient doesn't exist
    """
```

### Decorators

```python
@lru_cache(maxsize=128)
def expensive_calculation(n: int) -> int:
    """
    Perform expensive calculation with caching.

    Results are cached for performance. Cache size is limited to 128 entries.

    Args:
        n: Input number

    Returns:
        Calculated result
    """
```

### Multiple Return Types

```python
def get_patient(
    patient_id: Optional[UUID] = None,
    cpf: Optional[str] = None
) -> Optional[Patient]:
    """
    Get patient by ID or CPF.

    Args:
        patient_id: Patient UUID (optional)
        cpf: Patient CPF (optional)

    Returns:
        Patient if found, None otherwise

    Raises:
        ValueError: If neither patient_id nor cpf is provided
    """
```

## Coverage Requirements

- **All public functions**: 100% docstring coverage
- **All public classes**: 100% docstring coverage
- **Private functions**: Docstring if complex (>10 lines)
- **Test functions**: Optional (descriptive names preferred)

## Tools

### Check Coverage

```bash
# Check docstring coverage
interrogate app/ --fail-under 95 --verbose

# Generate missing docstrings report
python scripts/analyze_docstring_coverage.py --output missing_docstrings.txt
```

### Generate Templates

```bash
# Generate docstring template for specific function
python scripts/generate_docstrings.py \
    --add-to-file app/services/patient.py \
    --function create_patient \
    --line 45
```

## Common Mistakes

### ❌ Bad: Redundant or Useless

```python
def get_name():
    """Get name."""  # Useless - just repeats function name
    return self.name
```

### ✅ Good: Adds Value

```python
def get_name(self) -> str:
    """
    Get patient's full name in standardized format.

    Returns first and last name combined, with proper title casing
    and whitespace normalization.

    Returns:
        Full name in "First Last" format
    """
    return f"{self.first_name} {self.last_name}".strip().title()
```

### ❌ Bad: Outdated

```python
def create_user(data):
    """
    Create user in MySQL database.  # Outdated - we use PostgreSQL
    """
```

### ✅ Good: Current

```python
def create_user(data: UserCreate, db: Session) -> User:
    """
    Create user in PostgreSQL database.

    Validates data, encrypts password, and stores in users table.
    """
```

## Pre-commit Hook

Ensure docstring coverage with pre-commit:

```yaml
# .pre-commit-config.yaml
- repo: https://github.com/econchick/interrogate
  rev: 1.5.0
  hooks:
    - id: interrogate
      args: [--fail-under, "95", --verbose]
```

## References

- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- [PEP 257 - Docstring Conventions](https://www.python.org/dev/peps/pep-0257/)
- [Interrogate Documentation](https://interrogate.readthedocs.io/)
