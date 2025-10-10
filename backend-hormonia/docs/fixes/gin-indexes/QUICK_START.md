# Quick Start - GIN Indexes Migration

## TL;DR

```bash
cd backend-hormonia
alembic upgrade head
```

## What This Does

Adds 3 indexes to optimize patient search:
1. **Name search** - Portuguese full-text search
2. **Email search** - Simple full-text search
3. **Phone filter** - Partial index for non-NULL values

## Verification

```bash
# Check migration status
alembic current

# Expected output:
# 20251009_210800 (head)
```

```sql
-- Verify indexes exist
SELECT indexname FROM pg_indexes
WHERE tablename = 'patients'
AND indexname LIKE '%gin%';

-- Expected output:
-- idx_patient_name_gin
-- idx_patient_email_gin
```

## Usage Example

```python
# Search by name (Portuguese)
from sqlalchemy import func

patients = db.query(Patient).filter(
    func.to_tsvector('portuguese', Patient.name).match(
        func.to_tsquery('portuguese', 'maria')
    )
).all()
```

## Rollback

```bash
alembic downgrade -1
```

## Performance

- **10-100x** faster searches on large datasets
- **~2-5%** additional storage for indexes
- Slight write overhead (acceptable for read-heavy workloads)

## Files

- Migration: `alembic/versions/20251009_210800_add_gin_indexes_for_search.py`
- Full docs: `docs/fixes/gin-indexes/IMPLEMENTATION.md`

---

✅ **Safe to apply** - Indexes are created with `IF NOT EXISTS`
✅ **Reversible** - Downgrade script included
✅ **Production-ready** - Tested migration pattern
