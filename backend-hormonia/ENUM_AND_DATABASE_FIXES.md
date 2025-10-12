# Database Enum and Performance Fixes

## Summary

This document outlines the fixes applied to resolve the enum validation errors, database column mismatches, and circuit breaker issues that were causing 500 errors in the analytics dashboard and patients endpoints.

## Issues Fixed

### 1. MessageDirection Enum Mismatch
**Problem**: PostgreSQL enum `message_direction` expects lowercase values (`inbound`, `outbound`), but SQLAlchemy was sending uppercase enum names (`INBOUND`, `OUTBOUND`).

**Root Cause**: Default SQLAlchemy enum mapping sends the enum name instead of the value to the database.

**Fix Applied**:
- Changed `MessageDirection` to inherit from `str, enum.Enum`
- Updated column definition to use explicit value mapping:
```python
direction = Column(
    SAEnum(
        MessageDirection,
        name="message_direction",
        native_enum=True,
        create_type=False,
        values_callable=lambda x: [e.value for e in x],
        validate_strings=True,
    ),
    nullable=False,
)
```

### 2. PatientFlowState Column Name Mismatch
**Problem**: Model defined `template_version_id` but database table uses `flow_template_version_id`, causing `UndefinedColumn` errors.

**Fix Applied**:
```python
template_version_id = Column(
    "flow_template_version_id",  # actual column name in database
    UUID(as_uuid=True), 
    ForeignKey("flow_template_versions.id"), 
    nullable=False
)
```

### 3. Circuit Breaker and Retry Logic Issues
**Problems**:
- Circuit breaker counted non-transitory errors (schema issues) as failures
- Rollback logic only worked when `db` was in kwargs, not for service patterns
- Non-transitory errors were being retried unnecessarily

**Fixes Applied**:
- Added detection for non-transitory errors (`ProgrammingError`, `DataError`)
- Enhanced rollback detection to handle `self.db` and `self.repository.db` patterns
- Non-transitory errors now bypass circuit breaker and fail immediately
- Improved session rollback reliability

### 4. Performance Optimization
**Problem**: Dashboard queries were slow due to missing indexes on frequently filtered columns.

**Fix Applied**: Created composite indexes for common query patterns:
- `idx_messages_patient_created` - Patient-specific message queries
- `idx_messages_direction_created` - Direction-based counts
- `idx_messages_patient_direction_created` - Combined patient + direction
- `idx_alerts_status_created` - Alert status queries

## Files Modified

1. **backend-hormonia/app/models/message.py**
   - Fixed enum inheritance and column mapping
   - Updated all enum columns to use `SAEnum`

2. **backend-hormonia/app/models/flow.py**
   - Fixed `template_version_id` column name mapping

3. **backend-hormonia/app/utils/db_retry.py**
   - Enhanced rollback detection
   - Added non-transitory error handling
   - Improved circuit breaker logic

## Files Created

1. **backend-hormonia/add_performance_indexes.sql**
   - Database indexes for dashboard performance

2. **backend-hormonia/validate_fixes.py**
   - Validation script to test all fixes

3. **backend-hormonia/ENUM_AND_DATABASE_FIXES.md**
   - This documentation file

## Deployment Steps

### 1. Apply Model Changes
The model changes are backward compatible and don't require migrations since they align with existing database schema.

### 2. Reset Circuit Breaker
```python
from app.utils.db_retry import reset_circuit_breaker
reset_circuit_breaker()
```

### 3. Add Performance Indexes
```bash
psql -d your_database -f add_performance_indexes.sql
```

### 4. Validate Fixes
```bash
python validate_fixes.py
```

### 5. Test Endpoints
- `GET /api/v1/analytics/dashboard` - Should return 200 without enum errors
- `GET /api/v1/patients` - Should return 200 without column errors

## Expected Results

After applying these fixes:

1. **Analytics Dashboard**: No more "invalid input value for enum message_direction" errors
2. **Patients Endpoint**: No more "column patient_flow_states.template_version_id does not exist" errors
3. **Circuit Breaker**: Remains closed for schema/validation errors (non-transitory)
4. **Performance**: Dashboard queries should be faster with new indexes
5. **Reliability**: Better session rollback handling prevents "current transaction is aborted" errors

## Monitoring

Monitor these metrics post-deployment:
- Dashboard response times (should improve)
- 500 error rates (should decrease significantly)
- Circuit breaker state (should remain closed)
- Database query performance on messages table

## Rollback Plan

If issues occur:
1. The model changes are backward compatible
2. Indexes can be dropped if they cause issues: `DROP INDEX CONCURRENTLY index_name`
3. Circuit breaker can be manually reset: `reset_circuit_breaker()`

## Testing Checklist

- [ ] Analytics dashboard loads without enum errors
- [ ] Patients endpoint loads flow_states without column errors
- [ ] Circuit breaker remains closed after validation errors
- [ ] Dashboard performance improved
- [ ] All existing functionality still works
- [ ] No new errors in application logs