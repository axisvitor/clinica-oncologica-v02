# Pydantic V2 Migration - Quick Reference Guide

## TL;DR

✅ **Migration Status**: COMPLETE
✅ **Action Required**: NONE
✅ **Breaking Changes**: NONE

## What Changed?

### The One-Line Summary
`schema_extra` → `json_schema_extra` in all Pydantic model Config classes.

## For Developers

### ❌ Don't Do This (Old Way)
```python
class MySchema(BaseModel):
    name: str

    class Config:
        schema_extra = {  # ❌ DEPRECATED in Pydantic V2
            "example": {"name": "John"}
        }
```

### ✅ Do This Instead (New Way)
```python
class MySchema(BaseModel):
    name: str

    class Config:
        json_schema_extra = {  # ✅ CORRECT for Pydantic V2
            "example": {"name": "John"}
        }
```

## Verification

### Quick Check
```bash
# Run this before committing schema changes
cd backend-hormonia
py scripts/verify_pydantic_v2.py
```

### Expected Output
```
[SUCCESS] ALL CHECKS PASSED - Pydantic V2 migration complete!
```

## Common Questions

### Q: Do I need to update my existing code?
**A**: No, migration is already complete. Just follow the new pattern for new schemas.

### Q: What if I accidentally use `schema_extra`?
**A**: The verification script will catch it. Run `py scripts/verify_pydantic_v2.py` before committing.

### Q: Does this affect API endpoints?
**A**: No, all endpoints work the same. Only internal schema configuration changed.

### Q: Will this break tests?
**A**: No, all tests pass. The migration is backward compatible.

### Q: Do I need to update documentation?
**A**: No, OpenAPI/Swagger docs are generated automatically and work correctly.

## Files Involved

### Schema Files Using json_schema_extra
1. `app/schemas/admin_users.py` - Admin user schemas
2. `app/schemas/ai.py` - AI service schemas (10 classes)
3. `app/schemas/medico.py` - Doctor/medical schemas

### Other Schema Files
- `app/schemas/flow.py` - No Config examples needed
- 17 other schema files - Simple schemas without examples

## Pre-Commit Checklist

When creating or modifying schemas:

- [ ] Use `json_schema_extra` (not `schema_extra`)
- [ ] Run verification: `py scripts/verify_pydantic_v2.py`
- [ ] Ensure tests pass: `pytest tests/test_pydantic_v2_migration.py`
- [ ] Verify API docs display examples correctly

## Error Messages

### If you see this warning:
```
Warning: `schema_extra` is deprecated, use `json_schema_extra` instead
```

**Fix**: Replace `schema_extra` with `json_schema_extra` in the Config class.

### If verification fails:
```
[FAIL] Found deprecated schema_extra usage:
  filename.py:42 - schema_extra = {...}
```

**Fix**: Change line 42 to use `json_schema_extra` instead.

## Resources

- **Full Migration Doc**: `docs/deployment/PYDANTIC_V2_MIGRATION_COMPLETE.md`
- **Verification Script**: `backend-hormonia/scripts/verify_pydantic_v2.py`
- **Test Suite**: `backend-hormonia/tests/test_pydantic_v2_migration.py`
- **Pydantic V2 Docs**: https://docs.pydantic.dev/latest/

## Support

If you encounter issues:

1. Check this guide
2. Run verification script
3. Review full migration doc
4. Check Pydantic V2 documentation

---

**Last Updated**: 2025-10-07
**Status**: ✅ Migration Complete
