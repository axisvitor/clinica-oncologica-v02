# Patient Model Column Migration

## Overview

This migration moves patient clinical data from JSONB (`metadata`) to dedicated columns for better performance, data integrity, and query capabilities.

## Changes

### Database Schema (Migration: `add_dedicated_patient_columns`)

**New dedicated columns added to `patients` table:**

| Column | Type | Nullable | Indexed | Description |
|--------|------|----------|---------|-------------|
| `cpf` | VARCHAR(11) | Yes | Yes (unique) | Brazilian CPF (Cadastro de Pessoas Físicas) |
| `diagnosis` | VARCHAR(500) | Yes | Yes | Patient diagnosis information |
| `treatment_phase` | VARCHAR(100) | Yes | Yes | Current treatment phase |
| `doctor_notes` | TEXT | Yes | No | Doctor's clinical notes |

**Features:**
- ✅ Automatic data migration from `metadata` JSONB
- ✅ CPF validation function and trigger
- ✅ Treatment phase constraint (valid values: initial, adjustment, maintenance, monitoring, followup, completed)
- ✅ Indexes for performance optimization
- ✅ Backward compatibility (metadata cleanup after migration)

### Model Changes ([patient.py](app/models/patient.py))

**Before:**
```python
# Fields stored in patient_data (JSONB metadata)
@property
def cpf(self):
    return self.patient_data.get('cpf') if self.patient_data else None
```

**After:**
```python
# Now dedicated columns
cpf = Column(String(11), nullable=True, index=True)
diagnosis = Column(String(500), nullable=True, index=True)
treatment_phase = Column(String(100), nullable=True, index=True)
doctor_notes = Column(String, nullable=True)
```

### Service Changes ([patient.py](app/services/patient.py))

**Updated CPF validation** to check both direct attribute and metadata (for compatibility during transition):

```python
# Supports both old and new style
cpf = None
if hasattr(patient_data, 'cpf') and patient_data.cpf:
    cpf = patient_data.cpf
elif hasattr(patient_data, 'patient_data') and patient_data.patient_data:
    cpf = patient_data.patient_data.get('cpf')
```

## Migration Steps

### 1. Run Alembic Migration

```bash
cd backend-hormonia

# Check current migration status
python -m alembic current

# Run migration
python -m alembic upgrade head
```

### 2. Verify Migration

```sql
-- Check new columns exist
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'patients'
AND column_name IN ('cpf', 'diagnosis', 'treatment_phase', 'doctor_notes');

-- Verify data was migrated
SELECT
    COUNT(*) as total_patients,
    COUNT(cpf) as patients_with_cpf,
    COUNT(diagnosis) as patients_with_diagnosis,
    COUNT(treatment_phase) as patients_with_treatment_phase,
    COUNT(doctor_notes) as patients_with_notes
FROM patients;

-- Check metadata was cleaned up
SELECT
    COUNT(*) as patients_with_old_metadata
FROM patients
WHERE metadata ? 'cpf' OR metadata ? 'diagnosis'
   OR metadata ? 'treatment_phase' OR metadata ? 'doctor_notes';
```

Expected: `patients_with_old_metadata` should be 0.

### 3. Test CPF Validation

```sql
-- Should succeed (valid CPF)
UPDATE patients SET cpf = '12345678909' WHERE id = 'some-uuid';

-- Should fail (invalid CPF)
UPDATE patients SET cpf = '00000000000' WHERE id = 'some-uuid';
-- Error: Invalid CPF

-- Should fail (invalid format)
UPDATE patients SET cpf = 'abc123' WHERE id = 'some-uuid';
-- Error: violates check constraint "check_cpf_format"
```

### 4. Test Treatment Phase Constraint

```sql
-- Should succeed
UPDATE patients SET treatment_phase = 'maintenance' WHERE id = 'some-uuid';

-- Should fail
UPDATE patients SET treatment_phase = 'invalid_phase' WHERE id = 'some-uuid';
-- Error: violates check constraint "check_treatment_phase_values"
```

## Benefits

### Performance Improvements
- 🚀 **Indexed queries**: Direct column indexes vs JSONB GIN indexes
- 🚀 **Type safety**: Database enforces data types
- 🚀 **Faster filtering**: WHERE clauses on indexed columns

**Example:**
```sql
-- BEFORE (slow JSONB query)
SELECT * FROM patients WHERE metadata->>'cpf' = '12345678909';

-- AFTER (fast indexed query)
SELECT * FROM patients WHERE cpf = '12345678909';
```

### Data Integrity
- ✅ CPF validation at database level
- ✅ Treatment phase enumeration constraint
- ✅ Unique CPF constraint
- ✅ Consistent data types

### Code Quality
- ✅ Direct attribute access: `patient.cpf` instead of `patient.patient_data.get('cpf')`
- ✅ IDE autocomplete support
- ✅ Type hints work correctly
- ✅ Easier to query and join

## Backward Compatibility

The migration maintains **full backward compatibility**:

1. **Legacy property accessors** still work:
   ```python
   patient.cpf_from_metadata  # Returns patient.cpf
   ```

2. **Service layer** checks both locations during transition

3. **Metadata cleanup** happens automatically after migration

## Rollback (if needed)

```bash
# Rollback to previous version
python -m alembic downgrade -1
```

This will:
- Move data back to `metadata` JSONB
- Drop new columns and indexes
- Remove constraints and triggers

## Valid Treatment Phases

The following values are valid for `treatment_phase`:
- `initial` - Initial assessment/setup
- `adjustment` - Dosage/treatment adjustment phase
- `maintenance` - Stable maintenance phase
- `monitoring` - Active monitoring phase
- `followup` - Follow-up after treatment
- `completed` - Treatment completed

## CPF Validation

CPF validation includes:
- ✅ Exactly 11 digits
- ✅ Valid check digits (algorithm validation)
- ✅ Rejects known invalid patterns (00000000000, 11111111111, etc.)
- ✅ Database trigger validates on INSERT/UPDATE

## Notes

- `metadata` (accessed via `patient_data`) is still available for custom/dynamic fields
- Only clinical fields moved to dedicated columns
- All indexes created automatically during migration
- No application downtime required for migration
