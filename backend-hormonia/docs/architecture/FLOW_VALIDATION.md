# Flow Pre-flight Validation Architecture

**Critical P7 Fix** - Prevents flows from starting with incomplete patient data

## Overview

The Flow Pre-flight Validation system ensures that patient flows only start when all required patient information is complete and valid. This prevents treatment monitoring failures caused by missing or incorrect data.

## Problem Statement

**Before Fix:**
- Flows would start even with missing critical patient data (CPF, phone, treatment type)
- Incomplete data led to incorrect treatment monitoring
- No validation of data format or quality
- Errors only discovered after flow started

**After Fix:**
- Comprehensive pre-flight validation before flow start
- Clear validation error messages
- Multiple validation levels (critical vs. recommended)
- Flow-specific validation rules

## Architecture

### Components

```
┌─────────────────────────────────────────────┐
│         FlowEngine.start_flow()             │
│                                             │
│  1. Get Patient                             │
│  2. ┌──────────────────────────────────┐   │
│     │ Pre-flight Validation (NEW)      │   │
│     │  - Critical Fields               │   │
│     │  - Recommended Fields            │   │
│     │  - Flow-Specific Rules           │   │
│     └──────────────────────────────────┘   │
│  3. Get Template                            │
│  4. Create Flow State                       │
│  5. Schedule Steps                          │
└─────────────────────────────────────────────┘
```

### Validation Rules Hierarchy

```
ValidationRule (Base Class)
│
├── RequiredFieldRule
│   └── Validates field presence
│
├── CPFValidationRule
│   ├── Format validation (11 digits)
│   ├── Invalid patterns (all same digit)
│   └── Checksum validation (verifier digits)
│
├── PhoneValidationRule
│   ├── Length validation (10-11 digits)
│   └── Area code validation (Brazilian DDD)
│
├── TreatmentTypeValidationRule
│   └── Valid treatment type check
│
└── DateValidationRule
    ├── Format validation
    ├── Future/past date validation
    └── Age plausibility check
```

## Implementation

### 1. Validation Service

**File:** `backend-hormonia/app/services/flow_validation.py`

```python
class FlowPreflightValidator:
    """Pre-flight validation for patient flows."""

    def validate_patient_for_flow(
        self,
        patient: Patient,
        flow_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate patient before starting flow.

        Returns:
            {
                'valid': bool,
                'errors': [...],      # Critical errors (blocks flow)
                'warnings': [...],    # Recommendations (allows flow)
                'patient_id': str,
                'checked_fields': {...}
            }

        Raises:
            ValidationError: If critical validation fails
        """
```

### 2. Integration with FlowEngine

**File:** `backend-hormonia/app/services/flow_engine.py`

```python
def start_flow(
    self,
    patient_id: UUID,
    flow_type: str,
    ...
) -> PatientFlowState:
    # Get patient
    patient = self.patient_repo.get(patient_id)

    # CRITICAL FIX: Pre-flight validation
    validation_result = self._validate_patient_data(patient)
    logger.info(f"Patient {patient_id} validation passed")

    # Continue with flow creation...
```

### 3. Patient Model Enhancement

**File:** `backend-hormonia/app/models/patient.py`

The Patient model already has all required fields:
- `cpf` - CPF (Brazilian ID)
- `phone` - Phone number
- `treatment_type` - Treatment type
- `name` - Patient name
- `treatment_start_date` - Treatment start date
- `diagnosis` - Diagnosis
- `birth_date` - Date of birth

## Validation Levels

### Critical Validations (Block Flow Start)

1. **CPF Validation**
   - Must be present
   - Must be 11 digits
   - Cannot be all same digit (e.g., '11111111111')
   - Must pass checksum validation

2. **Phone Validation**
   - Must be present
   - Must be 10-11 digits (Brazilian format)
   - Valid area code (DDD)

3. **Treatment Type Validation**
   - Must be present
   - Should be a recognized type (warning if unknown)

### Recommended Validations (Generate Warnings)

1. **Name** - Should be present
2. **Treatment Start Date** - Should be present for most flows
3. **Birth Date** - Should be present and reasonable
4. **Diagnosis** - Should be present

### Flow-Specific Validations

**Hormone Therapy:**
- Requires `treatment_start_date`

**Chemotherapy:**
- Requires `diagnosis`

## Error Responses

### Validation Error Example

```json
{
  "detail": "Dados do paciente incompletos ou inválidos. Corrija os seguintes erros antes de iniciar o fluxo: cpf: CPF com formato inválido (deve ter 11 dígitos): 123; phone: Telefone não informado",
  "validation_details": {
    "valid": false,
    "patient_id": "123e4567-e89b-12d3-a456-426614174000",
    "patient_name": "Maria Silva",
    "errors": [
      {
        "field": "cpf",
        "message": "CPF com formato inválido (deve ter 11 dígitos): 123",
        "severity": "error",
        "code": "CPF_INVALID_LENGTH",
        "actual_length": 3
      },
      {
        "field": "phone",
        "message": "Telefone não informado",
        "severity": "error",
        "code": "PHONE_MISSING"
      }
    ],
    "warnings": [],
    "checked_fields": {
      "critical": ["cpf", "phone", "treatment_type"],
      "recommended": ["name", "treatment_start_date", "birth_date", "diagnosis"]
    },
    "timestamp": "2025-10-09T23:30:00.000Z"
  }
}
```

### Success with Warnings Example

```json
{
  "valid": true,
  "patient_id": "123e4567-e89b-12d3-a456-426614174000",
  "patient_name": "Maria Silva",
  "errors": [],
  "warnings": [
    {
      "field": "diagnosis",
      "message": "Diagnóstico não informado",
      "severity": "warning",
      "code": "REQUIRED_FIELD_MISSING"
    }
  ],
  "checked_fields": {
    "critical": ["cpf", "phone", "treatment_type"],
    "recommended": ["name", "treatment_start_date", "birth_date", "diagnosis"]
  },
  "timestamp": "2025-10-09T23:30:00.000Z"
}
```

## Usage Examples

### Starting a Flow

```python
from app.services.flow_engine import FlowEngine
from app.exceptions import ValidationError

flow_engine = FlowEngine(db)

try:
    flow_state = flow_engine.start_flow(
        patient_id=patient.id,
        flow_type='hormonia_fluxo_mama'
    )
    print(f"Flow started successfully: {flow_state.id}")
except ValidationError as e:
    # Handle validation error
    print(f"Cannot start flow: {e}")
    print(f"Errors: {e.details['errors']}")
    print(f"Fix these fields: {[err['field'] for err in e.details['errors']]}")
```

### Direct Validation

```python
from app.services.flow_validation import get_flow_validator

validator = get_flow_validator()

try:
    result = validator.validate_patient_for_flow(
        patient=patient,
        flow_type='hormonia_fluxo_mama'
    )
    print(f"Validation passed with {len(result['warnings'])} warnings")
except ValidationError as e:
    print(f"Validation failed: {e}")
```

### Batch Validation

```python
from app.services.flow_validation import get_flow_validator

validator = get_flow_validator()

results = validator.validate_multiple_patients(
    patients=patient_list,
    flow_type='hormonia_fluxo_mama'
)

print(f"Valid patients: {results['valid_patients']}")
print(f"Invalid patients: {results['invalid_patients']}")
print(f"Patients with warnings: {results['patients_with_warnings']}")
```

## Testing

### Test Coverage

Target: **100% coverage**

**Test Categories:**
1. Individual validation rules
2. Complete patient validation
3. Flow-specific validations
4. Batch validations
5. Error message formatting
6. Edge cases

**Run Tests:**
```bash
cd backend-hormonia
pytest tests/unit/services/test_flow_validation.py -v --cov=app/services/flow_validation --cov-report=term-missing
```

### Example Test Cases

```python
def test_validate_patient_missing_cpf():
    """Flow should not start without CPF."""
    patient.cpf = None

    with pytest.raises(ValidationError) as exc:
        validator.validate_patient_for_flow(patient)

    assert 'CPF' in str(exc.value)

def test_validate_patient_warnings_allowed():
    """Flow should start with warnings but no errors."""
    patient.diagnosis = None  # Recommended field

    result = validator.validate_patient_for_flow(patient)

    assert result['valid'] is True
    assert len(result['warnings']) > 0
```

## Benefits

### Before Fix
- ❌ Flows started with incomplete data
- ❌ Treatment monitoring failures
- ❌ Errors discovered late
- ❌ Poor user experience

### After Fix
- ✅ Pre-flight validation prevents incomplete data
- ✅ Clear, actionable error messages
- ✅ Warnings for recommended fields
- ✅ Flow-specific validation rules
- ✅ Better data quality
- ✅ Improved user experience

## Monitoring

### Metrics to Track

1. **Validation Failures:**
   - Count of flows blocked by validation
   - Most common validation errors
   - Validation failure rate

2. **Warnings:**
   - Count of warnings generated
   - Most common missing recommended fields

3. **Flow Success:**
   - Reduction in flow failures after validation
   - Improvement in data completeness

### Logging

```python
logger.info(f"Patient {patient_id} validation passed. Warnings: {len(warnings)}")
logger.error(f"Patient {patient_id} validation failed. Errors: {error_summary}")
logger.warning(f"Patient {patient_id} has warnings. Fields: {warning_summary}")
```

## Future Enhancements

1. **Custom Validation Rules:**
   - Allow configuration of validation rules per clinic
   - Dynamic rule creation through admin interface

2. **Validation Templates:**
   - Pre-configured validation sets for different flow types
   - Import/export validation configurations

3. **Data Quality Scoring:**
   - Score patients by data completeness
   - Reports on data quality across patient population

4. **Auto-correction:**
   - Suggest corrections for common errors
   - Auto-format phone and CPF inputs

## References

- **Issue:** P7 - Flow Validation Gap
- **Implementation:** `app/services/flow_validation.py`
- **Tests:** `tests/unit/services/test_flow_validation.py`
- **Integration:** `app/services/flow_engine.py` (lines 453-548, 579-586)

## Related Documentation

- [Flow Engine Architecture](./FLOW_ENGINE_ARCHITECTURE.md)
- [Patient Model Schema](../backend/README.md)
- [API Error Handling](../backend/API_ERROR_HANDLING.md)
