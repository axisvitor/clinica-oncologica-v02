# Clinical Metadata Quick Reference

**Quick guide for working with patient clinical JSONB fields**

---

## Import

```python
from app.utils.patient_metadata_schema import (
    validate_clinical_metadata,
    merge_clinical_metadata,
    extract_clinical_summary,
)
```

---

## Common Operations

### 1. Validate Metadata

```python
validated = validate_clinical_metadata(metadata, strict=True)
```

### 2. Update Patient Clinical Data

```python
updated = merge_clinical_metadata(
    existing=patient.patient_data,
    updates={"blood_type": "A+"},
    validate_result=True
)
patient.patient_data = updated
```

### 3. Get API Response

```python
return extract_clinical_summary(patient.patient_data)
```

---

## Field Reference

### Blood Type
- **Pattern**: `^(A|B|AB|O)[+-]$`
- **Examples**: `"A+"`, `"B-"`, `"AB+"`, `"O-"`

### Emergency Contact
- **Required**: `name` + `phone`
- **Phone Format**: E.164 (`+5511987654321`)

### Medical History
- `allergies`: `string[]`
- `medications`: `string[]`
- `conditions`: `string[]` (comorbidities)

---

## Quick Examples

### Create with Clinical Data
```python
metadata = {
    "medical_history": {
        "allergies": ["Penicillin"],
        "medications": ["Aspirin 100mg"],
        "conditions": ["Diabetes"]
    },
    "blood_type": "A+",
    "emergency_contact": {
        "name": "Maria Silva",
        "phone": "+5511987654321"
    }
}
```

### Update Existing
```python
updates = {"blood_type": "A+"}
patient.patient_data = merge_clinical_metadata(
    patient.patient_data,
    updates
)
```

### API Response
```python
summary = extract_clinical_summary(patient.patient_data)
# Returns:
# {
#   "allergies": [...],
#   "current_medications": [...],
#   "comorbidities": [...],
#   "blood_type": "A+",
#   "emergency_contact_name": "Maria",
#   "emergency_contact_phone": "+5511..."
# }
```

---

## Database Queries

### Find by Blood Type
```sql
SELECT * FROM patients
WHERE patient_data->>'blood_type' = 'A+';
```

### Find by Allergy
```sql
SELECT * FROM patients
WHERE patient_data->'medical_history'->'allergies' ? 'Penicillin';
```

---

## Error Handling

```python
from app.core.exceptions import ValidationError

try:
    validate_clinical_metadata(metadata)
except ValidationError as e:
    print(f"Validation failed: {e}")
```

---

## File Locations

- **Validation**: `/app/utils/patient_metadata_schema.py`
- **Tests**: `/tests/unit/test_patient_metadata_schema.py`
- **Full Docs**: `/docs/reference/CLINICAL_METADATA_SCHEMA.md`
- **Examples**: `/docs/examples/clinical_metadata_examples.py`
