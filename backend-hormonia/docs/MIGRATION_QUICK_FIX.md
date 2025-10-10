# Alembic Migration Quick Fix Guide

**CRITICAL**: 2 migrations need immediate fixes before deployment

---

## Problem Identified

Two recent migrations use Python 3.10+ type hints that Alembic's parser cannot read:

```python
# ❌ BREAKS ALEMBIC
revision: str = '20251009_230000'
down_revision: Union[str, None] = '20251009_210800'

# ✅ WORKS WITH ALEMBIC
revision = '20251009_230000'
down_revision = '20251009_210800'
```

---

## Quick Fix (5 minutes)

### File 1: `20251009_230000_add_whatsapp_delivery_failures.py`

**Lines 15-18, change from:**
```python
revision: str = '20251009_230000'
down_revision: Union[str, None] = '20251009_210800'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

**To:**
```python
revision = '20251009_230000'
down_revision = '20251009_225600'  # Changed parent to connect to GIN indexes chain
branch_labels = None
depends_on = None
```

### File 2: `20251009_235500_add_webhook_idempotency.py`

**Lines 15-18, change from:**
```python
revision: str = '20251009_235500'
down_revision: Union[str, None] = '20251009_230000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

**To:**
```python
revision = '20251009_235500'
down_revision = '20251009_230000'
branch_labels = None
depends_on = None
```

---

## Verification

After making changes, verify the migration chain:

```bash
cd backend-hormonia

# Check current migration state
alembic current

# View migration history
alembic history

# Check for multiple heads (should be 1)
alembic heads

# Preview migration SQL (don't apply yet)
alembic upgrade head --sql > preview.sql
```

Expected output from `alembic heads`:
```
5479068ccdaa (head)
```

If you see multiple heads, the fix didn't work or there are other issues.

---

## Testing

```bash
# In development environment
alembic upgrade head

# Check database state
psql $DATABASE_URL -c "\dt"

# Test rollback
alembic downgrade -1
alembic upgrade head

# Success!
```

---

## What This Fixes

| Before | After |
|--------|-------|
| ❌ 3 root migrations | ✅ 1 root migration |
| ❌ UNKNOWN revision IDs | ✅ Valid revision IDs |
| ❌ 4 orphaned migrations | ✅ 2 orphaned migrations (will fix later) |
| ❌ Broken webhook chain | ✅ Connected webhook chain |
| ❌ Deployment will fail | ✅ Deployment ready |

---

## Alternative: If You Want to Start Fresh Chain

If you prefer to keep the webhook migrations separate (starting new chain from current HEAD):

**File 1: `20251009_230000_add_whatsapp_delivery_failures.py`**

```python
revision = '20251009_230000'
down_revision = '5479068ccdaa'  # Current HEAD of main chain
branch_labels = None
depends_on = None
```

This connects the webhook migrations directly to the current HEAD instead of the GIN indexes branch.

---

## Common Errors After Fix

### Error: "Multiple heads found"
```
FAILED: Multiple head revisions are present for given argument 'head';
please specify a specific target revision
```

**Solution**: Create a merge migration
```bash
alembic merge heads
# Then edit the generated file to add proper upgrade/downgrade logic
```

### Error: "Can't locate revision identified by 'XXXXX'"
```
FAILED: Can't locate revision identified by '20251009_225600'
```

**Solution**: Check that the down_revision exists in another migration file
```bash
grep -r "revision = '20251009_225600'" alembic/versions/
```

### Error: "Destination database is not empty"
```
FAILED: Target database is not up to date.
```

**Solution**: Check current revision
```bash
alembic current
alembic history | grep "(head)"
```

---

## After Fixing

Update these documents:
1. Comment in this file confirming fix applied
2. Update `MIGRATION_ANALYSIS_SUMMARY.md` status
3. Mark as resolved in any related tickets

---

## Prevention for Future

Add to `alembic/versions/README.md`:

```markdown
# Migration Creation Guidelines

## DO NOT use type hints on revision identifiers
❌ BAD:
```python
revision: str = 'abc123'
down_revision: Union[str, None] = 'xyz789'
```

✅ GOOD:
```python
revision = 'abc123'
down_revision = 'xyz789'
```

Type hints are fine in function signatures, but not on module-level constants.
```

---

## Status

- [ ] File 1 fixed (`20251009_230000_add_whatsapp_delivery_failures.py`)
- [ ] File 2 fixed (`20251009_235500_add_webhook_idempotency.py`)
- [ ] Tested in development
- [ ] Tested in staging
- [ ] Deployed to production
- [ ] Documentation updated

---

Last Updated: 2025-10-09
