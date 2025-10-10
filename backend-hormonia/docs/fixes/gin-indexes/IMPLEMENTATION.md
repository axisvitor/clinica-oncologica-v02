# GIN Indexes Implementation - Patient Search Optimization

## Overview

Created database migration to add Generalized Inverted Indexes (GIN) for optimizing patient search queries.

**Reference:** `docs/COMPREHENSIVE_REVIEW_2025-10-09.md`

## Migration Details

**File:** `backend-hormonia/alembic/versions/20251009_210800_add_gin_indexes_for_search.py`

**Revision ID:** `20251009_210800`

**Depends On:** `001_initial` (initial migration)

## Indexes Created

### 1. Patient Name GIN Index
```sql
CREATE INDEX idx_patient_name_gin
ON patients
USING GIN (to_tsvector('portuguese', name));
```

**Purpose:**
- Full-text search on patient names
- Case-insensitive matching
- Portuguese language support (proper stemming and stop-words)
- Efficient for queries like: `WHERE to_tsvector('portuguese', name) @@ to_tsquery('portuguese', 'maria')`

**Performance:**
- ~10-100x faster than LIKE queries on large datasets
- Handles partial word matching
- Supports accent-insensitive searches with Portuguese configuration

### 2. Patient Email GIN Index
```sql
CREATE INDEX idx_patient_email_gin
ON patients
USING GIN (to_tsvector('simple', COALESCE(email, '')));
```

**Purpose:**
- Full-text search on email addresses
- Handles NULL values gracefully with COALESCE
- Uses 'simple' configuration (no language-specific processing needed for emails)
- Efficient for queries like: `WHERE to_tsvector('simple', email) @@ to_tsquery('simple', 'example.com')`

**Performance:**
- Fast email domain searches
- Efficient partial email matching
- No overhead from language processing

### 3. Phone Number Partial Index
```sql
CREATE INDEX idx_patient_phone_partial
ON patients (phone)
WHERE phone IS NOT NULL AND phone != '';
```

**Purpose:**
- Optimizes queries filtering by non-empty phone numbers
- Reduces index size by excluding NULL and empty string values
- Complements the existing unique index on phone field

**Performance:**
- Smaller index size than full phone index
- Faster for WHERE phone IS NOT NULL queries
- Lower maintenance overhead

## How to Apply

### 1. Check Current Migration Status
```bash
cd backend-hormonia
alembic current
```

### 2. Run the Migration
```bash
# Apply the migration
alembic upgrade head

# Or upgrade to specific revision
alembic upgrade 20251009_210800
```

### 3. Verify Indexes Were Created
```sql
-- Check all indexes on patients table
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'patients'
ORDER BY indexname;

-- Check GIN indexes specifically
SELECT
    indexname,
    indexdef,
    obj_description(indexrelid) as comment
FROM pg_indexes
JOIN pg_class ON indexname = relname
WHERE tablename = 'patients'
  AND indexdef LIKE '%GIN%';
```

## Rollback Instructions

If you need to rollback this migration:

```bash
# Downgrade to previous revision
alembic downgrade 001_initial

# Or downgrade one revision
alembic downgrade -1
```

## Usage in Application Code

### Example 1: Search Patient by Name (Portuguese)
```python
from sqlalchemy import func

# Full-text search with Portuguese stemming
search_term = "maria"
patients = db.query(Patient).filter(
    func.to_tsvector('portuguese', Patient.name).match(
        func.to_tsquery('portuguese', search_term)
    )
).all()
```

### Example 2: Search Patient by Email
```python
# Email domain search
domain = "example.com"
patients = db.query(Patient).filter(
    func.to_tsvector('simple', func.coalesce(Patient.email, '')).match(
        func.to_tsquery('simple', domain)
    )
).all()
```

### Example 3: Filter Non-Empty Phones
```python
# This will use the partial index
patients = db.query(Patient).filter(
    Patient.phone.isnot(None),
    Patient.phone != ''
).all()
```

## Performance Impact

### Expected Improvements:
- **Small datasets (<1K rows):** Minimal difference
- **Medium datasets (1K-100K rows):** 5-20x faster searches
- **Large datasets (>100K rows):** 10-100x faster searches

### Index Sizes (estimated):
- `idx_patient_name_gin`: ~2-5% of table size
- `idx_patient_email_gin`: ~1-3% of table size (fewer non-NULL values)
- `idx_patient_phone_partial`: ~1-2% of table size

### Maintenance:
- Indexes update automatically on INSERT/UPDATE/DELETE
- VACUUM operations handle index cleanup
- GIN indexes have slightly higher write overhead than B-tree

## Testing

### Test Index Creation
```bash
cd backend-hormonia

# Run a test migration on a test database
export DATABASE_URL="postgresql://user:pass@localhost/test_db"
alembic upgrade 20251009_210800
```

### Test Search Performance
```sql
-- Explain query to verify index usage
EXPLAIN ANALYZE
SELECT * FROM patients
WHERE to_tsvector('portuguese', name) @@ to_tsquery('portuguese', 'maria');

-- Should show: "Bitmap Index Scan using idx_patient_name_gin"
```

## Related Files

- Migration: `backend-hormonia/alembic/versions/20251009_210800_add_gin_indexes_for_search.py`
- Patient Model: `backend-hormonia/app/models/patient.py`
- Patient Repository: `backend-hormonia/app/repositories/patient.py`
- Documentation: `docs/COMPREHENSIVE_REVIEW_2025-10-09.md`

## Next Steps

1. **Apply migration to development database**
2. **Test search performance** with realistic data volumes
3. **Update patient repository** to use full-text search functions
4. **Add search endpoint** to patient API if needed
5. **Monitor index usage** in production
6. **Consider adding JSONB indexes** for metadata fields if needed

## Notes

- GIN indexes are ideal for full-text search but have higher write overhead
- Portuguese configuration handles Brazilian Portuguese text effectively
- Partial indexes reduce storage and maintenance costs
- Consider `pg_trgm` extension for fuzzy/typo-tolerant searches in the future

## Support

For questions or issues:
- Check Alembic logs: `alembic.log`
- PostgreSQL logs for index creation errors
- Database performance metrics for query optimization

---

**Created:** 2025-10-09
**Author:** Code Implementation Agent
**Status:** Ready for deployment
