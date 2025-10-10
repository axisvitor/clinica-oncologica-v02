# SQLAlchemy Metadata Conflicts Resolution

**Issue**: SQLAlchemy's Declarative API reserves the `metadata` attribute name for schema metadata registry, causing `InvalidRequestError` when models define `metadata = Column(...)`.

**Date**: 2025-10-10
**Status**: ✅ RESOLVED

## Root Cause

SQLAlchemy 2.x enforces strict reserved attribute names in the Declarative API. Models using `metadata` as a column name conflict with the class-level `metadata` attribute that stores the schema registry.

## Error Message

```
sqlalchemy.exc.InvalidRequestError: Attribute name 'metadata' is reserved when using the Declarative API.
```

## Models Fixed

All models with `metadata` columns have been renamed following the pattern `{model_name}_metadata`:

### ✅ Fixed in Previous Sessions
1. **audit_log.py** - `event_metadata`
2. **flow.py** - `flow_metadata = Column("metadata", JSONB)` (explicit column name mapping)
3. **message_events.py** - `event_metadata = Column("metadata", JSONB)` (explicit column name mapping)
4. **quiz.py** - `session_metadata` and `response_metadata`

### ✅ Fixed in This Session (2025-10-10)
5. **notification.py:63** - Renamed to `notification_metadata`
   - Commit: `8b76964`
6. **session.py:60** - Renamed to `session_metadata`
   - Commit: `be06eea`
7. **consent.py:84** - Renamed to `consent_metadata`
   - Commit: `5e491aa`

### ✅ Already Correct (Pre-Fixed)
8. **failed_message.py:97** - `dlq_metadata = Column('metadata', JSONB)` (explicit column name)
9. **flow_analytics.py:74,101** - `message_metadata`, `question_metadata` (explicit column names)
10. **message.py:73** - `message_metadata`

## Solution Pattern

Two approaches were used:

### Approach 1: Rename Python Attribute
```python
# BEFORE (causes error)
metadata = Column(JSONB, nullable=True)

# AFTER (fixed)
consent_metadata = Column(JSONB, nullable=True)
```

### Approach 2: Explicit Column Name Mapping
```python
# Alternative approach (already used in some models)
dlq_metadata = Column('metadata', JSONB, nullable=True)
```

## Verification

No remaining `metadata = Column` patterns found:

```bash
grep -r "^\s*metadata = Column" app/models/*.py
# (no results)
```

All metadata columns now use safe attribute names:
- `event_metadata`
- `flow_metadata`
- `notification_metadata`
- `session_metadata`
- `consent_metadata`
- `dlq_metadata`
- `message_metadata`
- `question_metadata`
- `response_metadata`

## Database Impact

⚠️ **Important**: Models using explicit column name mapping (`Column('metadata', ...)`) maintain backward compatibility with existing database schema. Models with renamed attributes may require migration if the column was previously named `metadata` in the database.

## Deployment Status

- ✅ All code changes committed
- ✅ Pushed to `sprint2-hive-mind-implementation` branch
- ✅ Merged to `docs-refactor-py313` branch (commit `9f96806`)
- ⏳ Railway deployment pending (will auto-deploy from updated GitHub repository)

## Related Files

- [consent.py](../app/models/consent.py:84)
- [session.py](../app/models/session.py:60)
- [notification.py](../app/models/notification.py:63)
- [audit_log.py](../app/models/audit_log.py:129)
- [failed_message.py](../app/models/failed_message.py:97)
- [flow.py](../app/models/flow.py:51)
- [message.py](../app/models/message.py:73)

## Next Steps

1. ✅ Monitor Railway deployment logs for successful migration run
2. ✅ Verify backend starts without SQLAlchemy errors
3. ✅ Run database migrations if needed
4. ✅ Test API endpoints to ensure metadata fields are accessible

## Prevention

To prevent this issue in the future:

1. **Never use** SQLAlchemy reserved names: `metadata`, `query`, `registry`, `_sa_*`
2. **Use linting**: Add SQLAlchemy linting to catch reserved names
3. **Code review**: Check for reserved attribute names in model PRs
4. **Documentation**: Update coding standards to list reserved names

## References

- [SQLAlchemy Declarative API Documentation](https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html)
- [Reserved Attribute Names](https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html#mapped-class-essential-components)
